import pandas as pd
import numpy as np
import os
import logging
from collections import defaultdict
from pydantic import ValidationError
from backend.schemas import (
    AllocationRequest, OptimizationParameters, CoverageDaysRule,
    OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule
)
from typing import Optional, Dict, Any, List, Union, Type

# --- Logger Setup ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def parse_and_validate_allocation_request(data: Dict[str, Any]) -> Optional[AllocationRequest]:
    """
    Parses and validates the incoming allocation request data using Pydantic models.

    Args:
        data: A dictionary representing the JSON payload.

    Returns:
        An AllocationRequest object if validation is successful, None otherwise.
        Logs validation errors.
    """
    try:
        request_model = AllocationRequest(**data)
        return request_model
    except ValidationError as e:
        logger.error(f"Input validation failed:\n{e}")
        return None

def _get_channel_id_from_row(row: pd.Series, potential_names: List[str]) -> str:
    """Safely gets the channel ID from a DataFrame row using potential column names."""
    for name in potential_names:
        if name in row.index:
            return str(row[name])
    raise KeyError(f"Could not find channel identifier using names {potential_names}. Found columns: {row.index.tolist()}")

def load_products_df(file_path: str, ean_col: str = 'product_gtin', 
                     div_col: str = 'operational_division', signature_col: str = 'operational_signature_label',
                     axe_col: str = 'operational_axe_label', sub_axe_col: str = 'operational_sub_axe_label', 
                     metier_col: str = 'operational_metier_label', sku_col: str = 'internal_product_code', 
                     description_col: str = 'product_description', cogs_col: str = 'unit_cost') -> pd.DataFrame:
    logger.info(f"Loading product data from: {file_path}")
    try:
        df = pd.read_csv(file_path)
        logger.debug(f"Successfully read CSV: {file_path}")
    except FileNotFoundError:
        logger.error(f"Product master data file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading product master data file {file_path}: {e}")
        raise

    column_mappings = {
        ean_col: 'ean', div_col: 'div', signature_col: 'signature',
        axe_col: 'axe', sub_axe_col: 'subAxe', metier_col: 'metier',
        sku_col: 'sku', description_col: 'description', cogs_col: 'cogs'
    }
    
    # Define which of the input column names are strictly required in the CSV
    # For example, EAN is essential. Others might be optional.
    required_input_cols = [ean_col, div_col, signature_col, axe_col, sub_axe_col, metier_col, sku_col, description_col] 
    # Cogs is often present but let's make it optional for broader compatibility if some files don't have it.
    
    for col_name in required_input_cols:
        if col_name not in df.columns:
            logger.error(f"Required column '{col_name}' (mapped to '{column_mappings.get(col_name)}') not found in product master data file: {file_path}. Found columns: {df.columns.tolist()}")
            raise ValueError(f"Required column '{col_name}' not found in product master data file: {file_path}.")

    # Select only the columns that are defined in column_mappings AND present in the DataFrame
    columns_to_process = [csv_col_name for csv_col_name in column_mappings.keys() if csv_col_name in df.columns]
    pdf = df[columns_to_process].copy()
    
    # Rename columns based on the subset that was processed
    rename_map_for_subset = {csv_col_name: target_name 
                             for csv_col_name, target_name in column_mappings.items() 
                             if csv_col_name in columns_to_process}
    pdf.rename(columns=rename_map_for_subset, inplace=True)
    
    if 'ean' not in pdf.columns:
        logger.error(f"EAN column '{ean_col}' (expected 'ean') not found after renaming in {file_path}.")
        raise ValueError(f"EAN column '{ean_col}' (expected 'ean') not found after renaming in {file_path}.")
    
    if pdf['ean'].duplicated().any():
        logger.warning(f"Duplicate EANs found in {file_path}. Keeping first occurrence.")
        pdf.drop_duplicates(subset=['ean'], keep='first', inplace=True)
        
    products_df_indexed = pdf.set_index('ean')
    for col in products_df_indexed.columns:
        if col == 'cogs':
            products_df_indexed[col] = pd.to_numeric(products_df_indexed[col], errors='coerce').fillna(0.0)
        else:
            products_df_indexed[col] = products_df_indexed[col].fillna('').astype(str)
    logger.info(f"Loaded {len(products_df_indexed)} products from {file_path}.")
    return products_df_indexed

