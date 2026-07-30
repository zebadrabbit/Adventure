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
from app.models.dungeon_instance import DungeonInstance
from app.routes.dungeon_api import advance_non_combat_time

from .validation import (
    GAME_ACTION,
    JOIN_GAME,
    LEAVE_GAME,
    validate,
)

import structlog

_log = structlog.get_logger(__name__)
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
    _log.info("join_game", room=room, user=user, members=len(info["members"]))


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
        "leave_game",
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
    _log.info("game_action", room=room, action=action)


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
        import structlog

        logger = structlog.get_logger(__name__)
        logger.error("movement_failed", error=str(e))
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
    resp = payload.copy() if isinstance(payload, dict) else {}
    try:
        patrol_resp = {}
        tick_val = advance_non_combat_time(instance, tick_amount=2, resp=patrol_resp)
        if tick_val is not None:
            resp["game_tick"] = int(tick_val)
        if "encounter" in patrol_resp:
            resp["encounter"] = patrol_resp["encounter"]
    except Exception:
        pass

    emit("dungeon_search_result", resp)


# There is no ``dungeon_claim_loot`` handler here on purpose. One existed and
# was deleted: it called ``roll_loot(row.slug, rolls=1)`` -- a str where the
# signature wants a monster dict, plus a keyword the function does not take --
# so it raised TypeError on every emit, and no shipped client ever emitted it.
# Repairing the call would not have been enough: it also skipped the adjacency
# check and the hidden-chest perception roll, ignored the per-entity
# ``data.loot_table`` override, and deleted the chest without granting anything.
# All of that already works, once, in ``dungeon.api_helpers.treasure``'s
# ``claim_treasure_entity``, which the REST path uses. If a socket claim is
# ever wanted, delegate to that -- do not re-implement it.
