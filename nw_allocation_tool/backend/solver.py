import pulp
import pandas as pd
from schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule
from collections import defaultdict

# --- ABC Classification Function ---
def calculate_abc_classification_and_new_skus(
    sellout_df: pd.DataFrame, # Raw sellout data
    product_master_df: pd.DataFrame, # products_df from main scope
    all_channel_ids: list, # list of all channel IDs
    sellout_ean_col: str,
    sellout_channel_col: str,
    sellout_qty_col: str
):
    """
    Calculates ABC classification per channel based on sellout data.
    Marks products not in sellout for a channel as 'NEW'.
    Returns a dictionary: {(product_ean, channel_id): 'A'/'B'/'C'/'NEW'}
    """
    product_channel_abc_map = {}

    # Ensure correct dtypes for sellout data
    sellout_df[sellout_ean_col] = sellout_df[sellout_ean_col].astype(str)
    sellout_df[sellout_channel_col] = sellout_df[sellout_channel_col].astype(str)
    sellout_df[sellout_qty_col] = pd.to_numeric(sellout_df[sellout_qty_col], errors='coerce').fillna(0)

    # Aggregate total sales per product per channel over the period in sellout_df
    channel_product_sales = sellout_df.groupby([sellout_channel_col, sellout_ean_col])[sellout_qty_col].sum().reset_index()

    for channel_id in all_channel_ids:
        channel_sales = channel_product_sales[channel_product_sales[sellout_channel_col] == channel_id].copy()

        if channel_sales.empty:
            # If a channel has no sales data at all, all products are 'NEW' for this channel
            for product_ean in product_master_df.index:
                product_channel_abc_map[(product_ean, channel_id)] = 'NEW'
            continue

        channel_sales = channel_sales.sort_values(by=sellout_qty_col, ascending=False)
        channel_sales['cumulative_sales'] = channel_sales[sellout_qty_col].cumsum()
        total_channel_sales = channel_sales[sellout_qty_col].sum()

        if total_channel_sales == 0: # Handle channels with products listed but zero sales for all
            for product_ean in product_master_df.index:
                if product_ean in channel_sales[sellout_ean_col].values:
                     product_channel_abc_map[(product_ean, channel_id)] = 'C' # Has entry but 0 sales
                else:
                     product_channel_abc_map[(product_ean, channel_id)] = 'NEW'
            continue
            
        channel_sales['cumulative_percent'] = channel_sales['cumulative_sales'] / total_channel_sales

        for _, row in channel_sales.iterrows():
            ean = row[sellout_ean_col]
            cum_percent = row['cumulative_percent']
            if cum_percent <= 0.2:
                product_channel_abc_map[(ean, channel_id)] = 'A'
            elif cum_percent <= 0.8:
                product_channel_abc_map[(ean, channel_id)] = 'B'
            else:
                product_channel_abc_map[(ean, channel_id)] = 'C'

        # Mark products in master but not in this channel's sales as 'NEW' for this channel
        sold_eans_in_channel = set(channel_sales[sellout_ean_col])
        for product_ean in product_master_df.index:
            if product_ean not in sold_eans_in_channel:
                product_channel_abc_map[(product_ean, channel_id)] = 'NEW'
                
    return product_channel_abc_map


