"""Socket.IO game namespace handlers.

Events:
    - join_game: Join a game room; payload { room }
    - leave_game: Leave a game room; payload { room }
    - game_action: Submit an action; payload { room, action }

Emits:
    - status: Room status updates (join/leave)
    - game_update: Acknowledgement of actions (placeholder for game logic)
"""

# Track active game rooms with simple membership counts for admin diagnostics
# Structure: { room_name: { 'members': set([sid,...]), 'created': timestamp } }
import time

from flask import session
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room

from app import db, socketio
from app.dungeon.api_helpers.encounters import maybe_spawn_encounter
from app.models import DungeonEntity
from app.models.dungeon_instance import DungeonInstance
from app.routes.dungeon_api import advance_non_combat_time

from .validation import (
    GAME_ACTION,
    JOIN_GAME,
    LEAVE_GAME,
    validate,
)

try:
    from app.logging_utils import log as _log
except Exception:  # pragma: no cover

    class _NoLog:  # fallback
        def info(self, **k):
            pass

    _log = _NoLog()
active_games = {}


@socketio.on("join_game")
def handle_join_game(data):
    ok, result = validate(data or {}, JOIN_GAME)
    if not ok:
        emit(
            "error",
            {
                "message": f"Invalid join_game: {result['error']}",
                "field": result["field"],
                "code": result["code"],
            },
        )
        return
    room = result["room"]
    join_room(room)
    try:
        user = getattr(current_user, "username", "Anonymous")
    except Exception:
        user = "Anonymous"
    # Track membership
    from flask import request

    sid = request.sid
    info = active_games.setdefault(room, {"members": set(), "created": time.time()})
    info["members"].add(sid)
    emit("status", {"msg": f"{user} has joined the game."}, room=room)
    _log.info(event="join_game", room=room, user=user, members=len(info["members"]))


@socketio.on("leave_game")
def handle_leave_game(data):
    ok, result = validate(data or {}, LEAVE_GAME)
    if not ok:
        emit(
            "error",
            {
                "message": f"Invalid leave_game: {result['error']}",
                "field": result["field"],
                "code": result["code"],
            },
        )
        return
    room = result["room"]
    leave_room(room)
    try:
        user = getattr(current_user, "username", "Anonymous")
    except Exception:
        user = "Anonymous"
    from flask import request

    sid = request.sid
    info = active_games.get(room)
    if info:
        info["members"].discard(sid)
        if not info["members"]:
            # prune empty room for cleanliness
            active_games.pop(room, None)
    emit("status", {"msg": f"{user} has left the game."}, room=room)
    _log.info(
        event="leave_game",
        room=room,
        user=user,
        remaining=len(info["members"]) if info else 0,
    )


@socketio.on("game_action")
def handle_game_action(data):
    ok, result = validate(data or {}, GAME_ACTION)
    if not ok:
        emit(
            "error",
            {
                "message": f"Invalid game_action: {result['error']}",
                "field": result["field"],
                "code": result["code"],
            },
        )
        return
    room = result["room"]
    action = result["action"]
    # Placeholder for future game logic
    emit("game_update", {"msg": f"Action processed: {action}"}, room=room)
    _log.info(event="game_action", room=room, action=action)


# ------------------ Adventure Real-Time Events ------------------


def _emit_error(msg: str, code: str = "bad_request"):
    emit(
        "error",
        {
            "message": msg,
            "code": code,
        },
    )


@socketio.on("dungeon_move", namespace="/game")
def ws_dungeon_move(payload):  # pragma: no cover - exercised via integration, thin logic
    """Real-time movement event equivalent to POST /api/dungeon/move.

    Payload: { dir: 'n'|'s'|'e'|'w' }
    Emits to caller only: dungeon_move_result {...same JSON...}
    Broadcast side-effects:
        - entities_update (already emitted elsewhere on patrol)
    """
    try:
        direction = (payload or {}).get("dir", "").lower()
    except Exception:
        direction = ""

    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return _emit_error("no_instance", code="no_instance")

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return _emit_error("no_instance", code="no_instance")

    # Use shared movement handler
    from app.dungeon.movement_handler import process_movement

    try:
        moved, resp = process_movement(instance, direction)
        emit("dungeon_move_result", resp)
    except Exception as e:
        from app.logging_utils import get_logger

        logger = get_logger(__name__)
        logger.error(event="movement_failed", error=str(e))
        return _emit_error("movement_failed", code="error")


@socketio.on("dungeon_search_tile", namespace="/game")
def ws_dungeon_search_tile(_payload):  # pragma: no cover - thin wrapper over service logic
    from app.dungeon.api_helpers.perception import search_current_tile

    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return _emit_error("no_instance", code="no_instance")
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return _emit_error("no_instance", code="no_instance")

    # Call the actual search logic from perception.py
    success, payload, status = search_current_tile(instance)

    # Advance time
    tick_val = None
    try:
        tick_val = advance_non_combat_time(instance, tick_amount=2)
    except Exception:
        pass

    resp = payload.copy() if isinstance(payload, dict) else {}
    if tick_val is not None:
        resp["game_tick"] = int(tick_val)

    # Check for encounter spawn
    try:
        maybe_spawn_encounter(instance, True, enc_dbg := {})
        if enc_dbg.get("encounter") and "encounter" not in resp:
            resp["encounter"] = enc_dbg["encounter"]
        if "encounter_chance" in enc_dbg:
            resp["encounter_chance"] = enc_dbg["encounter_chance"]
            resp["encounter_roll"] = enc_dbg.get("encounter_roll")
    except Exception:
        pass

    emit("dungeon_search_result", resp)


@socketio.on("dungeon_claim_loot", namespace="/game")
def ws_dungeon_claim_loot(payload):  # pragma: no cover
    entity_id = (payload or {}).get("entity_id")
    if not isinstance(entity_id, int):
        return _emit_error("invalid_entity_id")
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return _emit_error("no_instance", code="no_instance")
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return _emit_error("no_instance", code="no_instance")
    row = db.session.get(DungeonEntity, entity_id)
    if not row or row.instance_id != instance.id:
        return _emit_error("not_found", code="not_found")
    if row.type != "treasure":
        return _emit_error("wrong_type", code="wrong_type")
    from app.services import loot_service as _loot_service

    # Minimal loot roll: treat treasure as chest using row.slug as key
    items = _loot_service.roll_loot(row.slug or "treasure", rolls=1)
    try:
        db.session.delete(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _emit_error("db_error", code="db_error")
    tick_val = None
    try:
        tick_val = advance_non_combat_time(instance, tick_amount=1)
    except Exception:
        pass
    resp = {
        "claimed": True,
        "items": [i.to_dict() if hasattr(i, "to_dict") else getattr(i, "slug", str(i)) for i in items],
        "count": len(items),
    }
    if tick_val is not None:
        resp["game_tick"] = int(tick_val)
    emit("dungeon_claim_result", resp)
