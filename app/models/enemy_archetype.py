"""
project: Adventure MUD
module: enemy_archetype.py

Enemy archetype system defining template-based scaling for monsters.
Based on enemy_templates.csv from DESIGN.md specification.
"""

from app import db


class EnemyArchetype(db.Model):
    """Enemy archetype template for scaling monster stats.

    Attributes:
        archetype: Template type (Trash, Skirmisher, Brute, Caster, Elite, Champion, Miniboss, Boss)
        rank: Category (Normal, Elite, Boss)
        base_hp: Starting HP at level 1
        hp_per_level: HP gained per level
        base_damage: Starting damage at level 1
        damage_per_level: Damage gained per level
        armor_class_base: Starting AC
        armor_class_per_level: AC gained per level
        xp_base: Starting XP reward
        xp_per_level: XP gained per level
        loot_multiplier: Multiplier for loot quality/quantity
        notes: Design notes and flavor text
    """

    __tablename__ = "enemy_archetype"

    id = db.Column(db.Integer, primary_key=True)
    archetype = db.Column(db.String(40), unique=True, nullable=False, index=True)
    rank = db.Column(db.String(20), nullable=False)  # Normal, Elite, Boss
    base_hp = db.Column(db.Integer, nullable=False, default=25)
    hp_per_level = db.Column(db.Float, nullable=False, default=10.0)
    base_damage = db.Column(db.Integer, nullable=False, default=4)
    damage_per_level = db.Column(db.Float, nullable=False, default=2.0)
    armor_class_base = db.Column(db.Integer, nullable=False, default=10)
    armor_class_per_level = db.Column(db.Float, nullable=False, default=0.3)
    xp_base = db.Column(db.Integer, nullable=False, default=15)
    xp_per_level = db.Column(db.Float, nullable=False, default=5.0)
    loot_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    spawn_weight = db.Column(db.Integer, nullable=False, default=10)
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def calculate_hp(self, level: int) -> int:
        """Calculate HP for a given level."""
        return int(self.base_hp + (self.hp_per_level * (level - 1)))

    def calculate_damage(self, level: int) -> int:
        """Calculate damage for a given level."""
        return int(self.base_damage + (self.damage_per_level * (level - 1)))

    def calculate_armor_class(self, level: int) -> int:
        """Calculate armor class for a given level."""
        return int(self.armor_class_base + (self.armor_class_per_level * (level - 1)))

    def calculate_xp(self, level: int) -> int:
        """Calculate XP reward for a given level."""
        return int(self.xp_base + (self.xp_per_level * (level - 1)))

    def scale_to_level(self, level: int) -> dict:
        """Return fully scaled stats dictionary for a given level."""
        return {
            "archetype": self.archetype,
            "rank": self.rank,
            "level": level,
            "hp": self.calculate_hp(level),
            "damage": self.calculate_damage(level),
            "armor_class": self.calculate_armor_class(level),
            "xp": self.calculate_xp(level),
            "loot_multiplier": self.loot_multiplier,
        }

    def __repr__(self):
        return f"<EnemyArchetype {self.archetype} ({self.rank})>"
