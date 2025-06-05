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
- **Robust Error Handling**: Data loading utilities include specific error handling for file not found, missing columns, and data parsing issues, with integrated logging.

## Error Handling Patterns
- Input validation errors are caught early and presented to users for correction
- Optimization errors (infeasible solutions, etc.) are handled gracefully with explanations
- System errors are logged comprehensively while providing user-friendly messages

The system uses the Strategy pattern to apply different error handling approaches based on the error type and context.
