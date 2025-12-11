"""
project: Adventure MUD
module: weapon_category.py

Weapon category system defining damage dice, attack speeds, and class restrictions.
Based on weapon_categories.csv design specification.
"""

from app import db


class WeaponCategory(db.Model):
    """Weapon category template defining damage mechanics.

    Attributes:
        category_id: Unique identifier (e.g., 'sword_1h', 'dagger')
        name: Display name (e.g., 'One-Handed Sword', 'Dagger')
        weapon_type: Classification (Melee, Ranged, Magic)
        hands: Number of hands required (0 for unarmed, 1 or 2)
        base_dice_count: Number of dice rolled (e.g., 2 for 2d6)
        base_die: Die type (4, 6, 8, 10, 12)
        primary_stat: Damage scaling stat(s) (STR, DEX, INT, WIS, CHA, combinations)
        crit_multiplier: Critical hit damage multiplier (e.g., 1.5 = 150% damage)
        attack_speed: Attack speed modifier (1.0 = baseline, higher = faster)
        tags: Semicolon-separated tags (Versatile, Finesse, Heavy, Brutal, etc.)
        allowed_classes: Semicolon-separated class names that can equip
        notes: Design notes and flavor text
    """

    __tablename__ = "weapon_category"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    weapon_type = db.Column(db.String(20), nullable=False)  # Melee, Ranged, Magic
    hands = db.Column(db.String(10), nullable=False)  # "0", "1", "2", "1/2" (versatile)
    base_dice_count = db.Column(db.Integer, nullable=False, default=1)
    base_die = db.Column(db.Integer, nullable=False, default=6)
    primary_stat = db.Column(db.String(40), nullable=False)  # STR, DEX, STR/DEX, etc.
    crit_multiplier = db.Column(db.Float, nullable=False, default=1.5)
    attack_speed = db.Column(db.Float, nullable=False, default=1.0)
    tags = db.Column(db.Text, nullable=True)  # Semicolon-separated
    allowed_classes = db.Column(db.Text, nullable=True)  # Semicolon-separated
    notes = db.Column(db.Text, nullable=True)

    def has_tag(self, tag: str) -> bool:
        """Check if weapon has a specific tag."""
        if not self.tags:
            return False
        tag_list = [t.strip().lower() for t in self.tags.split(";")]
        return tag.lower() in tag_list

    def is_allowed_for_class(self, class_name: str) -> bool:
        """Check if a character class can equip this weapon category."""
        if not self.allowed_classes:
            return True  # No restrictions
        allowed = [c.strip().lower() for c in self.allowed_classes.split(";")]
        return class_name.lower() in allowed

    def get_damage_dice(self) -> str:
        """Return damage dice notation (e.g., '2d6', '1d12')."""
        return f"{self.base_dice_count}d{self.base_die}"

    def parse_primary_stats(self) -> list[str]:
        """Parse primary stat string into list of stat abbreviations."""
        if not self.primary_stat:
            return []
        # Handle STR/DEX, INT/WIS/CHA, etc.
        return [s.strip().upper() for s in self.primary_stat.replace("/", ",").split(",")]

    def calculate_base_damage(self) -> float:
        """Calculate average base damage (for display/comparison)."""
        avg_die = (self.base_die + 1) / 2.0
        return self.base_dice_count * avg_die

    def __repr__(self):
        return f"<WeaponCategory {self.category_id}: {self.name} ({self.get_damage_dice()})>"
