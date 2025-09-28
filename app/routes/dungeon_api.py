"""
project: Adventure MUD
module: dungeon_api.py
https://github.com/zebadrabbit/Adventure
License: MIT

Dungeon map, movement, and adventure API routes for Adventure MUD.

This module provides endpoints for dungeon map retrieval, player movement,
and the adventure UI. All routes require authentication.
"""

import json
import os
import threading
import time
from collections import deque
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app import db  # moved up to satisfy E402
from app.dungeon import DOOR, ROOM, TUNNEL, WALL, Dungeon
from app.loot.generator import LootConfig, generate_loot_for_seed  # added
from app.models.dungeon_instance import DungeonInstance
from app.models.loot import DungeonLoot
from app.models.models import Character, Item
from app.utils.tile_compress import compress_tiles, decompress_tiles
from app.services.time_service import advance_for  # standardized time advancement


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", "user") != "admin":
            return jsonify({"error": "admin only"}), 403
        return fn(*args, **kwargs)

    return wrapper


# Simple in-process cache (seed,size)->Dungeon instance. Thread-safe with a lock because Flask-SocketIO/eventlet may interleave greenlets.
_dungeon_cache = {}
_dungeon_cache_lock = threading.Lock()
_DUNGEON_CACHE_MAX = 8  # small LRU-ish manual cap


def get_cached_dungeon(seed: int, size_tuple: tuple[int, int, int]):
    import os

    if os.environ.get("DUNGEON_DISABLE_CACHE") == "1":
        return Dungeon(seed=seed, size=size_tuple)
    key = (seed, size_tuple)
    with _dungeon_cache_lock:
        dungeon = _dungeon_cache.get(key)
        if dungeon is not None:
            # Ensure final cleanup ran (older cached instances may predate added pass)
            if not getattr(dungeon, "structural_cleaned", False):
                try:
                    from app.dungeon.pipeline import Dungeon as _D

                    # Run a minimal cleanup by re-invoking final cleanup logic via a helper if available
                    # Fallback: regenerate (worst case) to guarantee invariants
                    dungeon2 = _D(seed=seed, size=size_tuple)
                    dungeon.grid = dungeon2.grid
                    dungeon.rooms = dungeon2.rooms
                    dungeon.room_id_grid = dungeon2.room_id_grid
                    dungeon.structural_cleaned = True
                except Exception:
                    pass
            return dungeon
    dungeon = Dungeon(seed=seed, size=size_tuple)
    dungeon.structural_cleaned = True
    with _dungeon_cache_lock:
        _dungeon_cache[key] = dungeon
        if len(_dungeon_cache) > _DUNGEON_CACHE_MAX:
            first_key = next(iter(_dungeon_cache.keys()))
            if first_key != key:
                _dungeon_cache.pop(first_key, None)
    return dungeon


bp_dungeon = Blueprint("dungeon", __name__)

# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory) & request metrics for seen tiles endpoint
# ---------------------------------------------------------------------------
_SEEN_POST_WINDOW_SECONDS = 10  # sliding window size per user
_SEEN_POST_MAX_REQUESTS = 8  # max requests in window
_SEEN_POST_LIMIT_TILES_PER_REQUEST = 4000  # reject excessively large payloads
_SEEN_SEED_TILE_CAP = 20000  # per-seed tile hard cap after merge
_SEEN_GLOBAL_SEED_CAP = 12  # max distinct seeds stored per user
_seen_post_request_times: dict[int, deque] = {}


def _rate_limited(user_id: int) -> bool:
    now = time.time()
    dq = _seen_post_request_times.setdefault(user_id, deque())
    cutoff = now - _SEEN_POST_WINDOW_SECONDS
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= _SEEN_POST_MAX_REQUESTS:
        return True
    dq.append(now)
    return False