def optimize_allocation(products_df: pd.DataFrame,
                        channels_df: pd.DataFrame,
                        inventory_df: pd.DataFrame, # This is the "bad stock" to be allocated
                        demand_dict: dict, # Assumes demand_quantity is WEEKLY demand
                        parameters: OptimizationParameters,
                        existing_stock_dict: dict, # New: {(ean, channel_id): quantity} for in-store & in-transit
                        product_channel_abc_map: dict): # New: {(ean, channel_id): 'A'/'B'/'C'/'NEW'}
    """
    Optimizes the allocation of inventory to different channels using Mixed Integer Programming.

    Args:
        products_df: DataFrame containing product information (indexed by EAN/SKU, columns: 'brand', 'division', 'axe', 'subaxis', 'metier', 'abc_class', etc.)
        channels_df: DataFrame containing channel information (indexed by channel ID string, columns: 'capacity', 'channel_type', etc.)
        inventory_df: DataFrame containing inventory information (columns: 'product_ean', 'quantity') for stock to be allocated.
        demand_dict: Dictionary of WEEKLY demand {(product_ean, channel_id): demand_quantity}
        parameters: OptimizationParameters object containing control parameters.
        existing_stock_dict: Dictionary {(product_ean, channel_id): quantity} representing current in-store and in-transit stock.

    Returns:
        Tuple: (model, status, list_of_allocation_decisions)
               model: The PuLP model object.
               status: PuLP solver status string.
               list_of_allocation_decisions: List of dictionaries representing allocations.
    """

    # --- Data Preparation ---
    # --- Data Preparation & Parameter Processing ---
    products_df.index = products_df.index.astype(str)
    channels_df.index = channels_df.index.astype(str)

    products = products_df.index.tolist() # List of SKUs
    channels = channels_df.index.tolist() # List of Channel IDs

    # Aggregate inventory by product EAN
    inventory_quantity = inventory_df.groupby('product_ean')['quantity'].sum().to_dict() # Use 'product_ean'

    # Process parameter rules into efficient lookup dictionaries
    coverage_rules_dict = {(rule.channel_id, rule.abc_class): rule.coverage_days for rule in parameters.coverage_days_rules}
    outlet_capacity_dict = {(rule.channel_id, rule.division, rule.axe): rule.max_skus for rule in parameters.outlet_sku_capacity_rules}
    # Assuming assortment rules apply across all outlets unless channel_id is added to OutletAssortmentRule schema
    outlet_assortment_dict = {(rule.metier, rule.subaxis, rule.brand): rule.max_skus for rule in parameters.outlet_assortment_rules}

    # Pre-group products by attributes needed for constraints
    products_by_outlet_capacity_group = defaultdict(list)
    products_by_outlet_assortment_group = defaultdict(list)
    outlet_channels = channels_df[channels_df['channel_type'] == 'outlet'].index.tolist()

    for p in products:
        # Ensure product attributes exist, handle missing values if necessary (e.g., assign to a default group or skip)
        division = products_df.loc[p].get('division')
        axe = products_df.loc[p].get('axe')
        metier = products_df.loc[p].get('metier')
        subaxis = products_df.loc[p].get('subaxis')
        brand = products_df.loc[p].get('brand')

        if division and axe:
            products_by_outlet_capacity_group[(division, axe)].append(p)
        if metier and subaxis and brand:
            products_by_outlet_assortment_group[(metier, subaxis, brand)].append(p)


    # --- Model Definition ---
    model = pulp.LpProblem("InventoryAllocation", pulp.LpMaximize)

    # --- Decision Variables ---

    # x[p, c]: Quantity of product p allocated to channel c
    x = pulp.LpVariable.dicts("allocation_qty",
                             ((p, c) for p in products for c in channels),
                             lowBound=0,
                             cat='Integer')

    # y[p, c]: Binary variable, 1 if product p is allocated to channel c, 0 otherwise
    # Needed for constraints like minimum SKUs per store.
    y = pulp.LpVariable.dicts("is_allocated",
                             ((p, c) for p in products for c in channels),
                              cat='Binary')


# Pour NEW SKU rajouter une table division / sous-axe  où on n'a pas de sell-out pas de couverture mais on veut ...
# ... pousser une quantité maximum

    # --- Objective Function ---
    # Objective: Maximize total allocated quantity (Sell-Through)
    total_quantity = pulp.lpSum(x[p, c] for p in products for c in channels)

    model += (total_quantity, "Maximize_Total_Allocation")

