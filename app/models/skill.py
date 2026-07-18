"""Skill and Talent Tree Models.

Provides character progression through unlockable skills and talent trees.
"""

from datetime import datetime

from app import db


class SkillTree(db.Model):
    """Skill tree template (warrior tree, mage tree, etc.).

    Attributes:
        id: Primary key
        name: Tree name (e.g., "Warrior Combat Tree")
        class_requirement: Required class to unlock (warrior, mage, etc.)
        description: Tree description
        icon: Visual icon identifier
        max_tier: Maximum tier in this tree
        is_active: Whether tree is available
    """

    __tablename__ = "skill_tree"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_requirement = db.Column(db.String(30))
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    max_tier = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    skills = db.relationship("Skill", backref="skill_tree", lazy=True, cascade="all, delete-orphan")

    def allows_class(self, char_class: str | None) -> bool:
        """True if this tree is universal or char_class is in the comma list."""
        if not self.class_requirement:
            return True
        if not char_class:
            return False
        allowed = {c.strip().lower() for c in self.class_requirement.split(",")}
        return char_class.strip().lower() in allowed


class Skill(db.Model):
    """Individual skill/talent in a tree.

    Attributes:
        id: Primary key
        tree_id: FK to SkillTree
        name: Skill name
        description: What the skill does
        tier: Skill tier (1-5, higher = more powerful)
        position_x: X coordinate in tree visualization
        position_y: Y coordinate in tree visualization
        required_level: Character level needed to unlock
        required_skill_id: Parent skill that must be learned first
        cost: Skill points needed to unlock
        effect_json: JSON data for skill effects
        cooldown: Cooldown in seconds (for active skills)
        skill_type: passive, active, toggle
        icon: Visual icon identifier
    """

    __tablename__ = "skill"

    id = db.Column(db.Integer, primary_key=True)
    tree_id = db.Column(db.Integer, db.ForeignKey("skill_tree.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tier = db.Column(db.Integer, nullable=False, default=1)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    required_level = db.Column(db.Integer, default=1)
    required_skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"))
    cost = db.Column(db.Integer, nullable=False, default=1)
    effect_json = db.Column(db.Text, nullable=False)
    cooldown = db.Column(db.Integer)  # Seconds
    mana_cost = db.Column(db.Integer, nullable=False, server_default="0", default=0)
    skill_type = db.Column(db.String(20), nullable=False, default="passive")
    icon = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Self-referential relationship for prerequisites
    required_skill = db.relationship("Skill", remote_side=[id], backref="unlocks")

    # Relationship to character skills
    character_skills = db.relationship("CharacterSkill", backref="skill", lazy=True)


class CharacterSkill(db.Model):
    """Character's learned skills.

    Attributes:
        id: Primary key
        character_id: FK to Character
        skill_id: FK to Skill
        unlocked_at: When skill was learned
        skill_rank: How many times upgraded (1-5)
        times_used: Usage counter for active skills
        last_used: Last time skill was activated
    """

    __tablename__ = "character_skill"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    skill_rank = db.Column(db.Integer, nullable=False, default=1)
    times_used = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)

    # Relationships
    character = db.relationship("Character", backref="learned_skills")

    # Ensure one skill per character
    __table_args__ = (db.UniqueConstraint("character_id", "skill_id", name="unique_character_skill"),)


class CharacterTalentPoints(db.Model):
    """Track available and spent talent points per character.

    Attributes:
        id: Primary key
        character_id: FK to Character
        total_earned: Total points ever earned (from leveling)
        total_spent: Points spent on skills
        available: Current unspent points
    """

    __tablename__ = "character_talent_points"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, unique=True)
    total_earned = db.Column(db.Integer, nullable=False, default=0)
    total_spent = db.Column(db.Integer, nullable=False, default=0)
    available = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    character = db.relationship("Character", backref="talent_points_record")
