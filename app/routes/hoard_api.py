"""Hoard API: view the per-user vault and withdraw items to a character."""

import json

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.economy import hoard_service
from app.economy.currency import COPPER_PER_GOLD, COPPER_PER_SILVER, format_copper
from app.inventory.utils import load_inventory
from app.models.hoard import Hoard
from app.models.models import Character

bp_hoard = Blueprint("hoard_api", __name__)


@bp_hoard.route("/api/hoard", methods=["GET"])
@login_required
def get_hoard():
    hoard = Hoard.get_or_create(current_user.id)
    db.session.commit()
    # Sum gold across the active session party; fall back to all owned chars
    party = session.get("party") or []
    party_ids = [p["id"] for p in party if isinstance(p, dict) and p.get("id")]
    if party_ids:
        chars = Character.query.filter(Character.id.in_(party_ids), Character.user_id == current_user.id).all()
    else:
        chars = Character.query.filter_by(user_id=current_user.id).all()

    def _char_copper(char):
        try:
            stats = json.loads(char.stats) if char.stats else {}
        except Exception:
            stats = {}
        return (
            int(stats.get("gold", 0) or 0) * COPPER_PER_GOLD
            + int(stats.get("silver", 0) or 0) * COPPER_PER_SILVER
            + int(stats.get("copper", 0) or 0)
        )

    party_gold = sum(_char_copper(c) for c in chars)
    hoard_copper = hoard.copper or 0
    return jsonify(
        {
            "items": json.loads(hoard.items_json or "[]"),
            "copper": hoard_copper,
            "copper_display": format_copper(hoard_copper),
            "party_gold": party_gold,
            "party_gold_display": format_copper(party_gold),
            "total_available": hoard_copper + party_gold,
            "total_available_display": format_copper(hoard_copper + party_gold),
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


@bp_hoard.route("/api/hoard/deposit-item", methods=["POST"])
@login_required
def deposit_item():
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
    ok = hoard_service.deposit_from_character(hoard, char, slug=slug, uid=uid)
    if not ok:
        return jsonify({"error": "Item not in character bag"}), 400
    db.session.commit()

    char_bag = load_inventory(char.items)
    hoard_items = load_inventory(hoard.items_json)
    return jsonify({"success": True, "hoard_items": hoard_items, "char_bag": char_bag})


def _char_copper_hoard(char):
    try:
        stats = json.loads(char.stats) if char.stats else {}
    except Exception:
        stats = {}
    return (
        int(stats.get("gold", 0) or 0) * COPPER_PER_GOLD
        + int(stats.get("silver", 0) or 0) * COPPER_PER_SILVER
        + int(stats.get("copper", 0) or 0)
    )


def _set_char_copper_hoard(char, total_copper):
    try:
        stats = json.loads(char.stats) if char.stats else {}
    except Exception:
        stats = {}
    total_copper = max(0, int(total_copper))
    g, rem = divmod(total_copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    stats["gold"] = g
    stats["silver"] = s
    stats["copper"] = c
    char.stats = json.dumps(stats)


@bp_hoard.route("/api/hoard/currency", methods=["POST"])
@login_required
def transfer_currency():
    data = request.get_json() or {}
    character_id = data.get("character_id")
    direction = data.get("direction")
    if direction not in ("deposit", "withdraw"):
        return jsonify({"error": "direction must be deposit or withdraw"}), 400
    try:
        amount = (
            int(data.get("gold", 0) or 0) * COPPER_PER_GOLD
            + int(data.get("silver", 0) or 0) * COPPER_PER_SILVER
            + int(data.get("copper", 0) or 0)
        )
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(current_user.id)
    char_copper = _char_copper_hoard(char)
    hoard_copper = hoard.copper or 0

    if direction == "deposit":
        if char_copper < amount:
            return jsonify({"error": "Not enough coins on character"}), 400
        _set_char_copper_hoard(char, char_copper - amount)
        hoard.copper = hoard_copper + amount
    else:  # withdraw
        if hoard_copper < amount:
            return jsonify({"error": "Not enough copper in hoard"}), 400
        hoard.copper = hoard_copper - amount
        _set_char_copper_hoard(char, char_copper + amount)

    db.session.commit()
    new_char_copper = _char_copper_hoard(char)
    g, rem = divmod(new_char_copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    return jsonify(
        {
            "success": True,
            "hoard_copper": hoard.copper,
            "hoard_copper_display": format_copper(hoard.copper),
            "char_gold": g,
            "char_silver": s,
            "char_copper": c,
            "char_display": format_copper(new_char_copper),
        }
    )


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