# Dans la fonction objectif maximiser la quantité bien sûr mais aussi la notation produit (notation SO/SI) ...
# ... pour inclure les new SKUs dans le jeu et retirer les anciens
# Et rajouter pénalités par channel, 0 pénalité sur outlet, 10 sur f&f, puis 30 donation, ...
# bien harmoniser les ordres de grandeur entre notation, pénalités ou bonus par channel et quantités pour ...
# ... allouer les bonnes quantités des bons produits dans les bons channels
# Avoir deux notations : 1 de sell-out et 1 de sell-in => mais à tester pour avoir les nouveaux SKUs qui soient alloués
# ... en sell-out


    # --- Constraints ---

    # 1. Supply Constraints: Cannot allocate more than available inventory for each product.
    for p in products:
        model += pulp.lpSum(x[p, c] for c in channels) <= inventory_quantity.get(p, 0), f"Supply_Product_{p}"

    # 2. Channel Capacity Constraints: Different logic for outlets vs other channels.
    for c in channels:
        channel_type = channels_df.loc[c, 'channel_type']

        if channel_type == 'outlet':
            # Outlet Capacity: Max SKUs per (Division, Axe)
            for (division, axe), group_products in products_by_outlet_capacity_group.items():
                # Find the max SKU rule for this specific outlet, division, axe
                max_skus = outlet_capacity_dict.get((c, division, axe)) # Lookup using channel ID
                if max_skus is not None and max_skus >= 0: # Apply if rule exists
                    model += pulp.lpSum(y[p, c] for p in group_products) <= max_skus, f"Outlet_Capacity_SKU_{c}_{division}_{axe}"
            # Note: If a product's division/axe doesn't match any rule for this outlet, it's not constrained by *this* rule.
            # Consider adding a default capacity rule or handling products not matching any rule.

        else:
            # Non-Outlet Capacity: Max total quantity
            capacity = pd.to_numeric(channels_df.loc[c, 'capacity'], errors='coerce')
            if pd.notna(capacity) and capacity >= 0:
                 model += pulp.lpSum(x[p, c] for p in products) <= capacity, f"Capacity_Channel_{c}"
            # else: handle cases where capacity might be missing or invalid if needed


    # 3. Maximum Coverage (in Days) Constraints: Allocation <= Daily_Demand * Coverage_Days
    #    Also handles PushNewSKU logic implicitly if abc_class is 'NEW' and a rule exists for it.
    push_new_sku_lookup = {(rule.division, rule.subaxis): rule.push_quantity for rule in parameters.push_new_sku_rules}

    for c in channels:
        for p in products:
            # Get dynamically calculated ABC class for this product-channel pair
            abc_class = product_channel_abc_map.get((p, c), 'C') # Default to 'C' if not found

            # Apply seasonality to weekly demand
            base_weekly_demand_qty = demand_dict.get((p, c), 0)
            adjusted_weekly_demand_qty = base_weekly_demand_qty * parameters.seasonality_coefficient
            
            current_stock_for_pc = existing_stock_dict.get((p,c), 0)

            if abc_class == 'NEW':
                product_division = products_df.loc[p].get('division')
                product_subaxis = products_df.loc[p].get('subaxis')
                push_quantity = 0
                if product_division and product_subaxis:
                    push_quantity = push_new_sku_lookup.get((product_division, product_subaxis), 0)
                
                # For NEW SKUs, the allocation should be at least the push quantity,
                # respecting supply. Coverage days constraint might not apply or be very high.
                # Here, we set x[p,c] to be at most the push_quantity if it's a NEW SKU.
                # If demand also exists (e.g. from a forecast for new items), this logic might need refinement.
                # For now, if NEW, it's driven by push quantity, not coverage of demand.
                # This also means if push_quantity is 0, allocation is 0.
                # The allocation x[p,c] is also limited by supply (Constraint 1)
                # and channel capacity (Constraint 2)
                model += x[p, c] <= push_quantity, f"Push_New_SKU_{p}_{c}"
                # We might also want a minimum push: model += x[p,c] >= push_quantity if supply allows.
                # For now, let's assume x[p,c] is simply capped by push_quantity for NEW.
                # If push_quantity is 0 for a NEW SKU (no rule), it can't be allocated via this logic.
            else:
                # Existing logic for A, B, C classes based on coverage days
                coverage_days = coverage_rules_dict.get((c, abc_class))
                if coverage_days is not None and coverage_days >= 0: # Apply if rule exists
                    if adjusted_weekly_demand_qty > 0:
                        daily_demand = adjusted_weekly_demand_qty / 7.0
                        max_total_stock_allowed = daily_demand * coverage_days
                        allowable_new_allocation = max(0, max_total_stock_allowed - current_stock_for_pc)
                        model += x[p, c] <= allowable_new_allocation, f"Max_Coverage_Days_{p}_{c}"
                    else:
                        # If adjusted weekly demand is 0, new allocation must be 0 for A,B,C.
                        model += x[p, c] <= 0, f"Max_Coverage_Days_Zero_Demand_{p}_{c}"
                # else: No coverage rule for this ABC/channel combo, no coverage constraint applied.

    # 4. Donation Eligibility Constraints (Brand-Level Only):
    # Correctly filter based on the 'channel_type' column before accessing the index
    donation_channels = channels_df.loc[channels_df['channel_type'] == 'donation'].index.tolist()
    if parameters.restricted_brands_for_donation and donation_channels:
        restricted_brands = set(parameters.restricted_brands_for_donation) # These are 'brand'/'signature' names
        for p in products:
            product_brand = products_df.loc[p].get('brand')
            if product_brand in restricted_brands:
                 for c in donation_channels:
                    model += x[p, c] == 0, f"Restricted_Brand_{product_brand}_Prod_{p}_Chan_{c}"

