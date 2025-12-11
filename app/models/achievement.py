"""Achievement System Models.

Tracks player accomplishments, milestones, and unlockable achievements.
"""

from datetime import datetime

from app import db


class Achievement(db.Model):
    """Achievement template/definition.

    Attributes:
        id: Primary key
        slug: Unique identifier (e.g., 'first-kill')
        name: Display name
        description: What player must do
        category: combat, exploration, social, progression, collection
        icon: Visual icon identifier
        points: Achievement points awarded
        hidden: Whether achievement is secret until unlocked
        requirement_type: kill_count, level_reached, gold_earned, etc.
        requirement_value: Numeric threshold
        requirement_data: JSON for complex requirements
        reward_gold: Gold awarded on unlock
        reward_items: JSON array of item slugs
        is_active: Whether achievement can be earned
    """

    __tablename__ = "achievement"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    icon = db.Column(db.String(50))
    points = db.Column(db.Integer, default=10)
    hidden = db.Column(db.Boolean, default=False)
    requirement_type = db.Column(db.String(50), nullable=False)
    requirement_value = db.Column(db.Integer, default=1)
    requirement_data = db.Column(db.Text)  # JSON for complex requirements
    reward_gold = db.Column(db.Integer, default=0)
    reward_items = db.Column(db.Text)  # JSON array
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    unlocks = db.relationship("CharacterAchievement", backref="achievement", lazy=True)


class CharacterAchievement(db.Model):
    """Character's unlocked achievements.

    Attributes:
        id: Primary key
        character_id: FK to Character
        achievement_id: FK to Achievement
        progress: Current progress toward requirement
        unlocked: Whether achievement is completed
        unlocked_at: When achievement was earned
        notified: Whether player was shown unlock notification
    """

    __tablename__ = "character_achievement"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey("achievement.id"), nullable=False)
    progress = db.Column(db.Integer, default=0)
    unlocked = db.Column(db.Boolean, nullable=False, default=False)
    unlocked_at = db.Column(db.DateTime)
    notified = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    character = db.relationship("Character", backref="achievements")

    # Ensure one achievement per character
    __table_args__ = (db.UniqueConstraint("character_id", "achievement_id", name="unique_character_achievement"),)


class AchievementCategory(db.Model):
    """Achievement categories for organization.

    Attributes:
        id: Primary key
        slug: Unique identifier
        name: Display name
        description: Category description
        icon: Visual icon
        display_order: Sort order in UI
    """

    __tablename__ = "achievement_category"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    display_order = db.Column(db.Integer, default=0)
