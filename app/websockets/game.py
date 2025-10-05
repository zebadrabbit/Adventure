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
from flask import session

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models import DungeonEntity
from app.routes.dungeon_api import (
    get_cached_dungeon,
    ROOM,
    TUNNEL,
    DOOR,
    char_to_type,
)
from app.dungeon.api_helpers.perception import (
    get_noticed_coords as _get_noticed_coords_helper,
)
from app.dungeon.api_helpers.encounters import maybe_spawn_encounter
from app.routes.dungeon_api import advance_non_combat_time  # reuse existing logic
import json as _json

from app import socketio

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
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}
    noop = False
    if direction == "":
        noop = True
    elif direction not in ("n", "s", "e", "w"):
        noop = True
    moved = False
    if not noop:
        deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
        dx, dy = deltas[direction]
        nx, ny = instance.pos_x + dx, instance.pos_y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            moved = True
        else:
            for alt in ["n", "e", "s", "w"]:
                if alt == direction:
                    continue
                adx, ady = deltas[alt]
                tx, ty = instance.pos_x + adx, instance.pos_y + ady
                if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and dungeon.grid[tx][ty] in walkable_chars:
                    instance.pos_x, instance.pos_y = tx, ty
                    moved = True
                    break
        if moved:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                moved = False
    combat_started = False
    combat_id = None
    encounter_payload = None
    if moved:
        try:
            monster_ent = DungeonEntity.query.filter_by(
                instance_id=instance.id,
                type="monster",
                x=instance.pos_x,
                y=instance.pos_y,
                z=instance.pos_z,
            ).first()
            if monster_ent:
                mdata = {}
                try:
                    if monster_ent.data:
                        mdata = _json.loads(monster_ent.data)
                except Exception:
                    mdata = {}
                monster_payload = {
                    "slug": monster_ent.slug,
                    "name": monster_ent.name or monster_ent.slug,
                    "hp": monster_ent.hp_current or mdata.get("hp", 30),
                    "damage": mdata.get("damage", 6),
                    "speed": mdata.get("speed", 10),
                }
                from app.services import combat_service as _combat_service

                session_row = _combat_service.start_session(current_user.id, monster_payload)
                combat_id = session_row.id
                combat_started = True
                try:
                    db.session.delete(monster_ent)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception:
            pass
    encounter_debug = {}
    if (moved or not noop) and not combat_started:
        maybe_spawn_encounter(instance, bool(moved or not noop), resp := {})
        if "encounter" in resp:
            combat_started = True
            combat_id = resp["encounter"].get("combat_id")
            encounter_payload = resp["encounter"]
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
        else:
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {char_to_type(tile_char)}."
    exits_map = []
    for d, (dx2, dy2) in {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}.items():
        tx, ty = x + dx2, y + dy2
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and dungeon.grid[tx][ty] in walkable_chars:
            exits_map.append(d)
    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        desc += " Exits: " + ", ".join(cardinal_full[e].capitalize() for e in exits_map) + "."
    noticed_flag = False
    try:
        coords_tmp = _get_noticed_coords_helper(instance)
        for cx, cy in coords_tmp:
            if cx == x and cy == y:
                noticed_flag = True
                desc = (desc + "\n" + "You notice something suspicious here.").strip()
                break
    except Exception:
        pass
    resp = {
        "ok": True,
        "moved": moved,
        "pos": [x, y, z],
        "desc": desc,
        "exits": exits_map,
        "noticed_loot": noticed_flag,
    }
    if encounter_debug:
        resp.update(encounter_debug)
    if combat_started and combat_id is not None:
        resp["combat_started"] = True
        resp["combat_id"] = combat_id
        resp["encounter"] = encounter_payload or {"combat_id": combat_id}
    else:
        try:
            tick_val = advance_non_combat_time(instance, tick_amount=1)
            if tick_val is not None:
                resp["game_tick"] = int(tick_val)
        except Exception:
            pass
    emit("dungeon_move_result", resp)


@socketio.on("dungeon_search_tile", namespace="/game")
def ws_dungeon_search_tile(_payload):  # pragma: no cover - thin wrapper over service logic
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return _emit_error("no_instance", code="no_instance")
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return _emit_error("no_instance", code="no_instance")
    rows = DungeonEntity.query.filter_by(
        instance_id=instance.id, x=instance.pos_x, y=instance.pos_y, z=instance.pos_z
    ).all()
    revealed = 0
    for r in rows:
        if r.type == "treasure" and r.data:
            try:
                meta = _json.loads(r.data)
                if isinstance(meta, dict) and meta.get("hidden"):
                    meta["hidden"] = False
                    r.data = _json.dumps(meta)
                    db.session.add(r)
                    revealed += 1
            except Exception:
                continue
    if revealed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            revealed = 0
    noticed_loot = any(r.type == "treasure" for r in rows)
    tick_val = None
    try:
        tick_val = advance_non_combat_time(instance, tick_amount=2)
    except Exception:
        pass
    resp = {"revealed_caches": revealed, "noticed_loot": noticed_loot}
    if tick_val is not None:
        resp["game_tick"] = int(tick_val)
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
    resp = {"claimed": True, "items": [i.to_dict() if hasattr(i, "to_dict") else getattr(i, "slug", str(i)) for i in items], "count": len(items)}
    if tick_val is not None:
        resp["game_tick"] = int(tick_val)
    emit("dungeon_claim_result", resp)