@bp_dungeon.route("/api/dungeon/map")
@login_required
def dungeon_map():
    """
    Return the current dungeon map and player position for the session's dungeon instance.
    Response: { 'grid': <2d array>, 'player_pos': [x, y, z] }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)
        if instance:
            MAP_SIZE = 75  # 75x75 grid
            dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
            # Loot generation (idempotent). Collect walkable tiles.
            walkable_chars = {ROOM, TUNNEL, DOOR}
            walkables = [
                (x, y) for x in range(MAP_SIZE) for y in range(MAP_SIZE) if dungeon.grid[x][y] in walkable_chars
            ]
            # Derive average party level (simplified: user characters avg or default 1)
            avg_level = 1
            try:
                from app.models.models import Character

                chars = Character.query.filter_by(user_id=current_user.id).all()
                if chars:
                    avg_level = max(1, sum(c.level for c in chars) // len(chars))
            except Exception:
                pass
            cfg = LootConfig(
                avg_party_level=avg_level,
                width=MAP_SIZE,
                height=MAP_SIZE,
                seed=instance.seed,
            )
            try:
                generate_loot_for_seed(cfg, walkables)
            except Exception:
                pass
            # Simplified entrance: first room center (if any)
            entrance = None
            if getattr(dungeon, "rooms", None):
                r0 = dungeon.rooms[0]
                entrance = (r0.center[0], r0.center[1], 0)
            walkable_chars = {ROOM, TUNNEL, DOOR}
            player_pos = [instance.pos_x, instance.pos_y, instance.pos_z]
            # Check if player's current position is valid (walkable and connected to entrance)
            px, py, pz = player_pos
            is_valid = (
                0 <= px < MAP_SIZE and 0 <= py < MAP_SIZE and 0 <= pz < 1 and dungeon.grid[px][py] in walkable_chars
            )
            # Flood fill from entrance to get all connected tiles
            connected = set()
            if entrance:
                from collections import deque

                queue = deque([(entrance[0], entrance[1])])
                connected.add((entrance[0], entrance[1]))
                while queue:
                    cx, cy = queue.popleft()
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and (nx, ny) not in connected:
                            if dungeon.grid[nx][ny] in walkable_chars:
                                connected.add((nx, ny))
                                queue.append((nx, ny))
            # If not valid, not connected, or at (0,0,0), move to entrance
            if (not is_valid or (px, py) not in connected or player_pos == [0, 0, 0]) and entrance:
                player_pos = list(entrance)
                # Also update DB so movement works
                instance.pos_x, instance.pos_y, instance.pos_z = entrance
                db.session.commit()
            # Return a 2D grid row-major (y first) so client index grid[y][x] matches visual orientation.
            # Previously it was column-major which inverted N/S perception in the UI.
            grid = [[_char_to_type(dungeon.grid[x][y]) for x in range(MAP_SIZE)] for y in range(MAP_SIZE)]
            entities_json = []
            if hasattr(dungeon, "spawn_manager"):
                try:
                    entities_json = dungeon.spawn_manager.to_json()
                except Exception:
                    entities_json = []
            return jsonify(
                {
                    "grid": grid,
                    "player_pos": player_pos,
                    "height": MAP_SIZE,
                    "width": MAP_SIZE,
                    "seed": instance.seed,
                    "entities": entities_json,
                }
            )
    return jsonify({"error": "No dungeon instance found"}), 404


@bp_dungeon.route("/api/dungeon/reveal", methods=["POST"])
@login_required
def reveal_secret_door():
    """Reveal a secret door at the given coordinates (if present and adjacent to player).

    Request JSON: {"x": int, "y": int}
    Rules:
      * Coordinates must be within bounds of current dungeon instance.
      * Tile must currently be a secret door ('S').
      * (Light proximity check) Player must be within Manhattan distance <= 2 (placeholder for future search/perception logic).
    Response:
      200 {"revealed": true, "tile": "D"} on success
      400/404 with {"error": <msg>} otherwise
    """
    data = request.get_json(silent=True) or {}
    x = data.get("x")
    y = data.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return jsonify({"error": "x and y required"}), 400
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "No dungeon instance"}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    if not (0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE):
        return jsonify({"error": "Out of bounds"}), 400
    # Proximity (placeholder simple rule)
    dist = abs(instance.pos_x - x) + abs(instance.pos_y - y)
    if dist > 2:
        return jsonify({"error": "Too far"}), 400
    if dungeon.grid[x][y] != getattr(dungeon, "SECRET_DOOR", "S") and dungeon.grid[x][y] != "S":
        return jsonify({"error": "Not a secret door"}), 400
    changed = dungeon.reveal_secret_door(x, y)
    if changed:
        return jsonify({"revealed": True, "tile": "D"})
    return jsonify({"error": "Reveal failed"}), 400


@bp_dungeon.route("/api/dungeon/move", methods=["POST"])
@login_required
def dungeon_move():
    """
    Move the party in the dungeon in the specified direction (n/s/e/w).
    Returns new position and cell description, including available exits.
    Request: { 'dir': 'n'|'s'|'e'|'w' }
    Response: { 'pos': [x, y, z], 'desc': <str>, 'exits': [<str>] }
        Notes:
            - An empty direction ('') is treated as a no-op and simply returns the current
                cell description & exits. The frontend uses this after the map initially
                loads to populate the movement pad without moving the player.
            - Coordinate system: The map is returned row-major (grid[y][x]) for the client.
                Visual 'north' corresponds to increasing y index, so deltas are adjusted
                accordingly (north => dy +1, south => dy -1).
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Dungeon instance not found"}), 404
    data = request.get_json(silent=True) or {}
    direction = (data.get("dir") or "").lower()
    # Regenerate / fetch dungeon for this seed from cache
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    # Include teleport pads (if any) as walkable

    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}
    # Treat x as column (horizontal, east/west), y as row (vertical, north visually increases y index as returned to client)
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z

    # --- Normalize starting position (mirrors logic in /api/dungeon/map) ---
    entrance = None
    if getattr(dungeon, "rooms", None):
        try:
            r0 = dungeon.rooms[0]
            entrance = (r0.center[0], r0.center[1], 0)
        except Exception:
            entrance = None

    def _is_walkable(px, py):
        return 0 <= px < MAP_SIZE and 0 <= py < MAP_SIZE and dungeon.grid[px][py] in walkable_chars

    if entrance and (not _is_walkable(x, y) or (x, y, z) == (0, 0, 0)):
        # Relocate player to entrance if current tile invalid / default placeholder
        x, y, z = entrance
        instance.pos_x, instance.pos_y, instance.pos_z = x, y, z
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    # Movement deltas (row-major grid returned to client where visual "north" corresponds to increasing y index)
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    moved = False
    if direction in deltas:
        dx, dy = deltas[direction]
        nx, ny = x + dx, y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            db.session.commit()
            x, y = nx, ny
            moved = True
            # Teleport activation: if current tile is a teleport pad, jump to its paired pad (if defined)
            if dungeon.grid[x][y] in ("P", getattr(dungeon, "TELEPORT", "P")):
                tp_lookup = dungeon.metrics.get("teleport_lookup") or {}
                dest = tp_lookup.get((x, y))
                if dest:
                    tx, ty = dest
                    instance.pos_x, instance.pos_y = tx, ty
                    db.session.commit()
                    x, y = tx, ty
    # Describe current cell
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {_char_to_type(tile_char)}."
    # Compute exits
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            exits_map.append(d)
    # Human readable exits portion for legacy parser in client (Exits: North, ...) pattern
    cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
    exits_words = [cardinal_full[e] for e in exits_map]
    if exits_words:
        desc += " Exits: " + ", ".join(word.capitalize() for word in exits_words) + "."
    # Perception check for loot at current tile
    noticed, extra_msg, roll_info = _maybe_perceive_and_mark_loot(instance, x, y)
    if extra_msg:
        # Append on a new line to make it stand out in the UI log panel
        desc = (desc + "\n" + extra_msg).strip()
    pos = [x, y, z]
    resp = {"pos": pos, "desc": desc, "exits": exits_map, "noticed_loot": noticed}
    if roll_info:
        resp["last_roll"] = roll_info
    # Advance time 1 tick only if an actual movement occurred
    if moved:
        try:
            advance_for("move", actor_id=None)
        except Exception:
            pass
    return jsonify(resp)


