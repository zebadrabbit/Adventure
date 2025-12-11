"""
project: Adventure MUD
module: dungeon_tier.py

Dungeon tier system for difficulty scaling (T1-T7).
"""

from app import db


class DungeonTier(db.Model):
    """Dungeon difficulty tier configuration.

    Attributes:
        tier: Tier number (1-7)
        name: Display name (e.g., "Novice", "Heroic")
        min_level: Minimum recommended party level
        max_level: Maximum recommended party level
        monster_level_modifier: Level adjustment for spawned monsters
        loot_quality_bonus: Bonus to loot rarity rolls
        xp_multiplier: XP reward multiplier
        description: Tier description
    """

    __tablename__ = "dungeon_tier"

    id = db.Column(db.Integer, primary_key=True)
    tier = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(40), nullable=False)
    min_level = db.Column(db.Integer, nullable=False)
    max_level = db.Column(db.Integer, nullable=False)
    monster_level_modifier = db.Column(db.Integer, nullable=False, default=0)
    loot_quality_bonus = db.Column(db.Float, nullable=False, default=0.0)
    xp_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    description = db.Column(db.Text, nullable=True)

    def is_appropriate_for_level(self, party_level: int) -> bool:
        """Check if this tier is appropriate for a given party level."""
        return self.min_level <= party_level <= self.max_level

    def __repr__(self):
        return f"<DungeonTier T{self.tier}: {self.name} (L{self.min_level}-{self.max_level})>"


class DungeonAffix(db.Model):
    """Dungeon modifier affixes (Frenzied, Bolstered, Volcanic, Necrotic, etc.).

    Attributes:
        affix_id: Unique identifier (e.g., 'frenzied', 'bolstered')
        name: Display name
        description: Effect description
        monster_hp_multiplier: HP scaling (1.0 = no change, 2.0 = double HP)
        monster_damage_multiplier: Damage scaling
        monster_speed_multiplier: Attack speed scaling
        player_damage_taken_multiplier: Damage taken scaling for players
        special_effect: JSON string for special mechanics
        color: Display color for UI highlighting
    """

    __tablename__ = "dungeon_affix"

    id = db.Column(db.Integer, primary_key=True)
    affix_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    monster_hp_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    monster_damage_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    monster_speed_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    player_damage_taken_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    special_effect = db.Column(db.Text, nullable=True)  # JSON for complex effects
    color = db.Column(db.String(20), nullable=True)  # Hex color for UI

    def apply_to_monster_stats(self, stats: dict) -> dict:
        """Apply affix modifiers to monster stats."""
        modified = stats.copy()
        modified["hp"] = int(stats["hp"] * self.monster_hp_multiplier)
        modified["damage"] = int(stats["damage"] * self.monster_damage_multiplier)
        if "attack_speed" in stats:
            modified["attack_speed"] = stats["attack_speed"] * self.monster_speed_multiplier
        return modified

    def __repr__(self):
        return f"<DungeonAffix {self.affix_id}: {self.name}>"
