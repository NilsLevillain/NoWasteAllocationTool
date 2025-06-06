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

        # Load in-store inventory for ABC classification, similar to solver.py's __main__
        app.logger.info(f"Loading in-store inventory from: {instore_stock_file_path} for ABC/NEW SKU calculation in API.")
        try:
            raw_in_store_inventory_df = pd.read_csv(instore_stock_file_path, dtype={'store_code': str, 'barcode': str})
            app.logger.info(f"Successfully loaded in-store inventory data for API: {raw_in_store_inventory_df.shape[0]} rows.")
        except FileNotFoundError:
            app.logger.error(f"In-store inventory file not found for API: {instore_stock_file_path}. Proceeding with empty DataFrame.")
            raw_in_store_inventory_df = pd.DataFrame(columns=['store_code', 'barcode', 'physical_quantity'])
        except Exception as e:
            app.logger.error(f"Error loading in-store inventory file for API {instore_stock_file_path}: {e}. Proceeding with empty DataFrame.")
            raw_in_store_inventory_df = pd.DataFrame(columns=['store_code', 'barcode', 'physical_quantity'])
        
        all_channel_ids_list = channels_df.index.tolist()
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            sellout_df=raw_sellout_df,
            product_master_df=products_df, # Already indexed by EAN (string)
            all_channel_ids=all_channel_ids_list, # List of string channel IDs
            sellout_ean_col='barcode', 
            sellout_channel_col='store_code',
            sellout_qty_col='total_items_weekly',
            in_store_inventory_df=raw_in_store_inventory_df # Pass the newly loaded DataFrame
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
    loading product/channel/inventory from files and allocations from the database.
    """
    try:
        app.logger.info("Loading base data from files and allocations from DB for /api/allocation_data...")

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
        inventory_df = load_inventory_df(inventory_file_path) # This now loads 'stockOrigin', 'flagExcess6months', 'flagExcess12months'
        if inventory_df.empty:
            app.logger.warning("Inventory data is empty. Product units will be zero.")
        
        # 5. Merge product and inventory data
        # products_df is indexed by 'ean' (string)
        # inventory_df has 'product_ean' (string) and 'plant' (string)
        
        # Reset index of products_df to make 'ean' a column for merging
        products_df_to_merge = products_df.reset_index()
        
        # Ensure EAN columns are of string type for merging
        products_df_to_merge['ean'] = products_df_to_merge['ean'].astype(str)
        inventory_df['product_ean'] = inventory_df['product_ean'].astype(str)
        
        # Perform the merge
        # We expect one row per EAN-Plant combination after this merge
        merged_df = pd.merge(
            products_df_to_merge, 
            inventory_df, 
            left_on='ean', 
            right_on='product_ean', 
            how='left' # Use left merge to keep all products, even if no inventory entry (though unlikely for bad stock)
        )
        
        # Handle cases where there might be no inventory for a product (though for bad stock, this should be rare)
        merged_df['quantity'] = merged_df['quantity'].fillna(0).astype(int)
        merged_df['plant'] = merged_df['plant'].fillna('N/A').astype(str)
        merged_df['stockOrigin'] = merged_df['stockOrigin'].fillna('N/A').astype(str)
        merged_df['flagExcess6months'] = merged_df['flagExcess6months'].fillna(0).astype(int)
        merged_df['flagExcess12months'] = merged_df['flagExcess12months'].fillna(0).astype(int)
        
        # Drop the redundant product_ean column from inventory_df if it exists
        if 'product_ean' in merged_df.columns:
            merged_df.drop(columns=['product_ean'], inplace=True)

        app.logger.debug(f"Merged DF columns after product and inventory merge: {merged_df.columns.tolist()}")
        app.logger.debug(f"Sample of merged_df (first 2 rows):\n{merged_df.head(2).to_string()}")


        # 6. Load current allocations from database
        app.logger.info("Fetching allocations from database...")
        db_allocations = Allocation.query.all()
        allocations_map = defaultdict(lambda: defaultdict(int))
        for alloc in db_allocations:
            allocations_map[alloc.product_ean][alloc.channel_id_string] = alloc.quantity
        
        app.logger.info(f"Loaded {len(db_allocations)} allocation records from DB, mapped to {len(allocations_map)} EANs.")

        # 7. Format data for frontend
        frontend_data = []
        for _, row in merged_df.iterrows():
            total_units = row.get('quantity', 0) # This is quantity for EAN-Plant from inventory_df merge
            
            # Get product master data fields
            div_val = row.get('div', 'N/A') # from products_df
            signature_val = row.get('signature', 'N/A') # from products_df
            axe_val = row.get('axe', 'N/A') # from products_df
            sub_axe_val = row.get('subAxe', 'N/A') # from products_df
            metier_val = row.get('metier', 'N/A') # from products_df
            ean_val = str(row.get('ean', 'N/A')) # from products_df (was index, now column)
            sku_val = row.get('sku', 'N/A') # from products_df
            description_val = row.get('description', 'N/A') # from products_df
            cogs_value = row.get('cogs', 0.0) # from products_df, default to 0.0

            # Get inventory specific fields (already merged)
            # plant_val is the plant CODE from inventory_df merge
            # stock_origin_val is the plant DESCRIPTION from inventory_df merge (loaded into 'stockOrigin' field by load_inventory_df)
            plant_code_val = str(row.get('plant', 'N/A')) 
            plant_description_val = row.get('stockOrigin', 'N/A') 
            flag6_val = row.get('flagExcess6months', 0) 
            flag12_val = row.get('flagExcess12months', 0) 
            
            # Populate channel_data using db_allocations for this ean_val
            # Allocation is still assumed to be at EAN level for now in the DB model
            product_specific_allocations = allocations_map.get(ean_val, {})
            channel_data = {chan_id: product_specific_allocations.get(chan_id, 0) for chan_id in channel_ids}
            
            # Create a unique ID for the frontend row, combining EAN and Plant CODE
            unique_row_id = f"{ean_val}_{plant_code_val}"

            item_data = {
                'id': unique_row_id,
                'div': div_val,
                'signature': signature_val,
                'axe': axe_val,
                'subAxe': sub_axe_val,
                'metier': metier_val,
                'ean': ean_val,
                'sku': sku_val,
                'description': description_val,
                'units': total_units, 
                'stockOrigin': plant_description_val, # This is the field for the "Stock origin / Plant Description" column
                'flagExcess6months': flag6_val,
                'flagExcess12months': flag12_val,
                'plant': plant_description_val, # This field is used for filtering and should be the description
                'plant_code': plant_code_val, # Keep plant code if needed for other logic, but 'plant' for UI is description
                'allocAccu': "0%", # Frontend calculates this
                'channels': channel_data,
                'cogs': cogs_value * total_units # COGS for the total units of this EAN-Plant
            }
            frontend_data.append(item_data)
            if _ == 0: # Log first item for debugging
                 app.logger.debug(f"First item processed for frontend: {item_data}")


        allocation_status_message = "Displaying Data with DB Allocations"
        if not db_allocations:
            allocation_status_message = "Displaying Data (No Allocations in DB)"
        
        app.logger.info(f"Prepared {len(frontend_data)} items for frontend. Status: {allocation_status_message}")

        return jsonify({
            "allocationData": frontend_data,
            "channelColumns": channel_ids,
            "allocationStatus": allocation_status_message
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

# --- New Endpoint for EAN Deep Dive Data ---
def get_ean_deep_dive_data_logic(ean_code: str):
    """
    Gathers and processes all relevant data for a specific EAN
    to provide a comprehensive view for debugging and understanding allocations.
    """
    app.logger.info(f"--- Starting EAN Deep Dive data gathering for EAN: {ean_code} ---")
    
    data_response = {
        "ean": ean_code,
        "product_info": {},
        "initial_stock": {},
        "channel_performance": [], # List of dicts, one per channel
        "applied_rules": [], # List of dicts, one per channel
        "final_allocation": [], # List of dicts, one per channel
        "solver_constraints_summary": [] # Simplified summary
    }

    # Define file paths (consistent with auto_allocate_endpoint)
    masterdata_file_path = os.path.join(app.root_path, 'data', 'InputData', 'masterdata.csv')
    bad_stock_inventory_file_path = os.path.join(app.root_path, 'data', 'InputData', 'bad_stock_inventory.csv')
    instore_stock_file_path = os.path.join(app.root_path, 'data', 'InputData', 'in_store_inventory.csv')
    intransit_stock_file_path = os.path.join(app.root_path, 'data', 'InputData', 'stock_in_transit.csv')
    sellout_file_path = os.path.join(app.root_path, 'data', 'InputData', 'sellout.csv')
    channellist_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'ChannelList.xlsx')
    # Rule files
    coverage_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CoverageperABCperChannel.xlsx')
    capacity_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'CapacityPerChannel.xlsx')
    assortment_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'AssortmentperSubaxeperSignature.xlsx')
    push_new_sku_file_path = os.path.join(app.root_path, 'data', 'ExcelParameters', 'PushNewSKU.xlsx')

    try:
        # 1. Load Product Master Data
        app.logger.debug(f"Loading product master data from {masterdata_file_path}")
        products_df_full = load_products_df(masterdata_file_path) # Returns df indexed by 'ean'
        if ean_code in products_df_full.index:
            product_series = products_df_full.loc[ean_code]
            data_response["product_info"] = {
                "description": product_series.get('name', 'N/A'), # Assuming 'name' column from load_products_df
                "brand": product_series.get('brand', 'N/A'),
                "division": product_series.get('div', 'N/A'),
                "axe": product_series.get('axe', 'N/A'),
                "sub_axe": product_series.get('subAxe', 'N/A'),
                "metier": product_series.get('metier', 'N/A'),
                "sku": product_series.get('sku', 'N/A'), # Assuming 'sku' is internal_product_code
                # Add other relevant fields from products_df if needed
            }
            app.logger.debug(f"Product info for EAN {ean_code}: {data_response['product_info']}")
        else:
            app.logger.warning(f"EAN {ean_code} not found in product master data.")
            data_response["product_info"] = {"error": "EAN not found in master data."}
            # Do not return early, try to gather other info if possible.
        
        # 2. Load Bad Stock Inventory (Initial stock to allocate for this EAN)
        app.logger.debug(f"Loading bad stock inventory from {bad_stock_inventory_file_path}")
        bad_stock_df_full = load_inventory_df(bad_stock_inventory_file_path) # Returns 'product_ean', 'quantity', 'plant', 'stockOrigin', etc.
        ean_bad_stock_df = bad_stock_df_full[bad_stock_df_full['product_ean'] == ean_code]
        
        if not ean_bad_stock_df.empty:
            total_bad_stock_for_ean = ean_bad_stock_df['quantity'].sum()
            data_response["initial_stock"]["bad_stock_to_allocate"] = int(total_bad_stock_for_ean)
            plant_breakdown = []
            for _, row in ean_bad_stock_df.iterrows():
                plant_breakdown.append({
                    "plant_code": row.get('plant', 'N/A'),
                    "plant_description": row.get('stockOrigin', 'N/A'), # stockOrigin is plant description
                    "quantity": int(row.get('quantity', 0)),
                    "flag_excess_6m": int(row.get('flagExcess6months', 0)),
                    "flag_excess_12m": int(row.get('flagExcess12months', 0))
                })
            data_response["initial_stock"]["bad_stock_plant_breakdown"] = plant_breakdown
            app.logger.debug(f"Bad stock for EAN {ean_code}: Total {total_bad_stock_for_ean}, Breakdown: {plant_breakdown}")
        else:
            data_response["initial_stock"]["bad_stock_to_allocate"] = 0
            data_response["initial_stock"]["bad_stock_plant_breakdown"] = []
            app.logger.debug(f"No bad stock found for EAN {ean_code}.")

        # 3. Load Existing Stock (In-Store and In-Transit)
        app.logger.debug(f"Loading existing stock from {instore_stock_file_path} and {intransit_stock_file_path}")
        # Re-using load_existing_stock_dict logic, then filtering for the EAN
        # This returns a dict of {(ean, channel): quantity}
        existing_stock_dict_full = load_existing_stock_dict(
            in_store_fp=instore_stock_file_path,
            in_transit_fp=intransit_stock_file_path
            # Assuming default column names are handled by load_existing_stock_dict
            # e.g., ean_col='barcode', channel_col='store_code', qty_col='physical_quantity'/'quantity'
        )
        
        ean_existing_channel_stock = []
        total_existing_stock_for_ean = 0
        # Need channel list to iterate through all possible channels
        channels_df_for_stock = load_channels_df(channellist_file_path)
        
        for channel_id_str in channels_df_for_stock.index.tolist():
            stock_qty = existing_stock_dict_full.get((ean_code, channel_id_str), 0)
            if stock_qty > 0: # Only list channels where this EAN has stock
                 ean_existing_channel_stock.append({
                    "channel_id": channel_id_str,
                    "channel_name": channels_df_for_stock.loc[channel_id_str, 'name'] if channel_id_str in channels_df_for_stock.index else channel_id_str,
                    "quantity": int(stock_qty)
                })
            total_existing_stock_for_ean += stock_qty
        
        data_response["initial_stock"]["total_existing_channel_stock"] = int(total_existing_stock_for_ean)
        data_response["initial_stock"]["existing_channel_stock_breakdown"] = ean_existing_channel_stock
        app.logger.debug(f"Existing channel stock for EAN {ean_code}: Total {total_existing_stock_for_ean}, Breakdown: {ean_existing_channel_stock}")

        # 4. Load Channels, Sellout, and Calculate ABC per channel for the EAN
        app.logger.debug(f"Loading channel data from {channellist_file_path}")
        channels_df = load_channels_df(channellist_file_path) # Indexed by 'id' (channel_id_string)
        
        app.logger.debug(f"Loading sellout data from {sellout_file_path}")
        sellout_df_full = pd.read_csv(sellout_file_path, dtype={'barcode': str, 'store_code': str})
        ean_sellout_df = sellout_df_full[sellout_df_full['barcode'] == ean_code]

        app.logger.debug(f"Loading in-store inventory for ABC calculation from {instore_stock_file_path}")
        # This is also used by load_existing_stock_dict, consider optimizing if performance becomes an issue
        # For now, reloading for clarity within this specific data gathering logic.
        in_store_inv_df_for_abc = pd.read_csv(instore_stock_file_path, dtype={'store_code': str, 'barcode': str})

        # Prepare product_master_df for calculate_abc_classification_and_new_skus
        # It needs to be a DataFrame, not a Series, and indexed by EAN.
        # products_df_full is already indexed by EAN. We need just the row for the current ean_code.
        # However, calculate_abc_classification_and_new_skus iterates product_master_df.index.
        # For a single EAN deep dive, we might need to adapt or call it carefully.
        # Let's pass the single-row DataFrame for the specific EAN.
        single_ean_product_master_df = products_df_full[products_df_full.index == ean_code]

        if not single_ean_product_master_df.empty:
            # The calculate_abc_classification_and_new_skus function returns a map for all products in product_master_df.
            # We are interested in the classification of *this* ean_code across all channels.
            # It might be more efficient to extract the logic for a single EAN or process its output.
            # For now, let's call it and then extract the relevant parts.
            # It expects all_channel_ids as a list.
            all_channel_ids_list_for_abc = channels_df.index.tolist()
            
            # Ensure sellout_df passed to ABC has the correct column names expected by the function
            # The function expects sellout_ean_col='barcode', sellout_channel_col='store_code', sellout_qty_col='total_items_weekly'
            # Our ean_sellout_df already has these.
            
            product_channel_abc_map_full = calculate_abc_classification_and_new_skus(
                sellout_df=ean_sellout_df, # Filtered sellout for the EAN
                product_master_df=single_ean_product_master_df, # DF for the single EAN
                all_channel_ids=all_channel_ids_list_for_abc,
                sellout_ean_col='barcode',
                sellout_channel_col='store_code',
                sellout_qty_col='total_items_weekly',
                in_store_inventory_df=in_store_inv_df_for_abc # Full in-store inventory
            )
        else:
            product_channel_abc_map_full = {} # EAN not in master, so no ABC
            app.logger.warning(f"EAN {ean_code} not in product_master_df, ABC map will be empty for it.")


        # Demand dict for the specific EAN
        # load_demand_dict returns {(ean, channel): demand_value}
        # We can filter this for our ean_code.
        demand_dict_full = load_demand_dict(sellout_file_path, ean_col='barcode', channel_col='store_code', demand_qty_col='total_items_weekly')

        for channel_id_str, channel_row in channels_df.iterrows():
            channel_performance_item = {
                "channel_id": channel_id_str,
                "channel_name": channel_row.get('name', channel_id_str),
                "channel_type": channel_row.get('channel_type', 'N/A'),
                "sellout_qty": 0, # Default
                "calculated_demand": 0, # Default
                "abc_class": "N/A" # Default
            }
            
            # Sellout quantity for this EAN in this channel
            # Sum 'total_items_weekly' from ean_sellout_df where store_code matches channel_id_str
            current_channel_sellout = ean_sellout_df[ean_sellout_df['store_code'] == channel_id_str]
            if not current_channel_sellout.empty:
                channel_performance_item["sellout_qty"] = int(current_channel_sellout['total_items_weekly'].sum())
            
            # Calculated demand for this EAN in this channel
            # Assuming seasonality_coefficient = 1.0 for this display, as in OptimizationParameters default
            channel_performance_item["calculated_demand"] = int(demand_dict_full.get((ean_code, channel_id_str), 0))
            
            # ABC Class
            channel_performance_item["abc_class"] = product_channel_abc_map_full.get((ean_code, channel_id_str), 'N/A')
            
            data_response["channel_performance"].append(channel_performance_item)
        app.logger.debug(f"Channel performance for EAN {ean_code}: {data_response['channel_performance']}")

        # 5. Load Rules and Determine Applicability for the EAN
        app.logger.debug(f"Loading optimization rules for EAN {ean_code} deep dive.")
        coverage_rules_list = load_optimization_rules(coverage_file_path, CoverageDaysRule)
        outlet_capacity_rules_list = load_optimization_rules(capacity_file_path, OutletSKUCapacityRule)
        outlet_assortment_rules_list = load_optimization_rules(assortment_file_path, OutletAssortmentRule)
        push_new_sku_rules_list = load_optimization_rules(push_new_sku_file_path, PushNewSKURule)
        
        # Convert rule lists to dictionaries for easier lookup if not already
        # For this deep dive, we'll iterate and match.
        # Product attributes needed for rule matching:
        product_div = data_response["product_info"].get("division", "N/A")
        product_axe = data_response["product_info"].get("axe", "N/A")
        product_sub_axe = data_response["product_info"].get("sub_axe", "N/A")
        product_metier = data_response["product_info"].get("metier", "N/A")
        product_brand = data_response["product_info"].get("brand", "N/A")

        # Placeholder for restricted brands (should come from config or parameters)
        # For now, using the same example as in auto_allocate_endpoint
        restricted_brands_for_donation_set = set(['BrandB'])


        for cp_item in data_response["channel_performance"]: # cp_item is a dict for a channel
            channel_id = cp_item["channel_id"]
            channel_type = cp_item["channel_type"]
            abc_class_in_channel = cp_item["abc_class"]
            
            applied_rules_for_channel = {
                "channel_id": channel_id,
                "coverage_rule": "N/A",
                "push_new_sku_rule": "N/A",
                "outlet_sku_capacity_rule": "N/A",
                "outlet_assortment_rule": "N/A",
                "restricted_brand_donation_rule": "N/A"
            }

            # Coverage Days Rule
            for rule in coverage_rules_list:
                if rule.channel_id == channel_id and rule.abc_class == abc_class_in_channel:
                    # Calculate max allocation based on this rule (simplified for display)
                    # demand_for_calc = cp_item["calculated_demand"] # Already calculated
                    # existing_stock_for_calc = existing_stock_dict_full.get((ean_code, channel_id), 0)
                    # max_alloc_coverage = "N/A"
                    # if demand_for_calc > 0:
                    #     max_alloc_coverage = max(0, (demand_for_calc / 7.0) * rule.coverage_days - existing_stock_for_calc)
                    applied_rules_for_channel["coverage_rule"] = f"Class {abc_class_in_channel}: {rule.coverage_days} days. Max units (approx): Check solver logic."
                    break
            
            # Push New SKU Rule (if NEW)
            if abc_class_in_channel == 'NEW':
                for rule in push_new_sku_rules_list:
                    if rule.division == product_div and rule.subaxis == product_sub_axe:
                        applied_rules_for_channel["push_new_sku_rule"] = f"Push {rule.push_quantity} units (Div: {product_div}, SubAxe: {product_sub_axe})."
                        break
            
            # Outlet SKU Capacity Rule (if outlet)
            if channel_type == 'outlet':
                for rule in outlet_capacity_rules_list:
                    if rule.channel_id == channel_id and rule.division == product_div and rule.axe == product_axe:
                        applied_rules_for_channel["outlet_sku_capacity_rule"] = f"Max {rule.max_skus} SKUs for Div '{product_div}', Axe '{product_axe}'."
                        break # Assuming one rule per channel-div-axe

            # Outlet Assortment Rule (if outlet)
            if channel_type == 'outlet':
                 for rule in outlet_assortment_rules_list:
                    # Note: OutletAssortmentRule in schemas.py is defined with metier, subaxis, brand but NO channel_id
                    # This implies it's a global rule for outlets for that metier/subaxis/brand combo.
                    if rule.metier == product_metier and rule.subaxis == product_sub_axe and rule.brand == product_brand:
                        applied_rules_for_channel["outlet_assortment_rule"] = f"Max {rule.max_skus} SKUs for Metier '{product_metier}', SubAxe '{product_sub_axe}', Brand '{product_brand}' in outlets."
                        break

            # Restricted Brands for Donation
            if channel_type == 'donation':
                if product_brand in restricted_brands_for_donation_set:
                    applied_rules_for_channel["restricted_brand_donation_rule"] = f"Brand '{product_brand}' is restricted for donation. Allocation = 0."
                else:
                    applied_rules_for_channel["restricted_brand_donation_rule"] = "Brand not restricted."
            
            data_response["applied_rules"].append(applied_rules_for_channel)
        app.logger.debug(f"Applied rules for EAN {ean_code}: {data_response['applied_rules']}")


        # 6. Fetch Final Allocation from Database
        app.logger.debug(f"Fetching final allocations for EAN {ean_code} from database.")
        db_allocations_for_ean = Allocation.query.filter_by(product_ean=ean_code).all()
        if db_allocations_for_ean:
            for alloc_db in db_allocations_for_ean:
                data_response["final_allocation"].append({
                    "channel_id": alloc_db.channel_id_string,
                    "quantity_allocated": alloc_db.quantity,
                    "allocation_date": alloc_db.allocation_date.isoformat() if alloc_db.allocation_date else None
                })
            app.logger.debug(f"Final allocations for EAN {ean_code}: {data_response['final_allocation']}")
        else:
            app.logger.debug(f"No final allocations found in DB for EAN {ean_code}.")


        app.logger.info(f"Successfully gathered data for EAN {ean_code} (partially implemented).")
        return data_response, 200

    except FileNotFoundError as fnf_error:
        app.logger.error(f"Data file not found during EAN deep dive for {ean_code}: {fnf_error}", exc_info=True)
        return {"error": f"A required data file was not found: {str(fnf_error)}"}, 500
    except Exception as e:
        app.logger.error(f"Unexpected error during EAN deep dive for {ean_code}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}, 500


@app.route('/api/ean_deep_dive_data', methods=['GET'])
# @jwt_required() # Consider adding authentication
def ean_deep_dive_data_endpoint():
    ean = request.args.get('ean')
    if not ean:
        return jsonify({"error": "EAN parameter is required"}), 400
    
    data, status_code = get_ean_deep_dive_data_logic(ean)
    return jsonify(data), status_code

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
