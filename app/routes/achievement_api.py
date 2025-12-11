"""Achievement API Routes.

Provides endpoints for viewing achievements, tracking progress, and unlocking rewards.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from app import db
from app.models.achievement import (
    Achievement,
    AchievementCategory,
    CharacterAchievement,
)
from app.models.models import Character

bp_achievement = Blueprint("achievement", __name__)


@bp_achievement.route("/api/achievements", methods=["GET"])
def get_all_achievements():
    """Get all active achievements."""
    achievements = (
        Achievement.query.filter_by(is_active=True).order_by(Achievement.category, Achievement.points.desc()).all()
    )

    return jsonify(
        [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "icon": a.icon,
                "points": a.points,
                "hidden": a.hidden,
                "requirement_type": a.requirement_type,
                "requirement_value": a.requirement_value,
                "reward_gold": a.reward_gold,
                "reward_items": json.loads(a.reward_items) if a.reward_items else [],
            }
            for a in achievements
        ]
    )


@bp_achievement.route("/api/achievements/categories", methods=["GET"])
def get_achievement_categories():
    """Get all achievement categories."""
    categories = AchievementCategory.query.order_by(AchievementCategory.display_order).all()

    return jsonify(
        [
            {
                "slug": c.slug,
                "name": c.name,
                "description": c.description,
                "icon": c.icon,
                "display_order": c.display_order,
            }
            for c in categories
        ]
    )


@bp_achievement.route("/api/characters/<int:character_id>/achievements", methods=["GET"])
def get_character_achievements(character_id):
    """Get character's achievement progress.

    Returns all achievements with progress and unlock status.
    """
    character = Character.query.get_or_404(character_id)

    # Get all achievements
    achievements = Achievement.query.filter_by(is_active=True).all()

    result = []
    for achievement in achievements:
        # Get or create progress record
        progress = CharacterAchievement.query.filter_by(
            character_id=character_id, achievement_id=achievement.id
        ).first()

        if not progress:
            progress = CharacterAchievement(
                character_id=character_id, achievement_id=achievement.id, progress=0, unlocked=False
            )
            db.session.add(progress)

        result.append(
            {
                "achievement_id": achievement.id,
                "slug": achievement.slug,
                "name": achievement.name,
                "description": achievement.description,
                "category": achievement.category,
                "icon": achievement.icon,
                "points": achievement.points,
                "hidden": achievement.hidden,
                "requirement_type": achievement.requirement_type,
                "requirement_value": achievement.requirement_value,
                "reward_gold": achievement.reward_gold,
                "progress": progress.progress,
                "unlocked": progress.unlocked,
                "unlocked_at": progress.unlocked_at.isoformat() if progress.unlocked_at else None,
                "notified": progress.notified,
            }
        )

    db.session.commit()

    return jsonify(result)


@bp_achievement.route("/api/characters/<int:character_id>/achievements/stats", methods=["GET"])
def get_achievement_stats(character_id):
    """Get character's achievement statistics."""
    character = Character.query.get_or_404(character_id)

    total_achievements = Achievement.query.filter_by(is_active=True).count()
    unlocked = CharacterAchievement.query.filter_by(character_id=character_id, unlocked=True).count()

    total_points = (
        db.session.query(db.func.sum(Achievement.points))
        .join(CharacterAchievement, CharacterAchievement.achievement_id == Achievement.id)
        .filter(CharacterAchievement.character_id == character_id, CharacterAchievement.unlocked == True)
        .scalar()
        or 0
    )

    return jsonify(
        {
            "total_achievements": total_achievements,
            "unlocked": unlocked,
            "locked": total_achievements - unlocked,
            "total_points": total_points,
            "completion_percent": round((unlocked / total_achievements * 100) if total_achievements > 0 else 0, 1),
        }
    )


@bp_achievement.route("/api/characters/<int:character_id>/achievements/check", methods=["POST"])
def check_achievements(character_id):
    """Check and update achievement progress based on game event.

    Request body:
        {
            "event_type": "enemy_kill" | "level_up" | "dungeon_complete" | etc,
            "event_data": {
                "count": 1,  # Increment amount
                "value": 100,  # Or specific value
                ... additional context
            }
        }

    Returns newly unlocked achievements.
    """
    character = Character.query.get_or_404(character_id)
    data = request.json

    event_type = data.get("event_type")
    event_data = data.get("event_data", {})

    if not event_type:
        return jsonify({"error": "event_type required"}), 400

    # Find achievements matching this event type
    matching_achievements = Achievement.query.filter_by(requirement_type=event_type, is_active=True).all()

    newly_unlocked = []

    for achievement in matching_achievements:
        # Get or create progress
        progress = CharacterAchievement.query.filter_by(
            character_id=character_id, achievement_id=achievement.id
        ).first()

        if not progress:
            progress = CharacterAchievement(
                character_id=character_id, achievement_id=achievement.id, progress=0, unlocked=False
            )
            db.session.add(progress)

        # Skip if already unlocked
        if progress.unlocked:
            continue

        # Update progress
        increment = event_data.get("count", 1)
        progress.progress += increment

        # Check if unlocked
        if progress.progress >= achievement.requirement_value:
            progress.unlocked = True
            progress.unlocked_at = datetime.utcnow()
            progress.notified = False  # Will show notification

            # Award rewards
            if achievement.reward_gold > 0:
                character.gold = (character.gold or 0) + achievement.reward_gold

            newly_unlocked.append(
                {
                    "id": achievement.id,
                    "slug": achievement.slug,
                    "name": achievement.name,
                    "description": achievement.description,
                    "icon": achievement.icon,
                    "points": achievement.points,
                    "reward_gold": achievement.reward_gold,
                }
            )

    db.session.commit()

    return jsonify({"checked": len(matching_achievements), "unlocked": newly_unlocked, "count": len(newly_unlocked)})