def load_channels_df(file_path: str, sheet_name: str = 'Feuil1', channel_id_col: str = 'channel_id',
                     channel_type_col: str = 'channel_type', delimiter: str = ';') -> pd.DataFrame:
    logger.info(f"Loading channel data from Excel: {file_path}, Sheet: {sheet_name}")
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        logger.debug(f"Successfully read Excel: {file_path}, Sheet: {sheet_name}")
        if df.empty: # Handle empty DataFrame early
            logger.warning(f"No channel data loaded from {file_path}, sheet {sheet_name} (file might be empty or sheet empty). Returning empty DataFrame.")
            return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')
        df.columns = [str(col).strip().strip('"') for col in df.columns]
    except FileNotFoundError:
        logger.error(f"Channel list file not found: {file_path}")
        raise
    except ValueError as e:
        logger.warning(f"Sheet '{sheet_name}' not found in '{file_path}' for loading channel data or other Excel read error: {e}. Returning empty DataFrame.")
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')
    except Exception as e:
        logger.error(f"Error reading channel list file {file_path}: {e}")
        raise

    actual_channel_id_col = None
    actual_channel_type_col = None

    # Check for empty columns list before accessing df.columns[0]
    if not df.columns.empty and delimiter in df.columns[0] and len(df.columns) == 1:
        original_col_name = df.columns[0]
        logger.debug(f"Attempting to parse single delimited column: {original_col_name}")
        # Split the data in the column first
        split_data = df[original_col_name].astype(str).str.split(delimiter, n=1, expand=True)
        
        # Determine new column names from the original header
        header_parts = [s.strip().strip('"') for s in original_col_name.split(delimiter, 1)]
        
        if split_data.shape[1] == 2 and len(header_parts) == 2:
            df = split_data.copy() # Use .copy()
            df.columns = header_parts
            actual_channel_type_col = df.columns[0] # First part of header
            actual_channel_id_col = df.columns[1]   # Second part of header
            logger.debug(f"Parsed single delimited column into: Type='{actual_channel_type_col}', ID='{actual_channel_id_col}'")
        elif split_data.shape[1] == 1 and len(header_parts) >= 1 : # Only one part after split or no delimiter found in data
            logger.warning(f"Could not effectively split column '{original_col_name}' by delimiter '{delimiter}'. Treating as single column or checking standard names.")
            # Fall through to standard column name check
            if channel_type_col in df.columns and channel_id_col in df.columns:
                 actual_channel_type_col = channel_type_col
                 actual_channel_id_col = channel_id_col
            else:
                logger.error(f"Could not parse delimited header '{original_col_name}' and standard columns not found in {file_path}")
                raise ValueError(f"Could not parse delimited header '{original_col_name}' and standard columns not found in {file_path}")
        else:
            logger.error(f"Could not parse delimited header '{original_col_name}' into two distinct columns in {file_path}. Parts: {header_parts}, Split data columns: {split_data.shape[1]}")
            raise ValueError(f"Could not parse delimited header '{original_col_name}' into two distinct columns in {file_path}")

    elif channel_type_col in df.columns and channel_id_col in df.columns:
        actual_channel_type_col = channel_type_col
        actual_channel_id_col = channel_id_col
        logger.debug(f"Using standard columns: Type='{actual_channel_type_col}', ID='{actual_channel_id_col}'")
    else:
        logger.error(f"Required columns '{channel_type_col}' and '{channel_id_col}' not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")
        raise ValueError(f"Required columns '{channel_type_col}' and '{channel_id_col}' not found in {file_path} sheet {sheet_name}.")

    if actual_channel_id_col not in df.columns or actual_channel_type_col not in df.columns:
        logger.error(f"After parsing, required columns '{actual_channel_id_col}' or '{actual_channel_type_col}' not found. Available: {df.columns.tolist()}")
        raise ValueError(f"After parsing, required columns '{actual_channel_id_col}' or '{actual_channel_type_col}' not found.")

    channel_data_list = []
    for _, row in df.iterrows():
        ch_id = str(row[actual_channel_id_col])
        ch_type = str(row[actual_channel_type_col])
        channel_data_list.append({
            'id': ch_id,
            'channel_type': ch_type,
            'capacity': 0 # Default capacity, can be extended if needed
        })
    
    if not channel_data_list:
        logger.warning(f"No channel data loaded from {file_path}, sheet {sheet_name}. Returning empty DataFrame.")
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')

    channels_df = pd.DataFrame(channel_data_list).set_index('id')
    logger.info(f"Loaded {len(channels_df)} channels from {file_path}.")
    return channels_df

