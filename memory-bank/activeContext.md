# Active Context: Current Development Focus
          
## Current Development Focus
          As of May 2025, development is concentrated on the following components:
          1. **Optimization Engine Refinement**
             - Defining all the constraints to respect business need
	     -  Modifying the objective function to take into account all the edge cases : in order to allocate best products in best channels, we need to have a ranking of the product & a ranking of the channel in this function
             - **ABC Classification Source Update**: The `calculate_abc_classification_and_new_skus` function in `backend/solver.py` has been refactored. It now sources ABC classifications directly from `data/InputData/ABC_ranking.csv` instead of calculating them from sellout data.
             - **"NEW" SKU Logic Preservation**: The logic for identifying "NEW" SKUs (not 'A', 'B', or 'C' in `ABC_ranking.csv` AND no in-store stock for the EAN-Channel) has been maintained.
             - **Default Classification for Unranked Stocked Items**: EAN-Channel combinations not found in `ABC_ranking.csv` but having existing in-store stock are now classified as 'C'.

          2. **User Interface Enhancements**
             - Redesigning the results visualization dashboard
             - Adding drag-and-drop functionality for manual adjustments
             - Implementing user preference saving
          3. **Understanding of the allocation**
	     - We should be able to see the input parameters of the problem in the output so that we can know how the allocation has been made
	     - We should be able to see which constraints have been applied and how to see the limiting factors and understand the logic of the program
	     - We be able to see the impact of some parameter or some constraint on the optimality of the solutions.
          