@bp_dungeon.route("/api/dungeon/state")
@login_required
def dungeon_state():
    """Return current dungeon cell state (position, description, exits) without moving.
    Response: { 'pos': [x,y,z], 'desc': str, 'exits': [dir...] }
    Uses same coordinate and description logic as movement endpoint but performs no movement.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Dungeon instance not found"}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))

    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {_char_to_type(tile_char)}."
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            exits_map.append(d)
    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        desc += " Exits: " + ", ".join(cardinal_full[e].capitalize() for e in exits_map) + "."
    # Non-destructive check: if this coordinate was already noticed and still has unclaimed loot,
    # surface the recall message so the client can render inline Search controls after reload.
    seed = instance.seed
    key = _session_noticed_key(seed)
    noticed_map = session.get(key) or {}
    ck = _coord_key(x, y)
    noticed_flag = False
    if noticed_map.get(ck):
        rows = _loot_rows_at(seed, x, y)
        if rows:
            noticed_flag = True
            desc = (desc + "\n" + "You recall a suspicious spot here.").strip()
    resp = {
        "pos": [x, y, z],
        "desc": desc,
        "exits": exits_map,
        "noticed_loot": noticed_flag,
    }
    return jsonify(resp)


def _char_to_type(ch: str) -> str:
    if ch == ROOM:
        return "room"
    if ch == TUNNEL:
        return "tunnel"
    if ch == DOOR:
        return "door"
    if ch == WALL:
        return "wall"
    return "cave"


def _get_party_for_current_user():
    """Return list of Character rows for the current session party if available; otherwise all user's characters.

    We attempt to match characters by name from session['party'] to DB rows for a more accurate stat pull.
    """
    party_meta = session.get("party") or []
    names = set()
    for m in party_meta:
        try:
            nm = (m.get("name") or "").strip()
            if nm:
                names.add(nm)
        except Exception:
            continue
    q = Character.query.filter_by(user_id=current_user.id)
    if names:
        rows = q.filter(Character.name.in_(list(names))).all()
        # Fallback to all if names mismatched
        if rows:
            return rows
    return q.all()


def _perception_mod_from_stats(stats_json: str) -> int:
    """Compute a perception modifier from a stats JSON string.

    Prioritizes explicit 'perception' value; otherwise derives from Wisdom (wis) using (wis-10)//2.
    """
    if not stats_json:
        return 0
    try:
        data = json.loads(stats_json)
        if isinstance(data, dict):
            if "perception" in data:
                val = data.get("perception")
                if isinstance(val, (int, float)):
                    return int(val)
            wis = data.get("wis") or data.get("WIS") or data.get("wisdom")
            if isinstance(wis, (int, float)):
                return int((wis - 10) // 2)
    except Exception:
        return 0
    return 0


def _roll_perception_for_user():
    """Return the best party perception roll details.

    Returns a dict: {
        'skill': 'perception', 'die': 'd20', 'roll': int, 'mod': int, 'total': int,
        'expr': '1d20+X', 'character': { 'id': int|None, 'name': str|None }
    }

    Behavior is unchanged from before: we roll a single d20 and add the best party modifier.
    We attribute the modifier to the character with the highest effective perception.
    If no characters, we use a default +1 and leave character as None.
    """
    import random as _random

    rows = _get_party_for_current_user()
    best = {"char": None, "mod": 1}
    if rows:
        # Choose the character with the highest effective modifier
        top = None
        top_mod = None
        for c in rows:
            try:
                eff = _perception_mod_from_stats(c.stats) + max(0, int(c.level) // 2)
            except Exception:
                eff = _perception_mod_from_stats(getattr(c, "stats", None))
            if top_mod is None or eff > top_mod:
                top_mod = int(eff)
                top = c
        if top is not None and top_mod is not None:
            best["char"] = top
            best["mod"] = int(top_mod)
    die_roll = _random.randint(1, 20)
    total = die_roll + int(best["mod"])
    return {
        "skill": "perception",
        "die": "d20",
        "roll": int(die_roll),
        "mod": int(best["mod"]),
        "total": int(total),
        "expr": f"1d20+{int(best['mod'])}",
        "character": ({"id": int(best["char"].id), "name": best["char"].name} if best["char"] is not None else None),
    }


def _loot_rows_at(seed: int, x: int, y: int) -> list[DungeonLoot]:
    return DungeonLoot.query.filter_by(seed=seed, x=x, y=y, z=0, claimed=False).all()


def _session_noticed_key(seed: int) -> str:
    return f"noticed:{seed}"


def _coord_key(x: int, y: int) -> str:
    return f"{x},{y}"


def _is_container_item(item: Item) -> bool:
    t = (item.type or "").lower().strip() if item and getattr(item, "type", None) else ""
    return t in ("container", "chest", "lockbox")


@bp_dungeon.route("/api/dungeon/notices", methods=["GET"])
@login_required
def get_noticed_coords():
    """Return all noticed coordinates for the current dungeon seed where unclaimed loot remains.

    Response: { notices: [[x,y], ...] }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"notices": []})
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"notices": []})
    key = _session_noticed_key(instance.seed)
    noticed_map = session.get(key) or {}
    coords = []
    for ck, val in noticed_map.items():
        if not val:
            continue
        try:
            xs, ys = ck.split(",")
            x = int(xs)
            y = int(ys)
        except Exception:
            continue
        # Only include if there is still unclaimed loot here
        rows = _loot_rows_at(instance.seed, x, y)
        if rows:
            coords.append([x, y])
    return jsonify({"notices": coords})


