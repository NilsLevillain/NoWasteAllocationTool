import pulp
import pandas as pd
from datetime import datetime, timedelta

def optimize_allocation(products_df, channels_df, inventory_df, demand, revenue):
    """
    Optimizes the allocation of inventory to different channels using Mixed Integer Programming.
    
    Args:
        products_df: DataFrame containing product information
        channels_df: DataFrame containing channel information
        inventory_df: DataFrame containing inventory information
        demand: Dictionary of demand by product and channel
        revenue: Dictionary of revenue by product and channel
    
    Returns:
        List of allocation decisions
    """
    
    # Create the model
    model = pulp.LpProblem("InventoryAllocation", pulp.LpMaximize)
    
    # Create decision variables
    products = products_df.index.tolist()
    channels = channels_df.index.tolist()
    
    x = pulp.LpVariable.dicts("allocation",
                             ((p, c) for p in products for c in channels),
                             lowBound=0,
                             cat='Integer')
    
    # Objective function: Maximize revenue
    model += pulp.lpSum(x[p, c] * revenue.get((p, c), 0)
                       for p in products for c in channels)
    
    # Constraints
    
    # 1. Supply constraints
    for p in products:
        model += pulp.lpSum(x[p, c] for c in channels) <= inventory_df.loc[
            inventory_df['product_id'] == p, 'quantity'
        ].iloc[0]
    
    # 2. Channel capacity constraints
    for c in channels:
        model += pulp.lpSum(x[p, c] for p in products) <= channels_df.loc[c, 'capacity']
    
    # 3. Minimum coverage constraints
    for c in channels:
        for p in products:
            if demand.get((p, c), 0) > 0:
                model += x[p, c] >= channels_df.loc[c, 'min_coverage'] * demand.get((p, c), 0)
    
    # 4. Donation eligibility constraints
    for p in products:
        if not products_df.loc[p, 'donation_eligible']:
            for c in channels:
                if channels_df.loc[c, 'channel_type'] == 'donation':
                    model += x[p, c] == 0
    
    # Solve the model
    model.solve()
    
    # Extract results
    allocation_results = []
    for p in products:
        for c in channels:
            if x[p, c].value() > 0:
                allocation_results.append({
                    'product_id': p,
                    'channel_id': c,
                    'quantity': int(x[p, c].value()),
                    'revenue': revenue.get((p, c), 0) * x[p, c].value()
                })
    
    return allocation_results