## Recent Changes and Decisions
          - **Data Loading Refactoring**: Centralized all data loading logic into `backend/utils.py` for improved modularity, reusability, and testability.
          - **Comprehensive Unit Testing**: Implemented a dedicated test suite (`tests/test_utils.py`) with 40 passing tests covering all data loading functions and their edge cases.
          - **Enhanced Logging**: Integrated robust logging (INFO, DEBUG, WARNING, ERROR) within data loading utilities for better debugging and traceability.
          - **Cross-Module Consistency**: Ensured `main.py` and `backend/solver.py` now use the same unified data loading functions.
          - **Environment Stability**: Resolved `ModuleNotFoundError` and persistent Pylance indentation issues in `backend/solver.py` for standalone execution.
          - Testing cases written (now specifically for data loading utilities)
	  - Logger added with warning, info, debug and critical (now specifically for data loading utilities)
	  - Taking into account input parameters and input data in the problem
          - Refactored `/api/auto_allocate` endpoint in `main.py` to load all data inputs (products, channels, inventory, rules, etc.) directly from files, mirroring the standalone solver script's data sourcing.
          - Standardized `seasonality_coefficient` to 1.0 in `auto_allocate_endpoint` for consistent solver behavior.
          - Enhanced client-side and server-side logging for the auto-allocation process to improve debugging of API communication and data parsing.
          - **Corrected Auto-Allocation Data Flow**: Modified the `/api/allocation_data` endpoint in `main.py` to fetch allocation results directly from the database. This ensures the frontend table accurately reflects the allocations made by the `auto_allocate_endpoint`.
          - **Improved Frontend Auto-Allocation Logic**: Refined the `autoAllocate` function in `frontend/app.js` to robustly handle the response from `/api/auto_allocate`. It now ensures that `fetchAllocationData` is always called to refresh the UI with the latest database state, and provides clearer error reporting for the auto-allocation process, resolving the "Failed to fetch" alert while ensuring data consistency.
          - **Fixed Frontend Validation Banner**: Resolved an issue in `frontend/app.js` where the validation error banner on the "Edit Allocation" page was always displayed. Corrected ID type mismatches in `validateAllInputs` and `validateInput` functions by ensuring consistent string-based comparisons, so the banner now accurately reflects the presence of allocation errors.
          - **Integrated Plant Data into UI (June 2025)**:
            - Modified `backend/utils.py` (`load_inventory_df`) to load "plant" data from inventory CSV and group by EAN-Plant.
            - Updated `/api/allocation_data` in `main.py` to provide plant-specific data to the frontend, including a composite ID for EAN-Plant rows.
            - Added "Plant" column to the detailed allocation table in `frontend/app.js` and `frontend/index.html`.
            - Implemented "Plant" filters in both summary and detailed views (JS logic and HTML structure in `frontend/app.js` and `frontend/index.html`).
            - Transformed the main allocation chart on the summary page into a horizontal stacked bar chart, displaying "Stock of EANs Allocated to Channels (by Plant)".
            - Adjusted chart data label colors for better readability, increased main chart height, and slightly increased global font size via CSS.
            - Resolved JavaScript syntax errors in `frontend/app.js` related to Highcharts configuration during development.
          - **Enhanced Detailed Allocation Table (June 2025)**:
            - Modified `frontend/index.html` to update the detailed allocation table headers to include 'Axe', 'SubAxe', 'Metier', 'SKU', 'Description', 'FlagExcess6months', and 'FlagExcess12months', and reordered columns.
            - Updated `frontend/app.js` (specifically `renderAllocationTable`, `staticColumnDefs`, cell creation logic, and `exportToExcel`) to reflect the new column structure and data keys.
            - Adjusted `backend/utils.py`:
                - `load_products_df` updated to load and map `operational_axe_label`, `operational_sub_axe_label`, `operational_metier_label`, `internal_product_code`, `product_description` from `masterdata.csv`.
                - `load_inventory_df` updated to load and map `plant_description` (as `stockOrigin`), `FlagExcess6months`, and `FlagExcess12months` from `bad_stock_inventory.csv`.
            - Modified `main.py` in the `/api/allocation_data` endpoint to correctly merge and pass these new fields from `products_df` and `inventory_df` to the frontend.
          - **UI Consistency and Dynamic Remaining Quantity (June 2025)**:
            - Updated `main.py` (`/api/allocation_data`) to send `plant_description` as the `plant` field to the frontend, ensuring consistency between the table display and filter population. The `stockOrigin` field in the API response now effectively carries the plant description, which is then mapped to `item.plant` on the frontend.
            - Modified `frontend/app.js`:
                - `staticColumnDefs` in `renderAllocationTable` updated to use "Plant" as the header text for the column displaying plant description (data key `plant`).
                - `populateFilters` will now correctly populate the plant filter using plant descriptions via `item.plant`.
                - `handleAllocationChange` enhanced to dynamically calculate and update the "Remaining Qty" cell for the specific row being edited, providing live feedback as allocation inputs are modified.
          - **Chart Color Palette Customization (June 2025)**:
            - Added a `generateColorShades` helper function in `frontend/app.js` to create color gradients.
            - Updated `renderDivisionChart` and `renderBrandChart` to use a yellow-to-green (`#ffff3f` to `#007f5f`) color palette generated by this function.
            - Modified `renderAllocationChart` to use a distinct, professional predefined color palette (`['#4285F4', '#DB4437', ...]`) for its series.
          - **EAN Allocation Deep Dive Feature (Initial Implementation - June 2025)**:
            - Created a new backend API endpoint `/api/ean_deep_dive_data` in `main.py` to gather comprehensive data for a specific EAN (product info, stock levels, channel performance, ABC class, applied rules, final allocations).
            - Ensured correct placement of the endpoint definition in `main.py` for proper route registration.
            - Developed a new frontend page `frontend/ean_deep_dive.html` to display this detailed information.
            - Implemented `frontend/ean_deep_dive.js` to fetch data from the new API and populate the page.
            - Integrated a "Details" link in the main allocation table (`frontend/index.html` and `frontend/app.js`) to navigate to the deep dive page.
            - Initiated a test file `tests/test_main_api_deep_dive.py` with basic structure for the new endpoint.
            - Resolved 404 error for `/api/ean_deep_dive_data` by correcting the frontend fetch URL to be absolute and ensuring proper backend route registration and logic.
            - Corrected JavaScript error handling in `frontend/ean_deep_dive.js` for missing data properties.
          - **Restored `/api/allocation_data` Endpoint (June 2025)**:
            - Ensured the `/api/allocation_data` route definition was correctly present in `main.py` after it was inadvertently omitted during a previous file write, resolving a 404 error for this endpoint.
          - **Frontend UI Filtering for Non-Allocatable Stock (June 2025)**:
            - Modified `main.py` (`/api/allocation_data` endpoint) to include `available_stock` in the JSON response, alongside `units` (for `StockToAllocate`).
            - Updated `frontend/app.js` (`fetchAllocationData` function) to filter the displayed inventory items, showing only those where `item.units > 0` AND `item.available_stock > 0`.
            - Added test data to `data/InputData/bad_stock_inventory.csv` to cover various scenarios of zero stock for allocation or availability.
          - **Implemented Plant-Level Stock Allocation Constraints (June 2025)**:
            - **Solver (`backend/solver.py`):**
                - Decision variables `x` redefined as `x[ean, plant, channel]`.
                - Auxiliary binary variable `y_ean_plant_channel` added for plant-level allocation decisions.
                - Auxiliary binary variable `y_ean_channel` added for EAN-level allocation decisions (used for SKU counting constraints).
                - Supply constraints now operate at the EAN-Plant level, ensuring `sum(x[ean, plant, c] for c in channels) <= min(stock_to_allocate_at_plant[ean, plant], available_stock_at_plant[ean, plant])`.
                - Linking constraints updated to connect `x`, `y_ean_plant_channel`, and `y_ean_channel`.
                - Coverage days, new SKU push, and restricted brand constraints now sum allocations across plants for a given EAN-Channel.
                - Outlet SKU capacity and assortment constraints now use `y_ean_channel` for SKU counting at the EAN level.
                - Solver results now include `plant_code`.
            - **Database Model (`backend/models.py`):**
                - Added `plant_code` field to the `Allocation` table.
            - **API Logic (`main.py`):**
                - `/api/auto_allocate`: Updated to save solver results (including `plant_code`) to the `Allocation` table.
                - `/api/allocation_data`: Modified to fetch and structure EAN-Plant-Channel allocations. The `allocations_map` now uses `(ean, plant_code)` as keys. Frontend data `item.channels` now represents allocations from the specific EAN-Plant combination.
                - `/api/save_allocations`: Updated to handle manual allocation changes at the EAN-Plant level, using the composite `id` (`ean_plantcode`) from the frontend.
            - **Frontend Logic (`frontend/app.js`):**
                - `saveAllocation` function updated to send EAN-Plant specific data (using `item.id` which is `ean_plantcode`) to the `/api/save_allocations` endpoint.
                - `handleAllocationChange` remains largely compatible due to the existing `item.id` structure.
                - No changes were required for `frontend/index.html` as the table structure already supported EAN-Plant rows.
          - **Refactored ABC Classification to Use `ABC_ranking.csv` (June 2025)**:
            - Modified `backend/solver.py`:
                - The `calculate_abc_classification_and_new_skus` function was refactored to read ABC classes from `data/InputData/ABC_ranking.csv` (semicolon-delimited).
                - Sellout-based calculation parameters were removed from its signature.
                - Logic for "NEW" SKUs (not A/B/C in file AND no in-store stock) and default 'C' (not in file BUT has stock) was implemented.
                - Return type (`product_channel_abc_map`) and existing logging patterns were preserved and adapted.
            - Updated `main.py`:
                - Calls to `calculate_abc_classification_and_new_skus` in `/api/auto_allocate` and `/api/ean_deep_dive_data` were updated with the new parameters (passing `abc_ranking_file_path`).
            - Implemented `tests/test_solver.py`:
                - Added comprehensive unit tests for the refactored `calculate_abc_classification_and_new_skus`.
                - Tests cover scenarios like normal ABC lookup, missing products, NEW SKU identification, default 'C' for stocked unranked items, empty ranking file, and handling of non-standard ABC classes in the file.
                - Mocking of `pd.read_csv` for `ABC_ranking.csv` and `in_store_inventory.csv` is used for deterministic testing.
                    
## Learnings from User Testing
          - Users prefer tabular views with sorting/filtering over purely graphical representations
          - The ability to save and compare multiple scenarios is highly valued
          - Manual override capabilities are essential for handling business exceptions
          - Users need clear explanations of why specific allocations were recommended
          - Export to Excel functionality is critical for integration with existing workflows
