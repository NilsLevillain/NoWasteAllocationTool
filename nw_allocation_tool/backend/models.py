from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))  # admin, country_manager, nowaste_team, channel_partner
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(50), unique=True)
    brand = db.Column(db.String(100), nullable=True) # Allow nullable for flexibility
    division = db.Column(db.String(50), nullable=True) # Allow nullable
    axe = db.Column(db.String(100), nullable=True) # Allow nullable, maybe increase length
    subaxis = db.Column(db.String(100), nullable=True) # Add subaxis, allow nullable
    donation_eligible = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'brand': self.brand,
            'division': self.division,
            'axe': self.axe,
            'subaxis': self.subaxis, # Add subaxis
            'donation_eligible': self.donation_eligible
        }

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    status = db.Column(db.String(20))  # excess, obsolete, returned
    expiry_date = db.Column(db.DateTime)
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'status': self.status,
            'expiry_date': self.expiry_date,
            'country': self.country
        }

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    channel_type = db.Column(db.String(50))  # outlet, donation, liquidation, friends_family
    country = db.Column(db.String(50))
    capacity = db.Column(db.Integer)
    min_coverage = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'channel_type': self.channel_type,
            'country': self.country,
            'capacity': self.capacity,
            'min_coverage': self.min_coverage
        }

class Allocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    quantity = db.Column(db.Integer)
    allocation_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'channel_id': self.channel_id,
            'quantity': self.quantity,
            'allocation_date': self.allocation_date,
            'status': self.status
        }