@bp_achievement.route("/api/characters/<int:character_id>/achievements/<int:achievement_id>/claim", methods=["POST"])
def claim_achievement_reward(character_id, achievement_id):
    """Manually claim achievement reward (if not auto-claimed)."""
    character = Character.query.get_or_404(character_id)
    achievement = Achievement.query.get_or_404(achievement_id)

    progress = CharacterAchievement.query.filter_by(character_id=character_id, achievement_id=achievement_id).first()

    if not progress or not progress.unlocked:
        return jsonify({"error": "Achievement not unlocked"}), 400

    # Award rewards (idempotent - can be called multiple times safely)
    if achievement.reward_gold > 0:
        character.gold = (character.gold or 0) + achievement.reward_gold

    # Mark as notified
    progress.notified = True

    db.session.commit()

    return jsonify({"success": True, "gold_awarded": achievement.reward_gold})


@bp_achievement.route("/api/characters/<int:character_id>/achievements/progress", methods=["POST"])
def update_achievement_progress(character_id):
    """Manually update achievement progress.

    Request body:
        {
            "achievement_slug": "first-blood",
            "progress": 1,
            "set": false  # If true, sets progress; if false, increments
        }
    """
    character = Character.query.get_or_404(character_id)
    data = request.json

    slug = data.get("achievement_slug")
    new_progress = data.get("progress", 1)
    set_mode = data.get("set", False)

    if not slug:
        return jsonify({"error": "achievement_slug required"}), 400

    achievement = Achievement.query.filter_by(slug=slug, is_active=True).first()
    if not achievement:
        return jsonify({"error": "Achievement not found"}), 404

    # Get or create progress
    progress = CharacterAchievement.query.filter_by(character_id=character_id, achievement_id=achievement.id).first()

    if not progress:
        progress = CharacterAchievement(
            character_id=character_id, achievement_id=achievement.id, progress=0, unlocked=False
        )
        db.session.add(progress)

    # Update progress
    if set_mode:
        progress.progress = new_progress
    else:
        progress.progress += new_progress

    # Check if unlocked
    unlocked = False
    if not progress.unlocked and progress.progress >= achievement.requirement_value:
        progress.unlocked = True
        progress.unlocked_at = datetime.utcnow()
        progress.notified = False
        unlocked = True

        # Award rewards
        if achievement.reward_gold > 0:
            character.gold = (character.gold or 0) + achievement.reward_gold

    db.session.commit()

    return jsonify(
        {
            "achievement_id": achievement.id,
            "slug": achievement.slug,
            "progress": progress.progress,
            "requirement": achievement.requirement_value,
            "unlocked": progress.unlocked,
            "newly_unlocked": unlocked,
        }
    )


@bp_achievement.route("/api/achievements/<int:achievement_id>", methods=["GET"])
def get_achievement_details(achievement_id):
    """Get detailed achievement information."""
    achievement = Achievement.query.get_or_404(achievement_id)

    # Count how many characters have unlocked it
    unlock_count = CharacterAchievement.query.filter_by(achievement_id=achievement_id, unlocked=True).count()

    return jsonify(
        {
            "id": achievement.id,
            "slug": achievement.slug,
            "name": achievement.name,
            "description": achievement.description,
            "category": achievement.category,
            "icon": achievement.icon,
            "points": achievement.points,
            "hidden": achievement.hidden,
            "requirement_type": achievement.requirement_type,
            "requirement_value": achievement.requirement_value,
            "requirement_data": json.loads(achievement.requirement_data) if achievement.requirement_data else None,
            "reward_gold": achievement.reward_gold,
            "reward_items": json.loads(achievement.reward_items) if achievement.reward_items else [],
            "unlock_count": unlock_count,
            "created_at": achievement.created_at.isoformat(),
        }
    )


@bp_achievement.route("/api/achievements/recent", methods=["GET"])
def get_recent_achievements():
    """Get recently unlocked achievements across all characters."""
    limit = request.args.get("limit", 10, type=int)

    recent = (
        CharacterAchievement.query.filter_by(unlocked=True)
        .order_by(CharacterAchievement.unlocked_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for ca in recent:
        achievement = Achievement.query.get(ca.achievement_id)
        character = Character.query.get(ca.character_id)

        result.append(
            {
                "achievement_id": achievement.id,
                "achievement_name": achievement.name,
                "achievement_icon": achievement.icon,
                "character_id": character.id,
                "character_name": character.name,
                "unlocked_at": ca.unlocked_at.isoformat(),
            }
        )

    return jsonify(result)
