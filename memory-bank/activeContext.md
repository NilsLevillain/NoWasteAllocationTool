# Active Context: Current Development Focus
          
## Current Development Focus
          As of May 2025, development is concentrated on the following components:
          1. **Optimization Engine Refinement**
             - Defining all the constraints to respect business need
	     -  Modifying the objective function to take into account all the edge cases : in order to allocate best products in best channels, we need to have a ranking of the product & a ranking of the channel in this function

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
                    
## Learnings from User Testing
          - Users prefer tabular views with sorting/filtering over purely graphical representations
          - The ability to save and compare multiple scenarios is highly valued
          - Manual override capabilities are essential for handling business exceptions
          - Users need clear explanations of why specific allocations were recommended
          - Export to Excel functionality is critical for integration with existing workflows
