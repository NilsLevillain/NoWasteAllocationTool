from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    # ... (existing User model) ...
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))  # admin, country_manager, nowaste_team, channel_partner
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # item_id = db.Column(db.String(50), unique=True) # Keep or replace with ean? Let's keep both for now.
    item_id = db.Column(db.String(50), unique=True, nullable=True) # Make nullable if EAN is primary identifier
    ean = db.Column(db.String(50), unique=True, nullable=False) # Added EAN as likely primary key
    name = db.Column(db.String(200), nullable=True) # Added Name
    brand = db.Column(db.String(100), nullable=True) # Maps to 'signature'
    division = db.Column(db.String(50), nullable=True) # Maps to 'div'
    axe = db.Column(db.String(100), nullable=True)
    subaxis = db.Column(db.String(100), nullable=True)
    hierarchy = db.Column(db.String(100), nullable=True) # Added Hierarchy (maps to category?)
    photo = db.Column(db.String(200), nullable=True) # Added Photo (filename/path)
    cogs = db.Column(db.Float, nullable=True) # Added COGS
    donation_eligible = db.Column(db.Boolean, default=False) # Keep this field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Inventory to easily get total units
    inventories = db.relationship('Inventory', backref='product', lazy=True)

    def to_dict(self, include_inventory_status=False):
        # Base dictionary
        data = {
            'id': self.id,
            'item_id': self.item_id,
            'ean': self.ean,
            'name': self.name,
            'brand': self.brand, # Frontend uses 'signature'
            'division': self.division, # Frontend uses 'div'
            'axe': self.axe,
            'subaxis': self.subaxis,
            'hierarchy': self.hierarchy, # Frontend uses 'hierarchy'
            'photo': self.photo,
            'cogs': self.cogs,
            'donation_eligible': self.donation_eligible
            # 'units' and 'stockOrigin' will be calculated/mapped in the API endpoint
        }
        # Optionally include inventory status if needed directly here,
        # but better handled in the API logic joining tables.
        # if include_inventory_status:
        #    data['inventory_status'] = [inv.status for inv in self.inventories]
        return data

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # product_id = db.Column(db.Integer, db.ForeignKey('product.id')) # Keep this FK
    product_ean = db.Column(db.String(50), db.ForeignKey('product.ean'), nullable=False) # Link via EAN
    quantity = db.Column(db.Integer)
    status = db.Column(db.String(50))  # excess, obsolete, returned, Obs, Freshness <12, Freshness <6 etc. - Make longer?
    expiry_date = db.Column(db.DateTime, nullable=True) # Allow nullable
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'product_ean': self.product_ean, # Use EAN
            'quantity': self.quantity,
            'status': self.status, # Maps to 'stockOrigin'
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'country': self.country
        }

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Use a unique string ID matching frontend/solver usage
    channel_id_string = db.Column(db.String(50), unique=True, nullable=False) # e.g., 'Outlet', 'Giverny'
    name = db.Column(db.String(100)) # Can be the same as channel_id_string or more descriptive
    channel_type = db.Column(db.String(50))  # outlet, donation, liquidation, friends_family, store etc.
    country = db.Column(db.String(50))
    # capacity = db.Column(db.Integer) # Capacity seems handled differently in solver now (max SKUs for outlets)
    # min_coverage = db.Column(db.Integer) # Coverage handled by rules in solver
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            # 'id': self.id, # Internal DB id
            'id': self.channel_id_string, # Use the string ID for consistency
            'name': self.name,
            'channel_type': self.channel_type,
            'country': self.country,
            # 'capacity': self.capacity,
            # 'min_coverage': self.min_coverage
        }

class Allocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # product_id = db.Column(db.Integer, db.ForeignKey('product.id')) # Link via EAN now
    product_ean = db.Column(db.String(50), db.ForeignKey('product.ean'), nullable=False)
    # channel_id = db.Column(db.Integer, db.ForeignKey('channel.id')) # Link via string ID now
    channel_id_string = db.Column(db.String(50), db.ForeignKey('channel.channel_id_string'), nullable=False)
    quantity = db.Column(db.Integer)
    allocation_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    run_id = db.Column(db.String(50), nullable=True) # Optional: To group allocations from a specific run

    # Add relationships for easier querying
    product_rel = db.relationship('Product', foreign_keys=[product_ean], primaryjoin="Allocation.product_ean == Product.ean")
    channel_rel = db.relationship('Channel', foreign_keys=[channel_id_string], primaryjoin="Allocation.channel_id_string == Channel.channel_id_string")


    def to_dict(self):
        return {
            'id': self.id,
            'product_ean': self.product_ean,
            'channel_id': self.channel_id_string, # Use string ID
            'quantity': self.quantity,
            'allocation_date': self.allocation_date.isoformat() if self.allocation_date else None,
            'status': self.status,
            'run_id': self.run_id
        }

# Optional: Add an AllocationRun model to track overall status ('IN PROGRESS', 'VALIDATED')
class AllocationRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(50), unique=True, nullable=False, default=lambda: f"run_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    run_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='IN PROGRESS') # IN PROGRESS, VALIDATED, FAILED
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    parameters_json = db.Column(db.Text, nullable=True) # Store parameters used for this run

    def to_dict(self):
        return {
            'run_id': self.run_id,
            'run_date': self.run_date.isoformat() if self.run_date else None,
            'status': self.status,
            'user_id': self.user_id
        }