def _maybe_perceive_and_mark_loot(instance, x: int, y: int) -> tuple[bool, str, dict | None]:
    """If there is unclaimed loot at (x,y), perform a perception check unless already noticed.

    Returns (noticed_now_or_before, message, roll_info_or_none). On failed perception for scattered loot, deletes the loot rows.
    """
    seed = instance.seed
    # Gather unclaimed loot rows and filter for scattered (non-container) vs containers
    rows = _loot_rows_at(seed, x, y)
    if not rows:
        return False, "", None
    # Track noticed coordinates per seed in session (kept small)
    key = _session_noticed_key(seed)
    noticed_map = session.get(key) or {}
    ck = _coord_key(x, y)
    if noticed_map.get(ck):
        # Already noticed previously; keep available for Search
        return True, "You recall a suspicious spot here.", None

    # Not yet noticed: roll perception
    roll_info = _roll_perception_for_user()
    total = roll_info["total"] if isinstance(roll_info, dict) else int(roll_info)
    DC = 13  # baseline difficulty; can evolve with dungeon depth later
    if total >= DC:
        noticed_map[ck] = True
        session[key] = noticed_map
        # Flask signed cookie session needs mark as modified when mutating a nested object
        try:
            session.modified = True
        except Exception:
            pass
        return (
            True,
            "You notice a glint of something hidden. You can Search this area.",
            roll_info if isinstance(roll_info, dict) else None,
        )
    else:
        # Failed perception: remove scattered loot (non-container). Keep chests.
        removed = 0
        for r in list(rows):
            item = db.session.get(Item, r.item_id)
            if not _is_container_item(item):
                try:
                    db.session.delete(r)
                    removed += 1
                except Exception:
                    pass
        if removed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return (
            False,
            "You find nothing of interest. Whatever was here is lost to the dark.",
            roll_info if isinstance(roll_info, dict) else None,
        )


