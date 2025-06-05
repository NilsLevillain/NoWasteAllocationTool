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
    for c in channels: 
        channel_type = channels_df.loc[c, 'channel_type']
        if channel_type == 'outlet':
            for (division, axe), group_products in products_by_outlet_capacity_group.items():
                max_skus = outlet_capacity_dict.get((c, division, axe))
                if max_skus is not None and max_skus >= 0:
                    model += pulp.lpSum(y[pg, c] for pg in group_products if pg in products) <= max_skus, f"Outlet_Capacity_SKU_{c}_{division}_{axe}"
                    logger.debug(f"Added SKU capacity constraint for channel {c}, div {division}, axe {axe}: max {max_skus} SKUs.")

    logger.info("Adding coverage days and new SKU push constraints.")
    for c in channels: 
        for p in products:
            abc_class = product_channel_abc_map.get((p, c), 'C') 
            current_stock_for_pc = existing_stock_dict.get((p, c), 0)
            if abc_class == 'NEW':
                div, sub = products_df.loc[p].get('division'), products_df.loc[p].get('subaxis')
                push_qty = push_new_sku_lookup.get((div, sub), 0) if div and sub else 0
                model += x[p, c] <= push_qty, f"Push_New_SKU_{p}_{c}"
                logger.debug(f"Push new SKU constraint for P:{p} C:{c} (NEW): qty <= {push_qty}")
            else: 
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
        M_val = inventory_quantity.get(p, 0) 
        for c in channels:
            if M_val > 0:
                model += x[p, c] <= M_val * y[p, c], f"Link_x_y_Prod_{p}_Chan_{c}"
                model += y[p, c] * M_val >= x[p, c], f"Link_y_x_Prod_{p}_Chan_{c}" 
            else: 
                model += x[p, c] == 0, f"Force_x_zero_NoInv_Prod_{p}_Chan_{c}"
                model += y[p, c] == 0, f"Force_y_zero_NoInv_Prod_{p}_Chan_{c}"

    logger.info("Writing LP model to allocation_model.lp")
    model.writeLP("allocation_model.lp")
    logger.info("Solving optimization model...")
    model.solve() 
    status_string = pulp.LpStatus[model.status] 
    logger.info(f"Solver status: {status_string}")

    results = []
    if status_string == 'Optimal':
        logger.info("Optimal solution found. Extracting results.")
        results = [{'product_sku': p, 'channel_id': c, 'quantity': int(round(x[p,c].varValue))} 
                   for p in products for c in channels if x[p,c].varValue is not None and x[p,c].varValue > 0.1]
        logger.info(f"Extracted {len(results)} allocation entries.")
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
            brand_col='operational_signature_label',
            div_col='operational_division',
            axe_col='operational_axe_label',
            sub_col='operational_sub_axe_label',
            met_col='operational_metier_label'
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

        inventory_df = load_inventory_df(
            bad_stock_file,
            ean_col='ean_code',
            qty_col='StockToAllocate'
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