#si pb de data quality : pas de marque pour un EAN => ne pas l'allouer et l'utilisateur le fera à la main
#élargir à sub brand - axis (voir clearance norm : ex Armani Privé pas en outlet ou Armani Skincare)


    # 5. Outlet Assortment Constraint: Max SKUs per (Metier, Subaxis, Brand/Signature) across all outlets.
    #    (Assumes rules in outlet_assortment_rules apply globally to the outlet channel type,
    #     modify if rules need to be per specific outlet channel ID).
    for c in outlet_channels: # Apply constraint per outlet
        for (metier, subaxis, brand), group_products in products_by_outlet_assortment_group.items():
            # Find the max SKU rule for this specific metier, subaxis, brand
            max_skus = outlet_assortment_dict.get((metier, subaxis, brand))
            if max_skus is not None and max_skus >= 0: # Apply if rule exists
                model += pulp.lpSum(y[p, c] for p in group_products) <= max_skus, f"Outlet_Assortment_{c}_{metier}_{subaxis}_{brand}"
        # Note: If a product's attributes don't match any rule, it's not constrained by *this* rule.


    # 6. Linking Constraints (x and y): If any quantity of product p is allocated to channel c (x > 0), then y must be 1.
    #    Use a 'Big M' approach. M should be larger than any possible value of x[p, c].
    #    Using individual product inventory quantity as M is a safe upper bound.
    for p in products:
        M = inventory_quantity.get(p, 0) # Max quantity of product p
        if M > 0: # Only add constraint if there's inventory
            for c in channels:
                model += x[p, c] <= M * y[p, c], f"Link_x_y_Prod_{p}_Chan_{c}"
        else: # If no inventory, ensure y is also 0
             for c in channels:
                 model += y[p, c] == 0, f"Force_y_zero_Prod_{p}_Chan_{c}"


    # --- Solve the Model ---
    # Write the model formulation to an .lp file for inspection/debugging
    model.writeLP("allocation_model.lp")
    # You might want to specify a solver, e.g., model.solve(pulp.PULP_CBC_CMD(msg=0))
    solver_status = model.solve()
    status_string = pulp.LpStatus[solver_status]

    # --- Extract Results ---
    allocation_results = []
    if status_string == 'Optimal':
        for p in products:
            for c in channels:
                allocated_qty = x[p, c].value()
                if allocated_qty is not None and allocated_qty > 0.1: # Use tolerance for float comparison
                    allocation_results.append({
                        'product_sku': p,
                        'channel_id': c,
                        'quantity': int(round(allocated_qty)) # Round and convert to int
                        # 'revenue': revenue_dict.get((p, c), 0) * allocated_qty # Removed revenue calculation
                    })

    # Return the model object along with status and results
    return model, status_string, allocation_results

# --- Helper Functions for Data Loading ---

def load_product_data(file_path, ean_col='EAN', brand_col='Brand', division_col='Division',
                      axe_col='Axe', subaxis_col='SubAxis', metier_col='Metier', abc_class_col=None): # abc_class_col is now optional
    """Loads product data from a CSV file."""
    df = pd.read_csv(file_path)
    # Rename columns to match expected names in products_df for the solver
    rename_map = {
        ean_col: 'ean', # This will be the index
        brand_col: 'brand',
        division_col: 'division',
        axe_col: 'axe',
        subaxis_col: 'subaxis',
        metier_col: 'metier',
    }
    # Add abc_class to rename_map only if abc_class_col is provided and exists
    if abc_class_col and abc_class_col in df.columns:
        rename_map[abc_class_col] = 'abc_class'
    
    # Keep only columns that exist in the CSV and are in our rename_map keys
    columns_to_select = [k for k in rename_map.keys() if k in df.columns]
    if not columns_to_select:
        raise ValueError(f"None of the specified product attribute columns found in {file_path}")

    products_df = df[columns_to_select].rename(columns=rename_map)

    if 'ean' not in products_df.columns: # Check for 'ean' after renaming
        raise ValueError(f"EAN column '{ean_col}' (expected to be renamed to 'ean') not found in product data from {file_path}.")
    products_df = products_df.set_index('ean')
    products_df.index = products_df.index.astype(str)
    return products_df

