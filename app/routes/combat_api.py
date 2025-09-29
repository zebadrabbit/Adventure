"""Combat API blueprint.

Provides read/update endpoints over existing combat_service. This keeps the
route layer thin; business logic remains in service.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template  # add render_template
from flask_login import current_user, login_required

from app import db
from app.models.models import CombatSession
from app.services import combat_service

bp_combat = Blueprint("combat", __name__)


def _session_or_404(combat_id: int):  # small helper
    row = CombatSession.query.filter_by(id=combat_id, archived=False).first()
    if not row:
        return None, (jsonify({"error": "not_found"}), 404)
    return row, None


@bp_combat.route("/api/combat/<int:combat_id>/state", methods=["GET"])  # poll fallback
@login_required
def combat_state(combat_id: int):
    row, err = _session_or_404(combat_id)
    if err:
        return err
    if row.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    data = row.to_dict()
    # Add derived monster_max_hp for front-end bars (monster dict already has hp snapshot)
    try:
        data["monster_max_hp"] = data.get("monster", {}).get("hp")
    except Exception:
        data["monster_max_hp"] = None
    return jsonify({"ok": True, "state": data})


@bp_combat.route("/api/combat/<int:combat_id>/attack", methods=["POST"])  # basic attack
@login_required
def combat_attack(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    result = combat_service.player_attack(combat_id, current_user.id, version, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/flee", methods=["POST"])  # attempt flee
@login_required
def combat_flee(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    result = combat_service.player_flee(combat_id, current_user.id, version, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/end_turn", methods=["POST"])  # placeholder end-turn (no action)
@login_required
def combat_end_turn(combat_id: int):
    # For now just advance turn if it's player's turn but they choose to skip.
    import json as _json

    from app.services.combat_service import (
        _advance_turn,
        _check_end,
        _emit_session,
        _load_session,
    )

    session = _load_session(combat_id)
    if not session:
        return jsonify({"error": "not_found"}), 404
    if session.user_id != current_user.id:
        return jsonify({"error": "forbidden", "state": session.to_dict()}), 403
    init = _json.loads(session.initiative_json or "[]")
    if not init:
        return jsonify({"error": "no_initiative"}), 400
    actor = init[session.active_index]
    if actor.get("type") != "player" or actor.get("controller_id") != current_user.id:
        return jsonify({"error": "not_your_turn", "state": session.to_dict()}), 403
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
    return jsonify({"ok": True, "state": session.to_dict()})


@bp_combat.route("/combat/<int:combat_id>", methods=["GET"])
@login_required
def combat_page(combat_id: int):
    row = CombatSession.query.filter_by(id=combat_id, archived=False, user_id=current_user.id).first()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return render_template("combat.html", combat_id=combat_id)
