"""Quest System API Routes.

Endpoints for quest management, NPC interaction, and quest progression.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.inventory.utils import add_item, dump_inventory, load_inventory
from app.models.models import Character, Item
from app.models.quest import NPC, QuestLog, QuestProgress, QuestTemplate

bp_quest = Blueprint("quest", __name__)


@bp_quest.route("/api/quests/available")
@login_required
def get_available_quests():
    """Get quests available for character based on level and prerequisites.

    Query params: character_id
    """
    character_id = request.args.get("character_id", type=int)
    if not character_id:
        return jsonify({"error": "character_id required"}), 400

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    # Get completed quest IDs for this character
    completed_quest_ids = [
        qp.quest_template_id
        for qp in QuestProgress.query.filter_by(character_id=character_id, status="completed").all()
    ]

    # Get active quest IDs
    active_quest_ids = [
        qp.quest_template_id for qp in QuestProgress.query.filter_by(character_id=character_id, status="active").all()
    ]

    # Find available quests
    available = []
    for quest in QuestTemplate.query.filter_by(is_active=True).all():
        # Skip if already active or completed (unless repeatable)
        if quest.id in active_quest_ids:
            continue
        if quest.id in completed_quest_ids and quest.quest_type != "repeatable":
            continue

        # Check level requirements
        if character.level < quest.level_min:
            continue
        if quest.level_max and character.level > quest.level_max:
            continue

        # Check prerequisites
        if quest.prereq_quest_ids:
            try:
                prereqs = json.loads(quest.prereq_quest_ids)
                if not all(pid in completed_quest_ids for pid in prereqs):
                    continue
            except Exception:
                pass

        available.append(_serialize_quest(quest, None))

    return jsonify({"quests": available})


@bp_quest.route("/api/quests/active")
@login_required
def get_active_quests():
    """Get active and completed quests for character.

    Query params: character_id
    """
    character_id = request.args.get("character_id", type=int)
    if not character_id:
        return jsonify({"error": "character_id required"}), 400

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    # Get active quests
    active_progress = QuestProgress.query.filter_by(character_id=character_id, status="active").all()

    active = [_serialize_quest(qp.template, qp) for qp in active_progress]

    # Get completed quests
    completed_progress = (
        QuestProgress.query.filter_by(character_id=character_id, status="completed")
        .order_by(QuestProgress.completed_at.desc())
        .limit(10)
        .all()
    )

    completed = [_serialize_quest(qp.template, qp) for qp in completed_progress]

    return jsonify({"active": active, "completed": completed})


@bp_quest.route("/api/quests/accept", methods=["POST"])
@login_required
def accept_quest():
    """Accept a quest for a character.

    Body: { character_id: int, quest_id: int }
    """
    data = request.get_json()
    character_id = data.get("character_id")
    quest_id = data.get("quest_id")

    if not character_id or not quest_id:
        return jsonify({"error": "character_id and quest_id required"}), 400

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    quest = db.session.get(QuestTemplate, quest_id)
    if not quest or not quest.is_active:
        return jsonify({"error": "Quest not found"}), 404

    # Check if already active
    existing = QuestProgress.query.filter_by(
        character_id=character_id, quest_template_id=quest_id, status="active"
    ).first()

    if existing:
        return jsonify({"error": "Quest already active"}), 400

    # Create progress record
    progress = QuestProgress(character_id=character_id, quest_template_id=quest_id, status="active", progress_json="{}")

    db.session.add(progress)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Database error"}), 500

    return jsonify({"success": True, "quest": _serialize_quest(quest, progress)})


@bp_quest.route("/api/quests/complete", methods=["POST"])
@login_required
def complete_quest():
    """Complete a quest and grant rewards.

    Body: { character_id: int, quest_id: int }
    """
    data = request.get_json()
    character_id = data.get("character_id")
    quest_id = data.get("quest_id")

    if not character_id or not quest_id:
        return jsonify({"error": "character_id and quest_id required"}), 400

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    # Find active progress
    progress = QuestProgress.query.filter_by(
        character_id=character_id, quest_template_id=quest_id, status="active"
    ).first()

    if not progress:
        return jsonify({"error": "Quest not active"}), 404

    quest = progress.template

    # Verify all objectives complete
    try:
        objectives = json.loads(quest.objectives_json)
        progress_data = json.loads(progress.progress_json)

        for obj in objectives:
            obj_id = obj.get("id", obj.get("type"))
            required = obj.get("count", 1)
            current = progress_data.get(obj_id, 0)

            if current < required:
                return jsonify({"error": "Objectives not complete"}), 400
    except Exception:
        pass

    # Grant rewards
    try:
        rewards = json.loads(quest.rewards_json)
    except Exception:
        rewards = {}

    granted = {}

    # XP
    if rewards.get("xp"):
        character.xp += int(rewards["xp"])
        granted["xp"] = rewards["xp"]

        # Check for level up
        from app.services.combat_service import _xp_required

        while character.xp >= _xp_required(character.level):
            character.level += 1

    # Gold (would need gold field on Character)
    if rewards.get("gold"):
        granted["gold"] = rewards["gold"]
        # TODO: Add gold to character when field exists

    # Items
    if rewards.get("items"):
        inv = load_inventory(character.items)
        granted_items = []

        for item_slug in rewards["items"]:
            item = Item.query.filter_by(slug=item_slug).first()
            if item:
                add_item(inv, item_slug, 1)
                granted_items.append(item_slug)

        character.items = dump_inventory(inv)
        granted["items"] = granted_items

    # Mark quest complete
    progress.status = "completed"
    progress.completed_at = datetime.utcnow()

    # Add to quest log
    log_entry = QuestLog(
        character_id=character_id, quest_template_id=quest_id, rewards_granted_json=json.dumps(granted)
    )
    db.session.add(log_entry)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Database error"}), 500

    return jsonify({"success": True, "rewards": granted})


@bp_quest.route("/api/quests/progress", methods=["POST"])
@login_required
def update_quest_progress():
    """Update progress on a quest objective.

    Body: { character_id: int, quest_id: int, objective_id: str, amount: int }
    """
    data = request.get_json()
    character_id = data.get("character_id")
    quest_id = data.get("quest_id")
    objective_id = data.get("objective_id")
    amount = data.get("amount", 1)

    if not all([character_id, quest_id, objective_id]):
        return jsonify({"error": "Missing required fields"}), 400

    progress = QuestProgress.query.filter_by(
        character_id=character_id, quest_template_id=quest_id, status="active"
    ).first()

    if not progress:
        return jsonify({"error": "Quest not active"}), 404

    # Update progress
    try:
        progress_data = json.loads(progress.progress_json)
        progress_data[objective_id] = progress_data.get(objective_id, 0) + amount
        progress.progress_json = json.dumps(progress_data)

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Database error"}), 500

    return jsonify({"success": True, "progress": progress_data})


@bp_quest.route("/api/npcs/<slug>")
@login_required
def get_npc(slug):
    """Get NPC details including dialogue and available quests."""
    npc = NPC.query.filter_by(slug=slug, is_active=True).first()
    if not npc:
        return jsonify({"error": "NPC not found"}), 404

    # Get dialogue
    try:
        dialogue_data = json.loads(npc.dialogue_json or "{}")
        dialogue = dialogue_data.get("greeting", "Greetings, adventurer!")
    except Exception:
        dialogue = "Greetings, adventurer!"

    # Get available quest
    quest_data = None
    if npc.quest_pool_json:
        try:
            quest_pool = json.loads(npc.quest_pool_json)
            if quest_pool:
                # Get first available quest from pool
                quest = db.session.get(QuestTemplate, quest_pool[0])
                if quest and quest.is_active:
                    quest_data = _serialize_quest(quest, None)
        except Exception:
            pass

    return jsonify(
        {
            "slug": npc.slug,
            "name": npc.name,
            "title": npc.npc_type.replace("_", " ").title(),
            "description": npc.description,
            "dialogue": dialogue,
            "icon": npc.sprite_icon or '<i class="bi bi-person-fill"></i>',
            "quest": quest_data,
        }
    )


# ── Daily / Weekly quests (user-scoped, auto-generated) ──────────────────


@bp_quest.route("/api/quests/daily")
@login_required
def get_daily_quests():
    from app.services.quest_generator import get_or_generate_daily

    quests = get_or_generate_daily(current_user.id)
    return jsonify({"quests": quests})


@bp_quest.route("/api/quests/weekly")
@login_required
def get_weekly_quest():
    from app.services.quest_generator import get_or_generate_weekly

    quest = get_or_generate_weekly(current_user.id)
    return jsonify({"quest": quest})


@bp_quest.route("/api/quests/daily/claim", methods=["POST"])
@login_required
def claim_daily_quest():
    data = request.get_json() or {}
    quest_id = data.get("quest_id")
    if not quest_id:
        return jsonify({"error": "quest_id required"}), 400

    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    pool = UserQuestPool.get_or_none(current_user.id, "daily", period_key_daily())
    if not pool:
        return jsonify({"error": "No daily quests found"}), 404

    quests = json.loads(pool.quests_json)
    quest = next((q for q in quests if q["id"] == quest_id), None)
    if not quest:
        return jsonify({"error": "Quest not found"}), 404
    if quest["status"] != "active" and quest["status"] != "complete":
        return jsonify({"error": "Quest already claimed"}), 400
    if quest.get("claimed_at"):
        return jsonify({"error": "Quest already claimed"}), 400

    obj = quest["objective"]
    if obj.get("current", 0) < obj.get("target", 1):
        return jsonify({"error": "Quest not complete yet"}), 400

    rewards = _grant_daily_rewards(current_user.id, quest["rewards"])
    quest["status"] = "claimed"
    quest["claimed_at"] = datetime.utcnow().isoformat()
    pool.quests_json = json.dumps(quests)
    db.session.commit()

    from app.services import quest_progress_service

    quest_progress_service.increment_daily_completions(current_user.id)

    return jsonify({"success": True, "rewards": rewards, "quest": quest})


@bp_quest.route("/api/quests/weekly/claim", methods=["POST"])
@login_required
def claim_weekly_quest():
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_weekly

    pool = UserQuestPool.get_or_none(current_user.id, "weekly", period_key_weekly())
    if not pool:
        return jsonify({"error": "No weekly quest found"}), 404

    quests = json.loads(pool.quests_json)
    if not quests:
        return jsonify({"error": "Weekly quest not found"}), 404
    quest = quests[0]

    if quest.get("claimed_at"):
        return jsonify({"error": "Weekly already claimed"}), 400

    obj = quest["objective"]
    if obj.get("current", 0) < obj.get("target", 10):
        return jsonify({"error": "Weekly not complete yet"}), 400

    rewards = _grant_daily_rewards(current_user.id, quest["rewards"])
    quest["status"] = "claimed"
    quest["claimed_at"] = datetime.utcnow().isoformat()
    pool.quests_json = json.dumps(quests)
    db.session.commit()

    return jsonify({"success": True, "rewards": rewards, "quest": quest})


def _grant_daily_rewards(user_id: int, rewards: dict) -> dict:
    """Grant XP to all characters, potions+copper to hoard. Returns summary."""
    from app.models.hoard import Hoard
    from app.models.models import Character

    granted = {}
    chars = Character.query.filter_by(user_id=user_id).all()

    # XP split across all characters
    xp = int(rewards.get("xp", 0))
    if xp and chars:
        share = max(1, xp // len(chars))
        for c in chars:
            c.xp = (c.xp or 0) + share
        granted["xp"] = xp

    # Potions to hoard
    hoard = Hoard.get_or_create(user_id)
    inv = load_inventory(hoard.items_json)
    potions_granted = []
    for potion in rewards.get("potions", []):
        slug = potion.get("slug")
        qty = int(potion.get("qty", 1))
        if slug:
            add_item(inv, slug, qty)
            potions_granted.append({"slug": slug, "qty": qty})
    hoard.items_json = dump_inventory(inv)
    granted["potions"] = potions_granted

    # Bonus copper
    copper = int(rewards.get("copper", 0))
    if copper:
        hoard.copper = (hoard.copper or 0) + copper
        granted["copper"] = copper

    # Gear roll (TODO: wire to loot generator when rewards.get("gear_roll") is True)
    granted["gear_roll"] = rewards.get("gear_roll", False)

    db.session.commit()
    return granted


def _serialize_quest(quest: QuestTemplate, progress: QuestProgress | None) -> dict:
    """Serialize quest template with optional progress data."""
    try:
        objectives = json.loads(quest.objectives_json)
    except Exception:
        objectives = []

    try:
        rewards = json.loads(quest.rewards_json)
    except Exception:
        rewards = {}

    progress_data = {}
    if progress and progress.progress_json:
        try:
            progress_data = json.loads(progress.progress_json)
        except Exception:
            pass

    return {
        "id": quest.id,
        "slug": quest.slug,
        "title": quest.title,
        "description": quest.description,
        "type": quest.quest_type,
        "level_min": quest.level_min,
        "level_max": quest.level_max,
        "objectives": objectives,
        "rewards": rewards,
        "progress": progress_data,
        "status": progress.status if progress else None,
        "started_at": progress.started_at.isoformat() if progress and progress.started_at else None,
    }
