"""
project: Adventure MUD
module: status_effect.py

Persistent per-character status effects (e.g. poison) that survive past the
end of a single combat encounter, decaying via the overworld GameClock
instead of only combat turns. See app/services/status_effects.py for the
decay/regen logic that reads and writes this table.
"""

from datetime import datetime

from app import db


class CharacterStatusEffect(db.Model):
    """An active status effect attached to a character.

    Attributes:
        character_id: FK to Character.id the effect is attached to.
        name: Effect identifier, e.g. "poison". Only "poison" is supported
            as a persistent effect today; combat-only effects (e.g. "stun")
            never get a row here.
        remaining: Ticks (overworld) or turns (combat) left before the
            effect expires and its row is deleted.
        data: Optional JSON string payload, e.g. '{"damage": 5}'. Mirrors
            the in-memory effect payload shape used by status_effects.py's
            combat-turn handlers, so the same handler functions can read
            either source without translation.
        created_at: Row creation timestamp, for debugging/observability.
    """

    __tablename__ = "character_status_effect"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    remaining = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