@bp_dungeon.route("/api/dungeon/search", methods=["POST"])
@login_required
def dungeon_search():
    """Reveal loot at the player's current tile if it was previously noticed.

    Response on success: { found: true, items: [{id, name, slug, rarity, level}], message: str }
    Otherwise: { found: false, message: str }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"found": False, "message": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"found": False, "message": "Dungeon instance not found"}), 404
    x, y, _ = instance.pos_x, instance.pos_y, instance.pos_z  # z unused here
    # Require that this coordinate was noticed to avoid blind searching spam
    key = _session_noticed_key(instance.seed)
    noticed_map = session.get(key) or {}
    ck = _coord_key(x, y)
    if not noticed_map.get(ck):
        return jsonify({"found": False, "message": "You see nothing here to search."}), 403
    rows = _loot_rows_at(instance.seed, x, y)
    if not rows:
        return jsonify({"found": False, "message": "There is nothing here."}), 404
    items = []
    for r in rows:
        item = db.session.get(Item, r.item_id)
        if not item:
            continue
        items.append(
            {
                "id": r.id,
                "name": item.name,
                "slug": item.slug,
                "rarity": getattr(item, "rarity", "common"),
                "level": getattr(item, "level", 0),
                "type": getattr(item, "type", ""),
                "value_copper": getattr(item, "value_copper", 0),
                "description": getattr(item, "description", "") or "",
            }
        )
    if not items:
        return jsonify({"found": False, "message": "There is nothing here."}), 404
    names = ", ".join(i["name"] for i in items)
    msg = f"You search the area and discover: {names}."
    try:
        advance_for("search", actor_id=None)
    except Exception:
        pass
    return jsonify({"found": True, "items": items, "message": msg})


@bp_dungeon.route("/adventure")
@login_required
def adventure():
    """
    Render the adventure UI with the current party and dungeon state.
    GET only. Renders adventure.html with party, seed, and position.
    """
    party = session.get("party")
    seed = session.get("dungeon_seed")
    pos = None
    dungeon_instance_id = session.get("dungeon_instance_id")
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)
        if instance:
            pos = (instance.pos_x, instance.pos_y, instance.pos_z)
            seed = instance.seed
    from app.models import GameClock

    clock = None
    try:
        clock = GameClock.get()
    except Exception:
        clock = None
    return render_template("adventure.html", party=party, seed=seed, pos=pos, game_clock=clock)


# Add other dungeon/gameplay routes here


@bp_dungeon.route("/api/dungeon/seen", methods=["GET"])
@login_required
def get_seen_tiles():
    """Return persisted seen tiles for the current user & seed.
    Response: { seed: <int>, tiles: "x,y;x,y;..." }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Instance not found"}), 404
    seed = instance.seed
    tiles_compact = ""
    user = current_user
    # Defensive: if column was just added and old connection/schema cached, guard attribute access
    try:
        explored_raw = getattr(user, "explored_tiles", None)
    except Exception:
        explored_raw = None
    if explored_raw:
        try:
            data = json.loads(explored_raw)
            tiles_compact = data.get(str(seed), "")
        except Exception:
            tiles_compact = ""
    # If compressed form stored, decompress
    # New format may store dict with {'v': value, 'ts': ...}
    if isinstance(tiles_compact, dict):
        raw_val = tiles_compact.get("v", "")
    else:
        raw_val = tiles_compact
    if isinstance(raw_val, str) and raw_val.startswith("D:"):
        try:
            raw_val = decompress_tiles(raw_val)
        except Exception:
            raw_val = ""
    tiles_compact = raw_val if isinstance(raw_val, str) else ""
    return jsonify({"seed": seed, "tiles": tiles_compact})


