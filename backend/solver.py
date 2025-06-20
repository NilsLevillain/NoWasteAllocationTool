# At the top of solver.py
import os
import sys
import pulp
import pandas as pd
from collections import defaultdict
import logging
import json # For structured logging example

# Adjust sys.path for standalone execution BEFORE other backend imports
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# --- Schemas Import ---
# This should now work whether imported or run directly due to sys.path adjustment above.
from backend.schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule

# --- Logger Setup ---
# For future tests, set this to the EAN string you want to filter for, or None to disable.
# EANs are typically logged without leading zeros in this system.
TARGET_EAN_FOR_LOGGING = '3600550817584'

class EANLogFilter(logging.Filter):
    def __init__(self, ean_to_filter=None):
        super().__init__()
        # Store the EAN to filter for, assuming it's already normalized (e.g., no leading zeros)
        self.ean_to_filter = str(ean_to_filter) if ean_to_filter else None

    def filter(self, record):
        # If no EAN filter is active, pass all records.
        if not self.ean_to_filter:
            return True

        message_content = record.getMessage() # Get the fully rendered message

        # Check if the target EAN is present in the message content.
        if self.ean_to_filter in message_content:
            return True
        
        # If the target EAN is not in the message:
        # Suppress DEBUG level messages, as they are likely details for other EANs or general debug info not relevant to the filtered EAN.
        if record.levelno == logging.DEBUG:
            return False
            
        # Allow INFO, WARNING, ERROR, CRITICAL messages to pass.
        # These are often general status updates, summaries, or errors not specific to an EAN,
        # or if they are for another EAN, they are important enough (e.g. an error) to show.
        return True

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

# Add EAN filter if TARGET_EAN_FOR_LOGGING is set
if TARGET_EAN_FOR_LOGGING:
    logger.info(f"EAN log filtering is active for EAN: {TARGET_EAN_FOR_LOGGING}")
    ean_filter = EANLogFilter(ean_to_filter=TARGET_EAN_FOR_LOGGING)
    ch.addFilter(ean_filter)

# Add ch to logger
if not logger.handlers: # Avoid adding multiple handlers if script is re-run in some contexts
    logger.addHandler(ch)

# --- Import utils for loading data when used as a module ---
# This ensures that when main.py imports optimize_allocation, these are available.
# The __main__ block in this file will handle its own imports for standalone execution.
if __name__ != "__main__":
    from backend.utils import (
        load_products_df, load_channels_df, load_inventory_df, load_demand_dict,
        load_existing_stock_dict, load_optimization_rules
    )

