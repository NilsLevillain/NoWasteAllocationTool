from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
import os
from sqlalchemy.orm import joinedload
from collections import defaultdict
from backend.models import db, Product, Inventory, Channel, Allocation, User, AllocationRun
from backend.solver import optimize_allocation, calculate_abc_classification_and_new_skus
from backend.schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule
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

# Helper function for EAN normalization
def normalize_ean(ean_value: Optional[str]) -> Optional[str]:
    if ean_value is None:
        return None
    return str(ean_value).lstrip('0')

# === Standard Endpoints ===
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
            'excess_stock': excess_stock, 'obsolete_items': obsolete_items,
            'returns': returns, 'expiring_soon': expiring_soon
        })
    except Exception as e:
        app.logger.error(f"Error in /api/dashboard/metrics: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/allocate', methods=['POST'])
@jwt_required()
def allocate_inventory(): # Older endpoint, seems to use DB data for DFs
    try:
        data = request.get_json()
        app.logger.warning("/api/inventory/allocate called. This endpoint might be outdated.")
        mock_params_data = data.get('parameters', {})
        mock_params = OptimizationParameters(
            seasonality_coefficient=mock_params_data.get('seasonality_coefficient', 1.0),
            coverage_days_rules=[], outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[], push_new_sku_rules=[],
            restricted_brands_for_donation=[]
        )

        allocation_result_tuple = optimize_allocation(
            products_df=pd.DataFrame([p.to_dict() for p in Product.query.all()]).set_index('ean') if Product.query.count() > 0 else pd.DataFrame(columns=['ean']).set_index('ean'),
            channels_df=pd.DataFrame([c.to_dict() for c in Channel.query.all()]).set_index('id') if Channel.query.count() > 0 else pd.DataFrame(columns=['id']).set_index('id'),
            inventory_df=pd.DataFrame([i.to_dict() for i in Inventory.query.all()]),
            demand_dict=data.get('demand', {}),
            parameters=mock_params,
            existing_stock_dict={},
            product_channel_abc_map={}
        )
        model, status, allocation_result_list = allocation_result_tuple
        
        for alloc in allocation_result_list:
            new_allocation = Allocation(
                product_ean=normalize_ean(str(alloc['product_sku'])), 
                channel_id_string=str(alloc['channel_id']),
                quantity=int(alloc['quantity']),
                allocation_date=datetime.now()
            )
            db.session.add(new_allocation)
        db.session.commit()
        return jsonify(allocation_result_list)
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in /api/inventory/allocate: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/channels/secondlife', methods=['GET'])
@jwt_required()
def get_secondlife_channels():
    try:
        channels = Channel.query.filter_by(channel_type='secondlife').all()
        return jsonify([channel.to_dict() for channel in channels])
    except Exception as e:
        app.logger.error(f"Error in /api/channels/secondlife: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400
    user = User.query.filter_by(username=username).first()
    if user and user.password_hash == password: # Insecure
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token)
    else:
        return jsonify({"msg": "Bad username or password"}), 401

# --- Test Route ---
@app.route('/api/ping_test', methods=['GET'])
def ping_test_endpoint():
    app.logger.info("Ping test endpoint reached!")
    return jsonify({"message": "Ping test successful!"}), 200

# --- EAN Deep Dive Endpoint ---
def get_ean_deep_dive_data_logic(ean_code_normalized: str): # Parameter is now normalized
    app.logger.info(f"--- Starting EAN Deep Dive data gathering for EAN (normalized): {ean_code_normalized} ---")
    data_response = {"ean": ean_code_normalized, "product_info": {}, "initial_stock": {}, "channel_performance": [], "applied_rules": [], "final_allocation": [], "solver_constraints_summary": []}
    base_data_path = os.path.join(app.root_path, 'data')
    masterdata_file_path = os.path.join(base_data_path, 'InputData', 'masterdata.csv')
    bad_stock_inventory_file_path = os.path.join(base_data_path, 'InputData', 'bad_stock_inventory.csv')
    instore_stock_file_path = os.path.join(base_data_path, 'InputData', 'in_store_inventory.csv')
    intransit_stock_file_path = os.path.join(base_data_path, 'InputData', 'stock_in_transit.csv')
    sellout_file_path = os.path.join(base_data_path, 'InputData', 'sellout.csv')
    channellist_file_path = os.path.join(base_data_path, 'ExcelParameters', 'ChannelList.xlsx')
    coverage_file_path = os.path.join(base_data_path, 'ExcelParameters', 'CoverageperABCperChannel.xlsx')
    capacity_file_path = os.path.join(base_data_path, 'ExcelParameters', 'CapacityPerChannel.xlsx')
    assortment_file_path = os.path.join(base_data_path, 'ExcelParameters', 'AssortmentperSubaxeperSignature.xlsx')
    push_new_sku_file_path = os.path.join(base_data_path, 'ExcelParameters', 'PushNewSKU.xlsx')
    abc_ranking_file_path = os.path.join(base_data_path, 'InputData', 'ABC_ranking.csv')

    try:
        products_df_full = load_products_df(masterdata_file_path) # EANs in index are already normalized
        if ean_code_normalized in products_df_full.index:
            product_series = products_df_full.loc[ean_code_normalized]
            data_response["product_info"] = {
                "description": product_series.get('description', 'N/A'), "brand": product_series.get('signature', 'N/A'),
                "division": product_series.get('div', 'N/A'), "axe": product_series.get('axe', 'N/A'),
                "sub_axe": product_series.get('subAxe', 'N/A'), "metier": product_series.get('metier', 'N/A'),
                "sku": product_series.get('sku', 'N/A'),
            }
        else: data_response["product_info"] = {"error": f"EAN {ean_code_normalized} not found in master data."}

        bad_stock_df_full = load_inventory_df(bad_stock_inventory_file_path)
        # Assuming product_ean in bad_stock_df_full is also normalized if it comes from a similar source or is handled by load_inventory_df
        bad_stock_df_full['product_ean_normalized'] = bad_stock_df_full['product_ean'].apply(normalize_ean)
        ean_bad_stock_df = bad_stock_df_full[bad_stock_df_full['product_ean_normalized'] == ean_code_normalized]
        if not ean_bad_stock_df.empty:
            data_response["initial_stock"]["bad_stock_to_allocate"] = int(ean_bad_stock_df['quantity'].sum())
            data_response["initial_stock"]["bad_stock_plant_breakdown"] = [
                {"plant_code": r.get('plant', 'N/A'), "plant_description": r.get('stockOrigin', 'N/A'), 
                 "quantity": int(r.get('quantity', 0)), "flag_excess_6m": int(r.get('flagExcess6months', 0)),
                 "flag_excess_12m": int(r.get('flagExcess12months', 0))}
                for _, r in ean_bad_stock_df.iterrows()]
        else:
            data_response["initial_stock"]["bad_stock_to_allocate"] = 0
            data_response["initial_stock"]["bad_stock_plant_breakdown"] = []

        existing_stock_dict_full = load_existing_stock_dict(instore_stock_file_path, intransit_stock_file_path) # Assumes keys are normalized by util
        channels_df_for_stock = load_channels_df(channellist_file_path)
        ean_existing_channel_stock = []
        total_existing_stock_for_ean = 0
        for ch_id_str in channels_df_for_stock.index.tolist():
            stock_qty = existing_stock_dict_full.get((ean_code_normalized, ch_id_str), 0) # Use normalized EAN
            channel_name_to_use = ch_id_str 
            if 'name' in channels_df_for_stock.columns and ch_id_str in channels_df_for_stock.index:
                 channel_name_to_use = channels_df_for_stock.loc[ch_id_str, 'name']
            if stock_qty > 0:
                 ean_existing_channel_stock.append({"channel_id": ch_id_str, "channel_name": channel_name_to_use, "quantity": int(stock_qty)})
            total_existing_stock_for_ean += stock_qty
        data_response["initial_stock"]["total_existing_channel_stock"] = int(total_existing_stock_for_ean)
        data_response["initial_stock"]["existing_channel_stock_breakdown"] = ean_existing_channel_stock
        
        channels_df = load_channels_df(channellist_file_path)
        
        sellout_df_full = pd.read_csv(sellout_file_path, dtype={'barcode': str, 'store_code': str})
        sellout_df_full['barcode_normalized'] = sellout_df_full['barcode'].apply(normalize_ean)
        ean_sellout_df = sellout_df_full[sellout_df_full['barcode_normalized'] == ean_code_normalized]
        
        in_store_inv_df_for_abc = pd.read_csv(instore_stock_file_path, dtype={'store_code': str, 'barcode': str})
        # Normalization of 'barcode' in in_store_inv_df_for_abc will be handled by calculate_abc_classification_and_new_skus
        
        single_ean_product_master_df = products_df_full[products_df_full.index == ean_code_normalized]
        product_channel_abc_map_full = {}
        if not single_ean_product_master_df.empty:
            product_channel_abc_map_full = calculate_abc_classification_and_new_skus(
                product_master_df=single_ean_product_master_df,
                all_channel_ids=channels_df.index.tolist(),
                in_store_inventory_df=in_store_inv_df_for_abc, # Pass as is, function will normalize
                abc_ranking_file_path=abc_ranking_file_path
            )
        
        demand_dict_full = load_demand_dict(sellout_file_path, ean_col='barcode', channel_col='store_code', demand_qty_col='total_items_weekly') # Assumes keys are normalized by util
        for ch_id_str, ch_row in channels_df.iterrows():
            channel_name_display = ch_id_str
            if 'name' in channels_df.columns: channel_name_display = ch_row.get('name', ch_id_str)
            
            ch_perf_item = {"channel_id": ch_id_str, "channel_name": channel_name_display, 
                            "channel_type": ch_row.get('channel_type', 'N/A'), "sellout_qty": 0, 
                            "calculated_demand": 0, "abc_class": "N/A"}
            current_ch_sellout = ean_sellout_df[ean_sellout_df['store_code'] == ch_id_str] # ean_sellout_df already filtered by normalized EAN
            if not current_ch_sellout.empty: ch_perf_item["sellout_qty"] = int(current_ch_sellout['total_items_weekly'].sum())
            ch_perf_item["calculated_demand"] = int(demand_dict_full.get((ean_code_normalized, ch_id_str), 0)) # Use normalized EAN
            ch_perf_item["abc_class"] = product_channel_abc_map_full.get((ean_code_normalized, ch_id_str), 'N/A') # Use normalized EAN
            data_response["channel_performance"].append(ch_perf_item)

        coverage_rules_list = load_optimization_rules(coverage_file_path, CoverageDaysRule, channel_id='channel_id', abc_class='abc_class', coverage_days='coverage_days')
        outlet_capacity_rules_list = load_optimization_rules(capacity_file_path, OutletSKUCapacityRule, channel_id='channel_id', division='operational_division', axe='operational_axe_label', max_skus='max_skus')
        outlet_assortment_rules_list = load_optimization_rules(assortment_file_path, OutletAssortmentRule, metier='operational_metier_label', subaxis='operational_sub_axe_label', brand='operational_signature_label', max_skus='max_skus')
        push_new_sku_rules_list = load_optimization_rules(push_new_sku_file_path, PushNewSKURule, division='operational_division', subaxis='operational_sub_axe_label', push_quantity='Push Quantity if New SKU')
        
        product_info = data_response["product_info"]
        product_div, product_axe, product_sub_axe, product_metier, product_brand = (product_info.get("division"), product_info.get("axe"), product_info.get("sub_axe"), product_info.get("metier"), product_info.get("brand"))
        restricted_brands_for_donation_set = set(['BrandB']) 

        for cp_item in data_response["channel_performance"]:
            ch_id, ch_type, abc_class = cp_item["channel_id"], cp_item["channel_type"], cp_item["abc_class"]
            rules = {"channel_id": ch_id, "coverage_rule": "N/A", "push_new_sku_rule": "N/A", "outlet_sku_capacity_rule": "N/A", "outlet_assortment_rule": "N/A", "restricted_brand_donation_rule": "N/A"}
            for r in coverage_rules_list: 
                if r.channel_id == ch_id and r.abc_class == abc_class: rules["coverage_rule"] = f"Class {abc_class}: {r.coverage_days} days."; break
            if abc_class == 'NEW':
                for r in push_new_sku_rules_list: 
                    if r.division == product_div and r.subaxis == product_sub_axe: rules["push_new_sku_rule"] = f"Push {r.push_quantity} units."; break
            if ch_type == 'outlet':
                for r_cap in outlet_capacity_rules_list: 
                    if r_cap.channel_id == ch_id and r_cap.division == product_div and r_cap.axe == product_axe: rules["outlet_sku_capacity_rule"] = f"Max {r_cap.max_skus} SKUs for Div/Axe."; break
                for r_assort in outlet_assortment_rules_list:
                    if r_assort.metier == product_metier and r_assort.subaxis == product_sub_axe and r_assort.brand == product_brand: rules["outlet_assortment_rule"] = f"Max {r_assort.max_skus} SKUs for Metier/SubAxe/Brand."; break
            if ch_type == 'donation': rules["restricted_brand_donation_rule"] = f"Brand '{product_brand}' restricted." if product_brand in restricted_brands_for_donation_set else "Brand not restricted."
            data_response["applied_rules"].append(rules)
        
        db_allocations = Allocation.query.filter_by(product_ean=ean_code_normalized).all() # Use normalized EAN
        if db_allocations:
            for alloc_db in db_allocations: data_response["final_allocation"].append({"channel_id": alloc_db.channel_id_string, "quantity_allocated": alloc_db.quantity, "allocation_date": alloc_db.allocation_date.isoformat() if alloc_db.allocation_date else None})
        
        app.logger.info(f"Successfully gathered full data for EAN {ean_code_normalized}.")
        return data_response, 200
    except FileNotFoundError as fnf_error:
        app.logger.error(f"Data file not found for EAN {ean_code_normalized}: {fnf_error}", exc_info=True)
        return {"error": f"A required data file was not found: {str(fnf_error)}"}, 500
    except Exception as e:
        app.logger.error(f"Error in EAN deep dive for {ean_code_normalized}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}, 500

@app.route('/api/ean_deep_dive_data', methods=['GET'])
# @jwt_required()
def ean_deep_dive_data_endpoint():
    ean = request.args.get('ean')
    if not ean: return jsonify({"error": "EAN parameter is required"}), 400
    normalized_ean = normalize_ean(ean) # Normalize EAN
    if not normalized_ean: return jsonify({"error": "Invalid EAN parameter after normalization"}), 400
    data, status_code = get_ean_deep_dive_data_logic(normalized_ean)
    return jsonify(data), status_code

# --- Auto-Allocation Endpoint (File-based) ---
@app.route('/api/auto_allocate', methods=['POST'])
# @jwt_required()
def auto_allocate_endpoint():
    try:
        app.logger.info("--- Starting Auto-Allocation from Files ---")
        base_data_path = os.path.join(app.root_path, 'data')
        masterdata_file_path = os.path.join(base_data_path, 'InputData', 'masterdata.csv')
        inventory_file_path = os.path.join(base_data_path, 'InputData', 'bad_stock_inventory.csv')
        channellist_file_path = os.path.join(base_data_path, 'ExcelParameters', 'ChannelList.xlsx')
        # sellout_file_path = os.path.join(base_data_path, 'InputData', 'sellout.csv') # Not directly used for ABC anymore
        coverage_file_path = os.path.join(base_data_path, 'ExcelParameters', 'CoverageperABCperChannel.xlsx')
        capacity_file_path = os.path.join(base_data_path, 'ExcelParameters', 'CapacityPerChannel.xlsx')
        assortment_file_path = os.path.join(base_data_path, 'ExcelParameters', 'AssortmentperSubaxeperSignature.xlsx')
        push_new_sku_file_path = os.path.join(base_data_path, 'ExcelParameters', 'PushNewSKU.xlsx')
        instore_stock_file_path = os.path.join(base_data_path, 'InputData', 'in_store_inventory.csv')
        intransit_stock_file_path = os.path.join(base_data_path, 'InputData', 'stock_in_transit.csv')
        abc_ranking_file_path = os.path.join(base_data_path, 'InputData', 'ABC_ranking.csv') # Path for ABC ranking

        products_df = load_products_df(masterdata_file_path) # EANs in index are normalized
        if products_df.empty: return jsonify({'error': 'Failed to load products data.'}), 500
        channels_df = load_channels_df(channellist_file_path)
        if channels_df.empty: return jsonify({'error': 'Failed to load channels data.'}), 500
        inventory_df = load_inventory_df(inventory_file_path) 
        # Ensure product_ean in inventory_df is normalized if it's used in joins/merges with products_df
        inventory_df['product_ean'] = inventory_df['product_ean'].apply(normalize_ean)

        demand_dict = load_demand_dict(os.path.join(base_data_path, 'InputData', 'sellout.csv')) # load_demand_dict should handle EAN normalization if needed
        
        coverage_rules = load_optimization_rules(coverage_file_path, CoverageDaysRule, channel_id='channel_id', abc_class='abc_class', coverage_days='coverage_days')
        outlet_capacity_rules = load_optimization_rules(capacity_file_path, OutletSKUCapacityRule, channel_id='channel_id', division='operational_division', axe='operational_axe_label', max_skus='max_skus')
        outlet_assortment_rules = load_optimization_rules(assortment_file_path, OutletAssortmentRule, metier='operational_metier_label', subaxis='operational_sub_axe_label', brand='operational_signature_label', max_skus='max_skus')
        push_new_sku_rules = load_optimization_rules(push_new_sku_file_path, PushNewSKURule, division='operational_division', subaxis='operational_sub_axe_label', push_quantity='Push Quantity if New SKU')
        
        parameters = OptimizationParameters(
            seasonality_coefficient=1.0, coverage_days_rules=coverage_rules,
            outlet_sku_capacity_rules=outlet_capacity_rules, outlet_assortment_rules=outlet_assortment_rules,
            push_new_sku_rules=push_new_sku_rules, restricted_brands_for_donation=['BrandB'] 
        )
        existing_stock_dict = load_existing_stock_dict(instore_stock_file_path, intransit_stock_file_path) # Assumes keys are normalized by util
        
        try: 
            raw_in_store_inventory_df = pd.read_csv(instore_stock_file_path, dtype={'store_code': str, 'barcode': str})
            # Normalization of 'barcode' in raw_in_store_inventory_df will be handled by calculate_abc_classification_and_new_skus
        except FileNotFoundError: 
            raw_in_store_inventory_df = pd.DataFrame(columns=['store_code', 'barcode', 'physical_quantity'])
        
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            product_master_df=products_df, # Has normalized EAN index
            all_channel_ids=channels_df.index.tolist(),
            in_store_inventory_df=raw_in_store_inventory_df, # Function will normalize 'barcode'
            abc_ranking_file_path=abc_ranking_file_path  # Function will normalize 'barcode'
        )
        
        model, status, allocation_results = optimize_allocation(
            products_df, channels_df, inventory_df, demand_dict, parameters, 
            existing_stock_dict, product_channel_abc_map
        )
        if status != 'Optimal': return jsonify({'error': f'Solver status: {status}'}), 500
        
        with db.session.begin_nested():
            Allocation.query.delete() 
            app.logger.debug(f"Solver returned {len(allocation_results)} allocation entries.")
            for alloc_res in allocation_results:
                db.session.add(Allocation(
                    product_ean=normalize_ean(str(alloc_res['product_sku'])), # Ensure EAN is normalized before saving
                    plant_code=str(alloc_res['plant_code']), 
                    channel_id_string=str(alloc_res['channel_id']),
                    quantity=int(alloc_res['quantity']),
                    allocation_date=datetime.now()
                ))
        db.session.commit()
        app.logger.info(f"Auto-allocation successful. Status: {status}. {len(allocation_results)} EAN-Plant-Channel allocations saved.")
        return jsonify({'message': 'Auto-allocation successful!', 'status': status, 'allocations_created': len(allocation_results)}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in /api/auto_allocate: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Endpoint for Saving Manual Allocations ---
@app.route('/api/save_allocations', methods=['POST'])
# @jwt_required()
def save_manual_allocations():
    try:
        changes = request.get_json() 
        if not isinstance(changes, list): return jsonify({'error': 'Invalid data format. Expected a list.'}), 400
        
        app.logger.info(f"Received {len(changes)} items for manual allocation saving.")
        
        eans_to_clear = set()
        normalized_changes = []

        for change in changes:
            item_id = change.get('id') 
            if not item_id or '_' not in item_id:
                app.logger.warning(f"Skipping change due to invalid id: {item_id}")
                continue
            ean_original, plant_code = item_id.split('_', 1)
            ean_normalized = normalize_ean(ean_original)
            if not ean_normalized:
                app.logger.warning(f"Skipping change due to invalid EAN after normalization: {ean_original}")
                continue
            
            eans_to_clear.add(ean_normalized)
            normalized_changes.append({
                'ean': ean_normalized,
                'plant_code': plant_code,
                'channels': change.get('channels', {})
            })

        with db.session.begin_nested():
            if eans_to_clear:
                app.logger.info(f"Clearing existing allocations for EANs: {list(eans_to_clear)}")
                Allocation.query.filter(Allocation.product_ean.in_(list(eans_to_clear))).delete(synchronize_session=False)

            for norm_change in normalized_changes:
                ean = norm_change['ean']
                plant_code = norm_change['plant_code']
                new_channel_allocations = norm_change['channels']

                if not isinstance(new_channel_allocations, dict):
                    app.logger.warning(f"Skipping EAN {ean}, Plant {plant_code} due to malformed channel data.")
                    continue
                
                for channel_id_str, quantity_str in new_channel_allocations.items():
                    try:
                        quantity = int(quantity_str or 0)
                        if quantity > 0:
                            app.logger.debug(f"Adding allocation: EAN={ean}, Plant={plant_code}, Channel={channel_id_str}, Qty={quantity}")
                            db.session.add(Allocation(
                                product_ean=ean, # Already normalized
                                plant_code=plant_code,
                                channel_id_string=channel_id_str,
                                quantity=quantity,
                                allocation_date=datetime.now()
                            ))
                    except ValueError:
                        app.logger.warning(f"Invalid quantity '{quantity_str}' for EAN {ean}, Plant {plant_code}, Channel {channel_id_str}. Skipping.")
                        
        db.session.commit()
        app.logger.info("Manual allocations saved successfully.")
        return jsonify({'message': 'Allocations saved successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in /api/save_allocations: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Endpoint for Frontend Allocation Table Data ---
@app.route('/api/allocation_data', methods=['GET'])
# @jwt_required()
def get_allocation_data():
    try:
        app.logger.info("Loading data for /api/allocation_data...")
        base_data_path = os.path.join(app.root_path, 'data')
        masterdata_file_path = os.path.join(base_data_path, 'InputData', 'masterdata.csv')
        inventory_file_path = os.path.join(base_data_path, 'InputData', 'bad_stock_inventory.csv')
        channellist_file_path = os.path.join(base_data_path, 'ExcelParameters', 'ChannelList.xlsx')

        channels_df = load_channels_df(channellist_file_path)
        channel_ids = channels_df.index.tolist() if not channels_df.empty else []
        
        products_df = load_products_df(masterdata_file_path) # EANs in index are normalized
        if products_df.empty: return jsonify({"allocationData": [], "channelColumns": channel_ids, "allocationStatus": "No Products"})
        
        inventory_df = load_inventory_df(inventory_file_path)
        inventory_df['product_ean'] = inventory_df['product_ean'].apply(normalize_ean) # Normalize EANs in inventory
        
        products_df_to_merge = products_df.reset_index() # 'ean' is now a column, already normalized
        
        merged_df = pd.merge(products_df_to_merge, inventory_df, left_on='ean', right_on='product_ean', how='left', suffixes=('', '_inv'))
        
        # Ensure correct columns are used after merge, especially if 'ean' was in both
        if 'ean_inv' in merged_df.columns: merged_df.drop(columns=['ean_inv'], inplace=True)

        merged_df['quantity'] = merged_df['quantity'].fillna(0).astype(int)
        merged_df['available_stock'] = merged_df['available_stock'].fillna(0).astype(int)
        merged_df['plant'] = merged_df['plant'].fillna('N/A').astype(str)
        merged_df['stockOrigin'] = merged_df['stockOrigin'].fillna('N/A').astype(str)
        merged_df['flagExcess6months'] = merged_df['flagExcess6months'].fillna(0).astype(int)
        merged_df['flagExcess12months'] = merged_df['flagExcess12months'].fillna(0).astype(int)
        merged_df['bad_stock_type'] = merged_df['bad_stock_type'].fillna('').astype(str)

        db_allocations = Allocation.query.all()
        allocations_map = defaultdict(lambda: defaultdict(int))
        for alloc in db_allocations:
            # Ensure keys used for allocations_map are normalized
            allocations_map[(normalize_ean(alloc.product_ean), alloc.plant_code)][alloc.channel_id_string] = alloc.quantity
        
        frontend_data = []
        for _, row in merged_df.iterrows():
            ean_val = normalize_ean(str(row.get('ean', 'N/A'))) # Ensure EAN is normalized
            if not ean_val: continue # Skip if EAN is invalid after normalization

            plant_code_val = str(row.get('plant', 'N/A')) 
            
            channel_data = {
                chan_id: allocations_map.get((ean_val, plant_code_val), {}).get(chan_id, 0)
                for chan_id in channel_ids
            }
            
            item_data = {
                'id': f"{ean_val}_{plant_code_val}", 
                'div': row.get('div', 'N/A'),
                'signature': row.get('signature', 'N/A'), 
                'axe': row.get('axe', 'N/A'),
                'subAxe': row.get('subAxe', 'N/A'), 'metier': row.get('metier', 'N/A'),
                'ean': ean_val, 'sku': row.get('sku', 'N/A'),
                'description': row.get('description', 'N/A'), 'units': row.get('quantity', 0),
                'available_stock': row.get('available_stock', 0), 
                'stockOrigin': row.get('stockOrigin', 'N/A'), 
                'bad_stock_type': row.get('bad_stock_type', ''), 
                'plant': row.get('stockOrigin', 'N/A'), 
                'plant_code': plant_code_val, 
                'allocAccu': "0%", 'channels': channel_data,
                'cogs': row.get('cogs', 0.0) * row.get('quantity', 0)
            }
            frontend_data.append(item_data)
        
        status_msg = "DB Allocations" if db_allocations else "No DB Allocations"
        return jsonify({"allocationData": frontend_data, "channelColumns": channel_ids, "allocationStatus": status_msg})
    except Exception as e:
        app.logger.error(f"Error in /api/allocation_data: {e}", exc_info=True)
        return jsonify({'error': f"Failed to fetch allocation data: {str(e)}"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.first():
            default_user = User(username='testuser', email='test@example.com', password_hash='password')
            db.session.add(default_user)
            db.session.commit()
            print("Created default user.")
        if not Product.query.first(): 
            print("Adding sample data...")
            sample_channel_names = ['Outlet', 'Giverny', 'Village', 'Corbeil', 'F&F', 'Liquidation', 'Donation']
            for name_channel in sample_channel_names:
                chan_type = 'outlet' if name_channel in ['Outlet', 'Giverny', 'Village', 'Corbeil'] else \
                            'donation' if name_channel == 'Donation' else \
                            'liquidation' if name_channel == 'Liquidation' else 'store' 
                db.session.add(Channel(channel_id_string=name_channel, name=name_channel, channel_type=chan_type, country='FR'))
            sample_products_fe = [
                {'div': 'LLD', 'signature': 'Armani Prive', 'ean': '3614273014588', 'hierarchy': 'Perfumes', 'photo': 'ap_cuir.jpg', 'name': 'AP CUIR AMETHYSTE EDP V50ML', 'units': 500, 'stockOrigin': 'Obs', 'cogs_per_unit': 50},
                {'div': 'PPD', 'signature': "L'Oreal Professionnel", 'ean': '3474636645800', 'hierarchy': 'Hair Care', 'photo': 'lp_serioxyl.jpg', 'name': 'LP SERIOXYL DENSERHAIR 90ML', 'units': 4500, 'stockOrigin': 'Excess', 'cogs_per_unit': 15},
            ]
            for p_data in sample_products_fe:
                # Normalize EAN before creating Product
                normalized_ean = normalize_ean(p_data['ean'])
                if normalized_ean:
                    prod = Product(ean=normalized_ean, name=p_data['name'], brand=p_data['signature'], division=p_data['div'], hierarchy=p_data['hierarchy'], photo=p_data['photo'], cogs=p_data['cogs_per_unit'])
                    db.session.add(prod)
                    inv = Inventory(product_ean=normalized_ean, quantity=p_data['units'], status=p_data['stockOrigin'], country='FR') 
                    db.session.add(inv)
            db.session.commit()
            print("Sample data added.")
    app.run(debug=True)
