"""Persistent dungeon entity models.

Introduces `DungeonEntity` for seeding and persisting world entities (monsters,
NPCs, treasure markers, etc.) per `DungeonInstance` so a user can leave and
later continue the same persistent map with unchanged entity placement.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class DungeonEntity(db.Model):
    __tablename__ = "dungeon_entity"

    id = db.Column(db.Integer, primary_key=True)
    # Owning user (mirrors DungeonInstance.user_id) to keep worlds isolated per user.
    user_id = db.Column(db.Integer, index=True, nullable=False)
    # Link to specific dungeon instance; if we later support multiple instances per user this disambiguates.
    instance_id = db.Column(db.Integer, db.ForeignKey("dungeon_instance.id"), index=True, nullable=False)
    seed = db.Column(db.Integer, index=True, nullable=False)
    type = db.Column(db.String(24), nullable=False)  # 'monster' | 'npc' | 'treasure' | future types
    slug = db.Column(db.String(80), nullable=True)
    name = db.Column(db.String(120), nullable=True)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    z = db.Column(db.Integer, nullable=False, default=0)
    hp_current = db.Column(db.Integer, nullable=True)
    # Arbitrary JSON payload (serialized externally) containing full monster stats, dialogue, loot, etc.
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):  # pragma: no cover - thin serializer
        return {
            "id": self.id,
            "type": self.type,
            "slug": self.slug,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "hp_current": self.hp_current,
        }


__all__ = ["DungeonEntity"]
