"""Combat API blueprint.

Provides read/update endpoints over existing combat_service. This keeps the
route layer thin; business logic remains in service.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request  # add render_template
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
    # Opportunistic monster auto turn progression when clients request state directly
    try:
        from app.services.combat_service import progress_monster_turn_if_needed as _pm

        _pm(combat_id)
        # Refresh row if mutated
        row = CombatSession.query.filter_by(id=combat_id, archived=False).first() or row
    except Exception:
        pass
    data = row.to_dict()
    # Add derived monster_max_hp for front-end bars (monster dict already has hp snapshot)
    try:
        data["monster_max_hp"] = data.get("monster", {}).get("hp")
    except Exception:
        data["monster_max_hp"] = None
    # Add percentages & active entity convenience
    try:
        if isinstance(data.get("party"), dict):
            for m in data["party"].get("members", []):
                hp = m.get("hp") or 0
                max_hp = m.get("max_hp") or 1
                m["hp_pct"] = round(100 * hp / max_hp, 1)
                mana = m.get("mana", 0)
                mana_max = m.get("mana_max", 0) or 1
                m["mana_pct"] = round(100 * mana / mana_max, 1)
            # Ensure item_counts present for older sessions (compute minimal potion-healing count)
            if "item_counts" not in data["party"]:
                import json as _json

                from app.models.models import Character as _Ch

                try:
                    counts = {"potion-healing": 0}
                    char_row = _Ch.query.filter_by(user_id=current_user.id).first()
                    if char_row and char_row.items:
                        inv = []
                        try:
                            inv = _json.loads(char_row.items)
                        except Exception:
                            inv = []
                        if isinstance(inv, list):
                            for entry in inv:
                                if isinstance(entry, str) and entry == "potion-healing":
                                    counts["potion-healing"] += 1
                                elif isinstance(entry, dict) and entry.get("slug") == "potion-healing":
                                    try:
                                        counts["potion-healing"] += int(entry.get("qty", 1))
                                    except Exception:
                                        counts["potion-healing"] += 1
                    data["party"]["item_counts"] = counts
                except Exception:
                    data["party"]["item_counts"] = {"potion-healing": 0}
        if data.get("monster_hp") is not None and data.get("monster_max_hp"):
            mhp = data["monster_hp"]
            mmax = data["monster_max_hp"] or 1
            data["monster_hp_pct"] = round(100 * mhp / mmax, 1)
        # active entity convenience
        init = data.get("initiative") or []
        idx = data.get("active_index", 0)
        if init and 0 <= idx < len(init):
            data["active_entity"] = init[idx]
    except Exception:
        pass
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


@bp_combat.route("/api/combat/<int:combat_id>/defend", methods=["POST"])  # defend action
@login_required
def combat_defend(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    result = combat_service.player_defend(combat_id, current_user.id, version, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/cast", methods=["POST"])  # cast spell
@login_required
def combat_cast_spell(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    spell = request.json.get("spell") if request.is_json else None
    result = combat_service.player_cast_spell(combat_id, current_user.id, version, spell, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/cast_skill", methods=["POST"])  # use an unlocked active skill
@login_required
def combat_cast_skill(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    skill_id = request.json.get("skill_id") if request.is_json else None
    result = combat_service.player_cast_skill(combat_id, current_user.id, version, skill_id, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/use_item", methods=["POST"])  # use item
@login_required
def combat_use_item(combat_id: int):
    version = int(request.json.get("version", 0)) if request.is_json else 0
    actor_id = request.json.get("actor_id") if request.is_json else None
    slug = request.json.get("slug") if request.is_json else None
    result = combat_service.player_use_item(combat_id, current_user.id, version, slug, actor_id=actor_id)
    code = 200 if result.get("ok") or result.get("error") not in ("not_found",) else 404
    return jsonify(result), code


@bp_combat.route("/api/combat/<int:combat_id>/end_turn", methods=["POST"])  # placeholder end-turn (no action)
@login_required
def combat_end_turn(combat_id: int):
    # For now just advance turn if it's player's turn but they choose to skip.
    import json as _json

    from app.services.combat_service import (
        _advance_turn,  # fallback direct advance
        _check_end,
        _emit_session,
        _load_session,
        _progress_phase,
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
    # Progress phase; if not yet advanced to next actor allow multiple end_turn presses to skip remaining phases
    advanced = _progress_phase(session)
    if not advanced and session.phase != "start":
        # If we are mid-cycle (e.g., moved to action) allow another press to push to end quickly
        advanced = _progress_phase(session)
    if not advanced and session.phase != "end":
        # Guarantee we don't get stuck; force advance
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