def load_channel_data(file_path, sheet_name='Channels', id_col='ChannelID', type_col='ChannelType', capacity_col='Capacity'):
    """Loads channel data from an Excel file sheet."""
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    rename_map = {
        id_col: 'id', # This will be the index
        type_col: 'channel_type',
        capacity_col: 'capacity'
    }
    actual_rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    channels_df = df[[k for k in actual_rename_map.keys()]].rename(columns=actual_rename_map)

    if 'id' not in channels_df.columns:
        raise ValueError(f"Channel ID column '{id_col}' not found or not mapped to 'id' in channel data.")
    channels_df = channels_df.set_index('id')
    channels_df.index = channels_df.index.astype(str)
    # Ensure capacity is numeric, fillna for outlets if capacity is not applicable or 0
    if 'capacity' in channels_df.columns:
        channels_df['capacity'] = pd.to_numeric(channels_df['capacity'], errors='coerce').fillna(0)
    else: # if capacity column is missing, create it with 0
        channels_df['capacity'] = 0

    if 'channel_type' not in channels_df.columns:
         raise ValueError(f"Channel Type column '{type_col}' not found or not mapped to 'channel_type' in channel data.")
    return channels_df

def load_inventory_data(file_path, ean_col='ean_code', qty_col='StockToAllocate'):
    """Loads inventory data (bad stock to allocate) from a CSV file."""
    df = pd.read_csv(file_path)
    if ean_col not in df.columns or qty_col not in df.columns:
        raise ValueError(f"Required columns ('{ean_col}', '{qty_col}') not found in inventory file {file_path}")
    inventory_df = df[[ean_col, qty_col]].rename(columns={ean_col: 'product_ean', qty_col: 'quantity'})
    inventory_df['product_ean'] = inventory_df['product_ean'].astype(str)
    inventory_df['quantity'] = pd.to_numeric(inventory_df['quantity'], errors='coerce').fillna(0)
    # Sum quantities for the same EAN, as bad_stock_inventory might have multiple lines per EAN (e.g. different plants)
    inventory_df = inventory_df.groupby('product_ean', as_index=False)['quantity'].sum()
    return inventory_df

def load_existing_stock_data(instore_file_path, intransit_file_path,
                             instore_ean_col='barcode', instore_channel_col='store_code', instore_qty_col='physical_quantity',
                             intransit_ean_col='ean_material_code', intransit_channel_col='store_code', intransit_qty_col='order_quantity'):
    """Loads and combines in-store and in-transit inventory into a dictionary {(ean, channel_id): quantity}."""
    existing_stock = defaultdict(float)

    # Load in-store inventory
    df_instore = pd.read_csv(instore_file_path)
    if not all(col in df_instore.columns for col in [instore_ean_col, instore_channel_col, instore_qty_col]):
        raise ValueError(f"Required columns not found in in-store inventory file {instore_file_path}")
    df_instore = df_instore[[instore_ean_col, instore_channel_col, instore_qty_col]].rename(columns={
        instore_ean_col: 'ean', instore_channel_col: 'channel_id', instore_qty_col: 'quantity'
    })
    df_instore['ean'] = df_instore['ean'].astype(str)
    df_instore['channel_id'] = df_instore['channel_id'].astype(str)
    df_instore['quantity'] = pd.to_numeric(df_instore['quantity'], errors='coerce').fillna(0)
    for _, row in df_instore.iterrows():
        existing_stock[(row['ean'], row['channel_id'])] += row['quantity']

    # Load in-transit inventory
    df_intransit = pd.read_csv(intransit_file_path)
    if not all(col in df_intransit.columns for col in [intransit_ean_col, intransit_channel_col, intransit_qty_col]):
        raise ValueError(f"Required columns not found in in-transit inventory file {intransit_file_path}")
    df_intransit = df_intransit[[intransit_ean_col, intransit_channel_col, intransit_qty_col]].rename(columns={
        intransit_ean_col: 'ean', intransit_channel_col: 'channel_id', intransit_qty_col: 'quantity'
    })
    df_intransit['ean'] = df_intransit['ean'].astype(str)
    df_intransit['channel_id'] = df_intransit['channel_id'].astype(str)
    df_intransit['quantity'] = pd.to_numeric(df_intransit['quantity'], errors='coerce').fillna(0)
    for _, row in df_intransit.iterrows():
        existing_stock[(row['ean'], row['channel_id'])] += row['quantity']

    return dict(existing_stock)

