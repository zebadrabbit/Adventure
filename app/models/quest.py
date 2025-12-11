"""Quest System Models.

Database models for quest tracking, NPC quest givers, and quest objectives.
"""

from datetime import datetime

from app import db


class QuestTemplate(db.Model):
    """Quest blueprint/template defining quest structure.

    Attributes:
        id: Primary key
        slug: Unique identifier for quest
        title: Quest name
        description: Quest story/flavor text
        quest_type: Type (main_story, side_quest, daily, repeatable)
        level_min: Minimum level requirement
        level_max: Maximum level (or None for no cap)
        objectives_json: JSON array of objectives [{"type": "kill", "target": "goblin", "count": 5}, ...]
        rewards_json: JSON rewards {"xp": 100, "gold": 50, "items": ["sword"], ...}
        prereq_quest_ids: JSON array of prerequisite quest IDs
        is_active: Whether quest is currently available
    """

    __tablename__ = "quest_template"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quest_type = db.Column(
        db.String(40), nullable=False, default="side_quest"
    )  # main_story, side_quest, daily, repeatable
    level_min = db.Column(db.Integer, nullable=False, default=1)
    level_max = db.Column(db.Integer, nullable=True)  # None = no cap
    objectives_json = db.Column(db.Text, nullable=False)  # [{"type": "kill", "target": "goblin", "count": 5}, ...]
    rewards_json = db.Column(db.Text, nullable=False)  # {"xp": 100, "gold": 50, "items": ["sword"]}
    prereq_quest_ids = db.Column(db.Text, nullable=True)  # JSON array of quest template IDs
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class QuestProgress(db.Model):
    """Character's progress on a quest.

    Attributes:
        id: Primary key
        character_id: FK to Character
        quest_template_id: FK to QuestTemplate
        status: current status (active, completed, failed, abandoned)
        progress_json: JSON tracking objective progress {"kill_goblin": 3, "collect_herbs": 2}
        started_at: When quest was accepted
        completed_at: When quest was completed/failed
    """

    __tablename__ = "quest_progress"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    quest_template_id = db.Column(db.Integer, db.ForeignKey("quest_template.id"), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="active")  # active, completed, failed, abandoned
    progress_json = db.Column(db.Text, nullable=False, default="{}")  # {"kill_goblin": 3, ...}
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    character = db.relationship("Character", backref="quest_progress")
    template = db.relationship("QuestTemplate", backref="progress_records")


class NPC(db.Model):
    """Non-player character that can give quests or provide services.

    Attributes:
        id: Primary key
        slug: Unique identifier
        name: Display name
        npc_type: Type (quest_giver, merchant, trainer, etc.)
        description: Flavor text
        location_type: Where NPC appears (town, dungeon_entrance, random_dungeon)
        location_data: JSON location specifics {"town": "Starting Village", "coordinates": [x, y]}
        dialogue_json: JSON dialogue tree
        quest_pool_json: JSON array of quest template IDs this NPC can offer
        is_active: Whether NPC is currently available
    """

    __tablename__ = "npc"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    npc_type = db.Column(db.String(40), nullable=False, default="quest_giver")  # quest_giver, merchant, trainer
    description = db.Column(db.Text, nullable=True)
    location_type = db.Column(db.String(40), nullable=False, default="town")  # town, dungeon_entrance, random_dungeon
    location_data = db.Column(db.Text, nullable=True)  # JSON: {"town": "Starting Village"}
    dialogue_json = db.Column(db.Text, nullable=True)  # JSON dialogue tree
    quest_pool_json = db.Column(db.Text, nullable=True)  # JSON array of quest template IDs
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sprite_icon = db.Column(db.String(120), nullable=True)  # Bootstrap icon class or emoji
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class QuestLog(db.Model):
    """Historical log of all quest completions for achievements/stats.

    Attributes:
        id: Primary key
        character_id: FK to Character
        quest_template_id: FK to QuestTemplate
        completed_at: Completion timestamp
        rewards_granted_json: JSON of what was actually awarded
    """

    __tablename__ = "quest_log"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    quest_template_id = db.Column(db.Integer, db.ForeignKey("quest_template.id"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    rewards_granted_json = db.Column(db.Text, nullable=True)

    character = db.relationship("Character", backref="quest_log")
    template = db.relationship("QuestTemplate", backref="completion_log")
