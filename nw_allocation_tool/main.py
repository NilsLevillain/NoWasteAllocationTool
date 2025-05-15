from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import pandas as pd
import os # Import os for path joining
from sqlalchemy.orm import joinedload
from collections import defaultdict # Import defaultdict
from backend.models import db, Product, Inventory, Channel, Allocation, User, AllocationRun # Import AllocationRun if used
from backend.solver import optimize_allocation
from backend.schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule # Import parameter schemas
from backend.config import Config

app = Flask(__name__)
app.config.from_object(Config)

CORS(app)
db.init_app(app)
jwt = JWTManager(app)

@app.route('/api/dashboard/metrics', methods=['GET'])
@jwt_required()
def get_dashboard_metrics():
    try:
        excess_stock = Inventory.query.filter_by(status='excess').count()
        obsolete_items = Inventory.query.filter_by(status='obsolete').count()
        returns = Inventory.query.filter_by(status='returned').count()
        expiring_soon = Inventory.query.filter(
            Inventory.expiry_date <= datetime.now() + timedelta(days=90)
        ).count()

        return jsonify({
            'excess_stock': excess_stock,
            'obsolete_items': obsolete_items,
            'returns': returns,
            'expiring_soon': expiring_soon
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/allocate', methods=['POST'])
@jwt_required()
def allocate_inventory():
    try:
        data = request.get_json()
        allocation_result = optimize_allocation(
            products_df=pd.DataFrame([p.to_dict() for p in Product.query.all()]),
            channels_df=pd.DataFrame([c.to_dict() for c in Channel.query.all()]),
            inventory_df=pd.DataFrame([i.to_dict() for i in Inventory.query.all()]),
            demand=data.get('demand', {}),
            # revenue=data.get('revenue', {}) # Removed revenue
            parameters=data.get('parameters', {}) # Assuming parameters are passed in request body now
        )

        # The optimize_allocation function now returns model, status, results
        model, status, allocation_result_list = allocation_result # Unpack the tuple

        # Save allocation results to database
        # Ensure allocation_result_list is used here
        for alloc in allocation_result_list: # Corrected loop variable
            new_allocation = Allocation(
                product_id=alloc['product_sku'], # Use 'product_sku' from results dict
                channel_id=alloc['channel_id'],
                quantity=alloc['quantity'],
                allocation_date=datetime.now()
            )
            db.session.add(new_allocation)

        db.session.commit()
        # Return the list of allocation decisions
        return jsonify(allocation_result_list)
    except Exception as e:
        db.session.rollback() # Rollback in case of error during commit
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/secondlife', methods=['GET'])
@jwt_required()
def get_secondlife_channels():
    try:
        channels = Channel.query.filter_by(channel_type='secondlife').all()
        return jsonify([channel.to_dict() for channel in channels])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """
    Basic login endpoint. Takes username and password.
    Returns JWT access token on success.
    WARNING: Uses plain text password comparison for simplicity. DO NOT use in production.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    user = User.query.filter_by(username=username).first()

    # WARNING: Plain text password comparison - highly insecure!
    # Replace with proper password hashing (e.g., Werkzeug's check_password_hash) in a real app.
    # Comparing input 'password' with the value stored in 'password_hash' field.
    if user and user.password_hash == password:
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token)
    else:
        return jsonify({"msg": "Bad username or password"}), 401


if __name__ == '__main__':
    with app.app_context():
        # Create tables first if they don't exist
        db.create_all()

        # Ensure a default user exists for testing if the table is empty
        if not User.query.first():
            # WARNING: Storing plain text password - highly insecure!
            # In a real app, use password hashing (e.g., Werkzeug's generate_password_hash)
            # Also, the User model expects 'password_hash', not 'password'.
            # For this basic setup, let's adjust the User model or store a dummy hash.
            # Simpler for now: Add a plain 'password' field to User model (less ideal)
            # OR store something in password_hash. Let's store the plain password there for now.
            # Re-emphasizing: THIS IS NOT SECURE FOR REAL APPLICATIONS.
            default_user = User(username='testuser', email='test@example.com', password_hash='password') # Store plain pwd in hash field for demo
            db.session.add(default_user)
            db.session.commit()
            print("Created default user: testuser / password (stored insecurely)")


# --- Helper Function to Safely Get Channel ID ---
def _get_channel_id(row, potential_names=['channel_id_string', 'channel_id', 'Channel ID', 'Channel']):
    """Safely gets the channel ID from a DataFrame row using potential column names."""
    for name in potential_names:
        if name in row.index:
            return row[name]
    # If none found, raise an error indicating the missing column and available columns
    raise KeyError(f"Could not find channel identifier using names {potential_names}. Found columns: {row.index.tolist()}")

# --- Helper Function to Load Parameters ---
def load_optimization_parameters():
    """Loads optimization parameters from Excel files using paths relative to app root."""
    # Construct paths relative to app.root_path
    coverage_file = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CoverageperABCperChannel.xlsx')
    capacity_file = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CapacityPerChannel.xlsx')
    assortment_file = os.path.join(app.root_path, 'data', 'ExcelParameters', 'AssortmentperSubaxeperSignature.xlsx')

    try:
        # Coverage Rules - Use helper function
        app.logger.info(f"Loading coverage rules from: {coverage_file}")
        coverage_df = pd.read_excel(coverage_file)
        app.logger.info(f"Coverage file columns: {coverage_df.columns.tolist()}")
        coverage_rules = [
            CoverageDaysRule(
                channel_id=_get_channel_id(row), # Use helper
                abc_class=row['abc_class'],
                coverage_days=row['coverage_days']
            ) for index, row in coverage_df.iterrows()
        ]
        app.logger.info(f"Loaded {len(coverage_rules)} coverage rules.")

        # Outlet SKU Capacity Rules - Use helper function
        app.logger.info(f"Loading capacity rules from: {capacity_file}")
        outlet_capacity_df = pd.read_excel(capacity_file)
        app.logger.info(f"Capacity file columns: {outlet_capacity_df.columns.tolist()}")
        outlet_capacity_rules = [
            OutletSKUCapacityRule(
                channel_id=_get_channel_id(row), # Use helper
                division=row['division'],
                axe=row['axe'],
                max_skus=row['max_skus']
            ) for index, row in outlet_capacity_df.iterrows() # Removed outlet filter for now, apply inside solver if needed based on channel_type from DB
              # if row['channel_type'] == 'outlet' # Filter might cause issues if column missing, handle in solver
        ]
        app.logger.info(f"Loaded {len(outlet_capacity_rules)} outlet capacity rules.")

        # Outlet Assortment Rules - Assumes correct columns exist
        app.logger.info(f"Loading assortment rules from: {assortment_file}")
        outlet_assortment_df = pd.read_excel(assortment_file)
        app.logger.info(f"Assortment file columns: {outlet_assortment_df.columns.tolist()}")
        outlet_assortment_rules = [
            OutletAssortmentRule(
                metier=row['metier'],
                subaxis=row['subaxis'],
                brand=row['brand'],
                max_skus=row['max_skus']
            ) for index, row in outlet_assortment_df.iterrows()
        ]
        app.logger.info(f"Loaded {len(outlet_assortment_rules)} assortment rules.")

        # Restricted Brands (Hardcoded for now)
        restricted_brands = ['BrandB'] # Example

        return OptimizationParameters(
            coverage_days_rules=coverage_rules,
            outlet_sku_capacity_rules=outlet_capacity_rules,
            outlet_assortment_rules=outlet_assortment_rules,
            restricted_brands_for_donation=restricted_brands
        )
    except FileNotFoundError as e:
        app.logger.error(f"Parameter file not found: {e.filename}")
        raise ValueError(f"Parameter file missing: {e.filename}")
    except KeyError as e: # Catch specific KeyError from _get_channel_id or direct access
        app.logger.error(f"Error loading parameters: Missing expected column '{e}' in one of the Excel files.")
        # The error message from _get_channel_id already includes details
        if "Could not find channel identifier" in str(e):
             raise ValueError(f"Error parsing parameter files: {str(e)}")
        else: # General KeyError
             raise ValueError(f"Error parsing parameter files: Missing column '{e}'")
    except Exception as e:
        app.logger.error(f"Error loading parameters: {e}")
        # Include original exception type and message for better debugging
        raise ValueError(f"Error parsing parameter files: {type(e).__name__} - {str(e)}")


# --- Helper Function to Load Demand ---
def load_demand_dict():
    """Loads demand data from sellout.csv and formats it using paths relative to app root."""
    sellout_df = None # Initialize in case of early error
    # Construct path relative to app.root_path
    sellout_path = os.path.join(app.root_path, 'data', 'InputData', 'sellout.csv')

    try:
        app.logger.info(f"Loading demand data from: {sellout_path}")
        sellout_df = pd.read_csv(sellout_path)
        app.logger.info(f"Demand file columns: {sellout_df.columns.tolist()}")

        # Find the actual channel ID column name
        channel_col_name = None
        potential_names = ['channel_id_string', 'channel_id', 'Channel ID', 'Channel']
        for name in potential_names:
            if name in sellout_df.columns:
                channel_col_name = name
                break
        
        if not channel_col_name:
             raise KeyError(f"Could not find channel identifier column in sellout.csv using names {potential_names}. Found columns: {sellout_df.columns.tolist()}")

        # Check for other required columns
        if 'ean' not in sellout_df.columns:
             raise KeyError(f"Missing 'ean' column in sellout.csv. Found columns: {sellout_df.columns.tolist()}")
        if 'weekly_demand' not in sellout_df.columns:
             raise KeyError(f"Missing 'weekly_demand' column in sellout.csv. Found columns: {sellout_df.columns.tolist()}")

        # Convert to dictionary format: {(ean, channel_id): weekly_demand}
        demand_dict = sellout_df.set_index(['ean', channel_col_name])['weekly_demand'].to_dict()
        app.logger.info(f"Loaded {len(demand_dict)} demand entries.")
        return demand_dict
    except FileNotFoundError:
        app.logger.warning("sellout.csv not found, using empty demand dictionary.")
        return {}
    except KeyError as e:
        # Log the specific KeyError message (which now includes details about missing channel ID or other columns)
        app.logger.error(f"Error loading demand data: {str(e)}")
        raise ValueError(f"Error parsing demand file: {str(e)}")
    except Exception as e:
        app.logger.error(f"Error loading demand data: {type(e).__name__} - {str(e)}")
        return {} # Return empty on other errors


# --- New Endpoint for Auto-Allocation ---
@app.route('/api/auto_allocate', methods=['POST'])
# @jwt_required() # Add authentication if needed
def auto_allocate_endpoint():
    """
    Triggers the allocation solver using current data and parameters.
    Clears previous allocations and saves the new results.
    """
    try:
        # 1. Load Data
        products_list = [p.to_dict() for p in Product.query.all()]
        channels_list = [c.to_dict() for c in Channel.query.all()]
        inventory_list = [i.to_dict() for i in Inventory.query.all()]

        if not products_list or not channels_list or not inventory_list:
             return jsonify({'error': 'Missing essential data (products, channels, or inventory)'}), 400

        # Create and validate channels_df
        temp_channels_df = pd.DataFrame(channels_list)
        # The 'id' column from to_dict() actually holds the channel_id_string
        if 'id' not in temp_channels_df.columns:
            app.logger.error(f"Missing 'id' column (containing channel_id_string) in Channel data. Columns found: {temp_channels_df.columns.tolist()}")
            return jsonify({'error': "Internal data error: Channel ID missing."}), 500
        required_channel_cols = ['channel_type'] # Columns needed by solver (capacity check removed as per comment)
        for col in required_channel_cols:
             if col not in temp_channels_df.columns:
                  app.logger.error(f"Missing '{col}' column in Channel data. Columns found: {temp_channels_df.columns.tolist()}")
                  # Allow capacity to be missing/null for outlets, handle inside solver
                  # return jsonify({'error': f"Internal data error: Channel column '{col}' missing."}), 500
                  pass # Relaxing this check, solver handles missing capacity
        # Set index using the 'id' column which contains the string identifier
        channels_df = temp_channels_df.set_index('id')

        # Create and validate products_df
        temp_products_df = pd.DataFrame(products_list)
        if 'ean' not in temp_products_df.columns:
             app.logger.error(f"Missing 'ean' column in Product data. Columns found: {temp_products_df.columns.tolist()}")
             return jsonify({'error': "Internal data error: Product EAN missing."}), 500
        # Add checks for other columns needed by solver if necessary
        required_product_cols = ['brand', 'division', 'axe', 'subaxis', 'metier', 'abc_class']
        for col in required_product_cols:
             if col not in temp_products_df.columns:
                  app.logger.warning(f"Optional product column '{col}' missing. Solver might behave unexpectedly if rules depend on it.")
                  # Don't fail, but log a warning
                  # return jsonify({'error': f"Internal data error: Product column '{col}' missing."}), 500
        products_df = temp_products_df.set_index('ean')

        # Inventory DataFrame validation
        inventory_df = pd.DataFrame(inventory_list)
        # Check for 'product_ean' as defined in Inventory.to_dict()
        if 'product_ean' not in inventory_df.columns or 'quantity' not in inventory_df.columns:
             app.logger.error(f"Missing required columns in Inventory data. Columns found: {inventory_df.columns.tolist()}")
             return jsonify({'error': "Internal data error: Inventory columns missing."}), 500


        demand_dict = load_demand_dict()
        parameters = load_optimization_parameters()

        # 2. Run Solver
        app.logger.info("Running allocation solver...")
        model, status, allocation_results = optimize_allocation(
            products_df=products_df,
            channels_df=channels_df,
            inventory_df=inventory_df,
            demand_dict=demand_dict,
            parameters=parameters
        )
        app.logger.info(f"Solver finished with status: {status}")

        # 3. Process Results
        if status != 'Optimal':
            # Optionally save the model file for debugging non-optimal results
            # model.writeLP("failed_allocation_model.lp")
            return jsonify({'error': f'Solver did not find an optimal solution. Status: {status}'}), 500

        # --- Save Results to Database ---
        try:
            # Start transaction
            # Clear existing allocations
            num_deleted = Allocation.query.delete()
            app.logger.info(f"Cleared {num_deleted} previous allocation entries.")
            # db.session.flush() # Ensure delete happens before insert if needed by DB constraints

            # Add new allocations
            for alloc_res in allocation_results:
                # Ensure keys match the Allocation model fields and solver output dict
                new_alloc = Allocation(
                    product_ean=alloc_res['product_sku'], # Solver uses 'product_sku' which is EAN here
                    channel_id_string=alloc_res['channel_id'], # Solver uses 'channel_id' which is channel_id_string here
                    quantity=alloc_res['quantity'],
                    allocation_date=datetime.now()
                    # Add run_id if AllocationRun is implemented
                )
                db.session.add(new_alloc)

            # Optional: Update AllocationRun status
            # latest_run = AllocationRun.query.order_by(AllocationRun.run_date.desc()).first()
            # if latest_run:
            #     latest_run.status = 'COMPLETED' # Or 'OPTIMAL'
            #     latest_run.completion_date = datetime.now()
            # else: # Or create a new run entry
            #     new_run = AllocationRun(status='COMPLETED', run_date=datetime.now())
            #     db.session.add(new_run)

            db.session.commit()
            app.logger.info(f"Successfully saved {len(allocation_results)} new allocation entries.")
            return jsonify({'message': 'Auto-allocation successful!', 'status': status, 'allocations_created': len(allocation_results)}), 200

        except Exception as db_error:
            db.session.rollback()
            app.logger.error(f"Database error saving allocation results: {db_error}")
            return jsonify({'error': f'Database error saving results: {str(db_error)}'}), 500

    except ValueError as ve: # Catch errors from parameter/demand loading
        app.logger.error(f"Value error during auto-allocation setup: {ve}")
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        app.logger.error(f"Unexpected error during auto-allocation: {e}")
        # Optionally rollback if a transaction was started earlier, though it's safer within the DB block
        # db.session.rollback()
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


# --- New Endpoint for Saving Manual Allocations ---
@app.route('/api/save_allocations', methods=['POST'])
# @jwt_required() # Add authentication if needed
def save_manual_allocations():
    """
    Receives manual allocation changes from the frontend and updates the database.
    """
    try:
        changes = request.get_json()
        if not isinstance(changes, list):
            return jsonify({'error': 'Invalid data format. Expected a list of changes.'}), 400

        app.logger.info(f"Received {len(changes)} allocation updates to save.")

        # Process changes within a transaction
        try:
            # Keep track of EANs processed to avoid duplicate deletes if multiple items map to same EAN
            processed_eans = set()

            for change in changes:
                ean = change.get('ean')
                new_channels = change.get('channels')

                if not ean or not isinstance(new_channels, dict):
                    app.logger.warning(f"Skipping invalid change item: {change}")
                    continue # Skip invalid entries

                # Find the product to ensure it exists (optional but good practice)
                product = Product.query.filter_by(ean=ean).first()
                if not product:
                    app.logger.warning(f"Product with EAN {ean} not found. Skipping save for this item.")
                    continue

                # Delete existing allocations for this product EAN only once per request
                if ean not in processed_eans:
                    Allocation.query.filter_by(product_ean=ean).delete()
                    processed_eans.add(ean)
                    # db.session.flush() # Optional: flush if needed before inserts

                # Create new allocation entries based on the received channels data
                for channel_id_str, quantity in new_channels.items():
                    quantity_int = int(quantity or 0) # Ensure integer, default to 0
                    if quantity_int > 0: # Only save allocations with quantity > 0
                         # Verify channel exists (optional but good practice)
                         channel = Channel.query.filter_by(channel_id_string=channel_id_str).first()
                         if not channel:
                             app.logger.warning(f"Channel '{channel_id_str}' not found. Skipping allocation for EAN {ean}.")
                             continue

                         new_alloc = Allocation(
                             product_ean=ean,
                             channel_id_string=channel_id_str,
                             quantity=quantity_int,
                             allocation_date=datetime.now()
                             # Add run_id if needed, perhaps link to a 'manual' run type
                         )
                         db.session.add(new_alloc)

            db.session.commit()
            app.logger.info("Successfully saved manual allocation changes.")
            return jsonify({'message': 'Allocations saved successfully!'}), 200

        except Exception as db_error:
            db.session.rollback()
            app.logger.error(f"Database error saving manual allocations: {db_error}")
            return jsonify({'error': f'Database error saving changes: {str(db_error)}'}), 500

    except Exception as e:
        app.logger.error(f"Error processing save request: {e}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


# --- New Endpoint for Frontend Data ---
@app.route('/api/allocation_data', methods=['GET'])
# @jwt_required() # Temporarily disable auth for easier testing if needed
def get_allocation_data():
    """
    Fetches and formats allocation data for the new frontend UI.
    """
    try:
        # --- Check if initial allocation needs to be run ---
        allocation_count = Allocation.query.count()
        if allocation_count == 0:
            app.logger.info("No existing allocations found. Running initial auto-allocation...")
            try:
                # Call the auto-allocation logic directly (or trigger the endpoint internally)
                # Reusing the logic here to avoid circular requests
                # 1. Load Data for allocation
                products_list_alloc = [p.to_dict() for p in Product.query.all()]
                channels_list_alloc = [c.to_dict() for c in Channel.query.all()]
                inventory_list_alloc = [i.to_dict() for i in Inventory.query.all()]

                if not products_list_alloc or not channels_list_alloc or not inventory_list_alloc:
                     app.logger.error("Cannot run initial allocation: Missing essential data.")
                     # Proceed without allocation for now, frontend will show empty state
                else:
                    # Create and validate DataFrames for allocation
                    temp_channels_df_alloc = pd.DataFrame(channels_list_alloc)
                    # Check for 'id' column (containing channel_id_string)
                    if 'id' in temp_channels_df_alloc.columns:
                        # Set index using the 'id' column
                        channels_df_alloc = temp_channels_df_alloc.set_index('id')
                    else:
                        raise ValueError("Initial alloc failed: channel id column missing")

                    temp_products_df_alloc = pd.DataFrame(products_list_alloc)
                    if 'ean' in temp_products_df_alloc.columns:
                        products_df_alloc = temp_products_df_alloc.set_index('ean')
                    else:
                          raise ValueError("Initial alloc failed: ean missing")

                    inventory_df_alloc = pd.DataFrame(inventory_list_alloc)
                    # Check for 'product_ean' as defined in Inventory.to_dict()
                    if 'product_ean' not in inventory_df_alloc.columns or 'quantity' not in inventory_df_alloc.columns:
                         raise ValueError("Initial alloc failed: inventory columns missing")

                    demand_dict_alloc = load_demand_dict()
                    parameters_alloc = load_optimization_parameters()

                    # 2. Run Solver for initial allocation
                    model_alloc, status_alloc, allocation_results_alloc = optimize_allocation(
                        products_df=products_df_alloc,
                        channels_df=channels_df_alloc,
                        inventory_df=inventory_df_alloc,
                        demand_dict=demand_dict_alloc,
                        parameters=parameters_alloc
                    )
                    app.logger.info(f"Initial allocation solver finished with status: {status_alloc}")

                    # 3. Save initial results if optimal
                    if status_alloc == 'Optimal':
                        try:
                            for alloc_res in allocation_results_alloc:
                                new_alloc = Allocation(
                                    product_ean=alloc_res['product_sku'],
                                    channel_id_string=alloc_res['channel_id'],
                                    quantity=alloc_res['quantity'],
                                    allocation_date=datetime.now()
                                )
                                db.session.add(new_alloc)
                            db.session.commit()
                            app.logger.info(f"Successfully saved {len(allocation_results_alloc)} initial allocation entries.")
                        except Exception as db_err_alloc:
                            db.session.rollback()
                            app.logger.error(f"Database error saving initial allocations: {db_err_alloc}")
                            # Proceed without allocation, frontend will show empty state
                    else:
                         app.logger.warning(f"Initial allocation did not find optimal solution (Status: {status_alloc}). Proceeding without initial allocation.")

            except Exception as initial_alloc_err:
                 app.logger.error(f"Error during initial auto-allocation: {initial_alloc_err}")
                 # Ensure rollback if any DB operations started but failed
                 db.session.rollback()
                 # Proceed without allocation, frontend will show empty state

        # --- Proceed with fetching data for the frontend ---
        # 1. Get all channels to know the columns needed
        channels = Channel.query.all()
        channel_ids = [c.channel_id_string for c in channels]

        # 2. Get all products with their inventory preloaded
        products = Product.query.options(joinedload(Product.inventories)).all()

        # 3. Get all current allocations (consider filtering by latest run_id if implemented)
        # For now, fetch all allocations and group them
        allocations = Allocation.query.all()
        allocations_by_product_ean = defaultdict(lambda: defaultdict(int))
        for alloc in allocations:
            allocations_by_product_ean[alloc.product_ean][alloc.channel_id_string] += alloc.quantity

        # 4. Format data for frontend
        frontend_data = []
        for prod in products:
            total_units = sum(inv.quantity for inv in prod.inventories)
            # Determine stockOrigin (simplistic: use status of first inventory item)
            stock_origin = prod.inventories[0].status if prod.inventories else 'Unknown'

            # Get allocated quantities for this product
            product_allocations = allocations_by_product_ean.get(prod.ean, {})

            # Calculate total allocated and accuracy
            total_allocated = sum(product_allocations.values())
            alloc_accu_percent = 0
            if total_units > 0:
                # Cap accuracy at 100% in case of over-allocation issues
                alloc_accu_percent = min(100, round((total_allocated / total_units) * 100))
            alloc_accu = f"{alloc_accu_percent}%"

            # Build the channel dictionary for the frontend
            channel_data = {chan_id: product_allocations.get(chan_id, 0) for chan_id in channel_ids}

            frontend_data.append({
                'id': prod.id, # Use DB id or EAN? Frontend uses a simple counter id. Let's use DB id.
                'div': prod.division,
                'signature': prod.brand,
                'ean': prod.ean,
                'hierarchy': prod.hierarchy,
                'photo': prod.photo, # Assuming photo stores filename like 'ap_cuir.jpg'
                'name': prod.name,
                'units': total_units,
                'stockOrigin': stock_origin,
                'allocAccu': alloc_accu,
                'channels': channel_data,
                'cogs': prod.cogs * total_units if prod.cogs and total_units else 0 # Calculate total COGS for the product inventory
            })

        # Optional: Get overall allocation status (e.g., from latest AllocationRun)
        latest_run = AllocationRun.query.order_by(AllocationRun.run_date.desc()).first()
        overall_status = latest_run.status if latest_run else "UNKNOWN"

        return jsonify({
            "allocationData": frontend_data,
            "channelColumns": channel_ids, # Send channel names for dynamic table header
            "allocationStatus": overall_status
        })

    except Exception as e:
        app.logger.error(f"Error fetching allocation data: {e}") # Log the error
        return jsonify({'error': f"Failed to fetch allocation data: {str(e)}"}), 500


# --- Existing Endpoints ---

if __name__ == '__main__':
    with app.app_context():
        # Create tables first if they don't exist
        db.create_all()

        # Ensure a default user exists for testing if the table is empty
        if not User.query.first():
            # WARNING: Storing plain text password - highly insecure!
            # In a real app, use password hashing (e.g., Werkzeug's generate_password_hash)
            # Also, the User model expects 'password_hash', not 'password'.
            # For this basic setup, let's adjust the User model or store a dummy hash.
            # Simpler for now: Add a plain 'password' field to User model (less ideal)
            # OR store something in password_hash. Let's store the plain password there for now.
            # Re-emphasizing: THIS IS NOT SECURE FOR REAL APPLICATIONS.
            default_user = User(username='testuser', email='test@example.com', password_hash='password') # Store plain pwd in hash field for demo
            db.session.add(default_user)
            db.session.commit()
            print("Created default user: testuser / password (stored insecurely)")

        # Optional: Add sample data if tables are empty for testing
        if not Product.query.first():
            print("Adding sample data...")
            # Add sample channels (matching frontend example)
            sample_channel_names = ['Outlet', 'Giverny', 'Village', 'Corbeil', 'F&F', 'Liquidation', 'Donation']
            for name in sample_channel_names:
                chan_type = 'outlet' if name in ['Outlet', 'Giverny', 'Village', 'Corbeil'] else \
                            'donation' if name == 'Donation' else \
                            'liquidation' if name == 'Liquidation' else \
                            'store' # Default or F&F type? Let's use store for F&F
                db.session.add(Channel(channel_id_string=name, name=name, channel_type=chan_type, country='FR'))

            # Add sample products (matching frontend example)
            sample_products_fe = [
                {'div': 'LLD', 'signature': 'Armani Prive', 'ean': '3614273014588', 'hierarchy': 'Perfumes', 'photo': 'ap_cuir.jpg', 'name': 'AP CUIR AMETHYSTE EDP V50ML', 'units': 500, 'stockOrigin': 'Obs', 'cogs_per_unit': 50},
                {'div': 'PPD', 'signature': "L'Oreal Professionnel", 'ean': '3474636645800', 'hierarchy': 'Hair Care', 'photo': 'lp_serioxyl.jpg', 'name': 'LP SERIOXYL DENSERHAIR 90ML', 'units': 4500, 'stockOrigin': 'Excess', 'cogs_per_unit': 15},
                # Add more sample products if needed...
            ]
            for p_data in sample_products_fe:
                prod = Product(
                    ean=p_data['ean'], name=p_data['name'], brand=p_data['signature'],
                    division=p_data['div'], hierarchy=p_data['hierarchy'], photo=p_data['photo'],
                    cogs=p_data['cogs_per_unit'] # Store COGS per unit
                )
                db.session.add(prod)
                # Add corresponding inventory
                inv = Inventory(product_ean=p_data['ean'], quantity=p_data['units'], status=p_data['stockOrigin'], country='FR')
                db.session.add(inv)

            db.session.commit()
            print("Sample data added.")


    app.run(debug=True)
