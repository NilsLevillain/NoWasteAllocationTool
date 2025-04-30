import pulp
import pandas as pd
from schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule
from collections import defaultdict

def optimize_allocation(products_df: pd.DataFrame,
                        channels_df: pd.DataFrame,
                        inventory_df: pd.DataFrame,
                        demand_dict: dict, # Assumes demand_quantity is WEEKLY demand
                        parameters: OptimizationParameters):
    """
    Optimizes the allocation of inventory to different channels using Mixed Integer Programming.

    Args:
        products_df: DataFrame containing product information (indexed by SKU, columns: 'brand', 'division', 'axe', 'subaxis', 'metier', 'abc_class', etc.)
        channels_df: DataFrame containing channel information (indexed by channel ID, columns: 'capacity', 'channel_type', etc.)
        inventory_df: DataFrame containing inventory information (columns: 'product_sku', 'quantity')
        demand_dict: Dictionary of WEEKLY demand {(product_sku, channel_id): demand_quantity}
        parameters: OptimizationParameters object containing control parameters (coverage rules, capacity rules, assortment rules, etc.).

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

    # Aggregate inventory by product SKU
    inventory_quantity = inventory_df.groupby('product_sku')['quantity'].sum().to_dict()

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
    for c in channels:
        for p in products:
            abc_class = products_df.loc[p].get('abc_class')
            # Find the coverage days rule for this specific channel and product class
            coverage_days = coverage_rules_dict.get((c, abc_class))

            if coverage_days is not None and coverage_days >= 0: # Apply if rule exists
                weekly_demand_qty = demand_dict.get((p, c), 0)
                if weekly_demand_qty > 0:
                    daily_demand = weekly_demand_qty / 7.0
                    max_allowed_allocation = daily_demand * coverage_days
                    model += x[p, c] <= max_allowed_allocation, f"Max_Coverage_Days_{p}_{c}"
                else:
                    # If weekly demand is 0, max coverage implies allocation should be 0
                    model += x[p, c] <= 0, f"Max_Coverage_Days_Zero_Demand_{p}_{c}"
            # else: Handle cases where abc_class is missing or no rule exists (currently no constraint applied)


    # 4. Donation Eligibility Constraints (Brand-Level Only):
    donation_channels = channels_df[channels_df['channel_type'] == 'donation'].index.tolist()
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

    # --- Example Usage (for testing purposes) ---
if __name__ == '__main__':
    # Create sample data matching the expected DataFrame/dict structures
    # --- Sample Products ---
    sample_products_data = {
        'sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004', 'SKU005'],
        'donation_eligible': [True, False, True, True, True], # Still present but not used in constraints
        'brand': ['BrandA', 'BrandA', 'BrandB', 'BrandC', 'BrandA'], # Signature
        'division': ['LLD', 'LLD', 'CPD', 'PPD', 'LLD'],
        'axe': ['Fragrance', 'Fragrance', 'Skincare', 'Makeup', 'Fragrance'],
        'subaxis': ['Men Fragrance', 'Women Fragrance', 'Face Care', 'Lip Makeup', 'Men Fragrance'],
        'metier': ['Eau de Toilette', 'Eau de Parfum', 'Moisturizer', 'Lipstick', 'After Shave'],
        'abc_class': ['A', 'B', 'A', 'C', 'B']
    }
    sample_products = pd.DataFrame(sample_products_data).set_index('sku')

    # --- Sample Channels ---
    sample_channels_data = {
        'id': ['STORE1', 'OUTLET1', 'DONATE1', 'STORE2', 'OUTLET2'],
        'capacity': [100, 0, 50, 80, 0], # Capacity only used for non-outlets now
        # 'max_coverage' removed
        'channel_type': ['store', 'outlet', 'donation', 'store', 'outlet']
    }
    sample_channels = pd.DataFrame(sample_channels_data).set_index('id')

    # --- Sample Inventory ---
    sample_inventory_data = {
        'product_sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004', 'SKU005', 'SKU001'],
        'quantity': [50, 30, 40, 60, 25, 20] # SKU001 has 70 total
    }
    sample_inventory = pd.DataFrame(sample_inventory_data)

    # --- Sample Demand (Weekly) ---
    sample_demand = {
        ('SKU001', 'STORE1'): 14, # 2 per day
        ('SKU002', 'STORE1'): 7,  # 1 per day
        ('SKU003', 'OUTLET1'): 21, # 3 per day
        ('SKU001', 'STORE2'): 7,  # 1 per day
        ('SKU004', 'STORE2'): 14, # 2 per day
        ('SKU005', 'OUTLET1'): 7, # 1 per day
        ('SKU001', 'OUTLET2'): 28, # 4 per day
    }

    # --- Sample Parameter Rules ---
    sample_coverage_rules = [
        CoverageDaysRule(channel_id='STORE1', abc_class='A', coverage_days=14),
        CoverageDaysRule(channel_id='STORE1', abc_class='B', coverage_days=21),
        CoverageDaysRule(channel_id='OUTLET1', abc_class='A', coverage_days=28),
        CoverageDaysRule(channel_id='OUTLET1', abc_class='B', coverage_days=21),
        CoverageDaysRule(channel_id='OUTLET2', abc_class='A', coverage_days=35),
        # Add more rules as needed...
    ]
    sample_outlet_capacity = [
        OutletSKUCapacityRule(channel_id='OUTLET1', division='LLD', axe='Fragrance', max_skus=2), # Outlet1 can have max 2 LLD Fragrance SKUs
        OutletSKUCapacityRule(channel_id='OUTLET1', division='CPD', axe='Skincare', max_skus=1),
        OutletSKUCapacityRule(channel_id='OUTLET2', division='LLD', axe='Fragrance', max_skus=1),
    ]
    sample_outlet_assortment = [
        OutletAssortmentRule(metier='Eau de Toilette', subaxis='Men Fragrance', brand='BrandA', max_skus=1), # Max 1 SKU001 across all outlets
        OutletAssortmentRule(metier='Lipstick', subaxis='Lip Makeup', brand='BrandC', max_skus=1),
    ]

    # --- Test Case 1: Run with new rules ---
    print("--- Test Case 1: Basic Run with New Rules ---")
    params1 = OptimizationParameters(
        restricted_brands_for_donation=['BrandB'], # Example restriction
        coverage_days_rules=sample_coverage_rules,
        outlet_sku_capacity_rules=sample_outlet_capacity,
        outlet_assortment_rules=sample_outlet_assortment
    )
    model1, status1, results1 = optimize_allocation(sample_products, sample_channels, sample_inventory, sample_demand, params1)
    print(f"Status: {status1}")
    if status1 == 'Optimal':
        print("Allocation Results:")
        results_df = pd.DataFrame(results1)
        if not results_df.empty:
            print(results_df.to_string())
        else:
            print("No allocation.")
    # print(f"Model: {model1}") # Optional: print model summary if needed

    # Add more test cases if needed to verify specific constraints
