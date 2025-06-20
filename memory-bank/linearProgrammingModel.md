# Linear Programming Model Documentation

## Overview

This document explains the linear programming model used in the inventory allocation optimization system. The model is implemented using PuLP in the `solver.py` file.

## Objective Function

The model maximizes the total quantity of products allocated from all EAN-Plant combinations to all channels:
Maximize: ∑(p∈P, plant∈PL, c∈C) x[p, plant, c]

Where:
- `x[p, plant, c]` represents the quantity of product EAN `p` from plant `plant` allocated to channel `c`.
- `P` is the set of all product EANs.
- `PL` is the set of all plants associated with a given EAN `p`.
- `C` is the set of all channels.

## Decision Variables

The model uses three main types of decision variables:

1.  **Allocation Quantity (`x[p, plant, c]`)**: Integer variable representing the quantity of product EAN `p` from plant `plant` allocated to channel `c`.
    -   Domain: Non-negative integers.
    -   Indexed by: (Product EAN, Plant Code, Channel ID).

2.  **Plant-Level Allocation Decision (`y_ean_plant_channel[p, plant, c]`)**: Binary variable indicating whether product EAN `p` from plant `plant` is allocated (any quantity > 0) to channel `c`.
    -   Domain: {0, 1}.
    -   Indexed by: (Product EAN, Plant Code, Channel ID).

3.  **EAN-Level Allocation Decision (`y_ean_channel[p, c]`)**: Binary variable indicating whether product EAN `p` is allocated to channel `c` from *any* plant. This is an auxiliary variable used primarily for SKU counting constraints that operate at the EAN level (e.g., outlet capacity).
    -   Domain: {0, 1}.
    -   Indexed by: (Product EAN, Channel ID).

## Constraints

### 1. Supply Constraints (Per EAN-Plant)

The total quantity of an EAN allocated from a specific plant cannot exceed the available stock at that EAN-Plant combination.
∑(c∈C) x[p, plant, c] ≤ min(stock_to_allocate[p, plant], available_stock[p, plant])
For all product EANs `p` and for each plant `plant` where `p` is stocked.

Where:
- `stock_to_allocate[p, plant]` is the "StockToAllocate" for EAN `p` at `plant`.
- `available_stock[p, plant]` is the "AvailableStock" for EAN `p` at `plant`.

### 2. Outlet SKU Capacity Constraints (Per EAN)

For outlet channels, the number of unique EANs (SKUs) allocated within each division-axe group is limited. This constraint uses the `y_ean_channel` variable.
∑(p∈P_div_axe) y_ean_channel[p,c] ≤ max_skus[c,division,axe]
For all outlet channels `c` and for each (division, axe) group.

Where:
- `P_div_axe` is the set of product EANs belonging to a specific division-axe group.
- `C_outlet` is the set of outlet channels.
- `max_skus[c,division,axe]` is the maximum number of SKUs allowed for the division-axe in channel `c`.

### 3. Coverage Days Constraints (Per EAN-Channel, Summing Over Plants)