def load_demand_data(file_path, ean_col='EAN', channel_col='ChannelID', demand_col='WeeklySalesQty'):
    """Loads demand data from a CSV file into a dictionary {(ean, channel_id): quantity}."""
    df = pd.read_csv(file_path)
    if not all(col in df.columns for col in [ean_col, channel_col, demand_col]):
        raise ValueError(f"Required columns not found in demand file {file_path}")
    
    demand_dict = {}
    df[ean_col] = df[ean_col].astype(str)
    df[channel_col] = df[channel_col].astype(str)
    df[demand_col] = pd.to_numeric(df[demand_col], errors='coerce').fillna(0)

    # Group by EAN and ChannelID, summing demand if there are duplicates
    grouped_demand = df.groupby([ean_col, channel_col])[demand_col].sum().reset_index()

    for _, row in grouped_demand.iterrows():
        demand_dict[(row[ean_col], row[channel_col])] = row[demand_col]
    return demand_dict

# Functions to load parameter rules from Excel
def load_coverage_rules_from_excel(file_path, sheet_name='Sheet1',
                                   channel_col='Channel', abc_col='ABC Class', coverage_col='Coverage (in days)'):
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"')) # Ensure string, strip whitespace and quotes
    rules = []

    # Use the sanitized column names for checking and access
    s_channel_col = channel_col.strip().strip('"')
    s_abc_col = abc_col.strip().strip('"')
    s_coverage_col = coverage_col.strip().strip('"')

    if not all(col in df.columns for col in [s_channel_col, s_abc_col, s_coverage_col]):
        raise ValueError(f"Required columns for coverage rules ('{s_channel_col}', '{s_abc_col}', '{s_coverage_col}') not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")
    for _, row in df.iterrows():
        rules.append(CoverageDaysRule(
            channel_id=str(row[s_channel_col]),
            abc_class=str(row[s_abc_col]),
            coverage_days=int(row[s_coverage_col])
        ))
    return rules

def load_outlet_sku_capacity_rules_from_excel(file_path, sheet_name='Sheet1',
                                              channel_col='Channel', div_axe_col='operational_division_operational_axe_label',
                                              max_skus_col='Max capacity (in # of SKU)', delimiter=';'):
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError: # Sheet might not exist
        print(f"Warning: Sheet '{sheet_name}' not found in '{file_path}'. No outlet SKU capacity rules loaded from this sheet.")
        return []
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))

    s_channel_col = channel_col.strip().strip('"')
    s_div_axe_col = div_axe_col.strip().strip('"')
    s_max_skus_col = max_skus_col.strip().strip('"')

    if not all(col in df.columns for col in [s_channel_col, s_div_axe_col, s_max_skus_col]):
        print(f"Warning: Required columns for outlet SKU capacity rules ('{s_channel_col}', '{s_div_axe_col}', '{s_max_skus_col}') not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}. Skipping these rules.")
        return []
        
    rules = []
    for _, row in df.iterrows():
        try:
            div_axe_combined = str(row[s_div_axe_col])
            div_axe_split = div_axe_combined.split(delimiter)
            if len(div_axe_split) == 2:
                division, axe = div_axe_split[0].strip(), div_axe_split[1].strip()
                rules.append(OutletSKUCapacityRule(
                    channel_id=str(row[s_channel_col]),
                    division=division,
                    axe=axe,
                    max_skus=int(row[s_max_skus_col])
                ))
            else:
                print(f"Warning: Could not split '{div_axe_combined}' from column '{s_div_axe_col}' into division and axe for row: {row}. Expected 2 parts, got {len(div_axe_split)}. Skipping.")
        except Exception as e:
            print(f"Error processing row in outlet SKU capacity: {row}. Error: {e}. Skipping.")
    return rules

def load_outlet_assortment_rules_from_excel(file_path, sheet_name='Sheet1',
                                            metier_col='operational_metier_label', subaxis_col='operational_sub_axe_label',
                                            brand_col='operational_signature_label', max_skus_col='# of SKUs to have in outlet (assortment)'):
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))
    rules = []

    s_metier_col = metier_col.strip().strip('"')
    s_subaxis_col = subaxis_col.strip().strip('"')
    s_brand_col = brand_col.strip().strip('"')
    s_max_skus_col = max_skus_col.strip().strip('"')
    
    if not all(col in df.columns for col in [s_metier_col, s_subaxis_col, s_brand_col, s_max_skus_col]):
        raise ValueError(f"Required columns for outlet assortment rules ('{s_metier_col}', '{s_subaxis_col}', '{s_brand_col}', '{s_max_skus_col}') not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")
        
    for _, row in df.iterrows():
        rules.append(OutletAssortmentRule(
            metier=str(row[s_metier_col]),
            subaxis=str(row[s_subaxis_col]),
            brand=str(row[s_brand_col]),
            max_skus=int(row[s_max_skus_col])
        ))
    return rules

