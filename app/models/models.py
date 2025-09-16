from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # Add more fields as needed

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    stats = db.Column(db.Text, nullable=False)  # JSON string for stats
    gear = db.Column(db.Text, nullable=True)    # JSON string for gear
    items = db.Column(db.Text, nullable=True)   # JSON string for items
    # Add more fields as needed
