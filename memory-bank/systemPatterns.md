# systemPatterns.md

# System Patterns: Architecture and Design

## Overall Architecture
The Bad Stock Allocation Optimizer follows a three-tier architecture:

1. **Presentation Layer**: Flask-based web interface with JavaScript frontend
2. **Application Layer**: Python business logic and optimization controller
3. **Optimization Engine**: PuLP-based linear programming solver

The system uses a Model-View-Controller (MVC) pattern to separate concerns and maintain code modularity.

## Linear Programming Model Structure
The core optimization model follows these structural patterns:

1. **Decision Variables**: Binary variables (x_ij) representing allocation of product i to channel j
2. **Objective Function**: Maximize total value recovery across all allocations
3. **Constraints**:
   - Channel capacity constraints
   - Product availability constraints
   - Channel priority constraints
   - Business rules constraints (e.g., certain products can only go to specific channels)

The model is implemented using the Factory pattern, allowing for different optimization models to be created based on user requirements.

## Component Relationships
Frontend (HTML/JS/CSS) <--> Flask Controllers <--> Optimization Service <--> PuLP Solver
                ^                    ^                      ^                    ^
                |                    |                      |                    |
                v                    v                      v                    v
        Visualization Components  Data Validators     Model Factories      Solver Adapters

The system uses a Service-oriented architecture pattern to separate the optimization logic from the web interface.

## Data Flow Patterns
1. Input Processing:
   - User inputs -> Validation -> Preprocessing -> Model Construction

2. Optimization Flow:
   - Model -> Solver -> Solution -> Post-processing -> Results

3. Output Processing:
   - Results -> Visualization -> User Interface
   - Results -> Excel Export -> SAP Integration

4. Persistence Flow:
   - Scenario -> Serialization -> Storage -> Retrieval -> Deserialization

The system implements the Observer pattern to notify various components when optimization results are available.

## Data Access Patterns
- **Centralized Data Utilities**: Data loading from various sources (CSV, Excel) is centralized in `backend/utils.py`. This promotes:
    - **Reusability**: Common functions for loading products, channels, inventory, demand, and optimization rules.
    - **Consistency**: Standardized data structures (Pandas DataFrames, dictionaries) returned by loading functions.
    - **Maintainability**: Single point of change for data loading logic.
    - **Testability**: Dedicated unit tests for data loading utilities ensure reliability.
- **Hybrid Data Sourcing for Frontend Display**:
    - The `/api/allocation_data` endpoint (responsible for populating the main frontend table) now employs a hybrid approach:
        - It loads base data such as product master information, channel definitions, and total inventory quantities from files (via `backend/utils.py`).
        - Crucially, it fetches the actual allocation quantities (product-channel assignments) directly from the `Allocation` table in the database.
        - This ensures that the frontend always displays the most current allocation results, reflecting outcomes from both automated solver runs and manual adjustments saved to the database.
- **File-First Data Sourcing for Solver Input**:
    - The `/api/auto_allocate` endpoint (for running the solver) continues to load all its primary data inputs (products, channels, inventory, rules, demand, existing stock) directly from files via `backend/utils.py`. This maintains consistency with standalone solver execution and allows for easy updates of input parameters through file modifications.
- **Robust Error Handling**: Data loading utilities include specific error handling for file not found, missing columns, and data parsing issues, with integrated logging.
- **Enhanced API Debugging and Frontend Robustness**:
    - Server-side logging in `main.py` for the `/api/auto_allocate` endpoint includes details of the data being prepared for the JSON response.
    - Client-side logic in `frontend/app.js` for the `autoAllocate` function has been improved:
        - It now ensures that UI data is refreshed by calling `fetchAllocationData` (which hits `/api/allocation_data`) after an auto-allocation attempt, regardless of whether the direct response from `/api/auto_allocate` was successfully received by the client.
        - This resolves previous issues where a "Failed to fetch" alert might appear while the underlying server operation succeeded and data was updated in the database. The UI now more reliably reflects the database state.
- **EAN Deep Dive Data Sourcing**:
    - A new endpoint `/api/ean_deep_dive_data` in `main.py` is responsible for gathering all relevant information for a single EAN.
    - This endpoint loads data from multiple sources:
        - Product master data (`masterdata.csv`) via `load_products_df`.
        - Bad stock inventory (`bad_stock_inventory.csv`) via `load_inventory_df`.
        - Existing in-store and in-transit stock (`in_store_inventory.csv`, `stock_in_transit.csv`) via `load_existing_stock_dict`.
        - Channel list (`ChannelList.xlsx`) via `load_channels_df`.
        - Sellout data (`sellout.csv`) via `pd.read_csv` and `load_demand_dict`.
        - In-store inventory (again, for ABC) via `pd.read_csv`.
        - All rule Excel files via `load_optimization_rules`.
        - Final allocations from the `Allocation` database table.
    - It calls `calculate_abc_classification_and_new_skus` to determine the ABC/NEW status for the EAN across channels.
    - The collected and processed data is returned as a structured JSON to the `frontend/ean_deep_dive.html` page.

## Error Handling Patterns
- Input validation errors are caught early and presented to users for correction
- Optimization errors (infeasible solutions, etc.) are handled gracefully with explanations
- System errors are logged comprehensively while providing user-friendly messages
- **Enhanced API Debugging**:
    - Server-side logging in `main.py` for the `/api/auto_allocate` endpoint now includes the exact data being prepared for the JSON response.
    - Client-side logging in `frontend/app.js` for the `autoAllocate` function has been improved to capture the raw text of the server's response before attempting JSON parsing, aiding in diagnosing "Failed to fetch" or JSON parsing errors.

The system uses the Strategy pattern to apply different error handling approaches based on the error type and context.
