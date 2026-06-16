from datetime import datetime

from app import db


class DungeonLoot(db.Model):
    """A loot node on the dungeon floor.

    Exactly one of `item_id` (a catalog Item) or `instance_json` (a procedurally
    generated gear instance dict) is set per row.
    """

    __tablename__ = "dungeon_loot"
    id = db.Column(db.Integer, primary_key=True)
    seed = db.Column(db.BigInteger, index=True, nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    z = db.Column(db.Integer, nullable=False, default=0)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)
    instance_json = db.Column(db.Text, nullable=True)
    claimed = db.Column(db.Boolean, nullable=False, default=False)
    claimed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def mark_claimed(self):
        if not self.claimed:
            from datetime import datetime as _dt

            self.claimed = True
            self.claimed_at = _dt.utcnow()
