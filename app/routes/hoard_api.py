"""Hoard API: view the per-user vault and withdraw items to a character."""

import json

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.models.hoard import Hoard
from app.models.models import Character

bp_hoard = Blueprint("hoard_api", __name__)


@bp_hoard.route("/api/hoard", methods=["GET"])
@login_required
def get_hoard():
    hoard = Hoard.get_or_create(current_user.id)
    db.session.commit()
    return jsonify(
        {
            "items": json.loads(hoard.items_json or "[]"),
            "copper": hoard.copper or 0,
            "copper_display": format_copper(hoard.copper or 0),
        }
    )


@bp_hoard.route("/api/hoard/withdraw", methods=["POST"])
@login_required
def withdraw():
    data = request.get_json() or {}
    character_id = data.get("character_id")
    slug = data.get("slug")
    uid = data.get("uid")
    if not character_id or not (slug or uid):
        return jsonify({"error": "Missing required fields"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(current_user.id)
    ok = hoard_service.withdraw_to_character(hoard, char, slug=slug, uid=uid)
    if not ok:
        return jsonify({"error": "Item not in hoard"}), 400
    db.session.commit()
    return jsonify({"success": True})
