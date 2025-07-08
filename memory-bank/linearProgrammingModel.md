# Updated Documentation: Linear Programming Model with Parameterizable Scoring and Coverage Days
## Overview
This document explains the linear programming model used in the inventory allocation optimization system. The model is implemented using PuLP in the solver.py file and includes a sophisticated weighted scoring system for value maximization.

## Objective Function
The model maximizes the total weighted value of products allocated from all EAN-Plant combinations to all channels, using a lexicographical approach:

**Maximize: ∑(p∈P, c∈C) y_ean_channel[p, c] * score[p, c] * SCORE_WEIGHT + ∑(p∈P, plant∈PL, c∈C) x[p, plant, c] * QUANTITY_WEIGHT**

Where:

- `x[p, plant, c]` represents the quantity of product EAN `p` from plant `plant` allocated to channel `c`
- `score[p, c]` is the calculated allocation score for EAN `p` to channel `c` based on ABC classification, sellin ranking, and demand
- `P` is the set of all product EANs
- `PL` is the set of all plants associated with a given EAN `p`
- `C` is the set of all channels

## Scoring System
The allocation score `score[p, c]` is calculated based on a tiered system depending on the SKU's ABC classification for that channel. This system prioritizes higher-value products.

- **Tier 1: Class A & B Products**
  - `score[p, c] = 2.0`
  - These products are given the highest priority in the allocation.

- **Tier 2: Class C Products**
  - `score[p, c] = min(1.99, 1 + (sellin_rank[p] / 100.0))`
  - The score is based on the product's sell-in ranking, capped at 1.99 to ensure it never exceeds the score of A/B products.

- **Tier 3: NEW Products**
  - `score[p, c] = 1 + 0.8 * (sellin_rank[p] / 100.0)`
  - The score for new products is also based on their sell-in ranking, but with a slightly lower weight compared to C-class products to manage their introduction into channels.

This structure ensures a clear hierarchy: A/B SKUs are always prioritized, followed by C SKUs, and then NEW SKUs, with sell-in ranking acting as a tie-breaker within the C and NEW tiers.

## Decision Variables
The model uses three main types of decision variables:

1.  **Allocation Quantity (`x[p, plant, c]`)**: Integer variable representing the quantity of product EAN `p` from plant `plant` allocated to channel `c`.
    -   **Domain**: Non-negative integers
    -   **Indexed by**: (Product EAN, Plant Code, Channel ID)
2.  **Plant-Level Allocation Decision (`y_ean_plant_channel[p, plant, c]`)**: Binary variable indicating whether product EAN `p` from plant `plant` is allocated (any quantity > 0) to channel `c`.
    -   **Domain**: {0, 1}
    -   **Indexed by**: (Product EAN, Plant Code, Channel ID)
3.  **EAN-Level Allocation Decision (`y_ean_channel[p, c]`)**: Binary variable indicating whether product EAN `p` is allocated to channel `c` from any plant. This is an auxiliary variable used primarily for SKU counting constraints.
    -   **Domain**: {0, 1}
    -   **Indexed by**: (Product EAN, Channel ID)

## Constraints
### 1. Supply Constraints (Per EAN-Plant)
The total quantity of an EAN allocated from a specific plant cannot exceed the available stock at that EAN-Plant combination.

**∑(c∈C) x[p, plant, c] ≤ min(stock_to_allocate[p, plant], available_stock[p, plant])**
For all product EANs `p` and for each plant `plant` where `p` is stocked.

### 2. Outlet SKU Capacity Constraints (Per EAN)
For outlet channels, the number of unique EANs (SKUs) allocated within each division-axe group is limited.

**∑(p∈P_div_axe) y_ean_channel[p,c] ≤ max_skus[c,division,axe]**
For all outlet channels `c` and for each (division, axe) group.

### 3. Coverage Days Constraints (Per EAN-Channel, Summing Over Plants)
For products with existing ABC classification (not NEW), the total quantity of an EAN allocated to a channel is limited by coverage days, using a "Big M" formulation:

`∑(plant∈PL_p) x[p, plant, c] ≤ allow_alloc + M_ean_total_stock * (1 - y_ean_channel[p, c])`

Where:
- `allow_alloc = max(0, (demand[p,c] / 14.0) × coverage_days[c,abc_class] × seasonality_coefficient - current_stock[p,c])`
- `M_ean_total_stock` is the total available stock for the EAN across all plants
- This constraint is only active if the SKU is selected for the channel (`y_ean_channel = 1`)

**Future Parameterizable Implementation:**
`∑(plant∈PL_p) x[p, plant, c] ≤ max(0, (demand[p,c] / coverage_days_divisor) × coverage_days[c,abc_class] × seasonality_coefficient - current_stock[p,c]) + M_ean_total_stock * (1 - y_ean_channel[p, c])`

