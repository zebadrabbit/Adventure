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

from flask_login import current_user
from flask_socketio import emit, join_room, leave_room

from app import socketio
from app.dungeon.entity_stream import build_snapshot, fetch_missing

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


@socketio.on("entities_sync_request")
def handle_entities_sync_request(data):
    """Client requests entity state since a given seq.

    Payload: { instance_id: int, since_seq: int }
    Emits back to requesting socket either:
      - entities_snapshot (full) when since_seq too old or missing
      - entities_delta (one-by-one) when replay possible (sent in order)
    """
    try:
        instance_id = int((data or {}).get("instance_id"))
        since_seq = int((data or {}).get("since_seq", 0))
    except Exception:
        emit("error", {"message": "bad_sync_request"})
        return
    # Fetch dungeon instance to build snapshot if needed
    from app.models import DungeonInstance as _DI
    from app.models.entities import DungeonEntity as _DE

    inst = _DI.query.filter_by(id=instance_id, user_id=getattr(current_user, "id", None)).first()
    if not inst:
        emit("error", {"message": "instance_not_found"})
        return
    missing = fetch_missing(instance_id, since_seq)
    if missing is None:
        # Need snapshot
        from app.models.models import GameClock as _GC

        tick_val = 0
        try:
            tick_val = _GC.get().tick
        except Exception:
            pass
        monsters = [_r.to_dict() for _r in _DE.query.filter_by(instance_id=inst.id, type="monster").all()]
        treasures = [_r.to_dict() for _r in _DE.query.filter_by(instance_id=inst.id, type="treasure").all()]
        snap = build_snapshot(instance_id, tick=tick_val, monsters=monsters, treasures=treasures)
        emit("entities_snapshot", snap)
        return
    # Replay deltas
    if not missing:
        # Nothing new
        emit(
            "entities_delta",
            {
                "event": "entities_delta",
                "instance_id": instance_id,
                "seq": since_seq,
                "tick": None,
                "monsters_changed": [],
                "monsters_removed": [],
                "treasures_changed": [],
                "treasures_removed": [],
            },
        )
        return
    for delta in missing:
        emit("entities_delta", delta)
