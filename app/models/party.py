"""Party Management Models.

Enhanced party system with formations, shared resources, and party buffs.
"""

from datetime import datetime

from app import db


class Party(db.Model):
    """Party group with persistent data across dungeon runs.

    Attributes:
        id: Primary key
        name: Party name
        leader_id: FK to Character who leads
        formation: JSON formation data (positions, roles)
        shared_gold: Party treasury for shared expenses
        party_level: Average level of active members
        created_at: When party was formed
        last_active: Last dungeon entry
    """

    __tablename__ = "party"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=True)
    formation_json = db.Column(db.Text, default="{}")  # {"positions": {...}, "roles": {...}}
    shared_gold = db.Column(db.Integer, nullable=False, default=0)
    party_level = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_active = db.Column(db.DateTime)

    # Relationships
    leader = db.relationship("Character", foreign_keys=[leader_id], backref="led_parties")
    members = db.relationship("PartyMember", backref="party", lazy=True, cascade="all, delete-orphan")
    buffs = db.relationship("PartyBuff", backref="party", lazy=True, cascade="all, delete-orphan")


class PartyMember(db.Model):
    """Character membership in a party.

    Attributes:
        id: Primary key
        party_id: FK to Party
        character_id: FK to Character
        role: Tank, DPS, Healer, Support
        position: Formation position (front, middle, back)
        joined_at: When character joined party
    """

    __tablename__ = "party_member"

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False)
    role = db.Column(db.String(20), default="dps")  # tank, dps, healer, support
    position = db.Column(db.String(20), default="middle")  # front, middle, back
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    character = db.relationship("Character", backref="party_memberships")

    # Ensure one character per party
    __table_args__ = (db.UniqueConstraint("party_id", "character_id", name="unique_party_character"),)


class PartyBuff(db.Model):
    """Active buffs/bonuses for a party.

    Attributes:
        id: Primary key
        party_id: FK to Party
        buff_type: leadership, synergy, formation, item
        name: Buff display name
        effect_json: JSON effect data (stat bonuses, abilities)
        duration: How long buff lasts (in game ticks, null = permanent)
        expires_at: When buff expires
        source: Where buff came from (character, item, quest)
    """

    __tablename__ = "party_buff"

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False)
    buff_type = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    effect_json = db.Column(db.Text, nullable=False)  # {"hp": +10, "damage": +5%}
    duration = db.Column(db.Integer)  # Game ticks
    expires_at = db.Column(db.DateTime)
    source = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PartySharedInventory(db.Model):
    """Shared party storage for consumables and resources.

    Attributes:
        id: Primary key
        party_id: FK to Party
        item_slug: Item identifier
        quantity: How many in shared storage
        added_by: Character ID who added it
        added_at: When item was added
    """

    __tablename__ = "party_shared_inventory"

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False)
    item_slug = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_by = db.Column(db.Integer, db.ForeignKey("character.id"))
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    contributor = db.relationship("Character", backref="party_contributions")

    # One entry per item per party
    __table_args__ = (db.UniqueConstraint("party_id", "item_slug", name="unique_party_item"),)
