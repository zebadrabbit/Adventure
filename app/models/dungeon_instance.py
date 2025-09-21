from app import db
from flask_login import UserMixin
import datetime

class DungeonInstance(db.Model):
    __tablename__ = 'dungeon_instances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seed = db.Column(db.BigInteger, nullable=False)
    pos_x = db.Column(db.Integer, default=0)
    pos_y = db.Column(db.Integer, default=0)
    pos_z = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Optionally, store a JSON summary or metadata (not the full grid)
    dungeon_metadata = db.Column(db.JSON, default={})

    def __repr__(self):
        return f'<DungeonInstance {self.id} user={self.user_id} seed={self.seed}>'
