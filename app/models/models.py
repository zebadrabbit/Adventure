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
    # Optional contact email for notifications
    email = db.Column(db.String(120), nullable=True)
    # Role for authorization: 'admin' | 'mod' | 'user'
    role = db.Column(db.String(20), nullable=False, default='user')
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
    xp = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1)
    # Add more fields as needed


class Item(db.Model):
    """Catalog of items that can appear in inventories.

    Attributes:
        id: Primary key
        slug: Unique identifier used to reference from JSON payloads
        name: Display name
        type: Category (e.g., 'weapon', 'armor', 'potion', 'tool')
        description: Short description
        value_copper: Integer value in copper coins
    """
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text, nullable=True)
    value_copper = db.Column(db.Integer, default=0, nullable=False)