@bp_dungeon.route("/api/dungeon/seen", methods=["POST"])
@login_required
def post_seen_tiles():
    """Persist seen tiles for current user & seed.
    Request JSON: { tiles: "x,y;x,y;..." } (semicolon separated list)
    Merges with existing (union). Returns { stored: <int> } count after merge.
    Size guard: silently truncate if > 50k tiles.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Instance not found"}), 404
    seed = instance.seed
    payload = request.get_json(silent=True) or {}

    # Rate limit check
    # Allow tests / admins to disable via env or app config
    disable_rl = False
    try:
        from flask import current_app

        disable_rl = bool(current_app.config.get("TESTING")) or bool(os.getenv("DISABLE_SEEN_RATE_LIMIT"))
    except Exception:
        pass
    # Allow per-request override to enforce during tests
    if payload.get("enforce_rate_limit"):
        disable_rl = False
    if not disable_rl and _rate_limited(current_user.id):
        return (
            jsonify(
                {
                    "error": "rate limit exceeded",
                    "retry_after": _SEEN_POST_WINDOW_SECONDS,
                }
            ),
            429,
        )

    tiles_compact = (payload.get("tiles") or "").strip()
    if tiles_compact and not all(part.count(",") == 1 for part in tiles_compact.split(";") if part):
        return jsonify({"error": "Bad tiles format"}), 400
    new_tiles = set([p for p in tiles_compact.split(";") if p]) if tiles_compact else set()
    if len(new_tiles) > _SEEN_POST_LIMIT_TILES_PER_REQUEST:
        return (
            jsonify(
                {
                    "error": "too many tiles in one request",
                    "limit": _SEEN_POST_LIMIT_TILES_PER_REQUEST,
                }
            ),
            413,
        )
    user = current_user
    existing = {}
    try:
        if getattr(user, "explored_tiles", None):
            try:
                existing = json.loads(user.explored_tiles) or {}
            except Exception:
                existing = {}
    except Exception:
        existing = {}
    # existing may store either raw "tiles", compressed value, or a dict with {'v': value, 'ts': timestamp}
    prior_entry = existing.get(str(seed))
    prior_raw_value = None
    if isinstance(prior_entry, dict):
        prior_raw_value = prior_entry.get("v", "")
    elif isinstance(prior_entry, str):
        prior_raw_value = prior_entry
    else:
        prior_raw_value = ""
    prior_value = prior_raw_value
    if isinstance(prior_value, str) and prior_value.startswith("D:"):
        # decompress for merge
        try:
            prior_value = decompress_tiles(prior_value)
        except Exception:
            prior_value = ""
    prior = set(prior_value.split(";")) if prior_value else set()
    merged = prior | new_tiles
    # Per-seed truncation
    if len(merged) > _SEEN_SEED_TILE_CAP:
        merged = set(list(sorted(merged))[:_SEEN_SEED_TILE_CAP])
    merged_str = ";".join(sorted(merged))
    raw_size = len(merged_str)
    stored_value = compress_tiles(merged_str)
    compressed_flag = stored_value != merged_str
    stored_size = len(stored_value)
    compression_ratio = round((1 - (stored_size / raw_size)) * 100, 2) if raw_size else 0.0
    # Update entry with metadata (last update timestamp) for LRU management
    existing[str(seed)] = {"v": stored_value, "ts": time.time()}

    # Global seed pruning (simple LRU by 'ts')
    if len(existing) > _SEEN_GLOBAL_SEED_CAP:
        # Keep newest N seeds
        try:
            sorted_seeds = sorted(
                [k for k in existing.keys()],
                key=lambda k: (existing[k]["ts"] if isinstance(existing[k], dict) and "ts" in existing[k] else 0),
                reverse=True,
            )
            to_keep = set(sorted_seeds[:_SEEN_GLOBAL_SEED_CAP])
            for k in list(existing.keys()):
                if k not in to_keep:
                    existing.pop(k, None)
        except Exception:
            # Fail-safe: if something odd, don't prune
            pass
    try:
        user.explored_tiles = json.dumps(existing)
        db.session.commit()
        return jsonify(
            {
                "stored": len(merged),
                "compressed": compressed_flag,
                "raw_size": raw_size,
                "stored_size": stored_size,
                "compression_saved_pct": compression_ratio,
            }
        )
    except Exception:
        # Column missing or commit failed; don't break gameplay.
        return jsonify({"stored": 0, "warning": "explored_tiles persistence unavailable"}), 202


@bp_dungeon.route("/api/dungeon/seen/clear", methods=["POST"])
@login_required
@admin_required
def clear_seen_tiles():
    """Admin-only: Clear seen tiles for a specified user and/or seed.
    Request JSON: { username?: str, seed?: int }
    If username omitted, operates on current user. If seed omitted, removes all seeds.
    Response: { cleared: bool, scope: 'all'|'seed', user: <username> }
    """
    payload = request.get_json(silent=True) or {}
    username = payload.get("username") or current_user.username
    seed_filter = payload.get("seed")
    from app.models.models import User as UserModel

    target = db.session.query(UserModel).filter_by(username=username).first()
    if not target:
        return jsonify({"error": "user not found"}), 404
    changed = False
    try:
        data = json.loads(target.explored_tiles) if target.explored_tiles else {}
    except Exception:
        data = {}
    if not data:
        return jsonify({"cleared": False, "user": username, "scope": "none"})
    if seed_filter is None:
        target.explored_tiles = None
        changed = True
        scope = "all"
    else:
        if str(seed_filter) in data:
            data.pop(str(seed_filter), None)
            target.explored_tiles = json.dumps(data) if data else None
            changed = True
        scope = "seed"
    if changed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "commit failed"}), 500
    return jsonify({"cleared": changed, "user": username, "scope": scope})


@bp_dungeon.route("/api/dungeon/seen/metrics", methods=["GET"])
@login_required
@admin_required
def seen_tiles_metrics():
    """Admin-only: Return metrics for all explored tiles per user (current user by default).
    Optional query params: username=<user>
    Response: {
        'user': <username>,
        'seeds': [ { 'seed': int, 'tiles': int, 'compressed': bool, 'raw_size': int, 'stored_size': int, 'saved_pct': float, 'last_update': <iso8601|null> } ],
        'totals': { 'tiles': int, 'raw_size': int, 'stored_size': int, 'saved_pct': float }
    }
    """
    from datetime import datetime

    username = request.args.get("username") or current_user.username
    from app.models.models import User as UserModel

    target = db.session.query(UserModel).filter_by(username=username).first()
    if not target:
        return jsonify({"error": "user not found"}), 404
    try:
        data = json.loads(target.explored_tiles) if target.explored_tiles else {}
    except Exception:
        data = {}
    seeds_stats = []
    total_tiles = 0
    total_raw = 0
    total_stored = 0
    for seed_key, entry in data.items():
        value = entry
        ts = None
        if isinstance(entry, dict) and "v" in entry:
            value = entry.get("v", "")
            ts_val = entry.get("ts")
            if isinstance(ts_val, (int, float)):
                try:
                    ts = datetime.utcfromtimestamp(ts_val).isoformat() + "Z"
                except Exception:
                    ts = None
        # decompress if needed
        raw_tiles_value = value
        compressed_flag = False
        if isinstance(raw_tiles_value, str) and raw_tiles_value.startswith("D:"):
            try:
                decompressed = decompress_tiles(raw_tiles_value)
                compressed_flag = True
                raw_tiles_value = decompressed
            except Exception:
                raw_tiles_value = ""
        tiles_list = [t for t in raw_tiles_value.split(";") if t]
        tiles_count = len(tiles_list)
        raw_size = len(raw_tiles_value)
        stored_size = (
            len(value) if isinstance(value, str) else len(value.get("v", "")) if isinstance(value, dict) else 0
        )
        saved_pct = round((1 - (stored_size / raw_size)) * 100, 2) if raw_size else 0.0
        seeds_stats.append(
            {
                "seed": int(seed_key) if seed_key.isdigit() else seed_key,
                "tiles": tiles_count,
                "compressed": compressed_flag,
                "raw_size": raw_size,
                "stored_size": stored_size,
                "saved_pct": saved_pct,
                "last_update": ts,
            }
        )
        total_tiles += tiles_count
        total_raw += raw_size
        total_stored += stored_size
    total_saved_pct = round((1 - (total_stored / total_raw)) * 100, 2) if total_raw else 0.0
    return jsonify(
        {
            "user": username,
            "seeds": seeds_stats,
            "totals": {
                "tiles": total_tiles,
                "raw_size": total_raw,
                "stored_size": total_stored,
                "saved_pct": total_saved_pct,
            },
        }
    )


@bp_dungeon.route("/api/dungeon/gen/metrics", methods=["GET"])
@login_required
@admin_required
def dungeon_generation_metrics():
    """Admin-only: Return generation metrics for the active dungeon seed in session.

    Response: { seed: int, size: [w,h,levels], metrics: {...}, flags: { allow_hidden_areas: bool, enable_metrics: bool } }
    If metrics disabled, returns an empty metrics object.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no active dungeon instance"}), 404
    from app.models.dungeon_instance import DungeonInstance

    inst = db.session.get(DungeonInstance, dungeon_instance_id)
    if not inst:
        return jsonify({"error": "instance not found"}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(inst.seed, (MAP_SIZE, MAP_SIZE, 1))
    metrics = dungeon.metrics if getattr(dungeon, "enable_metrics", True) else {}
    return jsonify(
        {
            "seed": dungeon.seed,
            "size": list(dungeon.size),
            "metrics": metrics,
            "flags": {
                "allow_hidden_areas": getattr(dungeon, "allow_hidden_areas", False),
                "enable_metrics": getattr(dungeon, "enable_metrics", True),
            },
        }
    )
