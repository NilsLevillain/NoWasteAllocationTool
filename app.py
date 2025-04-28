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

    app.run(debug=True)
