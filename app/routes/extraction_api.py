"""Extraction API endpoints.

Handles extraction mechanics, permadeath, and extraction UI.
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character
from app.services import extraction_service

bp_extraction = Blueprint("extraction", __name__)


@bp_extraction.route("/api/dungeon/extraction/status", methods=["GET"])
@login_required
def extraction_status():
    """Get extraction status for current dungeon instance."""
    dungeon_instance_id = request.args.get("instance_id")
    if not dungeon_instance_id:
        from flask import session

        dungeon_instance_id = session.get("dungeon_instance_id")

    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 404

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance or instance.user_id != current_user.id:
        return jsonify({"error": "Instance not found"}), 404

    status = extraction_service.get_extraction_status(instance, current_user.id)
    return jsonify(status)


@bp_extraction.route("/api/dungeon/extraction/extract", methods=["POST"])
@login_required
def extract():
    """Extract selected characters from dungeon.

    Body:
        {
            "instance_id": int,
            "character_ids": [int, ...]  # Characters to extract
        }
    """
    data = request.get_json() or {}
    dungeon_instance_id = data.get("instance_id")
    character_ids = data.get("character_ids", [])

    if not dungeon_instance_id:
        from flask import session

        dungeon_instance_id = session.get("dungeon_instance_id")

    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 400

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance or instance.user_id != current_user.id:
        return jsonify({"error": "Instance not found"}), 404

    if not character_ids:
        return jsonify({"error": "Must select at least one character"}), 400

    success, message, result = extraction_service.extract_party(instance, character_ids, current_user.id)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message, "result": result})


@bp_extraction.route("/api/dungeon/extraction/revive", methods=["POST"])
@login_required
def revive():
    """Revive a dead character (via item/spell/shrine).

    Body:
        {
            "character_id": int
        }
    """
    data = request.get_json() or {}
    character_id = data.get("character_id")

    if not character_id:
        return jsonify({"error": "character_id required"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    success, message = extraction_service.revive_character(char)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message})


@bp_extraction.route("/api/dungeon/extraction/boss_defeated", methods=["POST"])
@login_required
def boss_defeated():
    """Mark a boss as defeated in the dungeon instance.

    Body:
        {
            "instance_id": int (optional, uses session if not provided)
        }
    """
    data = request.get_json() or {}
    dungeon_instance_id = data.get("instance_id")

    if not dungeon_instance_id:
        from flask import session

        dungeon_instance_id = session.get("dungeon_instance_id")

    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 400

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance or instance.user_id != current_user.id:
        return jsonify({"error": "Instance not found"}), 404

    instance.bosses_defeated += 1

    # Check if all bosses defeated (simple: 1 boss per dungeon for now)
    # TODO: Make this configurable based on dungeon tier
    bosses_required = 1  # Can be extended based on tier
    if instance.bosses_defeated >= bosses_required:
        instance.extraction_available = True

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "bosses_defeated": instance.bosses_defeated,
            "extraction_available": instance.extraction_available,
        }
    )