def load_push_new_sku_rules_from_excel(file_path, sheet_name='Sheet1',
                                       division_col='operational_divison', # Typo "divison" as per user's feedback
                                       subaxis_col='operational_sub_axe_label',
                                       push_qty_col='Push Quantity if New SKU'):
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))
    rules = []

    s_division_col = division_col.strip().strip('"')
    s_subaxis_col = subaxis_col.strip().strip('"')
    s_push_qty_col = push_qty_col.strip().strip('"')

    if not all(col in df.columns for col in [s_division_col, s_subaxis_col, s_push_qty_col]):
        raise ValueError(f"Required columns for push new SKU rules ('{s_division_col}', '{s_subaxis_col}', '{s_push_qty_col}') not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")

    for _, row in df.iterrows():
        rules.append(PushNewSKURule(
            division=str(row[s_division_col]),
            subaxis=str(row[s_subaxis_col]),
            push_quantity=int(row[s_push_qty_col])
        ))
    return rules


    # --- Example Usage (for testing purposes) ---
if __name__ == '__main__':
    # Define file paths (relative to project root)
    # Assuming CWD is the project root 'nw_allocation_tool'
    data_path = 'data'
    product_master_file = f'{data_path}/InputData/masterdata.csv'
    bad_stock_file = f'{data_path}/InputData/bad_stock_inventory.csv'
    in_store_inventory_file = f'{data_path}/InputData/in_store_inventory.csv'
    stock_in_transit_file = f'{data_path}/InputData/stock_in_transit.csv'
    sellout_file = f'{data_path}/InputData/sellout.csv'

    # Parameters files
    excel_params_path = f'{data_path}/ExcelParameters'
    capacity_channel_file = f'{excel_params_path}/CapacityPerChannel.xlsx'
    coverage_rules_file = f'{excel_params_path}/CoverageperABCperChannel.xlsx'
    assortment_rules_file = f'{excel_params_path}/AssortmentperSubaxeperSignature.xlsx'
    push_new_sku_file = f'{excel_params_path}/PushNewSKU.xlsx'

    try:
        # --- Load Data ---
        print("Loading product data...")
        # Using column names provided by the user
        products_df = load_product_data(
            product_master_file,
            ean_col='product_gtin',
            brand_col='operational_signature_label',
            division_col='operational_division',
            axe_col='operational_axe_label',
            subaxis_col='operational_sub_axe_label',
            metier_col='operational_metier_label',
            abc_class_col=None # Explicitly None if not in masterdata.csv, or provide column name if it is
        )
        print(f"Loaded {len(products_df)} products.")

        print("Loading channel data...")
        # Assuming 'Channels' sheet for master, 'OutletSKUCapacity' for specific rules in CapacityPerChannel.xlsx
        # User did not provide column names for this, keeping previous assumptions for general channel master.
        # Specific rules from this file (OutletSKUCapacity) are handled below with user-provided names.
        channels_df = load_channel_data(capacity_channel_file, sheet_name='Channels', # Assuming a 'Channels' sheet for master list
                                        id_col='ChannelID', type_col='ChannelType', capacity_col='CapacityQty') 
        print(f"Loaded {len(channels_df)} channels from '{capacity_channel_file}' sheet 'Channels'.")

        print("Loading bad stock inventory...")
        inventory_df = load_inventory_data(bad_stock_file, ean_col='ean_code', qty_col='StockToAllocate')
        print(f"Loaded {inventory_df['quantity'].sum()} units of bad stock for {len(inventory_df)} EANs.")

        print("Loading existing in-store and in-transit stock...")
        existing_stock_dict = load_existing_stock_data(
            in_store_inventory_file, stock_in_transit_file,
            instore_ean_col='barcode', instore_channel_col='store_code', instore_qty_col='physical_quantity',
            intransit_ean_col='ean_material_code', intransit_channel_col='store_code', intransit_qty_col='order_quantity'
        )
        print(f"Loaded existing stock for {len(existing_stock_dict)} product-channel combinations.")

        print("Loading demand data...")
        demand_dict = load_demand_data(
            sellout_file,
            ean_col='barcode', # As per user: sellout.csv uses 'barcode' for EAN
            channel_col='store_code',
            demand_col='total_items_weekly'
        )
        print(f"Loaded demand for {len(demand_dict)} product-channel combinations.")

        # --- Load Parameter Rules ---
        print("Loading parameter rules...")
        # Using column names provided by the user for Excel parameter files
        coverage_rules = load_coverage_rules_from_excel(
            coverage_rules_file, sheet_name='Sheet1', 
            channel_col='Channel', abc_col='ABC Class', coverage_col='Coverage (in days)'
        )
        print(f"Loaded {len(coverage_rules)} coverage rules.")
        
        outlet_sku_capacity_rules = load_outlet_sku_capacity_rules_from_excel(
            capacity_channel_file, sheet_name='Sheet1', # Assuming rules are in 'Sheet1'
            channel_col='Channel', div_axe_col='operational_division_operational_axe_label',
            max_skus_col='Max capacity (in # of SKU)'
        )
        print(f"Loaded {len(outlet_sku_capacity_rules)} outlet SKU capacity rules.")
        
        assortment_rules = load_outlet_assortment_rules_from_excel(
            assortment_rules_file, sheet_name='Sheet1', 
            metier_col='operational_metier_label', subaxis_col='operational_sub_axe_label',
            brand_col='operational_signature_label', max_skus_col='# of SKUs to have in outlet (assortment)'
        )
        print(f"Loaded {len(assortment_rules)} outlet assortment rules.")

        push_new_sku_rules = load_push_new_sku_rules_from_excel(
            push_new_sku_file, sheet_name='Sheet1', 
            division_col='operational_divison', 
            subaxis_col='operational_sub_axe_label',
            push_qty_col='Push Quantity if New SKU'
        )
        print(f"Loaded {len(push_new_sku_rules)} push new SKU rules.")

        # Calculate ABC Classification
        print("Calculating ABC classification...")
        # Load raw sellout data for ABC calculation
        raw_sellout_df = pd.read_csv(sellout_file) 
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            raw_sellout_df,
            products_df, # Already loaded product master
            channels_df.index.tolist(), # All channel IDs
            sellout_ean_col='barcode', 
            sellout_channel_col='store_code', 
            sellout_qty_col='total_items_weekly'
        )
        print(f"Calculated ABC & NEW status for {len(product_channel_abc_map)} product-channel pairs.")
        # For inspection, you might want to add a step here to merge this ABC class back to products_df
        # or print some of the classifications.

        # Restricted brands for donation (example, replace with actual loading if available from a file or UI)
        restricted_brands_for_donation = [] 

        # Seasonality coefficient - get from user input for testing
        try:
            seasonality_input = input("Enter seasonality coefficient (e.g., 1.0 for no change, 1.2 for +20%): ")
            seasonality_coefficient = float(seasonality_input)
            if seasonality_coefficient < 0:
                print("Seasonality coefficient cannot be negative. Using 1.0.")
                seasonality_coefficient = 1.0
        except ValueError:
            print("Invalid input for seasonality. Using 1.0.")
            seasonality_coefficient = 1.0
        print(f"Using seasonality coefficient: {seasonality_coefficient}")


        params = OptimizationParameters(
            seasonality_coefficient=seasonality_coefficient, # Now included
            restricted_brands_for_donation=restricted_brands_for_donation, # Example
            coverage_days_rules=coverage_rules,
            outlet_sku_capacity_rules=outlet_sku_capacity_rules,
            outlet_assortment_rules=assortment_rules,
            push_new_sku_rules=push_new_sku_rules
        )
        print("Parameters loaded and OptimizationParameters model instantiated.")

        # --- Run Optimization ---
        print("\n--- Running Optimization with Loaded Data ---")
        model, status, results = optimize_allocation(
            products_df,
            channels_df,
            inventory_df, 
            demand_dict,
            params, # Contains seasonality_coefficient and push_new_sku_rules
            existing_stock_dict,
            product_channel_abc_map # Pass the new map
        )
        
        print(f"\nSolver Status: {status}")
        if status == 'Optimal':
            print("Allocation Results:")
            results_df = pd.DataFrame(results)
            if not results_df.empty:
                # To ensure product_sku is string for display if it's not already
                if 'product_sku' in results_df.columns:
                    results_df['product_sku'] = results_df['product_sku'].astype(str)
                if 'channel_id' in results_df.columns:
                    results_df['channel_id'] = results_df['channel_id'].astype(str)
                print(results_df.to_string())
            else:
                print("No allocation.")
        else:
            print("Optimization was not optimal. Check logs and model formulation (allocation_model.lp).")
            print("Consider reviewing constraints and data, especially if 'infeasible' or 'unbounded'.")

    except FileNotFoundError as e:
        print(f"Error: File not found. {e}")
    except ValueError as e:
        print(f"Error: Data loading or validation issue. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
