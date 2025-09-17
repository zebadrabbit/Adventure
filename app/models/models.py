"""Database models used by the Adventure MUD application.

Notes:
- Passwords are stored as hashed values (Werkzeug generate_password_hash).
- Character attributes like stats, gear, and items are stored as JSON strings
    for simplicity; consider normalizing into related tables as the project grows.
"""

from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    """Authenticated player account.

    Attributes:
        id: Primary key.
        username: Unique handle for login and display.
        password: Hashed password string (never store plaintext).
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # Add more fields as needed

class Character(db.Model):
    """A playable character owned by a user.

    Attributes:
        user_id: Foreign key to User.id
        name: Character name
        stats: JSON string of base stats (e.g., str, dex, int, wis, mana, hp)
        gear: JSON string list of equipped items
        items: JSON string list of inventory items
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    stats = db.Column(db.Text, nullable=False)  # JSON string for stats
    gear = db.Column(db.Text, nullable=True)    # JSON string for gear
    items = db.Column(db.Text, nullable=True)   # JSON string for items
    # Add more fields as needed
