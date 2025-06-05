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
                    
## Learnings from User Testing
          - Users prefer tabular views with sorting/filtering over purely graphical representations
          - The ability to save and compare multiple scenarios is highly valued
          - Manual override capabilities are essential for handling business exceptions
          - Users need clear explanations of why specific allocations were recommended
          - Export to Excel functionality is critical for integration with existing workflows
