# Linear Programming Model Documentation

## Overview

This document explains the linear programming model used in the inventory allocation optimization system. The model is implemented using PuLP in the `solver.py` file.

## Objective Function

The model maximizes the total quantity of products allocated across all channels:
Maximize: ∑(p∈P, c∈C) x[p,c]

Where:
- `x[p,c]` represents the quantity of product `p` allocated to channel `c`
- `P` is the set of all products
- `C` is the set of all channels

## Decision Variables

The model uses two types of decision variables:

1. **Allocation Quantity (`x[p,c]`)**: Integer variable representing the quantity of product `p` allocated to channel `c`
   - Domain: Non-negative integers

2. **Allocation Decision (`y[p,c]`)**: Binary variable indicating whether product `p` is allocated to channel `c`
   - Domain: {0, 1}

## Constraints

### 1. Supply Constraints

Each product's total allocation cannot exceed its available inventory:
∑(c∈C) x[p,c] ≤ inventory_quantity[p] for all p∈P

### 2. Outlet SKU Capacity Constraints

For outlet channels, the number of SKUs allocated within each division-axe group is limited:
∑(p∈P_div_axe) y[p,c] ≤ max_skus[c,division,axe] for all c∈C_outlet, (division,axe)

Where:
- `P_div_axe` is the set of products belonging to a specific division-axe group
- `C_outlet` is the set of outlet channels
- `max_skus[c,division,axe]` is the maximum number of SKUs allowed for the division-axe in channel c

### 3. Coverage Days Constraints

For products with existing ABC classification (not NEW):
x[p,c] ≤ max(0, (demand[p,c] / 7.0) * coverage_days[c,abc_class] - current_stock[p,c]) for all p∈P, c∈C

Where:
- `demand[p,c]` is the weekly demand for product p in channel c
- `coverage_days[c,abc_class]` is the target coverage days for the ABC class in channel c
- `current_stock[p,c]` is the existing stock of product p in channel c

### 4. New SKU Push Constraints

For products classified as NEW:
x[p,c] ≤ push_qty[division,subaxis] for all p∈P_new, c∈C

Where:
- `P_new` is the set of products classified as NEW
- `push_qty[division,subaxis]` is the maximum push quantity for new SKUs in that division-subaxis

### 5. Outlet Assortment Constraints

For outlet channels, the number of SKUs allocated within each metier-subaxis-brand group is limited:
∑(p∈P_metier_subaxis_brand) y[p,c] ≤ max_skus[metier,subaxis,brand] for all c∈C_outlet, (metier,subaxis,brand)

Where:
- `P_metier_subaxis_brand` is the set of products belonging to a specific metier-subaxis-brand group

### 6. Restricted Brands for Donation Constraints

Products from restricted brands cannot be allocated to donation channels:
x[p,c] = 0 for all p∈P_restricted_brands, c∈C_donation

### 7. Linking Constraints

These constraints link the allocation quantity variables `x[p,c]` with the binary allocation decision variables `y[p,c]`:
x[p,c] ≤ M * y[p,c] for all p∈P, c∈C

Where:
- `M` is a large number (in this case, the inventory quantity of product p)

## ABC Classification

The model uses an ABC classification system based on product sales:
- **A**: Top products that contribute to the first 20% of sales
- **B**: Products that contribute to the next 60% of sales (up to 80% cumulative)
- **C**: Products that contribute to the remaining 20% of sales (or products with no sales but existing in-store stock)
- **NEW**: Products with no sales history AND no existing in-store stock in a particular channel.

This classification influences the coverage days constraints.

## Data Inputs

The model requires several data inputs:
1. Product master data (EAN, brand, division, axe, etc.)
2. Channel data (channel ID, type)
3. Inventory data (available quantities)
4. Existing stock data (in-store and in-transit)
5. Demand data (weekly sales quantities)
6. Various rules defined in Excel files (coverage days, outlet capacity, assortment, push new SKU)

## Output

The model produces an allocation plan specifying the quantity of each product to allocate to each channel.
