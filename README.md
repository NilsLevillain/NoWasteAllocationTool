# NW Allocation Tool

This project implements a stock allocation optimization tool using Python, Flask, and PuLP.

## Project Structure

```
nw-allocation-tool/
│
├── backend/
│   ├── __init__.py
│   ├── solver.py        # PuLP optimization logic
│   ├── models.py        # SQLAlchemy database models
│   ├── schemas.py       # Pydantic schemas for validation
│   ├── utils.py         # Helper functions
│   ├── config.py        # Configuration settings
│   └── model_summary_generator.py # Script to generate model summary
│
├── frontend/
│   ├── index.html       # Main HTML page
│   ├── style.css        # CSS styles
│   ├── app.js           # Frontend JavaScript logic
│   └── static/          # Static assets (if any, e.g., React build)
│
├── tests/
│   ├── __init__.py
│   ├── test_solver.py   # Unit tests for the solver logic
│   └── test_schemas.py  # Unit tests for schemas
│
├── data/
│   ├── ExcelParameters/ # Input data in Excel format
│   └── instance/        # Instance-specific data (e.g., SQLite DB)
│
├── .env                 # Environment variables (sensitive config) - **DO NOT COMMIT**
├── .gitignore           # Specifies intentionally untracked files
├── main.py              # Flask application entry point
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── allocation_model.lp  # Example LP model file (generated)
├── model_summary.md     # Generated model summary
└── test.mps             # Example MPS model file (generated)
```

## Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure environment variables:**
    Create a `.env` file in the root directory (`nw-allocation-tool/`) and add necessary variables (see `.env.example` or `backend/config.py` for required variables like `SECRET_KEY`, `DATABASE_URL`).
    Example `.env`:
    ```dotenv
    SECRET_KEY='your_super_secret_key'
    SQLALCHEMY_DATABASE_URI='sqlite:///./data/instance/inventory.db'
    # Add other variables as needed
    ```
4.  **Run the application:**
    ```bash
    python main.py
    ```
    The application will be available at `http://127.0.0.1:5000`.

## Running Tests

```bash
python -m unittest discover -s tests
```

## Usage

-   Access the web interface to interact with the allocation tool.
-   Use the API endpoints (details TBD).
