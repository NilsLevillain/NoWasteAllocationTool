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
from backend.solver import optimize_allocation, calculate_abc_classification_and_new_skus # Import necessary functions
from backend.schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule # Import parameter schemas
from backend.config import Config
from backend.utils import (
    load_products_df, load_channels_df, load_inventory_df, load_demand_dict,
    load_existing_stock_dict, load_optimization_rules, _get_channel_id_from_row
)

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

# --- New Endpoint for Auto-Allocation ---
@app.route('/api/auto_allocate', methods=['POST'])
# @jwt_required() # Add authentication if needed
def auto_allocate_endpoint():
    """
    Triggers the allocation solver using current data and parameters from files.
    Clears previous allocations and saves the new results.
    """
    try:
        app.logger.info("--- Starting Auto-Allocation from Files ---")

        # Define file paths
        masterdata_file_path = os.path.join(app.root_path, 'data', 'InputData', 'masterdata.csv')
        inventory_file_path = os.path.join(app.root_path, 'data', 'InputData', 'bad_stock_inventory.csv')
        channellist_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'ChannelList.xlsx')
        sellout_file_path = os.path.join(app.root_path, 'data', 'InputData', 'sellout.csv')
        coverage_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CoverageperABCperChannel.xlsx')
        capacity_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CapacityPerChannel.xlsx')
        assortment_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'AssortmentperSubaxeperSignature.xlsx')
        push_new_sku_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'PushNewSKU.xlsx')
        instore_stock_file_path = os.path.join(app.root_path, 'data', 'InputData', 'in_store_inventory.csv')
        intransit_stock_file_path = os.path.join(app.root_path, 'data', 'InputData', 'stock_in_transit.csv')

        # 1. Load Data directly from files using backend.utils
        app.logger.info("Loading products_df from file...")
        products_df = load_products_df(
            masterdata_file_path,
            # Assuming default column names in load_products_df match masterdata.csv
            # ean_col='product_gtin', brand_col='operational_signature_label', etc.
        )
        if products_df.empty:
            app.logger.error("Failed to load products or products data is empty.")
            return jsonify({'error': 'Failed to load products data from file.'}), 500
        # Ensure index is 'ean' and it's a string
        if products_df.index.name != 'ean':
            if 'ean' in products_df.columns:
                products_df = products_df.set_index('ean')
            else: # If 'ean' is not even a column after loading (should be handled by load_products_df)
                 app.logger.error("EAN column not found in loaded products_df.")
                 return jsonify({'error': 'EAN column missing in products data.'}), 500
        products_df.index = products_df.index.astype(str)


        app.logger.info("Loading channels_df from file...")
        channels_df = load_channels_df(channellist_file_path)
        if channels_df.empty:
            app.logger.error("Failed to load channels or channels data is empty.")
            return jsonify({'error': 'Failed to load channels data from file.'}), 500
        # Ensure index is 'id' (channel_id_string) and it's a string
        if channels_df.index.name != 'id': # load_channels_df sets index to 'id'
            app.logger.error("Channel DataFrame not indexed by 'id' as expected.")
            return jsonify({'error': 'Channel data malformed after load.'}), 500
        channels_df.index = channels_df.index.astype(str)


        app.logger.info("Loading inventory_df from file...")
        inventory_df = load_inventory_df(inventory_file_path) # This returns a DataFrame with 'product_ean' and 'quantity'
        if inventory_df.empty:
            app.logger.warning("Inventory data is empty. Allocations might be zero if no stock.")
        # inventory_df is not indexed by default by load_inventory_df, it has 'product_ean' column

        app.logger.info("Loading demand_dict from file...")
        demand_dict = load_demand_dict(sellout_file_path)

        app.logger.info("Loading optimization rules from files...")
        coverage_rules = load_optimization_rules(
            coverage_file_path, CoverageDaysRule,
            channel_id='channel_id', abc_class='abc_class', coverage_days='coverage_days'
        )
        outlet_capacity_rules = load_optimization_rules(
            capacity_file_path, OutletSKUCapacityRule,
            channel_id='channel_id', division='operational_division',
            axe='operational_axe_label', max_skus='max_skus'
        )
        outlet_assortment_rules = load_optimization_rules(
            assortment_file_path, OutletAssortmentRule,
            metier='operational_metier_label', subaxis='operational_sub_axe_label',
            brand='operational_signature_label', max_skus='max_skus'
        )
        push_new_sku_rules = load_optimization_rules(
            push_new_sku_file_path, PushNewSKURule,
            division='operational_division', subaxis='operational_sub_axe_label',
            push_quantity='Push Quantity if New SKU'
        )
        
        app.logger.info("Creating OptimizationParameters...")
        parameters = OptimizationParameters(
            seasonality_coefficient=1.0,  # Hardcoded seasonality_coefficient
            coverage_days_rules=coverage_rules,
            outlet_sku_capacity_rules=outlet_capacity_rules,
            outlet_assortment_rules=outlet_assortment_rules,
            push_new_sku_rules=push_new_sku_rules,
            restricted_brands_for_donation=['BrandB'] # Example, make configurable if needed
        )

        app.logger.info("Loading existing_stock_dict from files...")
        existing_stock_dict = load_existing_stock_dict(
            in_store_fp=instore_stock_file_path,
            in_transit_fp=intransit_stock_file_path
        )
        
        app.logger.info("Calculating ABC classification...")
        raw_sellout_df = pd.read_csv(sellout_file_path)
        raw_sellout_df['barcode'] = raw_sellout_df['barcode'].astype(str) # Ensure EAN is string for matching
        
        all_channel_ids_list = channels_df.index.tolist()
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            sellout_df=raw_sellout_df,
            product_master_df=products_df, # Already indexed by EAN (string)
            all_channel_ids=all_channel_ids_list, # List of string channel IDs
            sellout_ean_col='barcode', 
            sellout_channel_col='store_code',
            sellout_qty_col='total_items_weekly'
        )
        app.logger.info(f"Calculated ABC map for {len(product_channel_abc_map)} product-channel pairs.")

        # 2. Run Solver
        app.logger.info("Running allocation solver with file-loaded data...")
        model, status, allocation_results = optimize_allocation(
            products_df=products_df,
            channels_df=channels_df,
            inventory_df=inventory_df, # This is the DataFrame with 'product_ean' and 'quantity'
            demand_dict=demand_dict,
            parameters=parameters,
            existing_stock_dict=existing_stock_dict,
            product_channel_abc_map=product_channel_abc_map
        )
        app.logger.info(f"Solver finished with status: {status}")

        # 3. Process Results
        if status != 'Optimal':
            app.logger.error(f'Solver did not find an optimal solution. Status: {status}')
            # model.writeLP("failed_allocation_model_endpoint.lp") # Optional: save model for debugging
            return jsonify({'error': f'Solver did not find an optimal solution. Status: {status}'}), 500

        # --- Save Results to Database ---
        try:
            with db.session.begin_nested(): # Use nested transaction for safety
                num_deleted = Allocation.query.delete()
                app.logger.info(f"Cleared {num_deleted} previous allocation entries.")
                
                for alloc_res in allocation_results:
                    new_alloc = Allocation(
                        product_ean=str(alloc_res['product_sku']), 
                        channel_id_string=str(alloc_res['channel_id']), 
                        quantity=int(alloc_res['quantity']),
                        allocation_date=datetime.now()
                    )
                    db.session.add(new_alloc)
            db.session.commit()
            app.logger.info(f"Successfully saved {len(allocation_results)} new allocation entries.")
            response_data = {'message': 'Auto-allocation successful!', 'status': status, 'allocations_created': len(allocation_results)}
            app.logger.info(f"Returning from auto_allocate_endpoint (success): {response_data}")
            return jsonify(response_data), 200

        except Exception as db_error:
            db.session.rollback()
            app.logger.error(f"Database error saving allocation results: {db_error}", exc_info=True)
            error_response_data = {'error': f'Database error saving results: {str(db_error)}'}
            app.logger.info(f"Returning from auto_allocate_endpoint (db_error): {error_response_data}")
            return jsonify(error_response_data), 500

    except FileNotFoundError as fnf_error:
        app.logger.error(f"Data file not found during auto_allocate_endpoint: {fnf_error}", exc_info=True)
        error_response_data = {'error': f"A required data file was not found: {str(fnf_error)}"}
        app.logger.info(f"Returning from auto_allocate_endpoint (fnf_error): {error_response_data}")
        return jsonify(error_response_data), 500
    except ValueError as ve: 
        app.logger.error(f"Value error during auto-allocation setup: {ve}", exc_info=True)
        error_response_data = {'error': f"Data integrity or configuration error: {str(ve)}"}
        app.logger.info(f"Returning from auto_allocate_endpoint (value_error): {error_response_data}")
        return jsonify(error_response_data), 400
    except Exception as e:
        app.logger.error(f"Unexpected error during auto-allocation: {e}", exc_info=True)
        error_response_data = {'error': f'An unexpected error occurred: {str(e)}'}
        app.logger.info(f"Returning from auto_allocate_endpoint (general_error): {error_response_data}")
        return jsonify(error_response_data), 500


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
    Fetches and formats allocation data for the new frontend UI,
    loading directly from data files.
    """
    try:
        app.logger.info("Loading allocation data directly from files...")

        # 1. Define file paths
        masterdata_file_path = os.path.join(app.root_path, 'data', 'InputData', 'masterdata.csv')
        inventory_file_path = os.path.join(app.root_path, 'data', 'InputData', 'bad_stock_inventory.csv')
        channellist_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'ChannelList.xlsx')

        # 2. Load channels
        channels_df = load_channels_df(channellist_file_path) 
        if channels_df.empty:
            app.logger.warning("Channel data is empty. Frontend might not display columns correctly.")
            channel_ids = []
        else:
            channel_ids = channels_df.index.tolist()

        # 3. Load products
        products_df = load_products_df(masterdata_file_path) 
        if products_df.empty:
            app.logger.warning("Product master data is empty.")
            return jsonify({
                "allocationData": [],
                "channelColumns": channel_ids,
                "allocationStatus": "Displaying File Data - No Products"
            })

        # 4. Load inventory
        inventory_df = load_inventory_df(inventory_file_path)
        if inventory_df.empty:
            app.logger.warning("Inventory data is empty. Product units will be zero.")
        
        # 5. Merge product and inventory data
        if products_df.index.name == 'ean':
            products_df_to_merge = products_df.reset_index()
        else: 
            products_df_to_merge = products_df.copy()
            if 'ean' not in products_df_to_merge.columns:
                 app.logger.error("EAN column missing in products_df for merge.")
                 products_df_to_merge['ean'] = products_df_to_merge.index
        
        # Ensure EAN columns are of string type before merging
        products_df_to_merge['ean'] = products_df_to_merge['ean'].astype(str)
        inventory_df['product_ean'] = inventory_df['product_ean'].astype(str)

        merged_df = pd.merge(products_df_to_merge, inventory_df, left_on='ean', right_on='product_ean', how='left')
        merged_df['quantity'] = merged_df['quantity'].fillna(0).astype(int)

        # 6. Format data for frontend
        frontend_data = []
        for _, row in merged_df.iterrows():
            total_units = row.get('quantity', 0)
            
            div = row.get('division', 'to come later')
            signature = row.get('brand', 'to come later') 
            ean_val = row.get('ean', 'to come later') 
            
            hierarchy = "to come later" 
            photo = "to come later"     
            name = "to come later"      
            stock_origin = "to come later" 
            cogs_value = 2.0

            channel_data = {chan_id: 0 for chan_id in channel_ids}

            frontend_data.append({
                'id': ean_val, 
                'div': div,
                'signature': signature,
                'ean': ean_val,
                'hierarchy': hierarchy,
                'photo': photo,
                'name': name,
                'units': total_units,
                'stockOrigin': stock_origin,
                'allocAccu': "0%", 
                'channels': channel_data,
                'cogs': cogs_value * total_units 
            })

        return jsonify({
            "allocationData": frontend_data,
            "channelColumns": channel_ids,
            "allocationStatus": "Displaying File Data"
        })

    except FileNotFoundError as fnf_error:
        app.logger.error(f"Data file not found during /api/allocation_data: {fnf_error}")
        return jsonify({'error': f"Failed to load data: {str(fnf_error)}"}), 500
    except ValueError as val_error: 
        app.logger.error(f"Data loading error during /api/allocation_data: {val_error}")
        return jsonify({'error': f"Data integrity issue: {str(val_error)}"}), 500
    except Exception as e:
        app.logger.error(f"Error fetching allocation data from files: {e}", exc_info=True) 
        return jsonify({'error': f"Failed to fetch allocation data: {str(e)}"}), 500


# --- Existing Endpoints ---

if __name__ == '__main__':
    with app.app_context():
        # Create tables first if they don't exist
        db.drop_all()
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
            for name_channel in sample_channel_names: # Renamed variable to avoid conflict
                chan_type = 'outlet' if name_channel in ['Outlet', 'Giverny', 'Village', 'Corbeil'] else \
                            'donation' if name_channel == 'Donation' else \
                            'liquidation' if name_channel == 'Liquidation' else \
                            'store' 
                db.session.add(Channel(channel_id_string=name_channel, name=name_channel, channel_type=chan_type, country='FR'))

            # Add sample products (matching frontend example)
            sample_products_fe = [
                {'div': 'LLD', 'signature': 'Armani Prive', 'ean': '3614273014588', 'hierarchy': 'Perfumes', 'photo': 'ap_cuir.jpg', 'name': 'AP CUIR AMETHYSTE EDP V50ML', 'units': 500, 'stockOrigin': 'Obs', 'cogs_per_unit': 50},
                {'div': 'PPD', 'signature': "L'Oreal Professionnel", 'ean': '3474636645800', 'hierarchy': 'Hair Care', 'photo': 'lp_serioxyl.jpg', 'name': 'LP SERIOXYL DENSERHAIR 90ML', 'units': 4500, 'stockOrigin': 'Excess', 'cogs_per_unit': 15},
            ]
            for p_data in sample_products_fe:
                prod = Product(
                    ean=p_data['ean'], name=p_data['name'], brand=p_data['signature'],
                    division=p_data['div'], hierarchy=p_data['hierarchy'], photo=p_data['photo'],
                    cogs=p_data['cogs_per_unit'] 
                )
                db.session.add(prod)
                inv = Inventory(product_ean=p_data['ean'], quantity=p_data['units'], status=p_data['stockOrigin'], country='FR')
                db.session.add(inv)

            db.session.commit()
            print("Sample data added.")


    app.run(debug=True)
