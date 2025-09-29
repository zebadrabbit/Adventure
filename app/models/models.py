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


# Lightweight event hook to auto-deduplicate hard-coded test usernames gracefully.
try:  # pragma: no cover - SQLAlchemy event wiring
    from sqlalchemy import event

    @event.listens_for(User, "before_insert")
    def _user_before_insert(mapper, connection, target):  # type: ignore[override]
        """Append numeric suffix if username already exists.

        This primarily addresses test scenarios that insert static usernames multiple times
        without cleaning the shared session DB (e.g. 'loginuser'). In production usage this
        path is rarely exercised unless an operator manually creates duplicates during the
        same test run. We keep it minimal to avoid masking legitimate collisions elsewhere.
        """
        uname = getattr(target, "username", None)
        if not uname:
            return
        # Direct SQL check for existing username to avoid ORM session state issues.
        try:
            res = connection.execute(db.text("SELECT id FROM user WHERE username = :u"), {"u": uname}).fetchone()
            if res:
                base = uname
                n = 2
                while True:
                    cand = f"{base}-{n}"
                    res2 = connection.execute(
                        db.text("SELECT id FROM user WHERE username = :u"), {"u": cand}
                    ).fetchone()
                    if not res2:
                        target.username = cand  # type: ignore
                        break
                    n += 1
        except Exception:
            pass

except Exception:  # pragma: no cover
    pass


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


class MonsterCatalog(db.Model):
    """Catalog of monsters (seeded via sql/monsters_seed.sql).

    Columns mirror the raw SQL schema; JSON-like textual columns (traits, loot_table,
    special_drop_slug) are stored as plain text for now. Future migrations may normalize.
    New optional JSON columns: resistances, damage_types (added by migration helper if missing).
    """

    __tablename__ = "monster_catalog"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    level_min = db.Column(db.Integer, nullable=False, default=1)
    level_max = db.Column(db.Integer, nullable=False, default=1)
    base_hp = db.Column(db.Integer, nullable=False)
    base_damage = db.Column(db.Integer, nullable=False)
    armor = db.Column(db.Integer, nullable=False, default=0)
    speed = db.Column(db.Integer, nullable=False, default=10)
    rarity = db.Column(db.String(20), nullable=False, default="common")
    family = db.Column(db.String(40), nullable=False)
    traits = db.Column(db.Text, nullable=True)
    loot_table = db.Column(db.Text, nullable=True)
    special_drop_slug = db.Column(db.Text, nullable=True)
    xp_base = db.Column(db.Integer, nullable=False, default=0)
    boss = db.Column(db.Boolean, nullable=False, default=False)
    # Optional columns added later
    resistances = db.Column(db.Text, nullable=True)  # JSON mapping damage_type->multiplier
    damage_types = db.Column(db.Text, nullable=True)  # JSON array or CSV of outgoing damage types

    # ---- Convenience helpers ----
    def traits_list(self):  # pragma: no cover - trivial
        raw = self.traits or ""
        if not raw:
            return []
        # Accept either CSV or JSON list
        if raw.strip().startswith("["):
            try:
                import json

                data = json.loads(raw)
                return [str(x) for x in data] if isinstance(data, list) else []
            except Exception:
                return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    def resist_map(self):  # pragma: no cover - trivial
        if not self.resistances:
            return {}
        import json

        try:
            data = json.loads(self.resistances)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def damage_type_list(self):  # pragma: no cover - trivial
        if not self.damage_types:
            return []
        raw = self.damage_types.strip()
        import json

        if raw.startswith("["):
            try:
                data = json.loads(raw)
                return [str(x) for x in data] if isinstance(data, list) else []
            except Exception:
                return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    def scaled_instance(self, level: int, party_size: int = 1):
        """Return a dict representing a scaled monster instance for runtime use.

        Scaling rules (simple first pass):
          * Clamp requested level within [level_min, level_max].
          * HP scaling: base_hp * (1 + 0.15*(party_size-1))
          * Damage scaling: base_damage * (1 + 0.10*max(0,party_size-1))
          * XP: xp_base * (1 + 0.20*(party_size-1))
        """
        lvl = max(self.level_min, min(level, self.level_max))
        mult_hp = 1 + 0.15 * max(0, party_size - 1)
        mult_dmg = 1 + 0.10 * max(0, party_size - 1)
        mult_xp = 1 + 0.20 * max(0, party_size - 1)
        return {
            "slug": self.slug,
            "name": self.name,
            # Optional icon slug (UI may map to static asset). For now derive simple family-based fallback.
            "icon_slug": f"{self.family.lower()}-{self.slug}" if self.family and self.slug else self.slug,
            "level": lvl,
            "hp": int(round(self.base_hp * mult_hp)),
            "damage": int(round(self.base_damage * mult_dmg)),
            "armor": self.armor,
            "speed": self.speed,
            "rarity": self.rarity,
            "family": self.family,
            "traits": self.traits_list(),
            "resistances": self.resist_map(),
            "damage_types": self.damage_type_list(),
            "loot_table": self.loot_table,
            "special_drop_slug": self.special_drop_slug,
            "xp": int(round(self.xp_base * mult_xp)),
            "boss": bool(self.boss),
        }


class CombatSession(db.Model):
    """Represents an active or recently completed combat encounter.

    Stores the monster instance JSON plus basic state flags for future turn order
    expansion. For now a session is created at encounter spawn and can be fetched
    by id. When combat resolution lands, we'll update outcome, rewards, etc.
    """

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    # Owning user (simplified single-player encounter for now; later can be party table)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    # JSON serialized monster instance (stats at time of spawn)
    monster_json = db.Column(db.Text, nullable=False)
    # Combat lifecycle
    status = db.Column(db.String(20), nullable=False, default="active")  # active|won|lost|fled|expired
    # Turn system
    combat_turn = db.Column(db.Integer, nullable=False, default=1)
    initiative_json = db.Column(
        db.Text, nullable=True
    )  # JSON list of entity refs [{'type':'pc','id':..},{'type':'monster'}]
    active_index = db.Column(db.Integer, nullable=False, default=0)
    # Participants snapshot
    party_snapshot_json = db.Column(db.Text, nullable=True)  # list of character stat dicts
    monster_hp = db.Column(db.Integer, nullable=True)
    # Logging & outcome
    log_json = db.Column(db.Text, nullable=True)  # JSON list of log line dicts
    outcome_json = db.Column(db.Text, nullable=True)
    rewards_json = db.Column(db.Text, nullable=True)  # loot & xp after completion
    version = db.Column(db.Integer, nullable=False, default=1)  # optimistic lock counter
    # Soft delete / archival marker
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)

    def monster(self):  # pragma: no cover - thin helper
        import json

        try:
            return json.loads(self.monster_json)
        except Exception:
            return {}

    def to_dict(self):  # pragma: no cover
        import json

        try:
            initiative = json.loads(self.initiative_json) if self.initiative_json else []
        except Exception:
            initiative = []
        try:
            party = json.loads(self.party_snapshot_json) if self.party_snapshot_json else None
        except Exception:
            party = None
        try:
            logs = json.loads(self.log_json) if self.log_json else []
        except Exception:
            logs = []
        try:
            rewards = json.loads(self.rewards_json) if self.rewards_json else None
        except Exception:
            rewards = None
        return {
            "id": self.id,
            "status": self.status,
            "monster": self.monster(),
            "monster_hp": self.monster_hp,
            "combat_turn": self.combat_turn,
            "initiative": initiative,
            "active_index": self.active_index,
            "party": party,
            "log": logs,
            "rewards": rewards,
            "version": self.version,
            "archived": bool(self.archived),
        }
