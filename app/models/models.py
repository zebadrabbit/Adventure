"""
project: Adventure MUD
module: models.py
https://github.com/zebadrabbit/Adventure
License: MIT

Database models used by the Adventure MUD application.

Notes:
- Passwords are stored as hashed values (Werkzeug generate_password_hash).
- Character attributes like stats, gear, and items are stored as JSON strings
    for simplicity; consider normalizing into related tables as the project grows.
"""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


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
    role = db.Column(db.String(20), nullable=False, default="user")
    # Moderation fields
    banned = db.Column(db.Boolean, nullable=False, default=False)
    ban_reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    banned_at = db.Column(db.DateTime, nullable=True)
    # Persistent mute flag (chat suppression); temporary rate-limit mutes may remain in-memory only
    muted = db.Column(db.Boolean, nullable=False, default=False)
    # JSON string storing explored dungeon tiles keyed by seed: {"<seed>": "x1,y1;x2,y2;..."}
    explored_tiles = db.Column(db.Text, nullable=True)
    # Add more fields as needed

    # Convenience helpers (tests call set_password). Keeps hashing logic centralized.
    def set_password(self, raw_password: str):
        """Hash and store a new password value.

        Provided primarily for tests / admin scripts. Application routes
        already perform hashing before assignment, but having this avoids
        duplication and supports legacy test patterns.
        """
        self.password = generate_password_hash(raw_password)

    def check_password(self, candidate: str) -> bool:
        """Return True if candidate matches stored hash (or legacy plaintext)."""
        stored = self.password or ""
        # Allow for extremely old legacy plaintext value just in case
        if not stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
            return stored == candidate
        try:
            return check_password_hash(stored, candidate)
        except Exception:
            return False


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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    stats = db.Column(db.Text, nullable=False)  # JSON string for stats
    gear = db.Column(db.Text, nullable=True)  # JSON string for gear
    items = db.Column(db.Text, nullable=True)  # JSON string for items
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
        level: Recommended minimum level (0 for utility / no-scaling)
        rarity: Drop frequency tier (common, uncommon, rare, epic, legendary, mythic)
    """

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text, nullable=True)
    value_copper = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, nullable=False, default=0)
    rarity = db.Column(db.String(20), nullable=False, default="common")
    # New: per-item weight used for encumbrance calculations (units = weight points)
    # Light = 0.1-0.5, Medium ~1-5, Heavy 10+, default conservative 1.0
    weight = db.Column(db.Float, nullable=False, default=1.0)


class GameConfig(db.Model):
    """Key/value style game configuration storage.

    Stores tunable gameplay constants (encumbrance thresholds, capacity formula
    parameters, starter item mappings, base stats, etc.) so they can be adjusted
    without code changes. Values are persisted as JSON-serializable text.

    Example rows:
        key='encumbrance', value='{"base_capacity":10,"per_str":5,"warn_pct":1.0,"over_pct":1.10,"dex_penalty":2}'
        key='starter_items', value='{"fighter":[...],"mage":[...]}'
    """

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

    @staticmethod
    def get(key: str):  # pragma: no cover - thin convenience
        row = GameConfig.query.filter_by(key=key).first()
        return row.value if row else None

    @staticmethod
    def set(key: str, value: str):  # pragma: no cover
        from app import db

        row = GameConfig.query.filter_by(key=key).first()
        if not row:
            row = GameConfig(key=key, value=value)
            db.session.add(row)
        else:
            row.value = value
        db.session.commit()


class UserPref(db.Model):
    """Arbitrary user preference storage (e.g., UI modes).

    Attributes:
        user_id: FK to User.id
        key: preference key (e.g., 'tooltip_mode')
        value: stored value (string/JSON serialized externally if needed)
    Unique constraint ensures a single row per (user_id,key).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    key = db.Column(db.String(80), nullable=False)
    value = db.Column(db.Text, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "key", name="uq_userpref_user_key"),)

    @staticmethod
    def get(user_id: int, key: str, default=None):  # pragma: no cover - simple getter
        row = UserPref.query.filter_by(user_id=user_id, key=key).first()
        return row.value if row else default

    @staticmethod
    def set(user_id: int, key: str, value: str):  # pragma: no cover
        row = UserPref.query.filter_by(user_id=user_id, key=key).first()
        if not row:
            row = UserPref(user_id=user_id, key=key, value=value)
            db.session.add(row)
        else:
            row.value = value
        db.session.commit()


class GameClock(db.Model):
    """Global non-combat game clock (simple tick counter).

    Single-row table (id=1) that advances for each non-combat action: movement,
    searching, using an item, casting a spell, etc. Future combat turns will
    temporarily pause real-time ticking and instead advance via turn order.
    """

    id = db.Column(db.Integer, primary_key=True, default=1)
    tick = db.Column(db.Integer, nullable=False, default=0, index=True)
    # When True, non-combat actions should not auto-advance time; turn system controls progression
    combat = db.Column(db.Boolean, nullable=False, default=False)

    @staticmethod
    def get():  # pragma: no cover - thin convenience
        from app import db as _db

        inst = _db.session.get(GameClock, 1)
        if not inst:
            inst = GameClock(id=1, tick=0)
            _db.session.add(inst)
            try:
                _db.session.commit()
            except Exception:  # pragma: no cover
                _db.session.rollback()
        return inst
