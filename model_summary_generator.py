import pandas as pd
from pulp import *
# Import the function and necessary schema/classes
from allocation_service import optimize_allocation
from schemas import OptimizationParameters

# --- Create Sample Data to Build the Model ---
# (You can reuse the sample data from allocation_service.py or define specific data here)
sample_products = pd.DataFrame({
    'sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004'],
    'donation_eligible': [True, False, True, True],
    'brand': ['BrandA', 'BrandA', 'BrandB', 'BrandC']
}).set_index('sku')

sample_channels = pd.DataFrame({
    'id': ['STORE1', 'OUTLET1', 'DONATE1', 'STORE2'],
    'capacity': [100, 200, 50, 80],
    'min_coverage': [0.5, 0.0, 0.0, 0.6],
    'channel_type': ['store', 'outlet', 'donation', 'store']
}).set_index('id')

sample_inventory = pd.DataFrame({
    'product_sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004', 'SKU001'],
    'quantity': [50, 30, 40, 60, 20] # SKU001 has 70 total
})

sample_demand = {
    ('SKU001', 'STORE1'): 40, ('SKU002', 'STORE1'): 20,
    ('SKU003', 'OUTLET1'): 50,
    ('SKU001', 'STORE2'): 30, ('SKU004', 'STORE2'): 50,
}

sample_revenue = {
    ('SKU001', 'STORE1'): 10, ('SKU002', 'STORE1'): 12,
    ('SKU003', 'OUTLET1'): 5,
    ('SKU001', 'DONATE1'): 0, ('SKU003', 'DONATE1'): 0, ('SKU004', 'DONATE1'): 0,
    ('SKU001', 'STORE2'): 11, ('SKU004', 'STORE2'): 9,
}

# Use default parameters for generating the model structure
params = OptimizationParameters(
    default_min_coverage=None,
    min_skus_per_store=None,
    restricted_brands_for_donation=None
)

# --- Call the function to get the model object ---
# The function now returns (model, status, results)
try:
    model, status, results = optimize_allocation(
        sample_products, sample_channels, sample_inventory,
        sample_demand, sample_revenue, params
    )

    # --- Generate Markdown Summary ---
    with open("model_summary.md", "w") as f:
        f.write("# Model Summary\n\n")
        f.write(f"Generated for model: {model.name}\n")
        f.write(f"Status after solve (using sample data): {status}\n\n")

        if model.objective:
            f.write("## Objective Function\n\n")
            f.write(f"{model.objective}\n\n")
        else:
            f.write("## Objective Function\n\n")
            f.write("No objective function defined.\n\n")

        f.write("## Decision Variables\n\n")
        if model.variables():
            for v in model.variables():
                f.write(f"- {v.name}: ")
                if v.lowBound is not None:
                    f.write(f"{v.lowBound} <= ")
                f.write(f"{v} ")
                if v.upBound is not None:
                    f.write(f"<= {v.upBound}")
                f.write("\n")
        else:
            f.write("No decision variables defined.\n\n")

        f.write("\n## Constraints\n\n")
        if model.constraints:
            for name, c in model.constraints.items():
                f.write(f"- {name}: {c}\n")
        else:
            f.write("No constraints defined.\n\n")

    print("Model summary written to model_summary.md")

except Exception as e:  # Handle potential errors (e.g., file writing issues)
    print(f"An error occurred: {e}")