# --- ABC Classification Function ---
def calculate_abc_classification_and_new_skus(
    product_master_df: pd.DataFrame,
    all_channel_ids: list, # Specific channel IDs like 'A90', 'B10'
    in_store_inventory_df: pd.DataFrame, # Expected to have 'barcode', 'store_code', 'physical_quantity'
    abc_ranking_file_path: str # Path to ABC_ranking.csv
):
    product_channel_abc_map = {}
    logger.info(f"Starting ABC classification using file: {abc_ranking_file_path}")

    # 1. Process in-store inventory to identify stocked EAN-channel pairs
    logger.debug("Processing in-store inventory data for NEW SKU and default 'C' logic.")
    # Ensure correct types for relevant columns from in_store_inventory_df
    # These column names are fixed based on the expected structure of in_store_inventory.csv
    if not in_store_inventory_df.empty:
        # EANs are expected to be clean strings now, just ensure they are strings and strip leading zeros
        in_store_inventory_df['barcode'] = in_store_inventory_df['barcode'].astype(str).str.lstrip('0').fillna('')
        in_store_inventory_df['store_code'] = in_store_inventory_df['store_code'].astype(str)
        in_store_inventory_df['physical_quantity'] = pd.to_numeric(in_store_inventory_df['physical_quantity'], errors='coerce').fillna(0)
        
        # Filter out rows where barcode might have become empty after stripping (e.g., if it was "0")
        valid_inventory_df = in_store_inventory_df[in_store_inventory_df['barcode'] != '']
        
        stocked_df = valid_inventory_df[valid_inventory_df['physical_quantity'] > 0]
        stocked_product_channel_pairs = set()
        if not stocked_df.empty:
            stocked_product_channel_pairs = set(zip(stocked_df['barcode'], stocked_df['store_code'])) # Uses normalized barcodes
            logger.debug(f"Found {len(stocked_product_channel_pairs)} product-channel pairs with existing stock from in_store_inventory_df.")
        else:
            logger.debug("No product-channel pairs with existing stock found in in_store_inventory_df (after filtering for positive quantity or invalid EANs).")
    else:
        logger.debug("In-store inventory data is empty. No stocked product-channel pairs to identify.")
        stocked_product_channel_pairs = set()


    # 2. Read ABC_ranking.csv
    logger.debug(f"Reading ABC ranking data from: {abc_ranking_file_path}")
    try:
        # Specify dtype for barcode and store_code to handle them as strings,
        # especially if barcode can be numeric/scientific.
        abc_ranking_df = pd.read_csv(
            abc_ranking_file_path, 
            sep=';', 
            dtype={'barcode': str, 'store_code': str, 'abc_class': str}
        )
        # EANs are expected to be clean strings now, just ensure they are strings and strip leading zeros
        abc_ranking_df['barcode'] = abc_ranking_df['barcode'].astype(str).str.lstrip('0').fillna('')
        abc_ranking_df['store_code'] = abc_ranking_df['store_code'].astype(str).fillna('')
        abc_ranking_df['abc_class'] = abc_ranking_df['abc_class'].astype(str).fillna('').str.upper() # Standardize to uppercase

        # Filter out rows where essential data might be missing or EAN became empty
        abc_ranking_df = abc_ranking_df[
            (abc_ranking_df['barcode'] != '') & 
            (abc_ranking_df['store_code'] != '') & 
            (abc_ranking_df['abc_class'] != '') &
            (abc_ranking_df['abc_class'].isin(['A', 'B', 'C'])) # Only consider valid ABC classes from file
        ]
        logger.info(f"Successfully loaded and processed {len(abc_ranking_df)} valid rows from {abc_ranking_file_path}.")
    except FileNotFoundError:
        logger.error(f"ABC ranking file not found: {abc_ranking_file_path}. All products will be classified based on stock (C or NEW).")
        abc_ranking_df = pd.DataFrame(columns=['barcode', 'store_code', 'abc_class']) # Empty DataFrame
    except Exception as e:
        logger.error(f"Error reading ABC ranking file {abc_ranking_file_path}: {e}. All products will be classified based on stock (C or NEW).")
        abc_ranking_df = pd.DataFrame(columns=['barcode', 'store_code', 'abc_class'])

    # Create a lookup map from ABC_ranking.csv: {(ean, channel): abc_class}
    abc_lookup_map = {}
    if not abc_ranking_df.empty:
        # Use normalized 'barcode' for the lookup map keys
        for _, row in abc_ranking_df.iterrows():
            ean_key = row['barcode'] # Already normalized and string
            channel_key = row['store_code'] # Already string
            abc_lookup_map[(ean_key, channel_key)] = row['abc_class'] # Already uppercase and validated A, B, C
        logger.debug(f"Created ABC lookup map with {len(abc_lookup_map)} entries from ABC_ranking.csv.")

    # 3. Iterate through all EANs (from product_master_df.index, which are already normalized by load_products_df) and all_channel_ids
    for product_ean_str in product_master_df.index: # Already normalized strings
        for channel_id_str in map(str, all_channel_ids): # Ensure channel_ids are also strings
            current_pair = (product_ean_str, channel_id_str)
            
            # Attempt to find ABC class in the lookup map
            if current_pair in abc_lookup_map:
                abc_class = abc_lookup_map[current_pair] # Class is already validated A, B, or C
                product_channel_abc_map[current_pair] = abc_class
                logger.debug(f"EAN {product_ean_str}, Channel {channel_id_str}: classified as '{abc_class}' from ABC_ranking.csv.")
            else:
                # Not found in ABC_ranking.csv. Check stock.
                has_stock_in_channel = current_pair in stocked_product_channel_pairs
                
                if has_stock_in_channel:
                    # Not in file, but HAS stock -> 'C'
                    product_channel_abc_map[current_pair] = 'C'
                    logger.debug(f"EAN {product_ean_str}, Channel {channel_id_str}: not in ABC_ranking.csv, has stock. Classified as 'C'.")
                else:
                    # Not in file, AND NO stock -> 'NEW'
                    product_channel_abc_map[current_pair] = 'NEW'
                    logger.debug(f"EAN {product_ean_str}, Channel {channel_id_str}: not in ABC_ranking.csv, no stock. Classified as 'NEW'.")
                    
    logger.info(f"Finished ABC classification. Total product-channel pairs processed: {len(product_channel_abc_map)}.")
    return product_channel_abc_map

