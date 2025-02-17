from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import pandas as pd
from models import db, Product, Inventory, Channel, Allocation, User
from allocation_service import optimize_allocation
from config import Config

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
            revenue=data.get('revenue', {})
        )
        
        # Save allocation results to database
        for alloc in allocation_result:
            new_allocation = Allocation(
                product_id=alloc['product_id'],
                channel_id=alloc['channel_id'],
                quantity=alloc['quantity'],
                allocation_date=datetime.now()
            )
            db.session.add(new_allocation)
        
        db.session.commit()
        return jsonify(allocation_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/secondlife', methods=['GET'])
@jwt_required()
def get_secondlife_channels():
    try:
        channels = Channel.query.filter_by(channel_type='secondlife').all()
        return jsonify([channel.to_dict() for channel in channels])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
