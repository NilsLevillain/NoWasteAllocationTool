import pulp
import pandas as pd
from schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule
from collections import defaultdict
import logging
import json # For structured logging example

# --- Logger Setup ---
# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Set default level to DEBUG to capture all messages

# Create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
json_formatter = logging.Formatter('{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": %(message)s}') # For structured JSON

# Add formatter to ch
ch.setFormatter(formatter) # Use standard formatter by default

# Add ch to logger
if not logger.handlers: # Avoid adding multiple handlers if script is re-run in some contexts
    logger.addHandler(ch)

# --- ABC Classification Function ---
def calculate_abc_classification_and_new_skus(
    sellout_df: pd.DataFrame, 
    product_master_df: pd.DataFrame, 
    all_channel_ids: list, # Now specific channel IDs like 'A90', 'B10'
    sellout_ean_col: str,
    sellout_channel_col: str, # This is 'store_code' from sellout.csv
    sellout_qty_col: str
):
    product_channel_abc_map = {}

    logger.debug(f"Starting ABC classification. Sellout EAN col: {sellout_ean_col}, Channel col: {sellout_channel_col}, Qty col: {sellout_qty_col}")
    sellout_df[sellout_ean_col] = sellout_df[sellout_ean_col].astype(str)
    sellout_df[sellout_channel_col] = sellout_df[sellout_channel_col].astype(str)
    sellout_df[sellout_qty_col] = pd.to_numeric(sellout_df[sellout_qty_col], errors='coerce').fillna(0)
    
    # Pre-aggregate sellout by channel and EAN
    logger.debug("Aggregating sellout data by channel and EAN.")
    channel_product_sales_agg = sellout_df.groupby([sellout_channel_col, sellout_ean_col])[sellout_qty_col].sum().reset_index()

    for channel_id_from_list in all_channel_ids: # e.g., 'A90', 'B10' from ChannelList.xlsx
        logger.debug(f"Processing ABC for channel_id: {channel_id_from_list}")
        # Filter aggregated sales for the current channel_id from the list
        # sellout_channel_col is the column in sellout_df that matches channel_id_from_list (e.g. 'store_code')
        channel_sales = channel_product_sales_agg[channel_product_sales_agg[sellout_channel_col] == channel_id_from_list].copy()

        if channel_sales.empty:
            logger.info(f"No sales data for channel {channel_id_from_list}. Marking all products as 'NEW'.")
            for product_ean in product_master_df.index:
                product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            continue

        channel_sales = channel_sales.sort_values(by=sellout_qty_col, ascending=False)
        channel_sales['cumulative_sales'] = channel_sales[sellout_qty_col].cumsum()
        total_channel_sales = channel_sales[sellout_qty_col].sum()
        logger.debug(f"Total sales for channel {channel_id_from_list}: {total_channel_sales}")

        if total_channel_sales == 0:
            logger.info(f"Total sales are zero for channel {channel_id_from_list}. Marking existing as 'C', others as 'NEW'.")
            for product_ean in product_master_df.index:
                if product_ean in channel_sales[sellout_ean_col].values:
                     product_channel_abc_map[(product_ean, channel_id_from_list)] = 'C'
                else:
                     product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            continue
            
        channel_sales['cumulative_percent'] = channel_sales['cumulative_sales'] / total_channel_sales

        for _, row in channel_sales.iterrows():
            # Example of structured logging for a specific event
            log_detail = {
                "event": "abc_assignment_iteration",
                "channel_id": channel_id_from_list,
                "ean": row[sellout_ean_col],
                "cumulative_percent": row['cumulative_percent']
            }
            # To use JSON formatter, you'd typically set it on the handler.
            # For this example, I'll just log the JSON string directly if needed,
            # or rely on a custom formatter if one was fully set up.
            # logger.info(json.dumps(log_detail)) # If logging JSON strings directly

            logger.debug(f"Assigning ABC for EAN {row[sellout_ean_col]} in channel {channel_id_from_list} with cum_percent {row['cumulative_percent']}", extra=log_detail) # 'extra' can be used by custom formatters

            ean = row[sellout_ean_col]
            cum_percent = row['cumulative_percent']
            if cum_percent <= 0.2: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'A'
            elif cum_percent <= 0.8: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'B'
            else: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'C'

        sold_eans_in_this_channel = set(channel_sales[sellout_ean_col])
        for product_ean in product_master_df.index:
            if product_ean not in sold_eans_in_this_channel:
                product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            
    return product_channel_abc_map

