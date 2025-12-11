"""Procedural affix models for item stat generation.

Affixes are procedurally applied to items during loot generation to create
randomized stat bonuses (Diablo-style prefixes and suffixes).
"""

from app import db


class ProceduralAffix(db.Model):
    """Template for procedural item stat modifiers.

    Affixes are rolled during loot generation based on item rarity tier.
    Each affix adds a random stat bonus within its min/max range.

    Attributes:
        affix_id: Unique string identifier (e.g., 'hp_flat', 'crit_chance')
        name: Display name (e.g., 'of Vitality', 'Brutal')
        slot: 'Prefix' or 'Suffix' (affects name generation)
        affected_stat: Stat key modified (e.g., 'MaxHP', 'STR', 'CritChancePercent')
        min_value: Minimum rolled value
        max_value: Maximum rolled value
        scaling_per_level: Additional bonus per item level
        rarity_weight: Probability weight for affix selection
        allowed_item_types: Semicolon-separated types (e.g., 'Weapon;Armor')
        tags: Semicolon-separated categories (e.g., 'Defensive;Elemental')
        notes: Description of affix effect
    """

    __tablename__ = "procedural_affix"

    id = db.Column(db.Integer, primary_key=True)
    affix_id = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    slot = db.Column(db.String(20), nullable=False)  # Prefix or Suffix
    affected_stat = db.Column(db.String(60), nullable=False)
    min_value = db.Column(db.Float, nullable=False)
    max_value = db.Column(db.Float, nullable=False)
    scaling_per_level = db.Column(db.Float, nullable=False, default=0.0)
    rarity_weight = db.Column(db.Integer, nullable=False, default=100)
    allowed_item_types = db.Column(db.Text, nullable=True)  # Semicolon-separated
    tags = db.Column(db.Text, nullable=True)  # Semicolon-separated
    notes = db.Column(db.Text, nullable=True)

    def is_allowed_for_type(self, item_type: str) -> bool:
        """Check if this affix can apply to the given item type."""
        if not self.allowed_item_types:
            return True
        allowed = [t.strip().lower() for t in self.allowed_item_types.split(";")]
        return item_type.lower() in allowed

    def roll_value(self, item_level: int = 1) -> float:
        """Roll a random value for this affix scaled by item level.

        Args:
            item_level: Item level for scaling bonus

        Returns:
            Final rolled value (base roll + level scaling)
        """
        import random

        base_roll = random.uniform(self.min_value, self.max_value)
        level_bonus = self.scaling_per_level * max(0, item_level - 1)
        return base_roll + level_bonus

    def __repr__(self):
        return f"<ProceduralAffix {self.affix_id} '{self.name}'>"


class ItemAffix(db.Model):
    """Applied affix instance on a specific item drop.

    Links a generated item to its rolled affixes with specific values.
    This allows items to have unique stat combinations.

    Attributes:
        item_id: Foreign key to Item (base item template)
        affix_id: Foreign key to ProceduralAffix (affix template)
        rolled_value: Actual rolled value for this instance
        dungeon_seed: Seed of dungeon where item dropped (for tracking)
        x, y, z: Coordinates where item was placed
    """

    __tablename__ = "item_affix"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    affix_id = db.Column(db.String(60), db.ForeignKey("procedural_affix.affix_id"), nullable=False)
    rolled_value = db.Column(db.Float, nullable=False)
    dungeon_seed = db.Column(db.Integer, nullable=True, index=True)
    x = db.Column(db.Integer, nullable=True)
    y = db.Column(db.Integer, nullable=True)
    z = db.Column(db.Integer, nullable=True)

    # Relationships
    item = db.relationship("Item", backref="affixes")
    affix = db.relationship("ProceduralAffix")

    def __repr__(self):
        return f"<ItemAffix item={self.item_id} affix={self.affix_id} value={self.rolled_value:.1f}>"