For products with existing ABC classification (not NEW), the total quantity of an EAN allocated to a channel (summed across all plants it's sourced from) is limited by coverage days.
∑(plant∈PL_p) x[p, plant, c] ≤ max(0, (demand[p,c] / 7.0) * coverage_days[c,abc_class] - current_stock[p,c])
For all product EANs `p` and channels `c`.

Where:
- `PL_p` is the set of plants stocking EAN `p`.
- `demand[p,c]` is the weekly demand for EAN `p` in channel `c`.
- `coverage_days[c,abc_class]` is the target coverage days for the ABC class of EAN `p` in channel `c`.
- `current_stock[p,c]` is the existing stock of EAN `p` in channel `c`.

### 4. New SKU Push Constraints (Per EAN-Channel, Summing Over Plants)

For products classified as NEW, the total quantity of an EAN allocated to a channel (summed across all plants) is limited by a push quantity.
∑(plant∈PL_p) x[p, plant, c] ≤ push_qty[division,subaxis]
For all EANs `p` classified as NEW in channel `c`.

Where:
- `P_new` is the set of EANs classified as NEW for a given channel.
- `push_qty[division,subaxis]` is the maximum push quantity for new SKUs in that EAN's division-subaxis.

### 5. Outlet Assortment Constraints (Per EAN)

For outlet channels, the number of unique EANs (SKUs) allocated within each metier-subaxis-brand group is limited. This uses `y_ean_channel`.
∑(p∈P_metier_subaxis_brand) y_ean_channel[p,c] ≤ max_skus[metier,subaxis,brand]
For all outlet channels `c` and for each (metier, subaxis, brand) group.

Where:
- `P_metier_subaxis_brand` is the set of product EANs belonging to a specific metier-subaxis-brand group.

### 6. Restricted Brands for Donation Constraints (Per EAN-Plant-Channel)

Products from restricted brands cannot be allocated to donation channels from any plant.
x[p, plant, c] = 0
For all EANs `p` belonging to restricted brands, for all plants `plant` stocking `p`, and for all donation channels `c`.

### 7. Linking Constraints

These constraints link the allocation quantity variables with the binary decision variables:

-   **Linking `x[p, plant, c]` to `y_ean_plant_channel[p, plant, c]`**:
    x[p, plant, c] ≤ M_plant * y_ean_plant_channel[p, plant, c]
    For all (p, plant, c). `M_plant` is a large number, typically min(stock_to_allocate[p,plant], available_stock[p,plant]).
    This ensures if any quantity is allocated from a plant, the corresponding plant-level decision variable is 1.

-   **Linking `y_ean_plant_channel[p, plant, c]` to `y_ean_channel[p, c]`**:
    1.  y_ean_plant_channel[p, plant, c] ≤ y_ean_channel[p, c]
        For all (p, plant, c). If an EAN is allocated from a specific plant to a channel, then that EAN is considered allocated to that channel.
    2.  y_ean_channel[p, c] ≤ ∑(plant∈PL_p) y_ean_plant_channel[p, plant, c]
        For all (p, c). If an EAN is considered allocated to a channel, it must have been allocated from at least one plant.

## ABC Classification

The ABC classification is now determined by the `calculate_abc_classification_and_new_skus` function in `backend/solver.py` based on the following logic:
1.  **Primary Source**: `data/InputData/ABC_ranking.csv`. This file provides pre-calculated ABC classes ('A', 'B', 'C') for EAN-Channel combinations.
    -   The file is semicolon-delimited. Key columns used are `barcode` (EAN), `store_code` (Channel ID), and `abc_class`.
2.  **"NEW" SKU Logic**: An EAN-Channel combination is classified as 'NEW' if:
    *   It is **not** found with an 'A', 'B', or 'C' classification in `ABC_ranking.csv` for that specific EAN and Channel.
    *   AND, there is no existing in-store stock for that EAN-Channel combination (checked via `data/InputData/in_store_inventory.csv`).
3.  **Default 'C' Classification**: If an EAN-Channel combination is **not** found in `ABC_ranking.csv` BUT *does* have existing in-store stock (from `data/InputData/in_store_inventory.csv`), it is classified as 'C'.
4.  **Output**: The function returns a map `product_channel_abc_map[(ean, channel)]` with values 'A', 'B', 'C', or 'NEW'.

This classification influences the coverage days constraints and new SKU push constraints.

## Data Inputs

The model requires several data inputs:
1.  Product master data (EAN, brand, division, axe, metier, subaxis, etc.)
2.  Channel data (channel ID, type)
3.  **Inventory data (EAN-Plant specific)**: `product_ean`, `plant` (plant code), `quantity` (StockToAllocate at plant), `available_stock` (AvailableStock at plant).
    -   **Note on Frontend Display**: The 'Units' column displayed in the frontend for each EAN-Plant combination now represents `min(StockToAllocate, AvailableStock)` from the inventory data, aligning with the quantity considered by the solver's supply constraint for that EAN-Plant.
4.  Existing stock data (in-store and in-transit, typically at EAN-Channel level).
5.  Demand data (weekly sales quantities, typically at EAN-Channel level).
6.  Various rules defined in Excel files (coverage days, outlet capacity, assortment, push new SKU).

## Output

The model produces an allocation plan specifying the quantity of each product EAN from each specific plant to allocate to each channel (`product_sku`, `plant_code`, `channel_id`, `quantity`).
