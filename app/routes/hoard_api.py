"""Hoard API: view the per-user vault and withdraw items to a character."""

import json

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.inventory.utils import load_inventory
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


@bp_hoard.route("/api/dungeon/loot-body", methods=["POST"])
@login_required
def loot_body():
    """Transfer a downed ally's bag onto a surviving character.

    The downed character keeps is_dead; once looted they are typically left behind
    (permadeath happens at extraction). Only the owner's characters are eligible.
    """
    data = request.get_json() or {}
    downed_id = data.get("downed_id")
    survivor_id = data.get("survivor_id")
    if not downed_id or not survivor_id:
        return jsonify({"error": "Missing required fields"}), 400

    downed = db.session.get(Character, downed_id)
    survivor = db.session.get(Character, survivor_id)
    if not downed or not survivor or downed.user_id != current_user.id or survivor.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404
    if not downed.is_dead:
        return jsonify({"error": "Character is not downed"}), 400
    # Same-run guard: owning both characters isn't enough — survivor must
    # actually be part of the party that started this run, or any character
    # could risklessly vacuum up a downed ally's loot via an uninvolved mule
    # that never entered the dungeon at all.
    current_party_ids = session.get("last_party_ids") or []
    if downed_id not in current_party_ids or survivor_id not in current_party_ids:
        return jsonify({"error": "Character not part of the current run"}), 403

    bag = load_inventory(downed.items)
    survivor_bag = load_inventory(survivor.items)
    for entry in bag:
        survivor_bag.append(entry)
    survivor.items = json.dumps(survivor_bag)
    downed.items = "[]"
    db.session.commit()
    return jsonify({"success": True})