def optimize_allocation(products_df: pd.DataFrame, channels_df: pd.DataFrame, inventory_df: pd.DataFrame,
                        demand_dict: dict, parameters: OptimizationParameters, existing_stock_dict: dict,
                        product_channel_abc_map: dict):
    logger.info("Starting inventory allocation optimization.")
    logger.debug(f"Number of products: {len(products_df)}, Number of channels: {len(channels_df)}")
    logger.debug(f"Optimization Parameters: {parameters}")

    products_df.index = products_df.index.astype(str)
    channels_df.index = channels_df.index.astype(str)
    products = products_df.index.tolist() # List of unique EANs
    channels = channels_df.index.tolist() # List of unique Channel IDs

    # inventory_df is already EAN-Plant specific from load_inventory_df
    # It has 'product_ean', 'plant', 'quantity' (StockToAllocate), 'available_stock'
    ean_plant_pairs = list(inventory_df[['product_ean', 'plant']].itertuples(index=False, name=None))
    logger.debug(f"Found {len(ean_plant_pairs)} EAN-Plant combinations from inventory_df.")

    stock_to_allocate_per_ean_plant = inventory_df.set_index(['product_ean', 'plant'])['quantity'].to_dict()
    logger.debug(f"StockToAllocate per EAN-Plant: {len(stock_to_allocate_per_ean_plant)} entries.")
    
    available_stock_per_ean_plant = inventory_df.set_index(['product_ean', 'plant'])['available_stock'].to_dict()
    logger.debug(f"AvailableStock per EAN-Plant: {len(available_stock_per_ean_plant)} entries.")

    coverage_rules_dict = {(r.channel_id, r.abc_class): r.coverage_days for r in parameters.coverage_days_rules}
    logger.debug(f"Coverage Rules Dictionary created with {len(coverage_rules_dict)} entries: {coverage_rules_dict}") # Log the dict
    outlet_capacity_dict = {(r.channel_id, r.division, r.axe): r.max_skus for r in parameters.outlet_sku_capacity_rules}
    outlet_assortment_dict = {(r.metier, r.subaxis, r.brand): r.max_skus for r in parameters.outlet_assortment_rules}
    push_new_sku_lookup = {(r.division, r.subaxis): r.push_quantity for r in parameters.push_new_sku_rules}
    products_by_outlet_capacity_group = defaultdict(list)
    products_by_outlet_assortment_group = defaultdict(list)
    
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
    
    # Decision variable for quantity allocated from a specific EAN-Plant to a Channel
    x = pulp.LpVariable.dicts("allocation_qty", 
                               ((p, plant, c) for p, plant in ean_plant_pairs for c in channels), 
                               lowBound=0, cat='Integer')
    
    # Binary variable indicating if EAN p from Plant plant is allocated to Channel c
    y_ean_plant_channel = pulp.LpVariable.dicts("is_allocated_from_plant", 
                                                ((p, plant, c) for p, plant in ean_plant_pairs for c in channels), 
                                                cat='Binary')
    
    # Auxiliary binary variable: is EAN p allocated to Channel c (from ANY plant)? Used for SKU counting constraints.
    y_ean_channel = pulp.LpVariable.dicts("is_ean_allocated_to_channel", 
                                          ((p, c) for p in products for c in channels), 
                                          cat='Binary')

    model += (pulp.lpSum(x[p, plant, c] for p, plant in ean_plant_pairs for c in channels), "Maximize_Total_Allocation")
    logger.debug("Objective function added: Maximize_Total_Allocation.")

    logger.info("Adding supply constraints (per EAN-Plant).")
    for p, plant_code in ean_plant_pairs:
        s_to_allocate = stock_to_allocate_per_ean_plant.get((p, plant_code), 0)
        a_stock = available_stock_per_ean_plant.get((p, plant_code), 0)
        max_allocatable_at_plant = min(s_to_allocate, a_stock)
        
        model += pulp.lpSum(x[p, plant_code, c] for c in channels) <= max_allocatable_at_plant, f"Supply_Product_{p}_Plant_{plant_code}"
        logger.debug(f"Supply constraint for P:{p} Plant:{plant_code}: sum(alloc) <= {max_allocatable_at_plant} (StockToAllocate: {s_to_allocate}, AvailableStock: {a_stock})")

    logger.info("Linking allocation quantity (x) with plant-level decision (y_ean_plant_channel) and EAN-level decision (y_ean_channel).")
    for p_ean, plant_code_specific in ean_plant_pairs:
        M_val_plant = min(stock_to_allocate_per_ean_plant.get((p_ean, plant_code_specific), 0), 
                          available_stock_per_ean_plant.get((p_ean, plant_code_specific), 0))
        for c_channel in channels:
            # Link x[p,plant,c] to y_ean_plant_channel[p,plant,c]
            if M_val_plant > 0:
                model += x[p_ean, plant_code_specific, c_channel] <= M_val_plant * y_ean_plant_channel[p_ean, plant_code_specific, c_channel], f"Link_x_y_plant_P{p_ean}_Pl{plant_code_specific}_C{c_channel}"
            else: # No stock at this plant for this EAN
                model += x[p_ean, plant_code_specific, c_channel] == 0, f"Force_x_zero_NoInv_P{p_ean}_Pl{plant_code_specific}_C{c_channel}"
                model += y_ean_plant_channel[p_ean, plant_code_specific, c_channel] == 0, f"Force_y_plant_zero_NoInv_P{p_ean}_Pl{plant_code_specific}_C{c_channel}"

    # Link y_ean_plant_channel to y_ean_channel
    for p_ean in products: # Iterate over unique EANs
        plants_for_this_ean = [pl for ean_tuple, pl in ean_plant_pairs if ean_tuple == p_ean]
        if not plants_for_this_ean: continue # Should not happen if products list is derived from ean_plant_pairs

        for c_channel in channels:
            # If any y_ean_plant_channel[p, plant, c] is 1, then y_ean_channel[p,c] must be 1
            for pl_specific in plants_for_this_ean:
                model += y_ean_plant_channel[p_ean, pl_specific, c_channel] <= y_ean_channel[p_ean, c_channel], f"Link_yPlant_yEAN_P{p_ean}_Pl{pl_specific}_C{c_channel}"
            
            # If y_ean_channel[p,c] is 1, at least one y_ean_plant_channel[p, plant, c] must be 1 (this is implicitly handled by the above and objective)
            # More strongly: y_ean_channel[p,c] <= sum(y_ean_plant_channel[p,plant,c] for plant in plants_for_this_ean)
            model += y_ean_channel[p_ean, c_channel] <= pulp.lpSum(y_ean_plant_channel[p_ean, pl_specific, c_channel] for pl_specific in plants_for_this_ean), f"Link_yEAN_sum_yPlant_P{p_ean}_C{c_channel}"
            
    logger.info("Adding outlet SKU capacity constraints (using y_ean_channel).")
    for c in channels: 
        channel_type = channels_df.loc[c, 'channel_type']
        if channel_type == 'outlet':
            for (division, axe), group_products_eans in products_by_outlet_capacity_group.items(): # group_products_eans contains EANs
                max_skus = outlet_capacity_dict.get((c, division, axe))
                if max_skus is not None and max_skus >= 0:
                    # Sum over y_ean_channel for EANs in this group
                    model += pulp.lpSum(y_ean_channel[pg_ean, c] for pg_ean in group_products_eans if pg_ean in products) <= max_skus, f"Outlet_Capacity_SKU_{c}_{division}_{axe}"
                    logger.debug(f"Added SKU capacity constraint for channel {c}, div {division}, axe {axe}: max {max_skus} SKUs (EAN level).")

    logger.info("Adding coverage days and new SKU push constraints (sum of x over plants for an EAN-Channel).")
    for c in channels: 
        for p_ean in products: # p_ean is an EAN
            plants_for_this_ean = [pl for ean_tuple, pl in ean_plant_pairs if ean_tuple == p_ean]
            if not plants_for_this_ean:
                logger.debug(f"EAN {p_ean} has no plants in ean_plant_pairs. Skipping coverage/push constraints for channel {c}.")
                continue

            abc_class = product_channel_abc_map.get((p_ean, c), 'C') 
            logger.debug(f"Coverage/Push: EAN {p_ean}, Channel {c}, ABC Class: {abc_class}")
            current_stock_for_pc = existing_stock_dict.get((p_ean, c), 0) # This is EAN-Channel level existing stock

            if abc_class == 'NEW':
                div, sub = products_df.loc[p_ean].get('division'), products_df.loc[p_ean].get('subaxis')
                push_qty = push_new_sku_lookup.get((div, sub), 0) if div and sub else 0
                # Sum of allocations for this EAN to this Channel, across all plants, must be <= push_qty
                model += pulp.lpSum(x[p_ean, pl_specific, c] for pl_specific in plants_for_this_ean) <= push_qty, f"Push_New_SKU_{p_ean}_{c}"
                logger.debug(f"Push new SKU constraint for EAN:{p_ean} C:{c} (NEW): sum_plants(qty) <= {push_qty}. Applied.")
            else: 
                # Get channel type for the current channel ID c
                channel_type_for_c = channels_df.loc[c, 'channel_type']
                lookup_key = (channel_type_for_c, abc_class)
                logger.debug(f"Coverage lookup: EAN {p_ean}, C_ID {c}, C_Type {channel_type_for_c}, ABC {abc_class}. Using key: {lookup_key}")
                cov_days = coverage_rules_dict.get(lookup_key) 
                logger.debug(f"Coverage lookup result for EAN {p_ean}, C_ID {c} (Type {channel_type_for_c}), ABC {abc_class} (key {lookup_key}): cov_days = {cov_days} (Type: {type(cov_days)})")
                
                if cov_days is not None and cov_days >= 0:
                    adj_demand = demand_dict.get((p_ean, c), 0) * parameters.seasonality_coefficient # EAN-Channel demand
                    logger.debug(f"Coverage calc: EAN {p_ean}, C_ID {c}. Adjusted demand: {adj_demand}, Current stock: {current_stock_for_pc}, Cov_days: {cov_days}")
                    if adj_demand > 0:
                        allow_alloc = max(0, (adj_demand / 14.0) * cov_days - current_stock_for_pc)
                        # Sum of allocations for this EAN to this Channel, across all plants
                        model += pulp.lpSum(x[p_ean, pl_specific, c] for pl_specific in plants_for_this_ean) <= allow_alloc, f"Max_Coverage_Days_{p_ean}_{c}"
                        logger.debug(f"Coverage constraint for EAN:{p_ean} C_ID:{c} (ABC:{abc_class}): sum_plants(qty) <= {allow_alloc}. Applied.")
                    else: 
                        model += pulp.lpSum(x[p_ean, pl_specific, c] for pl_specific in plants_for_this_ean) <= 0, f"Max_Coverage_Days_Zero_Demand_{p_ean}_{c}"
                        logger.debug(f"Coverage constraint for EAN:{p_ean} C_ID:{c} (ABC:{abc_class}): Zero demand, sum_plants(qty) <= 0. Applied.")
                else:
                    logger.debug(f"Coverage constraint for EAN:{p_ean} C_ID:{c} (ABC:{abc_class}): Skipped (cov_days is None or negative: {cov_days}).")
    
    if parameters.restricted_brands_for_donation:
        logger.info("Adding restricted brands for donation constraints.")
        don_chans_from_df = channels_df[channels_df['channel_type'] == 'donation'].index.tolist()
        if don_chans_from_df: 
            restr_brands = set(parameters.restricted_brands_for_donation)
            for p_ean in products:
                if products_df.loc[p_ean].get('brand') in restr_brands:
                    plants_for_this_ean = [pl for ean_tuple, pl in ean_plant_pairs if ean_tuple == p_ean]
                    for dc_channel in don_chans_from_df: 
                        if dc_channel in channels: 
                            for pl_specific in plants_for_this_ean:
                                model += x[p_ean, pl_specific, dc_channel] == 0, f"Restricted_Brand_{products_df.loc[p_ean].get('brand')}_P{p_ean}_Pl{pl_specific}_C{dc_channel}"
                                logger.debug(f"Restricted brand {products_df.loc[p_ean].get('brand')} for P:{p_ean} Pl:{pl_specific} in donation channel {dc_channel}.")
    
    logger.info("Adding outlet assortment constraints (using y_ean_channel).")
    for c_out in outlet_channels: 
        if c_out not in channels: 
            logger.warning(f"Outlet channel {c_out} from outlet_channels list not in main channels list. Skipping assortment rules for it.")
            continue 
        for (metier, subaxis, brand), group_products_eans in products_by_outlet_assortment_group.items(): # group_products_eans contains EANs
            max_skus = outlet_assortment_dict.get((metier, subaxis, brand)) 
            if max_skus is not None and max_skus >= 0:
                # Sum over y_ean_channel for EANs in this group
                model += pulp.lpSum(y_ean_channel[pg_ean, c_out] for pg_ean in group_products_eans if pg_ean in products) <= max_skus, f"Outlet_Assortment_{c_out}_{metier}_{subaxis}_{brand}"
                logger.debug(f"Added assortment constraint for outlet {c_out}, metier {metier}, subaxis {subaxis}, brand {brand}: max {max_skus} SKUs (EAN level).")

    # Linking constraints for x[p,plant,c] and y_ean_plant_channel[p,plant,c] are already done above.
    # Linking constraints for y_ean_plant_channel[p,plant,c] and y_ean_channel[p,c] are also done above.

    logger.info("Writing LP model to allocation_model.lp")
    model.writeLP("allocation_model.lp")
    logger.info("Solving optimization model...")
    model.solve() 
    status_string = pulp.LpStatus[model.status] 
    logger.info(f"Solver status: {status_string}")

    results = []
    if status_string == 'Optimal':
        logger.info("Optimal solution found. Extracting results.")
        results = []
        for p_ean, plant_code in ean_plant_pairs:
            for c_channel in channels:
                var_value = x[p_ean, plant_code, c_channel].varValue
                if var_value is not None and var_value > 0.1: # Using 0.1 to handle potential float inaccuracies
                    results.append({
                        'product_sku': p_ean,          # EAN
                        'plant_code': plant_code,      # Plant Code
                        'channel_id': c_channel,       # Channel ID
                        'quantity': int(round(var_value))
                    })
        logger.info(f"Extracted {len(results)} allocation entries (EAN-Plant-Channel).")
    else:
        logger.warning(f"Optimization was not optimal. Status: {status_string}. No results extracted.")
    return model, status_string, results