def load_inventory_df(file_path: str, ean_col: str = 'ean_code', qty_col: str = 'StockToAllocate', 
                        plant_code_col: str = 'plant', plant_desc_col: str = 'plant_description',
                        flag6_col: str = 'FlagExcess6months', flag12_col: str = 'FlagExcess12months') -> pd.DataFrame:
    logger.info(f"Loading inventory data from: {file_path}")
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        logger.error(f"Inventory data file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading inventory data file {file_path}: {e}")
        raise
        
    required_cols = [ean_col, qty_col, plant_code_col, plant_desc_col, flag6_col, flag12_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Required columns {missing_cols} missing in inventory file: {file_path}. Found: {df.columns.tolist()}")
        raise ValueError(f"Required columns {missing_cols} missing in {file_path}")
    
    idf = df[required_cols].rename(columns={
        ean_col: 'product_ean', 
        qty_col: 'quantity', 
        plant_code_col: 'plant', 
        plant_desc_col: 'stockOrigin',
        flag6_col: 'flagExcess6months',
        flag12_col: 'flagExcess12months'
    })
    idf['product_ean'] = idf['product_ean'].astype(str)
    idf['plant'] = idf['plant'].astype(str) # This is the plant code
    idf['stockOrigin'] = idf['stockOrigin'].astype(str)
    idf['quantity'] = pd.to_numeric(idf['quantity'], errors='coerce').fillna(0)
    idf['flagExcess6months'] = pd.to_numeric(idf['flagExcess6months'], errors='coerce').fillna(0).astype(int) # Assuming 0 or 1
    idf['flagExcess12months'] = pd.to_numeric(idf['flagExcess12months'], errors='coerce').fillna(0).astype(int) # Assuming 0 or 1
    
    # Group by EAN and Plant (code), then aggregate
    # For flags and description, 'first' is used assuming they are consistent per EAN-Plant group or taking the first is acceptable.
    result_df = idf.groupby(['product_ean', 'plant'], as_index=False).agg({
        'quantity': 'sum',
        'stockOrigin': 'first',
        'flagExcess6months': 'first',
        'flagExcess12months': 'first'
    })

    # Create the 'bad_stock_type' column based on flag values
    conditions = [
        (result_df['flagExcess6months'] == 1) & (result_df['flagExcess12months'] == 1),
        (result_df['flagExcess6months'] == 1) & (result_df['flagExcess12months'] == 0),
        (result_df['flagExcess6months'] == 0) & (result_df['flagExcess12months'] == 1)
    ]
    choices = [
        "Excess 6 & 12 months",
        "Excess 6 months",
        "Excess 12 months"
    ]
    result_df['bad_stock_type'] = np.select(conditions, choices, default="")
    
    logger.info(f"Loaded inventory for {len(result_df)} EAN-plant combinations from {file_path}. Total quantity: {result_df['quantity'].sum()}. 'bad_stock_type' column created.")
    return result_df

def load_existing_stock_dict(in_store_fp: str, in_transit_fp: str,
                             in_store_ean_col: str = 'barcode', in_store_channel_col: str = 'store_code', in_store_qty_col: str = 'physical_quantity',
                             in_transit_ean_col: str = 'ean_material_code', in_transit_channel_col: str = 'store_code', in_transit_qty_col: str = 'order_quantity') -> Dict[tuple, float]:
    logger.info(f"Loading existing stock data from in-store: {in_store_fp} and in-transit: {in_transit_fp}")
    stock = defaultdict(float)
    
    files_to_process = [
        (in_store_fp, in_store_ean_col, in_store_channel_col, in_store_qty_col),
        (in_transit_fp, in_transit_ean_col, in_transit_channel_col, in_transit_qty_col)
    ]

    for fp, ean_c, chan_c, qty_c in files_to_process:
        logger.debug(f"Processing stock file: {fp}")
        try:
            df = pd.read_csv(fp)
        except FileNotFoundError:
            logger.error(f"Stock data file not found: {fp}")
            raise
        except Exception as e:
            logger.error(f"Error reading stock data file {fp}: {e}")
            raise

        if not all(c in df.columns for c in [ean_c, chan_c, qty_c]):
            logger.error(f"Required columns missing in stock file {fp}. Expected: '{ean_c}', '{chan_c}', '{qty_c}'. Found: {df.columns.tolist()}")
            raise ValueError(f"Required columns missing in {fp}")
        
        df_renamed = df[[ean_c, chan_c, qty_c]].rename(columns={ean_c:'ean', chan_c:'channel_id', qty_c:'quantity'})
        df_renamed[['ean','channel_id']] = df_renamed[['ean','channel_id']].astype(str)
        df_renamed['quantity'] = pd.to_numeric(df_renamed['quantity'], errors='coerce').fillna(0)
        for _, r in df_renamed.iterrows():
            stock[(r['ean'], r['channel_id'])] += r['quantity']
    
    logger.info(f"Loaded existing stock for {len(stock)} product-channel combinations.")
    return dict(stock)

def load_demand_dict(file_path: str, ean_col: str = 'barcode', channel_col: str = 'store_code', demand_qty_col: str = 'total_items_weekly') -> Dict[tuple, float]:
    logger.info(f"Loading demand data from: {file_path}")
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        logger.warning(f"Demand data file not found: {file_path}. Returning empty demand dictionary.")
        return {}
    except Exception as e:
        logger.error(f"Error reading demand data file {file_path}: {e}")
        raise
    
    if not all(c in df.columns for c in [ean_col, channel_col, demand_qty_col]):
        logger.error(f"Required columns ('{ean_col}', '{channel_col}', '{demand_qty_col}') missing in demand file: {file_path}. Found: {df.columns.tolist()}")
        raise ValueError(f"Required columns missing in {file_path}")
    
    df[[ean_col, channel_col]] = df[[ean_col, channel_col]].astype(str)
    df[demand_qty_col] = pd.to_numeric(df[demand_qty_col], errors='coerce').fillna(0)
    
    demand_dict = {}
    for _, r in df.groupby([ean_col, channel_col])[demand_qty_col].sum().reset_index().iterrows():
        demand_dict[(r[ean_col], r[channel_col])] = r[demand_qty_col]
    
    logger.info(f"Loaded demand for {len(demand_dict)} product-channel combinations from {file_path}.")
    return demand_dict

def load_optimization_rules(file_path: str, rule_type: Type[Union[CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule]],
                            sheet_name: str = 'Feuil1', **column_mappings) -> List[Union[CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule]]:
    logger.info(f"Loading {rule_type.__name__} rules from: {file_path}, Sheet: {sheet_name}")
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except FileNotFoundError:
        logger.error(f"Rules file not found: {file_path}")
        raise
    except ValueError as e:
        logger.warning(f"Sheet '{sheet_name}' not found in '{file_path}' for {rule_type.__name__} rules or other Excel error: {e}. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error reading {rule_type.__name__} rules file {file_path}: {e}")
        raise
        
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))
    
    # column_mappings maps pydantic_field_name (key) to excel_column_name (value)
    # We need to check if all specified excel_column_names are present in the df
    expected_excel_cols = list(column_mappings.values())
    missing_excel_cols = [col for col in expected_excel_cols if col not in df.columns]
    
    if missing_excel_cols:
        logger.error(f"Required Excel columns {missing_excel_cols} missing in {rule_type.__name__} file {file_path} sheet {sheet_name}. DataFrame columns found: {df.columns.tolist()}")
        raise ValueError(f"Required Excel columns missing in {file_path} sheet {sheet_name} for {rule_type.__name__}: {missing_excel_cols}")
    
    rules = []
    for i, r in df.iterrows():
        try:
            # rule_data keys should be pydantic field names, values from excel row using excel col name
            rule_data = {pydantic_field: r[excel_col] for pydantic_field, excel_col in column_mappings.items()}
            
            # Special handling for integer conversion if needed by Pydantic model
            for key, value in rule_data.items(): # Here, key is pydantic_field_name
                if key in ['coverage_days', 'max_skus', 'push_quantity']:
                    val_numeric = pd.to_numeric(value, errors='coerce')
                    if pd.isna(val_numeric):
                        rule_data[key] = 0  # Default to 0 if coercion fails or value is NaN
                    else:
                        rule_data[key] = int(val_numeric)
                else:
                    rule_data[key] = str(value) # Ensure all other values are strings
            rules.append(rule_type(**rule_data))
        except Exception as e:
            logger.error(f"Error processing row {i} in {rule_type.__name__} file {file_path}: {r.to_dict()}. Error: {e}. Skipping row.")
    
    logger.info(f"Loaded {len(rules)} {rule_type.__name__} rules from {file_path}.")
    return rules