def optimize_allocation(products_df: pd.DataFrame, channels_df: pd.DataFrame, inventory_df: pd.DataFrame,
                        demand_dict: dict, parameters: OptimizationParameters, existing_stock_dict: dict,
                        product_channel_abc_map: dict):
    logger.info("Starting inventory allocation optimization.")
    logger.debug(f"Number of products: {len(products_df)}, Number of channels: {len(channels_df)}")
    logger.debug(f"Optimization Parameters: {parameters}")

    products_df.index = products_df.index.astype(str)
    channels_df.index = channels_df.index.astype(str)
    products = products_df.index.tolist()
    channels = channels_df.index.tolist() # These are now 'A90', 'B10' etc.
    inventory_quantity = inventory_df.groupby('product_ean')['quantity'].sum().to_dict()
    logger.debug(f"Total inventory quantity by product: {inventory_quantity}")

    coverage_rules_dict = {(r.channel_id, r.abc_class): r.coverage_days for r in parameters.coverage_days_rules}
    outlet_capacity_dict = {(r.channel_id, r.division, r.axe): r.max_skus for r in parameters.outlet_sku_capacity_rules}
    outlet_assortment_dict = {(r.metier, r.subaxis, r.brand): r.max_skus for r in parameters.outlet_assortment_rules}
    push_new_sku_lookup = {(r.division, r.subaxis): r.push_quantity for r in parameters.push_new_sku_rules}
    products_by_outlet_capacity_group = defaultdict(list)
    products_by_outlet_assortment_group = defaultdict(list)
    
    # outlet_channels list might not be strictly necessary if all channels in channels_df are outlets,
    # but good for explicit filtering if other types were to be mixed in channels_df later.
    outlet_channels = channels_df[channels_df['channel_type'] == 'outlet'].index.tolist()
    logger.debug(f"Outlet channels identified: {outlet_channels}")


    for p in products:
        division, axe = products_df.loc[p].get('division'), products_df.loc[p].get('axe')
        metier, subaxis, brand = products_df.loc[p].get('metier'), products_df.loc[p].get('subaxis'), products_df.loc[p].get('brand')
        if division and axe: products_by_outlet_capacity_group[(division, axe)].append(p)
        if metier and subaxis and brand: products_by_outlet_assortment_group[(metier, subaxis, brand)].append(p)
    logger.debug(f"Products grouped by outlet capacity: {len(products_by_outlet_capacity_group)} groups.")
    logger.debug(f"Products grouped by outlet assortment: {len(products_by_outlet_assortment_group)} groups.")

    logger.info("Defining PuLP model and variables.")
    model = pulp.LpProblem("InventoryAllocation", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("allocation_qty", ((p, c) for p in products for c in channels), lowBound=0, cat='Integer')
    y = pulp.LpVariable.dicts("is_allocated", ((p, c) for p in products for c in channels), cat='Binary')
    model += (pulp.lpSum(x[p, c] for p in products for c in channels), "Maximize_Total_Allocation")
    logger.debug("Objective function added: Maximize_Total_Allocation.")

    logger.info("Adding supply constraints.")
    for p in products: model += pulp.lpSum(x[p, c] for c in channels) <= inventory_quantity.get(p, 0), f"Supply_Product_{p}"
    
    logger.info("Adding outlet SKU capacity constraints.")
    for c in channels: # c is now 'A90', 'B10', etc.
        channel_type = channels_df.loc[c, 'channel_type']
        if channel_type == 'outlet':
            for (division, axe), group_products in products_by_outlet_capacity_group.items():
                max_skus = outlet_capacity_dict.get((c, division, axe))
                if max_skus is not None and max_skus >= 0:
                    model += pulp.lpSum(y[pg, c] for pg in group_products if pg in products) <= max_skus, f"Outlet_Capacity_SKU_{c}_{division}_{axe}"
                    logger.debug(f"Added SKU capacity constraint for channel {c}, div {division}, axe {axe}: max {max_skus} SKUs.")
        # else: # Logic for other channel types if they were present
            # capacity = pd.to_numeric(channels_df.loc[c, 'capacity'], errors='coerce')
            # if pd.notna(capacity) and capacity >= 0: model += pulp.lpSum(x[pp, c] for pp in products) <= capacity, f"Capacity_Channel_{c}"

    logger.info("Adding coverage days and new SKU push constraints.")
    for c in channels: # c is 'A90', 'B10', etc.
        for p in products:
            abc_class = product_channel_abc_map.get((p, c), 'C') 
            current_stock_for_pc = existing_stock_dict.get((p, c), 0)
            if abc_class == 'NEW':
                div, sub = products_df.loc[p].get('division'), products_df.loc[p].get('subaxis')
                push_qty = push_new_sku_lookup.get((div, sub), 0) if div and sub else 0
                model += x[p, c] <= push_qty, f"Push_New_SKU_{p}_{c}"
                logger.debug(f"Push new SKU constraint for P:{p} C:{c} (NEW): qty <= {push_qty}")
            else: # A, B, C
                cov_days = coverage_rules_dict.get((c, abc_class)) 
                if cov_days is not None and cov_days >= 0:
                    adj_demand = demand_dict.get((p, c), 0) * parameters.seasonality_coefficient 
                    if adj_demand > 0:
                        allow_alloc = max(0, (adj_demand / 7.0) * cov_days - current_stock_for_pc)
                        model += x[p, c] <= allow_alloc, f"Max_Coverage_Days_{p}_{c}"
                        logger.debug(f"Coverage constraint for P:{p} C:{c} (ABC:{abc_class}): qty <= {allow_alloc} (demand:{adj_demand}, stock:{current_stock_for_pc}, cov_days:{cov_days})")
                    else: 
                        model += x[p, c] <= 0, f"Max_Coverage_Days_Zero_Demand_{p}_{c}"
                        logger.debug(f"Coverage constraint for P:{p} C:{c} (ABC:{abc_class}): Zero demand, qty <= 0")
    
    if parameters.restricted_brands_for_donation:
        logger.info("Adding restricted brands for donation constraints.")
        don_chans_from_df = channels_df[channels_df['channel_type'] == 'donation'].index.tolist()
        if don_chans_from_df: 
            restr_brands = set(parameters.restricted_brands_for_donation)
            for p in products:
                if products_df.loc[p].get('brand') in restr_brands:
                    for dc in don_chans_from_df: 
                        if dc in channels: 
                            model += x[p, dc] == 0, f"Restricted_Brand_{products_df.loc[p].get('brand')}_Prod_{p}_Chan_{dc}"
                            logger.debug(f"Restricted brand {products_df.loc[p].get('brand')} for P:{p} in donation channel {dc}.")
    
    logger.info("Adding outlet assortment constraints.")
    for c_out in outlet_channels: 
        if c_out not in channels: 
            logger.warning(f"Outlet channel {c_out} from outlet_channels list not in main channels list. Skipping assortment rules for it.")
            continue 
        for (metier, subaxis, brand), group_products in products_by_outlet_assortment_group.items():
            max_skus = outlet_assortment_dict.get((metier, subaxis, brand)) 
            if max_skus is not None and max_skus >= 0:
                model += pulp.lpSum(y[pg, c_out] for pg in group_products if pg in products) <= max_skus, f"Outlet_Assortment_{c_out}_{metier}_{subaxis}_{brand}"
                logger.debug(f"Added assortment constraint for outlet {c_out}, metier {metier}, subaxis {subaxis}, brand {brand}: max {max_skus} SKUs.")

    logger.info("Linking allocation quantity (x) and allocation decision (y) variables.")
    for p in products:
        M_val = inventory_quantity.get(p, 0) # Renamed M to M_val to avoid conflict if M is used elsewhere
        for c in channels:
            if M_val > 0:
                model += x[p, c] <= M_val * y[p, c], f"Link_x_y_Prod_{p}_Chan_{c}"
                model += y[p, c] * M_val >= x[p, c], f"Link_y_x_Prod_{p}_Chan_{c}" # Redundant with x <= M*y and x >= 0, but common
            else: # No inventory for product p
                model += x[p, c] == 0, f"Force_x_zero_NoInv_Prod_{p}_Chan_{c}"
                model += y[p, c] == 0, f"Force_y_zero_NoInv_Prod_{p}_Chan_{c}"

    logger.info("Writing LP model to allocation_model.lp")
    model.writeLP("allocation_model.lp")
    logger.info("Solving optimization model...")
    model.solve() # PuLP's default solver, consider specifying one if needed
    status_string = pulp.LpStatus[model.status] # Use model.status
    logger.info(f"Solver status: {status_string}")

    results = []
    if status_string == 'Optimal':
        logger.info("Optimal solution found. Extracting results.")
        results = [{'product_sku': p, 'channel_id': c, 'quantity': int(round(x[p,c].varValue))} # Use .varValue
                   for p in products for c in channels if x[p,c].varValue is not None and x[p,c].varValue > 0.1]
        logger.info(f"Extracted {len(results)} allocation entries.")
    else:
        logger.warning(f"Optimization was not optimal. Status: {status_string}. No results extracted.")
    return model, status_string, results

def load_product_data(fp, ean_c='EAN', brand_c='Brand', div_c='Division', axe_c='Axe', sub_c='SubAxis', met_c='Metier', abc_c=None):
    logger.info(f"Loading product data from: {fp}")
    try:
        df = pd.read_csv(fp)
        logger.debug(f"Successfully read CSV: {fp}")
    except FileNotFoundError:
        logger.error(f"Product master data file not found: {fp}")
        raise
    except Exception as e:
        logger.error(f"Error reading product master data file {fp}: {e}")
        raise

    rn_map = {ean_c:'ean', brand_c:'brand', div_c:'division', axe_c:'axe', sub_c:'subaxis', met_c:'metier'}
    if abc_c and abc_c in df.columns: rn_map[abc_c] = 'abc_class'
    
    if ean_c not in df.columns: 
        logger.error(f"EAN column '{ean_c}' not found in product master data file: {fp}")
        raise ValueError(f"EAN column '{ean_c}' not found in product master data file: {fp}")

    columns_to_process = list(set([k for k in rn_map.keys() if k in df.columns] + [ean_c]))
    columns_present_in_df = [col for col in columns_to_process if col in df.columns]
    logger.debug(f"Columns to process from product data: {columns_present_in_df}")
    
    pdf = df[columns_present_in_df].copy()
    pdf.rename(columns=rn_map, inplace=True)
    
    if 'ean' not in pdf.columns: 
        logger.error(f"EAN column '{ean_c}' (expected 'ean') not found after renaming in {fp}.")
        raise ValueError(f"EAN column '{ean_c}' (expected 'ean') not found after renaming in {fp}.")
    
    if pdf['ean'].duplicated().any():
        logger.warning(f"Duplicate EANs found in {fp}. Using first occurrence.")
        pdf.drop_duplicates(subset=['ean'], keep='first', inplace=True)
        
    products_df_indexed = pdf.set_index('ean')
    for col in products_df_indexed.columns:
        products_df_indexed[col] = products_df_indexed[col].fillna('').astype(str)
    logger.info(f"Loaded {len(products_df_indexed)} products from {fp}.")
    return products_df_indexed

def load_channel_data_from_channellist(file_path, sheet_name='Feuil1', channel_id_col='channel_id', channel_type_col='channel_type', delimiter=';'):
    logger.info(f"Loading channel data from Excel: {file_path}, Sheet: {sheet_name}")
    """
    Loads channel data from ChannelList.xlsx.
    Expects columns like 'channel_type;channel_id' and splits them if a delimiter is present in header.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        logger.debug(f"Successfully read Excel: {file_path}, Sheet: {sheet_name}")
        
        # Normalize column names immediately after reading
        df.columns = [str(col).strip().strip('"') for col in df.columns]

    except FileNotFoundError:
        logger.error(f"Channel list file not found: {file_path}")
        raise
    except ValueError as e: # Handles sheet not found
        logger.warning(f"Sheet '{sheet_name}' not found in '{file_path}' for loading channel data or other Excel read error: {e}. Returning empty DataFrame.")
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')
    except Exception as e:
        logger.error(f"Error reading channel list file {file_path}: {e}")
        raise

    # Check for delimited header
    header = df.columns[0] 
    if delimiter in header and len(df.columns) >= 1: 
        logger.debug(f"Attempting to parse delimited header: {header}")
        if len(df.columns) == 1 and delimiter in df.columns[0]: 
            split_cols = df.columns[0].split(delimiter)
            if len(split_cols) == 2:
                df.columns = split_cols
                actual_channel_type_col = split_cols[0].strip().strip('"')
                actual_channel_id_col = split_cols[1].strip().strip('"')
                logger.debug(f"Parsed single delimited header into: Type='{actual_channel_type_col}', ID='{actual_channel_id_col}'")
            else: 
                 logger.error(f"Could not parse delimited header '{df.columns[0]}' into two columns in {file_path}")
                 raise ValueError(f"Could not parse delimited header '{df.columns[0]}' into two columns in {file_path}")
        elif len(df.columns) >= 2: 
            col1_name = str(df.columns[0]).strip().strip('"')
            col2_name = str(df.columns[1]).strip().strip('"')
            if col1_name == channel_type_col and col2_name == channel_id_col:
                 actual_channel_type_col = col1_name
                 actual_channel_id_col = col2_name
            elif channel_type_col in df.columns and channel_id_col in df.columns:
                actual_channel_type_col = channel_type_col
                actual_channel_id_col = channel_id_col
            else: 
                logger.warning(f"Using first two columns from {file_path} as type and ID due to header mismatch. Expected '{channel_type_col}', '{channel_id_col}'. Got '{df.columns[0]}', '{df.columns[1]}'")
                actual_channel_type_col = df.columns[0]
                actual_channel_id_col = df.columns[1]
        else:
            logger.error(f"Insufficient columns in {file_path} sheet {sheet_name} to determine channel type and ID from delimited header.")
            raise ValueError(f"Insufficient columns in {file_path} sheet {sheet_name} to determine channel type and ID.")

    elif channel_type_col in df.columns and channel_id_col in df.columns: 
        actual_channel_type_col = channel_type_col
        actual_channel_id_col = channel_id_col
        logger.debug(f"Using standard columns: Type='{actual_channel_type_col}', ID='{actual_channel_id_col}'")
    else:
        logger.error(f"Required columns '{channel_type_col}' and '{channel_id_col}' not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")
        raise ValueError(f"Required columns '{channel_type_col}' and '{channel_id_col}' not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")

    actual_channel_type_col = actual_channel_type_col.strip().strip('"')
    actual_channel_id_col = actual_channel_id_col.strip().strip('"')

    if actual_channel_id_col not in df.columns or actual_channel_type_col not in df.columns:
        logger.error(f"After parsing, required columns '{actual_channel_id_col}' or '{actual_channel_type_col}' not found. Parsed from input: type='{channel_type_col}', id='{channel_id_col}'. Available: {df.columns.tolist()}")
        raise ValueError(f"After parsing, required columns '{actual_channel_id_col}' or '{actual_channel_type_col}' not found. Parsed from input: type='{channel_type_col}', id='{channel_id_col}'.")

    # Create a list of dictionaries for DataFrame creation
    channel_data_list = []
    for _, row in df.iterrows():
        ch_id = str(row[actual_channel_id_col])
        ch_type = str(row[actual_channel_type_col])
        # For now, all channels from this list are 'outlet' as per user, capacity 0
        channel_data_list.append({
            'id': ch_id,
            'channel_type': 'outlet', # Override with 'outlet' for now
            'capacity': 0 
        })
    
    if not channel_data_list:
        logger.warning(f"No channel data loaded from {file_path}, sheet {sheet_name}. Returning empty DataFrame.")
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')

    channels_df = pd.DataFrame(channel_data_list).set_index('id')
    logger.info(f"Loaded {len(channels_df)} channels from {file_path}.")
    return channels_df


def load_inventory_data(fp, ean_c='ean_code', qty_c='StockToAllocate'):
    logger.info(f"Loading inventory data from: {fp}")
    try:
        df = pd.read_csv(fp)
    except FileNotFoundError:
        logger.error(f"Inventory data file not found: {fp}")
        raise
    except Exception as e:
        logger.error(f"Error reading inventory data file {fp}: {e}")
        raise
        
    if ean_c not in df.columns or qty_c not in df.columns: 
        logger.error(f"Required columns ('{ean_c}', '{qty_c}') missing in inventory file: {fp}")
        raise ValueError(f"Cols missing in {fp}")
    idf = df[[ean_c, qty_c]].rename(columns={ean_c:'product_ean', qty_c:'quantity'})
    idf['product_ean'] = idf['product_ean'].astype(str)
    idf['quantity'] = pd.to_numeric(idf['quantity'], errors='coerce').fillna(0)
    result_df = idf.groupby('product_ean', as_index=False)['quantity'].sum()
    logger.info(f"Loaded inventory for {len(result_df)} EANs from {fp}. Total quantity: {result_df['quantity'].sum()}")
    return result_df

def load_existing_stock_data(inst_fp, intr_fp, iec='barcode', icc='store_code', iqc='physical_quantity',itec='ean_material_code', itcc='store_code', itqc='order_quantity'):
    logger.info(f"Loading existing stock data from in-store: {inst_fp} and in-transit: {intr_fp}")
    stock = defaultdict(float)
    try:
        df_i = pd.read_csv(inst_fp)
        df_it = pd.read_csv(intr_fp)
    except FileNotFoundError as e:
        logger.error(f"Stock data file not found: {e.filename}")
        raise
    except Exception as e:
        logger.error(f"Error reading stock data files: {e}")
        raise

    for df,ec,cc,qc, source_file in [(df_i,iec,icc,iqc, inst_fp),(df_it,itec,itcc,itqc, intr_fp)]:
        logger.debug(f"Processing stock file: {source_file}")
        if not all(c in df.columns for c in [ec,cc,qc]): 
            logger.error(f"Required columns missing in stock file {source_file}. Expected: {ec}, {cc}, {qc}. Found: {df.columns.tolist()}")
            raise ValueError(f"Cols missing in {source_file}")
        df_renamed = df[[ec,cc,qc]].rename(columns={ec:'ean',cc:'channel_id',qc:'quantity'})
        df_renamed[['ean','channel_id']] = df_renamed[['ean','channel_id']].astype(str)
        df_renamed['quantity'] = pd.to_numeric(df_renamed['quantity'],errors='coerce').fillna(0)
        for _,r in df_renamed.iterrows(): stock[(r['ean'],r['channel_id'])] += r['quantity']
    logger.info(f"Loaded existing stock for {len(stock)} product-channel combinations.")
    return dict(stock)

def load_demand_data(fp, ean_c='EAN', chan_c='ChannelID', dem_c='WeeklySalesQty'):
    logger.info(f"Loading demand data from: {fp}")
    try:
        df = pd.read_csv(fp)
    except FileNotFoundError:
        logger.error(f"Demand data file not found: {fp}")
        raise
    except Exception as e:
        logger.error(f"Error reading demand data file {fp}: {e}")
        raise
    d_dict = {}
    if not all(c in df.columns for c in [ean_c,chan_c,dem_c]): 
        logger.error(f"Required columns ('{ean_c}', '{chan_c}', '{dem_c}') missing in demand file: {fp}")
        raise ValueError(f"Cols missing in {fp}")
    df[[ean_c,chan_c]] = df[[ean_c,chan_c]].astype(str)
    df[dem_c] = pd.to_numeric(df[dem_c],errors='coerce').fillna(0)
    for _,r in df.groupby([ean_c,chan_c])[dem_c].sum().reset_index().iterrows(): d_dict[(r[ean_c],r[chan_c])] = r[dem_c]
    logger.info(f"Loaded demand for {len(d_dict)} product-channel combinations from {fp}.")
    return d_dict

def load_coverage_rules_from_excel(fp, sheet='Feuil1', chan_c='Channel', abc_c='ABC Class', cov_c='Coverage (in days)'):
    logger.info(f"Loading coverage rules from: {fp}, Sheet: {sheet}")
    try:
        df = pd.read_excel(fp, sheet_name=sheet)
    except FileNotFoundError:
        logger.error(f"Coverage rules file not found: {fp}")
        raise
    except ValueError as e: # Sheet not found
        logger.warning(f"Sheet '{sheet}' not found in '{fp}' for coverage rules or other Excel error: {e}. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error reading coverage rules file {fp}: {e}")
        raise
        
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    scc,sac,sccov = chan_c.strip('"'), abc_c.strip('"'), cov_c.strip('"')
    if not all(c in df.columns for c in [scc,sac,sccov]): 
        logger.error(f"Required columns ('{scc}', '{sac}', '{sccov}') missing in coverage rules file {fp} sheet {sheet}. Found: {df.columns.tolist()}")
        raise ValueError(f"Cols missing in {fp} sheet {sheet}")
    for i,r in df.iterrows(): 
        try:
            rules.append(CoverageDaysRule(channel_id=str(r[scc]),abc_class=str(r[sac]),coverage_days=int(r[sccov])))
        except Exception as e:
            logger.error(f"Error processing row {i} in coverage rules file {fp}: {r}. Error: {e}. Skipping row.")
    logger.info(f"Loaded {len(rules)} coverage rules from {fp}.")
    return rules

def load_outlet_sku_capacity_rules_from_excel(fp, sheet='Feuil1', chan_c='Channel', div_c='operational_division', axe_c='operational_axe_label', max_skus_c='Max capacity (in # of SKU)'):
    logger.info(f"Loading outlet SKU capacity rules from: {fp}, Sheet: {sheet}")
    try: 
        df = pd.read_excel(fp, sheet_name=sheet)
    except FileNotFoundError:
        logger.error(f"Outlet SKU capacity rules file not found: {fp}")
        raise
    except ValueError: 
        logger.warning(f"Sheet '{sheet}' not found in '{fp}' for outlet SKU capacity rules. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error reading outlet SKU capacity rules file {fp}: {e}")
        raise

    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))
    scc, sdc, sac, smsc = chan_c.strip('"'), div_c.strip('"'), axe_c.strip('"'), max_skus_c.strip('"')
    if not all(c in df.columns for c in [scc, sdc, sac, smsc]): 
        logger.warning(f"Cols missing for outlet SKU capacity in {fp} sheet {sheet}. Need: '{scc}', '{sdc}', '{sac}', '{smsc}'. Found: {df.columns.tolist()}. Skipping file.")
        return []
    rules = []
    for i, r in df.iterrows():
        try:
            rules.append(OutletSKUCapacityRule(channel_id=str(r[scc]), division=str(r[sdc]), axe=str(r[sac]), max_skus=int(r[smsc])))
        except Exception as e: 
            logger.error(f"Error processing row {i} in outlet SKU capacity file {fp}: {r}. Error: {e}. Skipping row.")
    logger.info(f"Loaded {len(rules)} outlet SKU capacity rules from {fp}.")
    return rules

def load_outlet_assortment_rules_from_excel(fp, sheet='Feuil1', met_c='operational_metier_label', sub_c='operational_sub_axe_label', brand_c='operational_signature_label', max_skus_c='# of SKUs to have in outlet (assortment)'):
    logger.info(f"Loading outlet assortment rules from: {fp}, Sheet: {sheet}")
    try:
        df = pd.read_excel(fp, sheet_name=sheet)
    except FileNotFoundError:
        logger.error(f"Outlet assortment rules file not found: {fp}")
        raise
    except ValueError:
        logger.warning(f"Sheet '{sheet}' not found in '{fp}' for outlet assortment rules. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error reading outlet assortment rules file {fp}: {e}")
        raise
        
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    smc,ssc,sbc,smsc = met_c.strip('"'), sub_c.strip('"'), brand_c.strip('"'), max_skus_c.strip('"')
    if not all(c in df.columns for c in [smc,ssc,sbc,smsc]): 
        logger.error(f"Required columns ('{smc}', '{ssc}', '{sbc}', '{smsc}') missing in outlet assortment file {fp} sheet {sheet}. Found: {df.columns.tolist()}")
        raise ValueError(f"Cols missing in {fp} sheet {sheet}")
    for i,r in df.iterrows(): 
        try:
            rules.append(OutletAssortmentRule(metier=str(r[smc]),subaxis=str(r[ssc]),brand=str(r[sbc]),max_skus=int(r[smsc])))
        except Exception as e:
            logger.error(f"Error processing row {i} in outlet assortment file {fp}: {r}. Error: {e}. Skipping row.")
    logger.info(f"Loaded {len(rules)} outlet assortment rules from {fp}.")
    return rules

def load_push_new_sku_rules_from_excel(fp, sheet='Feuil1', div_c='operational_division', sub_c='operational_sub_axe_label', push_qty_c='Push Quantity if New SKU'):
    logger.info(f"Loading push new SKU rules from: {fp}, Sheet: {sheet}")
    try:
        df = pd.read_excel(fp, sheet_name=sheet)
    except FileNotFoundError:
        logger.error(f"Push new SKU rules file not found: {fp}")
        raise
    except ValueError:
        logger.warning(f"Sheet '{sheet}' not found in '{fp}' for push new SKU rules. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error reading push new SKU rules file {fp}: {e}")
        raise
        
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    sdc,ssc,spqc = div_c.strip('"'), sub_c.strip('"'), push_qty_c.strip('"')
    if not all(c in df.columns for c in [sdc,ssc,spqc]): 
        logger.error(f"Required columns ('{sdc}', '{ssc}', '{spqc}') missing in push new SKU file {fp} sheet {sheet}. Need '{sdc}', '{ssc}', '{spqc}'. Found: {df.columns.tolist()}")
        raise ValueError(f"Cols missing in {fp} sheet {sheet}. Need '{sdc}', '{ssc}', '{spqc}'. Found: {df.columns.tolist()}")
    for i,r in df.iterrows(): 
        try:
            rules.append(PushNewSKURule(division=str(r[sdc]),subaxis=str(r[ssc]),push_quantity=int(r[spqc])))
        except Exception as e:
            logger.error(f"Error processing row {i} in push new SKU file {fp}: {r}. Error: {e}. Skipping row.")
    logger.info(f"Loaded {len(rules)} push new SKU rules from {fp}.")
    return rules

if __name__ == '__main__':
    # --- Main script logger setup (can be more sophisticated) ---
    # Basic configuration is done at the top of the file for the module logger.
    # If you want a specific configuration for the __main__ block, you can adjust here.
    # For example, to set a file handler for the main execution:
    # file_handler = logging.FileHandler('solver_run.log')
    # file_handler.setFormatter(formatter) # Use the same formatter or a different one
    # logger.addHandler(file_handler)
    # logger.setLevel(logging.INFO) # Or DEBUG for more verbosity in the file

    logger.info("Solver script started.")
    data_path = 'data'; excel_params_path = f'{data_path}/ExcelParameters'
    product_master_file = f'{data_path}/InputData/masterdata.csv'
    bad_stock_file = f'{data_path}/InputData/bad_stock_inventory.csv'
    in_store_inventory_file = f'{data_path}/InputData/in_store_inventory.csv'
    stock_in_transit_file = f'{data_path}/InputData/stock_in_transit.csv'
    sellout_file = f'{data_path}/InputData/sellout.csv'
    
    channel_list_file = f'{excel_params_path}/ChannelList.xlsx' 

    capacity_channel_file = f'{excel_params_path}/CapacityPerChannel.xlsx'
    coverage_rules_file = f'{excel_params_path}/CoverageperABCperChannel.xlsx'
    assortment_rules_file = f'{excel_params_path}/AssortmentperSubaxeperSignature.xlsx'
    push_new_sku_file = f'{excel_params_path}/PushNewSKU.xlsx'

    try:
        logger.info("--- Starting Data Loading ---")
        products_df = load_product_data(product_master_file, ean_c='product_gtin', brand_c='operational_signature_label', div_c='operational_division', axe_c='operational_axe_label', sub_c='operational_sub_axe_label', met_c='operational_metier_label')
        
        channels_df = load_channel_data_from_channellist(
            channel_list_file, 
            sheet_name='Feuil1', 
            channel_id_col='channel_id', 
            channel_type_col='channel_type'
        )
        if channels_df.empty: 
            logger.critical("No channels loaded from ChannelList.xlsx. Cannot proceed.")
            raise ValueError("No channels loaded from ChannelList.xlsx.")

        inventory_df = load_inventory_data(bad_stock_file, ean_c='ean_code', qty_c='StockToAllocate')
        
        existing_stock_dict = load_existing_stock_data(in_store_inventory_file, stock_in_transit_file)
        
        demand_dict = load_demand_data(sellout_file, ean_c='barcode', chan_c='store_code', dem_c='total_items_weekly')
        
        logger.info("--- Loading Parameter Rules ---")
        coverage_rules = load_coverage_rules_from_excel(coverage_rules_file, sheet='Feuil1')
        
        outlet_sku_capacity_rules = load_outlet_sku_capacity_rules_from_excel(
            capacity_channel_file, sheet='Feuil1', chan_c='Channel', 
            div_c='operational_division', axe_c='operational_axe_label', 
            max_skus_c='Max capacity (in # of SKU)'
        )
        
        assortment_rules = load_outlet_assortment_rules_from_excel(assortment_rules_file, sheet='Feuil1')
        
        push_new_sku_rules = load_push_new_sku_rules_from_excel(push_new_sku_file, sheet='Feuil1') 
        
        logger.info("--- Calculating ABC Classification ---")
        raw_sellout_df = pd.read_csv(sellout_file) 
        
        all_loaded_channel_ids = channels_df.index.tolist()
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            raw_sellout_df,
            products_df, 
            all_channel_ids=all_loaded_channel_ids, 
            sellout_ean_col='barcode', 
            sellout_channel_col='store_code', 
            sellout_qty_col='total_items_weekly'
        )
        logger.info(f"Calculated ABC & NEW status for {len(product_channel_abc_map)} product-channel pairs.")

        seasonality_coefficient = 1.0
        try:
            s_input = input("Enter seasonality coefficient (e.g., 1.0): ") # Input remains for interaction
            seasonality_coefficient = float(s_input)
            if seasonality_coefficient < 0: 
                logger.warning(f"Negative seasonality coefficient {seasonality_coefficient} entered. Resetting to 1.0.")
                seasonality_coefficient = 1.0
        except ValueError: 
            logger.warning("Invalid seasonality input. Using default 1.0.")
        logger.info(f"Using seasonality coefficient: {seasonality_coefficient}")

        params = OptimizationParameters(
            seasonality_coefficient=seasonality_coefficient, restricted_brands_for_donation=[],
            coverage_days_rules=coverage_rules, outlet_sku_capacity_rules=outlet_sku_capacity_rules,
            outlet_assortment_rules=assortment_rules, push_new_sku_rules=push_new_sku_rules
        )
        logger.info("OptimizationParameters object created.")

        logger.info("\n--- Running Optimization ---")
        model, status, results = optimize_allocation(products_df, channels_df, inventory_df, demand_dict, params, existing_stock_dict, product_channel_abc_map)
        
        logger.info(f"\nSolver Status: {status}")
        if status == 'Optimal':
            logger.info("Allocation Results:")
            results_df = pd.DataFrame(results)
            if not results_df.empty:
                results_df[['product_sku','channel_id']] = results_df[['product_sku','channel_id']].astype(str)
                # Log results summary instead of full df to console for brevity, full df could go to a file or DEBUG
                logger.info(f"Optimal allocation found with {len(results_df)} entries.")
                logger.debug(f"Full allocation results:\n{results_df.to_string()}") 
            else: 
                logger.info("Optimal solution, but no allocation quantities > 0.1.")
        else: 
            logger.error(f"Optimization not optimal. Status: {status}. Check allocation_model.lp for details.")

    except FileNotFoundError as e: 
        logger.critical(f"Critical File Not Found Error: {e}. Aborting.")
    except ValueError as e: 
        logger.critical(f"Critical Value Error: {e}. Aborting.") 
    except Exception as e: 
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True) # exc_info=True logs stack trace
    logger.info("Solver script finished.")
