"""Skill Tree API Routes.

Provides endpoints for skill trees, talent points, and skill unlocking.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from app import db
from app.models.models import Character
from app.models.skill import CharacterSkill, CharacterTalentPoints, Skill, SkillTree

bp_skill = Blueprint("skill", __name__)


@bp_skill.route("/api/skill-trees", methods=["GET"])
def get_skill_trees():
    """Get all active skill trees."""
    trees = SkillTree.query.filter_by(is_active=True).all()

    return jsonify(
        [
            {
                "id": tree.id,
                "name": tree.name,
                "class_requirement": tree.class_requirement,
                "description": tree.description,
                "icon": tree.icon,
                "max_tier": tree.max_tier,
                "is_active": tree.is_active,
            }
            for tree in trees
        ]
    )


@bp_skill.route("/api/skill-trees/<int:tree_id>/skills", methods=["GET"])
def get_tree_skills(tree_id):
    """Get all skills in a specific tree."""
    tree = db.session.get(SkillTree, tree_id)
    if not tree:
        return jsonify({"error": "Skill tree not found"}), 404

    skills = Skill.query.filter_by(tree_id=tree_id, is_active=True).all()

    return jsonify(
        [
            {
                "id": skill.id,
                "tree_id": skill.tree_id,
                "name": skill.name,
                "description": skill.description,
                "tier": skill.tier,
                "position_x": skill.position_x,
                "position_y": skill.position_y,
                "required_level": skill.required_level,
                "required_skill_id": skill.required_skill_id,
                "cost": skill.cost,
                "effect_json": skill.effect_json,
                "cooldown": skill.cooldown,
                "skill_type": skill.skill_type,
                "icon": skill.icon,
            }
            for skill in skills
        ]
    )


@bp_skill.route("/api/characters/<int:character_id>/talent-points", methods=["GET"])
def get_talent_points(character_id):
    """Get character's talent points."""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    # Get or create talent points record
    talent_points = CharacterTalentPoints.query.filter_by(character_id=character_id).first()

    if not talent_points:
        # Initialize talent points (1 per level)
        talent_points = CharacterTalentPoints(
            character_id=character_id, total_earned=character.level, total_spent=0, available=character.level
        )
        db.session.add(talent_points)
        db.session.commit()

    return jsonify(
        {
            "character_id": character_id,
            "total_earned": talent_points.total_earned,
            "total_spent": talent_points.total_spent,
            "available": talent_points.available,
            "last_updated": talent_points.last_updated.isoformat() if talent_points.last_updated else None,
        }
    )


@bp_skill.route("/api/characters/<int:character_id>/skills", methods=["GET"])
def get_character_skills(character_id):
    """Get all skills learned by a character."""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    character_skills = CharacterSkill.query.filter_by(character_id=character_id).all()

    result = []
    for cs in character_skills:
        skill = cs.skill
        result.append(
            {
                "character_skill_id": cs.id,
                "skill_id": skill.id,
                "skill_name": skill.name,
                "skill_description": skill.description,
                "skill_type": skill.skill_type,
                "tier": skill.tier,
                "effect_json": skill.effect_json,
                "skill_rank": cs.skill_rank,
                "times_used": cs.times_used,
                "unlocked_at": cs.unlocked_at.isoformat() if cs.unlocked_at else None,
                "last_used": cs.last_used.isoformat() if cs.last_used else None,
            }
        )

    return jsonify(result)


@bp_skill.route("/api/characters/<int:character_id>/skills", methods=["POST"])
def unlock_skill(character_id):
    """Unlock a skill for a character."""
    data = request.get_json()
    skill_id = data.get("skill_id")

    if not skill_id:
        return jsonify({"error": "Missing skill_id"}), 400

    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    skill = db.session.get(Skill, skill_id)
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    # Check if already unlocked
    existing = CharacterSkill.query.filter_by(character_id=character_id, skill_id=skill_id).first()

    if existing:
        return jsonify({"error": "Skill already unlocked"}), 400

    # Check level requirement
    if character.level < skill.required_level:
        return jsonify({"error": f"Requires level {skill.required_level}"}), 400

    # Check prerequisite skill
    if skill.required_skill_id:
        prerequisite = CharacterSkill.query.filter_by(
            character_id=character_id, skill_id=skill.required_skill_id
        ).first()

        if not prerequisite:
            prereq_skill = db.session.get(Skill, skill.required_skill_id)
            return jsonify({"error": f'Requires skill: {prereq_skill.name if prereq_skill else "Unknown"}'}), 400

    # Check talent points
    talent_points = CharacterTalentPoints.query.filter_by(character_id=character_id).first()

    if not talent_points:
        # Initialize talent points
        talent_points = CharacterTalentPoints(
            character_id=character_id, total_earned=character.level, total_spent=0, available=character.level
        )
        db.session.add(talent_points)

    if talent_points.available < skill.cost:
        return jsonify({"error": f"Insufficient talent points. Need {skill.cost}, have {talent_points.available}"}), 400

    # Unlock the skill
    character_skill = CharacterSkill(character_id=character_id, skill_id=skill_id, skill_rank=1)

    # Deduct talent points
    talent_points.total_spent += skill.cost
    talent_points.available -= skill.cost
    talent_points.last_updated = datetime.utcnow()

    db.session.add(character_skill)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "skill_id": skill_id,
            "skill_name": skill.name,
            "remaining_points": talent_points.available,
            "message": f"Unlocked {skill.name}!",
        }
    )


