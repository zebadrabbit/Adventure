"""Merchant and Trading Models.

Database models for merchant NPCs, shops, and trading transactions.
"""

from datetime import datetime

from app import db


class Merchant(db.Model):
    """Merchant NPC with shop inventory.

    Attributes:
        id: Primary key
        slug: Unique identifier
        name: Merchant name
        description: Flavor text
        location: Where merchant appears (town, dungeon_entrance, etc.)
        merchant_type: Type (general, weapons, armor, potions, rare)
        inventory_json: JSON array of item slugs available for purchase
        buy_price_modifier: Multiplier for buy prices (default 1.0)
        sell_price_modifier: Multiplier for sell prices (default 0.5)
        restocks_every_hours: How often inventory refreshes (0 = never)
        is_active: Whether merchant is currently available
    """

    __tablename__ = "merchant"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(80), nullable=False, default="town")
    merchant_type = db.Column(db.String(40), nullable=False, default="general")
    inventory_json = db.Column(db.Text, nullable=False, default="[]")  # [{"slug": "sword", "stock": 5}, ...]
    buy_price_modifier = db.Column(db.Float, nullable=False, default=1.0)
    sell_price_modifier = db.Column(db.Float, nullable=False, default=0.5)
    restocks_every_hours = db.Column(db.Integer, nullable=False, default=0)
    last_restock = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sprite_icon = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class TradeTransaction(db.Model):
    """Historical record of trades for analytics and debugging.

    Attributes:
        id: Primary key
        character_id: FK to Character
        merchant_id: FK to Merchant (nullable for player-to-player)
        transaction_type: 'buy' or 'sell'
        item_slug: Item traded
        quantity: Number of items
        price_per_item: Gold per item
        total_gold: Total transaction value
        created_at: Transaction timestamp
    """

    __tablename__ = "trade_transaction"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchant.id"), nullable=True)
    transaction_type = db.Column(db.String(20), nullable=False)  # buy, sell
    item_slug = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_per_item = db.Column(db.Integer, nullable=False)
    total_gold = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    character = db.relationship("Character", backref="trade_history")
    merchant = db.relationship("Merchant", backref="transactions")


class MerchantStock(db.Model):
    """Current stock levels for merchant inventory (for limited stock items).

    Attributes:
        id: Primary key
        merchant_id: FK to Merchant
        item_slug: Item slug
        current_stock: Current quantity available
        max_stock: Maximum stock after restock
        last_updated: When stock was last modified
    """

    __tablename__ = "merchant_stock"

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchant.id"), nullable=False, index=True)
    item_slug = db.Column(db.String(80), nullable=False)
    current_stock = db.Column(db.Integer, nullable=False, default=0)
    max_stock = db.Column(db.Integer, nullable=False, default=10)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    merchant = db.relationship("Merchant", backref="stock_levels")

    __table_args__ = (db.UniqueConstraint("merchant_id", "item_slug", name="_merchant_item_uc"),)