Where:
- `coverage_days_divisor` will be a parameter (currently hardcoded to 14.0 for bi-weekly)
- Common values: 7.0 (weekly), 14.0 (bi-weekly), 30.0 (monthly)
- `seasonality_coefficient` is already a parameter in `OptimizationParameters`

### 4. New SKU Push Constraints (Per EAN-Channel, Summing Over Plants)
For products classified as NEW, the total quantity of an EAN allocated to a channel is limited by a push quantity, using a "Big M" formulation:

`∑(plant∈PL_p) x[p, plant, c] ≤ push_qty[division,subaxis] + M_ean_total_stock * (1 - y_ean_channel[p, c])`

Where:
- `M_ean_total_stock` is the total available stock for the EAN across all plants
- This constraint is only active if the SKU is selected for the channel (`y_ean_channel = 1`)

### 5. Outlet Assortment Constraints (Per EAN)
For outlet channels, the number of unique EANs (SKUs) allocated within each metier-subaxis-brand group is limited.

**∑(p∈P_metier_subaxis_brand) y_ean_channel[p,c] ≤ max_skus[metier,subaxis,brand]**
For all outlet channels `c` and for each (metier, subaxis, brand) group.

### 6. Restricted Brands for Donation Constraints (Per EAN-Plant-Channel)
Products from restricted brands cannot be allocated to donation channels from any plant.

**x[p, plant, c] = 0**
For all EANs `p` belonging to restricted brands, for all plants `plant` stocking `p`, and for all donation channels `c`.

### 7. Linking Constraints
These constraints link the allocation quantity variables with the binary decision variables:

- **Linking `x[p, plant, c]` to `y_ean_plant_channel[p, plant, c]`**:
  - `x[p, plant, c] ≤ M_plant × y_ean_plant_channel[p, plant, c]`
- **Linking `y_ean_plant_channel[p, plant, c]` to `y_ean_channel[p, c]`**:
  - `y_ean_plant_channel[p, plant, c] ≤ y_ean_channel[p, c]`
  - `y_ean_channel[p, c] ≤ ∑(plant∈PL_p) y_ean_plant_channel[p, plant, c]`

## ABC Classification
The ABC classification is determined by the `calculate_abc_classification_and_new_skus` function based on:

-   **Primary Source**: `data/InputData/ABC_ranking.csv` (pre-calculated ABC classes)
-   **"NEW" SKU Logic**: Not in `ABC_ranking.csv` AND no existing in-store stock
-   **Default 'C' Classification**: Not in `ABC_ranking.csv` BUT has existing in-store stock
-   **Output**: Map `product_channel_abc_map[(ean, channel)]` with values 'A', 'B', 'C', or 'NEW'

## Future OptimizationParameters Schema Enhancements
The following parameters will be added to make the system fully configurable:
```python
@dataclass
class OptimizationParameters:
    # Existing parameters
    seasonality_coefficient: float
    restricted_brands_for_donation: List[str]
    coverage_days_rules: List[CoverageDaysRule]
    outlet_sku_capacity_rules: List[OutletSKUCapacityRule]
    outlet_assortment_rules: List[OutletAssortmentRule]
    push_new_sku_rules: List[PushNewSKURule]
    
    # Future scoring parameters
    a_b_class_score: float = 2.0
    new_sku_ranking_weight: float = 1.0
    c_class_demand_weight: float = 0.5
    c_class_demand_scaling_factor: float = 0.001
    default_allocation_score: float = 1.0
    sellin_ranking_max_value: float = 100.0
    
    # Future coverage calculation parameters
    coverage_days_divisor: float = 14.0  # 7.0=weekly, 14.0=bi-weekly, 30.0=monthly
```

## Data Inputs
The model requires several data inputs:

-   Product master data (EAN, brand, division, axe, metier, subaxis, etc.)
-   Channel data (channel ID, type)
-   Inventory data (EAN-Plant specific): `product_ean`, `plant`, `quantity` (StockToAllocate), `available_stock`
-   Existing stock data (in-store and in-transit, typically at EAN-Channel level)
-   Demand data (weekly sales quantities, typically at EAN-Channel level)
-   Sellin ranking data: For NEW SKU prioritization
-   Various rules defined in Excel files (coverage days, outlet capacity, assortment, push new SKU)

## Output
The model produces an allocation plan specifying the quantity of each product EAN from each specific plant to allocate to each channel (`product_sku`, `plant_code`, `channel_id`, `quantity`).

## Current Prototype Limitations
### Hardcoded Values (to be parameterized):
-   All scoring weights and factors
-   Coverage days calculation basis (bi-weekly vs weekly)
-   Sellin ranking normalization values

### Future Enhancements:
-   Full parameter configurability through UI
-   Dynamic scoring weight adjustment
-   Flexible coverage calculation periods
-   Sensitivity analysis for key parameters

This documentation reflects the current state of the prototype while outlining the planned parameterization for production use.
