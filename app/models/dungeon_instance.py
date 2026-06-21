import datetime
import json

from app import db


class DungeonInstance(db.Model):
    # Use singular table name to align with foreign key references (dungeon_instance.id)
    __tablename__ = "dungeon_instance"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seed = db.Column(db.BigInteger, nullable=False)
    pos_x = db.Column(db.Integer, default=0)
    pos_y = db.Column(db.Integer, default=0)
    pos_z = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Optionally, store a JSON summary or metadata (not the full grid)
    dungeon_metadata = db.Column(db.JSON, default={})
    # Enemy scaling system
    tier = db.Column(db.Integer, default=1)
    affix_ids = db.Column(db.Text, nullable=True)  # JSON array of affix_id strings
    monster_family = db.Column(db.String(40), nullable=True)  # Per-instance enemy theme (MonsterCatalog.family value)
    # Extraction mechanics and progress tracking
    bosses_defeated = db.Column(db.Integer, default=0)
    bosses_total = db.Column(db.Integer, default=1)  # Total bosses in dungeon
    elites_defeated = db.Column(db.Integer, default=0)
    monsters_defeated = db.Column(db.Integer, default=0)
    extraction_available = db.Column(db.Boolean, default=False)
    # Track unlocked doors by coordinate "x,y"
    unlocked_doors_json = db.Column(db.Text, nullable=True)

    def get_unlocked_doors(self):
        """Parse unlocked_doors_json into set of (x,y) tuples."""
        if not self.unlocked_doors_json:
            return set()
        try:
            data = json.loads(self.unlocked_doors_json)
            return {tuple(coord) for coord in data}
        except Exception:
            return set()

    def unlock_door(self, x, y):
        """Mark a door at (x,y) as unlocked."""
        unlocked = self.get_unlocked_doors()
        unlocked.add((x, y))
        self.unlocked_doors_json = json.dumps(list(unlocked))

    def is_door_unlocked(self, x, y):
        """Check if door at (x,y) is unlocked."""
        return (x, y) in self.get_unlocked_doors()

    def get_affixes(self):
        """Parse affix_ids JSON string into list."""
        if not self.affix_ids:
            return []
        try:
            return json.loads(self.affix_ids)
        except Exception:
            return []

    def set_affixes(self, affix_list):
        """Set affix_ids from a list of affix_id strings."""
        self.affix_ids = json.dumps(affix_list) if affix_list else None

    def __repr__(self):
        return f"<DungeonInstance {self.id} user={self.user_id} seed={self.seed} tier={self.tier}>"