@bp_skill.route("/api/characters/<int:character_id>/skills/<int:skill_id>/use", methods=["POST"])
def use_skill(character_id, skill_id):
    """Use an active skill (track usage)."""
    character_skill = CharacterSkill.query.filter_by(character_id=character_id, skill_id=skill_id).first()

    if not character_skill:
        return jsonify({"error": "Skill not unlocked"}), 404

    skill = character_skill.skill

    if skill.skill_type != "active":
        return jsonify({"error": "Only active skills can be used"}), 400

    # Check cooldown (simplified - you'd want more sophisticated cooldown tracking)
    if character_skill.last_used and skill.cooldown:
        time_since_use = (datetime.utcnow() - character_skill.last_used).total_seconds()
        if time_since_use < skill.cooldown:
            remaining = skill.cooldown - time_since_use
            return jsonify({"error": "Skill on cooldown", "remaining_seconds": int(remaining)}), 400

    # Update usage
    character_skill.times_used += 1
    character_skill.last_used = datetime.utcnow()
    db.session.commit()

    # Parse and return effects
    effects = json.loads(skill.effect_json)

    return jsonify(
        {
            "success": True,
            "skill_name": skill.name,
            "effects": effects,
            "times_used": character_skill.times_used,
            "message": f"Used {skill.name}!",
        }
    )


@bp_skill.route("/api/characters/<int:character_id>/talent-points/grant", methods=["POST"])
def grant_talent_points(character_id):
    """Grant talent points to a character (typically on level up)."""
    data = request.get_json()
    points = data.get("points", 1)

    if points < 1:
        return jsonify({"error": "Invalid point amount"}), 400

    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    talent_points = CharacterTalentPoints.query.filter_by(character_id=character_id).first()

    if not talent_points:
        talent_points = CharacterTalentPoints(
            character_id=character_id, total_earned=points, total_spent=0, available=points
        )
        db.session.add(talent_points)
    else:
        talent_points.total_earned += points
        talent_points.available += points
        talent_points.last_updated = datetime.utcnow()

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "points_granted": points,
            "new_total": talent_points.total_earned,
            "available": talent_points.available,
        }
    )


@bp_skill.route("/api/characters/<int:character_id>/skills/reset", methods=["POST"])
def reset_skills(character_id):
    """Reset all skills and refund talent points (respec)."""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    # Get all character skills
    character_skills = CharacterSkill.query.filter_by(character_id=character_id).all()

    # Delete all learned skills
    for cs in character_skills:
        db.session.delete(cs)

    # Reset talent points
    talent_points = CharacterTalentPoints.query.filter_by(character_id=character_id).first()

    if talent_points:
        talent_points.available = talent_points.total_earned
        talent_points.total_spent = 0
        talent_points.last_updated = datetime.utcnow()

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "skills_reset": len(character_skills),
            "refunded_points": talent_points.total_earned if talent_points else 0,
            "message": "Skills reset successfully!",
        }
    )


@bp_skill.route("/api/skills/<int:skill_id>", methods=["GET"])
def get_skill_details(skill_id):
    """Get detailed information about a specific skill."""
    skill = db.session.get(Skill, skill_id)
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    tree = skill.skill_tree

    # Get prerequisite skill if exists
    prereq = None
    if skill.required_skill_id:
        prereq_skill = db.session.get(Skill, skill.required_skill_id)
        if prereq_skill:
            prereq = {"id": prereq_skill.id, "name": prereq_skill.name}

    return jsonify(
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "tree_name": tree.name,
            "tree_id": tree.id,
            "tier": skill.tier,
            "position_x": skill.position_x,
            "position_y": skill.position_y,
            "required_level": skill.required_level,
            "prerequisite": prereq,
            "cost": skill.cost,
            "effects": json.loads(skill.effect_json),
            "cooldown": skill.cooldown,
            "skill_type": skill.skill_type,
            "icon": skill.icon,
        }
    )