# Removed all load_* functions from here as they are now in backend/utils.py

if __name__ == '__main__':
    # --- Imports for standalone execution ---
    # utils are imported here because the conditional import at the top (if __name__ != "__main__")
    # would not have run. Schemas are already imported globally thanks to sys.path modification.
    from backend.utils import (
        load_products_df, load_channels_df, load_inventory_df, load_demand_dict,
        load_existing_stock_dict, load_optimization_rules
    )
    # Schemas (OptimizationParameters, etc.) are already available from top-level import.
    
    logger.info("Solver script started (running as __main__).")
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.abspath(os.path.join(current_script_dir, '..')) 

    data_path = os.path.join(project_root_dir, 'data')
    excel_params_path = os.path.join(data_path, 'ExcelParameters')
    input_data_path = os.path.join(data_path, 'InputData')

    product_master_file = os.path.join(input_data_path, 'masterdata.csv')
    bad_stock_file = os.path.join(input_data_path, 'bad_stock_inventory.csv')
    in_store_inventory_file = os.path.join(input_data_path, 'in_store_inventory.csv')
    stock_in_transit_file = os.path.join(input_data_path, 'stock_in_transit.csv')
    sellout_file = os.path.join(input_data_path, 'sellout.csv')
    
    channel_list_file = os.path.join(excel_params_path, 'ChannelList.xlsx')
    capacity_channel_file = os.path.join(excel_params_path, 'CapacityPerChannel.xlsx')
    coverage_rules_file = os.path.join(excel_params_path, 'CoverageperABCperChannel.xlsx')
    assortment_rules_file = os.path.join(excel_params_path, 'AssortmentperSubaxeperSignature.xlsx')
    push_new_sku_file = os.path.join(excel_params_path, 'PushNewSKU.xlsx')

    try:
        logger.info("--- Starting Data Loading using backend.utils (in __main__) ---")
        products_df = load_products_df(
            product_master_file,
            ean_col='product_gtin',
            signature_col='operational_signature_label', # Corrected from brand_col
            div_col='operational_division',
            axe_col='operational_axe_label',
            sub_axe_col='operational_sub_axe_label',
            metier_col='operational_metier_label'
            # sku_col and description_col will use default values from the function signature
            # cogs_col will also use its default
        )
        
        channels_df = load_channels_df(
            channel_list_file,
            sheet_name='Feuil1',
            channel_id_col='channel_id',
            channel_type_col='channel_type'
        )
        if channels_df.empty:
            logger.critical("No channels loaded from ChannelList.xlsx. Cannot proceed.")
            raise ValueError("No channels loaded from ChannelList.xlsx.")

        inventory_df = load_inventory_df( # This now returns EAN-Plant level data
            bad_stock_file,
            ean_col='ean_code', # Correct parameter name for ean column in bad_stock_inventory.csv
            qty_col='StockToAllocate',
            available_stock_col='AvailableStock', # Ensure this is passed
            plant_code_col='plant', # Ensure this is passed
            plant_desc_col='plant_description', # Ensure this is passed
            flag6_col='FlagExcess6months', # Ensure this is passed
            flag12_col='FlagExcess12months' # Ensure this is passed
        )
        
        existing_stock_dict = load_existing_stock_dict(
            in_store_fp=in_store_inventory_file,
            in_transit_fp=stock_in_transit_file
        )
        
        demand_dict = load_demand_dict(
            sellout_file,
            ean_col='barcode',
            channel_col='store_code',
            demand_qty_col='total_items_weekly'
        )
        
        logger.info("--- Loading Parameter Rules using backend.utils (in __main__) ---")
        CoverageRuleSchema = CoverageDaysRule
        OutletCapRuleSchema = OutletSKUCapacityRule
        AssortRuleSchema = OutletAssortmentRule
        PushRuleSchema = PushNewSKURule
        OptParamsSchema = OptimizationParameters # Use the globally imported one
        # No need to check for MainCoverageRule etc. as schemas are globally imported

        coverage_rules = load_optimization_rules(
            coverage_rules_file, CoverageDaysRule, sheet_name='Feuil1',
            channel_id='channel_id', abc_class='abc_class', coverage_days='coverage_days'
        )
        
        outlet_sku_capacity_rules = load_optimization_rules(
            capacity_channel_file, OutletSKUCapacityRule, sheet_name='Feuil1',
            channel_id='channel_id', 
            division='operational_division',
            axe='operational_axe_label',
            max_skus='max_skus'
        )
        
        assortment_rules = load_optimization_rules(
            assortment_rules_file, OutletAssortmentRule, sheet_name='Feuil1',
            metier='operational_metier_label',
            subaxis='operational_sub_axe_label',
            brand='operational_signature_label',
            max_skus='max_skus'
        )
        
        push_new_sku_rules = load_optimization_rules(
            push_new_sku_file, PushNewSKURule, sheet_name='Feuil1',
            division='operational_division',
            subaxis='operational_sub_axe_label',
            push_quantity='Push Quantity if New SKU'
        )
        
        logger.info("--- Calculating ABC Classification (in __main__) ---")
        # raw_sellout_df is no longer directly needed for calculate_abc_classification_and_new_skus
        # but might be loaded for other purposes if any. For now, its direct usage here is removed.
        # raw_sellout_df = pd.read_csv(sellout_file) 
        
        # Load in-store inventory for ABC classification
        logger.info(f"Loading in-store inventory from: {in_store_inventory_file} for ABC/NEW SKU calculation.")
        try:
            # Assuming standard column names 'store_code', 'barcode', 'physical_quantity'
            raw_in_store_inventory_df = pd.read_csv(in_store_inventory_file, sep=';', dtype={'store_code': str, 'barcode': str}) # Added sep=';'
            logger.info(f"Successfully loaded in-store inventory data: {raw_in_store_inventory_df.shape[0]} rows.")
        except FileNotFoundError:
            logger.error(f"In-store inventory file not found: {in_store_inventory_file}. Proceeding without it for NEW SKU, this may affect NEW classification.")
            raw_in_store_inventory_df = pd.DataFrame(columns=['store_code', 'barcode', 'physical_quantity']) # Empty df
        except Exception as e:
            logger.error(f"Error loading in-store inventory file {in_store_inventory_file}: {e}. Proceeding with empty df.")
            raw_in_store_inventory_df = pd.DataFrame(columns=['store_code', 'barcode', 'physical_quantity'])

        all_loaded_channel_ids = channels_df.index.tolist()
        abc_ranking_file = os.path.join(input_data_path, 'ABC_ranking.csv')

        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            product_master_df=products_df, # products_df is the master data in this context
            all_channel_ids=all_loaded_channel_ids,
            in_store_inventory_df=raw_in_store_inventory_df,
            abc_ranking_file_path=abc_ranking_file
        )
        logger.info(f"Calculated ABC & NEW status for {len(product_channel_abc_map)} product-channel pairs using ABC_ranking.csv.")

        seasonality_coefficient = 1.0
        try:
            s_input = input("Enter seasonality coefficient (e.g., 1.0): ")
            seasonality_coefficient = float(s_input)
            if seasonality_coefficient < 0: 
                logger.warning(f"Negative seasonality coefficient {seasonality_coefficient} entered. Resetting to 1.0.")
                seasonality_coefficient = 1.0
        except ValueError: 
            logger.warning("Invalid seasonality input. Using default 1.0.")
        logger.info(f"Using seasonality coefficient: {seasonality_coefficient}")

        params = OptParamsSchema(
            seasonality_coefficient=seasonality_coefficient, restricted_brands_for_donation=[],
            coverage_days_rules=coverage_rules, outlet_sku_capacity_rules=outlet_sku_capacity_rules,
            outlet_assortment_rules=assortment_rules, push_new_sku_rules=push_new_sku_rules
        )
        logger.info("OptimizationParameters object created.")

        logger.info("\n--- Running Optimization (in __main__) ---")
        model, status, results = optimize_allocation(products_df, channels_df, inventory_df, demand_dict, params, existing_stock_dict, product_channel_abc_map)
        
        logger.info(f"\nSolver Status: {status}")
        if status == 'Optimal':
            logger.info("Allocation Results:")
            results_df = pd.DataFrame(results)
            if not results_df.empty:
                results_df[['product_sku','channel_id']] = results_df[['product_sku','channel_id']].astype(str)
                logger.info(f"Optimal allocation found with {len(results_df)} entries.")
                logger.debug(f"Full allocation results:\n{results_df.to_string()}") 
            else: 
                logger.info("Optimal solution, but no allocation quantities > 0.1.")
        else: 
            logger.error(f"Optimization not optimal. Status: {status}. Check allocation_model.lp for details.")

    except FileNotFoundError as e: 
        logger.critical(f"Critical File Not Found Error in __main__: {e}. Aborting.")
    except ValueError as e: 
        logger.critical(f"Critical Value Error in __main__: {e}. Aborting.") 
    except Exception as e: 
        logger.critical(f"An unexpected critical error occurred in __main__: {e}", exc_info=True)
    logger.info("Solver script (__main__) finished.")
