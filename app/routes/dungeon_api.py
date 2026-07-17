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
import threading
from functools import wraps

import structlog
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.dungeon import DOOR, ROOM, TUNNEL, Dungeon
from app.dungeon.api_helpers.encounters import run_monster_patrols
from app.dungeon.api_helpers.perception import (
    get_noticed_coords as _get_noticed_coords_helper,
)
from app.dungeon.api_helpers.perception import (
    search_current_tile as _search_current_tile_helper,
)
from app.dungeon.api_helpers.tiles import char_to_type
from app.dungeon.api_helpers.treasure import (
    claim_treasure_entity as _claim_treasure_entity,
)
from app.dungeon.spawn_integration import (
    load_spawns_from_db,
    persist_spawns,
    populate_spawn_stats,
)
from app.dungeon.spawn_manager import SpawnConfig, SpawnManager
from app.loot.generator import LootConfig, generate_loot_for_seed
from app.models import CharacterStatusEffect, DungeonEntity
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, GameClock
from app.services import spawn_service  # Still needed for encounters
from app.services.loot_service import roll_loot
from app.services.rate_limiter import rate_limit as rate_limit_decorator

logger = structlog.get_logger()

"""NOTE: Legacy seen-tiles subsystem removed.

The prior implementation persisted a per-user set of explored dungeon tiles via
`/api/dungeon/seen*` endpoints. A newer fog-of-war mechanic supersedes that
approach, so those endpoints and all related persistence/rate-limiting logic
have been removed to reduce complexity and session payload size.

If any external client still calls the old endpoints, they should be updated
to rely on the fog-of-war data delivered with the map / state endpoints.
"""


# Backward compatibility shim for tests referencing _char_to_type.
def _char_to_type(ch: str) -> str:  # pragma: no cover - thin wrapper
    return char_to_type(ch)


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

# Blueprint needs to be declared before any @bp_dungeon.route decorators
bp_dungeon = Blueprint("dungeon", __name__)


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
                # Older cached instances lacked a cleanup flag. If future cleanup steps
                # are required they can be injected here. For now just mark cleaned.
                dungeon.structural_cleaned = True
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


@bp_dungeon.route("/api/dungeon/move", methods=["POST"])
@login_required
# Movement rate limit: allow up to 300 moves/minute (~5/sec burst) to prevent inadvertent soft locks
@rate_limit_decorator(limit=300, window=60)
def dungeon_move():
    """Move the player one tile in the requested cardinal direction.

    Body JSON: {"dir": "n"|"s"|"e"|"w"}
    Returns 200 JSON:
      { ok: true, moved: bool, pos: [x,y,z], desc: str, exits: [dir...], noticed_loot: bool }
    Errors:
      400 if bad direction
      404 if no active dungeon instance
    Movement rules mirror those in dungeon_state() & dungeon_map(): only walkable tiles
    (ROOM, TUNNEL, DOOR) are allowed.
    """
    data = request.get_json(silent=True) or {}
    direction = (data.get("dir") or "").lower()

    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    # Use shared movement handler
    from app.dungeon.movement_handler import process_movement

    try:
        moved, resp = process_movement(instance, direction)
        return jsonify(resp)
    except Exception as e:
        logger.error(event="rest_movement_failed", error=str(e))
        return jsonify({"error": "movement_failed"}), 500


## Seen tiles subsystem removed: rate limiting constants & helpers deleted.


@bp_dungeon.route("/api/dungeon/restore_from_combat/<int:combat_id>", methods=["POST", "GET"])
@login_required
def restore_from_combat(combat_id: int):
    """Restore dungeon position using a completed combat session's snapshot.

    Preconditions:
      * Combat session must exist, belong to user, and not be active.
      * Session must contain dungeon_snapshot_json with instance_id and pos.
      * Referenced DungeonInstance must still exist for the user.

    On success updates the instance coordinates and sets session['dungeon_instance_id'].
    """
    from app.models.models import CombatSession as _CS

    row = _CS.query.filter_by(id=combat_id, user_id=current_user.id, archived=False).first()
    if not row:
        return jsonify({"error": "not_found"}), 404
    if getattr(row, "status", "active") == "active":
        return jsonify({"error": "combat_active"}), 400
    snap = {}
    try:
        raw = getattr(row, "dungeon_snapshot_json", None)
        if raw:
            snap = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        snap = {}
    if not isinstance(snap, dict) or not snap.get("instance_id") or not isinstance(snap.get("pos"), dict):
        return jsonify({"error": "no_snapshot"}), 404
    inst = db.session.get(DungeonInstance, snap["instance_id"])
    if not inst or inst.user_id != current_user.id:
        return jsonify({"error": "instance_not_found"}), 404
    pos = snap.get("pos") or {}
    try:
        inst.pos_x = int(pos.get("x", inst.pos_x))
        inst.pos_y = int(pos.get("y", inst.pos_y))
        inst.pos_z = int(pos.get("z", inst.pos_z))
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "update_failed"}), 500
    from flask import session as _sess

    _sess["dungeon_instance_id"] = inst.id
    return jsonify({"ok": True, "instance_id": inst.id, "pos": {"x": inst.pos_x, "y": inst.pos_y, "z": inst.pos_z}})


@bp_dungeon.route("/api/dungeon/reveal", methods=["POST"])
@login_required
def dungeon_reveal_secret():
    """Reveal a secret door at provided coordinates near the player.

    Body JSON: {"x": int, "y": int}
    Success: 200 { revealed: bool }
    Errors:
      404 if no active instance
      400 if too far (>2), not a secret door, or bad payload
    """
    data = request.get_json(silent=True) or {}
    try:
        x = int(data.get("x"))
        y = int(data.get("y"))
    except Exception:
        return jsonify({"error": "Bad coords"}), 400
    inst_id = session.get("dungeon_instance_id")
    if not inst_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, inst_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    if not (0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE):
        return jsonify({"error": "Bad coords"}), 400
    dist = max(abs(x - instance.pos_x), abs(y - instance.pos_y))
    if dist > 2:
        return jsonify({"error": "Too far"}), 400
    secret_symbol = getattr(dungeon, "SECRET_DOOR", "S")
    if dungeon.grid[x][y] != secret_symbol:
        return jsonify({"error": "Not a secret door"}), 400
    changed = dungeon.reveal_secret_door(x, y)
    return jsonify({"revealed": bool(changed)})


@bp_dungeon.route("/api/dungeon/unlock", methods=["POST"])
@login_required
def dungeon_unlock_door():
    """Unlock a locked door using a key or rogue lockpicking.

    Request JSON:
      {"x": <int>, "y": <int>, "method": "key"|"lockpick", "key_slug": <optional>}

    Responses:
      200: {"unlocked": true, "method": "key"|"lockpick"}
      400: {"error": "Bad coords"|"Too far"|"Not locked"|"No key"|"Lockpick failed"|"Not rogue"}
      404: {"error": "no_instance"}
    """
    data = request.get_json(silent=True) or {}
    try:
        x = int(data.get("x"))
        y = int(data.get("y"))
        method = data.get("method", "key")  # "key" or "lockpick"
    except Exception:
        return jsonify({"error": "Bad coords"}), 400

    inst_id = session.get("dungeon_instance_id")
    if not inst_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, inst_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))

    if not (0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE):
        return jsonify({"error": "Bad coords"}), 400

    # Check distance (within 1 tile)
    dist = max(abs(x - instance.pos_x), abs(y - instance.pos_y))
    if dist > 1:
        return jsonify({"error": "Too far"}), 400

    # Check if it's a locked door
    from app.dungeon import LOCKED_DOOR

    if dungeon.grid[x][y] != LOCKED_DOOR:
        return jsonify({"error": "Not locked"}), 400

    # Check if already unlocked
    if instance.is_door_unlocked(x, y):
        return jsonify({"error": "Already unlocked"}), 400

    # Get current character
    from app.models.models import Character

    char_id = session.get("character_id")
    if not char_id:
        return jsonify({"error": "No character"}), 400
    char = db.session.get(Character, char_id)
    if not char:
        return jsonify({"error": "No character"}), 400

    # Method 1: Use a key
    if method == "key":
        key_slug = data.get("key_slug")
        if not key_slug:
            # Try to find any key in inventory
            import json as _json

            items = _json.loads(char.items or "[]")
            key_types = ["rusty-key", "master-key", "boss-key"]
            found_key = None
            for item in items:
                if isinstance(item, dict) and item.get("slug") in key_types:
                    found_key = item.get("slug")
                    break
                elif item in key_types:
                    found_key = item
                    break

            if not found_key:
                return jsonify({"error": "No key"}), 400
            key_slug = found_key

        # Consume the key
        import json as _json

        items = _json.loads(char.items or "[]")
        key_found = False
        new_items = []
        for item in items:
            if isinstance(item, dict):
                if item.get("slug") == key_slug and not key_found:
                    key_found = True
                    continue
            elif item == key_slug and not key_found:
                key_found = True
                continue
            new_items.append(item)

        if not key_found:
            return jsonify({"error": "No key"}), 400

        char.items = _json.dumps(new_items)
        instance.unlock_door(x, y)
        db.session.commit()
        return jsonify({"unlocked": True, "method": "key", "key_used": key_slug})

    # Method 2: Rogue lockpicking
    elif method == "lockpick":
        # Check if character is a rogue
        import json as _json

        stats = _json.loads(char.stats or "{}")

        # Derive character class from stats
        dex = stats.get("dex", 10)
        str_stat = stats.get("str", 10)
        int_stat = stats.get("int", 10)
        wis = stats.get("wis", 10)
        cha = stats.get("cha", 10)

        is_rogue = dex >= str_stat and dex >= int_stat and dex >= wis and cha < 14

        if not is_rogue:
            return jsonify({"error": "Not rogue"}), 400

        # Check for lockpicks in inventory
        items = _json.loads(char.items or "[]")
        has_lockpicks = False
        for item in items:
            if isinstance(item, dict):
                if item.get("slug") == "lockpicks":
                    has_lockpicks = True
                    break
            elif item == "lockpicks":
                has_lockpicks = True
                break

        if not has_lockpicks:
            return jsonify({"error": "No lockpicks"}), 400

        # Lockpick skill check: DEX-based with difficulty
        # DC = 10 + (dungeon tier * 2)
        import random

        dc = 10 + (instance.tier * 2)
        roll = random.randint(1, 20)
        dex_bonus = max(0, (dex - 10) // 2)  # D&D 5e modifier
        total = roll + dex_bonus

        if total >= dc:
            # Success!
            instance.unlock_door(x, y)
            db.session.commit()
            return jsonify({"unlocked": True, "method": "lockpick", "roll": roll, "total": total, "dc": dc})
        else:
            # Failure - lockpicks might break on critical failure
            if roll == 1:
                # Critical failure - break lockpicks
                new_items = []
                lockpick_removed = False
                for item in items:
                    if isinstance(item, dict):
                        if item.get("slug") == "lockpicks" and not lockpick_removed:
                            lockpick_removed = True
                            continue
                    elif item == "lockpicks" and not lockpick_removed:
                        lockpick_removed = True
                        continue
                    new_items.append(item)
                char.items = _json.dumps(new_items)
                db.session.commit()
                return (
                    jsonify({"error": "Lockpick failed", "broken": True, "roll": roll, "total": total, "dc": dc}),
                    400,
                )
            else:
                return (
                    jsonify({"error": "Lockpick failed", "broken": False, "roll": roll, "total": total, "dc": dc}),
                    400,
                )

    return jsonify({"error": "Invalid method"}), 400


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
                # A failed statement aborts the whole Postgres transaction, not just
                # this query -- roll back so later commits in this request don't
                # fail with "current transaction is aborted" on an unrelated statement.
                db.session.rollback()
                logger.warning("dungeon_map: failed to compute avg_level", exc_info=True)
            cfg = LootConfig(
                avg_party_level=avg_level,
                width=MAP_SIZE,
                height=MAP_SIZE,
                seed=instance.seed,
            )
            try:
                generate_loot_for_seed(cfg, walkables)
            except Exception:
                db.session.rollback()
                logger.warning("dungeon_map: failed to generate loot for seed", seed=instance.seed, exc_info=True)
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

            # Calculate visibility and explored tiles
            from app.dungeon.explored_tiles import (
                load_explored_tiles,
                update_explored_tiles,
            )
            from app.dungeon.visibility import calculate_visible_tiles

            # Get previously explored tiles
            explored = load_explored_tiles(instance.seed)

            # Calculate currently visible tiles
            visible = calculate_visible_tiles(dungeon.grid, player_pos[0], player_pos[1])

            # Merge visible tiles into explored set
            explored.update(visible)
            update_explored_tiles(instance.seed, explored)

            # Build grid with fog of war: only return explored tiles
            # For unexplored tiles, return None or 'unknown'
            grid = []
            for y in range(MAP_SIZE):
                row = []
                for x in range(MAP_SIZE):
                    if (x, y) in explored:
                        row.append(char_to_type(dungeon.grid[x][y]))
                    else:
                        row.append("unknown")  # Unexplored tile
                grid.append(row)

            # ---------------- Entity Validation Utilities ----------------
            def _is_walkable_tile(tx: int, ty: int) -> bool:
                try:
                    return 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and dungeon.grid[tx][ty] in walkable_chars
                except Exception:
                    return False

            def _nearest_walkable(tx: int, ty: int, occupied: set[tuple[int, int]]):
                """Return nearest walkable coordinate not currently occupied using BFS; None if none.

                We cap search radius defensively at 12 to avoid pathological full-map scans.
                """
                from collections import deque as _deque

                if _is_walkable_tile(tx, ty) and (tx, ty) not in occupied:
                    return (tx, ty)
                seen = {(tx, ty)}
                q = _deque([(tx, ty, 0)])
                LIMIT = 12
                while q:
                    cx, cy, dist = q.popleft()
                    if dist > LIMIT:
                        break
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if (nx, ny) in seen:
                            continue
                        seen.add((nx, ny))
                        if _is_walkable_tile(nx, ny) and (nx, ny) not in occupied:
                            return (nx, ny)
                        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dist + 1 <= LIMIT:
                            q.append((nx, ny, dist + 1))
                return None

            def _validate_entities(raw_rows: list["DungeonEntity"]):
                """Ensure all existing entities reside on walkable tiles; repair or remove if not.

                Strategy:
                  * Build an occupied set (x,y) for quick collision checks.
                  * For each entity not on a walkable tile, attempt to relocate to nearest walkable.
                  * If relocation fails, delete the entity (logged via print for now).
                Idempotent & safe to run each map request. Returns (updated_rows, changed_count).
                """
                changed = 0
                occupied = {(e.x, e.y) for e in raw_rows}
                for e in list(raw_rows):
                    if not _is_walkable_tile(e.x, e.y):
                        new_pos = _nearest_walkable(e.x, e.y, occupied - {(e.x, e.y)})
                        if new_pos:
                            ox, oy = e.x, e.y
                            e.x, e.y = new_pos
                            occupied.discard((ox, oy))
                            occupied.add(new_pos)
                            changed += 1
                        else:
                            try:
                                db.session.delete(e)
                                raw_rows.remove(e)
                                changed += 1
                            except Exception:
                                continue
                if changed:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                return raw_rows, changed

            # New spawn system: Use SpawnManager for deterministic, configurable spawns
            entities_rows = DungeonEntity.query.filter_by(instance_id=instance.id, seed=instance.seed).all()

            def _initialize_spawn_system():
                """Initialize or load spawn system for dungeon."""
                # Create spawn manager
                config = SpawnConfig()
                spawn_manager = SpawnManager(dungeon, instance, config=config)

                # Update instance with total boss count
                if instance.bosses_total == 1:  # Default value, update it
                    # Calculate actual boss count from config
                    base = config.boss_per_dungeon
                    tier = instance.tier or 1
                    instance.bosses_total = max(1, base + (tier - 1) // 2)  # Scale with tier
                    db.session.add(instance)

                # Check if spawns already exist in DB
                existing = load_spawns_from_db(instance, spawn_manager)

                if existing:
                    # Spawns loaded from DB, validate positions
                    try:
                        spawn_manager.spawns, _changed = _validate_entities(
                            [spawn_to_entity(s, instance, current_user.id) for s in spawn_manager.spawns]
                        )
                    except Exception:
                        # If validation fails, reinitialize
                        existing = None

                if not existing:
                    # Initialize new spawns
                    try:
                        chars = Character.query.filter_by(user_id=current_user.id).all()
                        avg_level = max(1, sum(c.level for c in chars) // len(chars)) if chars else 1
                    except Exception:
                        avg_level = 1

                    # Generate all spawns
                    spawn_manager.initialize_spawns(party_level=avg_level)

                    # Populate with stats
                    for spawn in spawn_manager.spawns:
                        populate_spawn_stats(spawn, avg_level, instance)

                    # Persist to database
                    persist_spawns(spawn_manager, instance, current_user.id)

                # Also seed treasure caches (separate from monster spawns)
                _seed_treasure_caches()

                return spawn_manager

            def _seed_treasure_caches():
                """Seed treasure caches separately from spawn manager."""
                # Check if treasure already exists
                existing_treasure = DungeonEntity.query.filter_by(
                    instance_id=instance.id, seed=instance.seed, type="treasure"
                ).first()

                if existing_treasure:
                    return

                import random as _r

                _r.seed(instance.seed ^ 0xCA6E)  # Different seed for treasure

                # Place 2-3 treasure caches
                treasure_count = _r.randint(2, 3)
                treasure_tiles = _r.sample(walkables, min(treasure_count, len(walkables))) if walkables else []

                treasure_tables = [
                    "potion-healing, potion-mana, iron-dagger, leather-armor",
                    "potion-healing, short-sword, chain-armor",
                    "potion-healing, dagger, dagger, cloak-common",
                ]

                for idx, (tx, ty) in enumerate(treasure_tiles):
                    try:
                        if not _is_walkable_tile(tx, ty):
                            continue

                        meta = {
                            "loot_table": treasure_tables[idx % len(treasure_tables)],
                            "kind": "cache",
                            "tier": 1,
                            "hidden": True,
                        }

                        ent = DungeonEntity(
                            user_id=current_user.id,
                            instance_id=instance.id,
                            seed=instance.seed,
                            type="treasure",
                            slug="treasure-cache",
                            name="Hidden Cache",
                            x=tx,
                            y=ty,
                            z=0,
                            data=json.dumps(meta),
                        )
                        db.session.add(ent)
                    except Exception:
                        continue

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            def spawn_to_entity(spawn, instance, user_id):
                """Helper to convert spawn to entity for validation."""
                return DungeonEntity(
                    user_id=user_id,
                    instance_id=instance.id,
                    seed=instance.seed,
                    type="monster",
                    slug=spawn.slug,
                    name=spawn.name,
                    x=spawn.x,
                    y=spawn.y,
                    z=spawn.z,
                    hp_current=spawn.hp_current,
                    data=json.dumps(spawn.data),
                )

            # Initialize spawn system
            if not entities_rows:
                try:
                    _initialize_spawn_system()
                    # Reload entities after initialization
                    entities_rows = DungeonEntity.query.filter_by(instance_id=instance.id, seed=instance.seed).all()
                except Exception:
                    db.session.rollback()
                    entities_rows = []
            else:
                # Entities exist, validate them
                try:
                    entities_rows, _changed = _validate_entities(entities_rows)
                    if not entities_rows:
                        # All invalid, reinitialize
                        _initialize_spawn_system()
                        entities_rows = DungeonEntity.query.filter_by(instance_id=instance.id, seed=instance.seed).all()
                except Exception:
                    pass
            entities_json = [e.to_dict() for e in entities_rows]
            # Build a light-weight overlay grid (same height/width) marking entity types for client iconography.
            # To avoid large payload bloat, use single letters and only for tiles that contain an entity.
            overlay = [[None for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
            for ent in entities_rows:
                try:
                    if 0 <= ent.x < MAP_SIZE and 0 <= ent.y < MAP_SIZE:
                        if ent.type == "monster":
                            overlay[ent.y][ent.x] = "M"
                        elif ent.type == "treasure":
                            # Only show treasure if not hidden (search required to reveal)
                            hidden_flag = False
                            if ent.data:
                                try:
                                    meta = json.loads(ent.data)
                                    if isinstance(meta, dict):
                                        hidden_flag = bool(meta.get("hidden", False))
                                except Exception:
                                    hidden_flag = False
                            if not hidden_flag:
                                overlay[ent.y][ent.x] = "T"
                        else:
                            overlay[ent.y][ent.x] = overlay[ent.y][ent.x] or "E"
                except Exception:
                    continue
            return jsonify(
                {
                    "grid": grid,
                    "player_pos": player_pos,
                    "height": MAP_SIZE,
                    "width": MAP_SIZE,
                    "seed": instance.seed,
                    "entities": entities_json,
                    "entity_overlay": overlay,
                }
            )
    return jsonify({"error": "No dungeon instance found"}), 404


# --------------------------- Admin Monster Endpoints ---------------------------


@bp_dungeon.route("/api/admin/monsters")
@login_required
@admin_required
def admin_list_monsters():
    """List monsters filtered optionally by level or family.

    Query params: level (int), family (str), boss (bool)
    Returns array of slim catalog rows (no scaling) for inspection.
    """
    try:
        level = request.args.get("level", type=int)
        family = request.args.get("family", type=str)
        boss_flag = request.args.get("boss")
        from app.models import MonsterCatalog

        q = MonsterCatalog.query
        if level is not None:
            q = q.filter(MonsterCatalog.level_min <= level, MonsterCatalog.level_max >= level)
        if family:
            q = q.filter(MonsterCatalog.family == family)
        if boss_flag is not None:
            val = boss_flag.lower() in ("1", "true", "t", "yes")
            q = q.filter(MonsterCatalog.boss == val)
        rows = q.limit(200).all()
        out = []
        for r in rows:
            out.append(
                {
                    "slug": r.slug,
                    "name": r.name,
                    "level_min": r.level_min,
                    "level_max": r.level_max,
                    "rarity": r.rarity,
                    "family": r.family,
                    "boss": bool(r.boss),
                }
            )
        return jsonify({"monsters": out, "count": len(out)})
    except Exception as e:  # pragma: no cover - defensive
        return jsonify({"error": str(e)}), 500


@bp_dungeon.route("/api/admin/force_spawn", methods=["POST"])
@login_required
@admin_required
def admin_force_spawn():
    """Force-generate an encounter for testing.

    Body (JSON): {"slug": optional specific monster slug, "level": optional int, "party_size": optional int}
    If slug is provided, it is looked up directly and scaled; otherwise uses choose_monster.
    Returns encounter with optional loot preview.
    """
    data = request.get_json(silent=True) or {}
    slug = data.get("slug")
    level = int(data.get("level") or 1)
    party_size = int(data.get("party_size") or 1)
    try:
        if slug:
            from app.models import MonsterCatalog

            row = MonsterCatalog.query.filter_by(slug=slug).first()
            if not row:
                return jsonify({"error": "slug not found"}), 404
            monster = row.scaled_instance(level=level, party_size=party_size)
        else:
            monster = spawn_service.choose_monster(level=level, party_size=party_size)
        loot_preview = roll_loot(monster)
        return jsonify({"encounter": {"monster": monster, "preview_loot": loot_preview}})
    except Exception as e:  # pragma: no cover - defensive
        return jsonify({"error": str(e)}), 500


@bp_dungeon.route("/api/admin/monster_ai_config", methods=["GET"])
@login_required
@admin_required
def admin_get_monster_ai_config():
    """Return the current monster_ai configuration JSON.

    Response: {"config": {..}} or {"config": {}, "source": "missing"}
    """
    from app.models import GameConfig

    raw = GameConfig.get("monster_ai")
    if not raw:
        return jsonify({"config": {}, "source": "missing"})
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(cfg, dict):  # defensive
            cfg = {}
    except Exception:
        cfg = {}
    return jsonify({"config": cfg})


@bp_dungeon.route("/api/admin/monster_ai_config", methods=["POST"])
@login_required
@admin_required
def admin_update_monster_ai_config():
    """Merge and persist updates to monster_ai configuration.

    Body JSON can include any subset of numeric/toggle keys. Unknown keys rejected.
    Validation:
      - Probabilities (chance keys) must be between 0 and 1 inclusive.
      - Radius / turns / thresholds coerced to non-negative numbers.
    Returns new merged config.
    """
    from app.models import GameConfig

    allowed_keys_meta = {
        "flee_threshold": ("prob",),
        "flee_chance": ("prob",),
        "help_threshold": ("prob",),
        "help_chance": ("prob",),
        "spell_chance": ("prob",),
        "cooldown_turns": ("int",),
        "ambush_chance": ("prob",),
        "patrol_enabled": ("bool",),
        "patrol_step_chance": ("prob",),
        "patrol_radius": ("int",),
    }
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON object"}), 400
    unknown = [k for k in data.keys() if k not in allowed_keys_meta]
    if unknown:
        return jsonify({"error": f"Unknown keys: {', '.join(unknown)}"}), 400
    # Load existing config
    raw = GameConfig.get("monster_ai")
    try:
        current = json.loads(raw) if raw else {}
        if not isinstance(current, dict):
            current = {}
    except Exception:
        current = {}
    updated = dict(current)
    # Validation & coercion
    for k, v in data.items():
        meta = allowed_keys_meta[k]
        if "prob" in meta:
            try:
                fv = float(v)
            except Exception:
                return jsonify({"error": f"{k} must be a float"}), 400
            if not (0.0 <= fv <= 1.0):
                return jsonify({"error": f"{k} must be between 0 and 1"}), 400
            updated[k] = fv
        elif "int" in meta:
            try:
                iv = int(v)
            except Exception:
                return jsonify({"error": f"{k} must be an int"}), 400
            if iv < 0:
                iv = 0
            updated[k] = iv
        elif "bool" in meta:
            if isinstance(v, bool):
                updated[k] = v
            elif isinstance(v, (int, float)) and v in (0, 1):
                updated[k] = bool(v)
            elif isinstance(v, str) and v.lower() in ("true", "false", "1", "0", "yes", "no"):
                updated[k] = v.lower() in ("true", "1", "yes")
            else:
                return jsonify({"error": f"{k} must be boolean"}), 400
    try:
        GameConfig.set("monster_ai", json.dumps(updated))
    except Exception as e:
        return jsonify({"error": f"Failed to persist: {e}"}), 500
    return jsonify({"config": updated, "updated_keys": list(data.keys())})


@bp_dungeon.route("/api/dungeon/affixes")
@login_required
def get_affixes():
    """Return all available dungeon affixes.

    Response: [{affix_id, name, description, threat_weight, color, monster_hp_multiplier,
                monster_damage_multiplier, monster_count_multiplier, xp_multiplier}, ...]
    """
    from app.models.dungeon_tier import DungeonAffix

    affixes = DungeonAffix.query.all()
    return jsonify(
        [
            {
                "affix_id": a.affix_id,
                "name": a.name,
                "description": a.description,
                "threat_weight": a.threat_weight,
                "color": a.color or "#888",
                "monster_hp_multiplier": a.monster_hp_multiplier,
                "monster_damage_multiplier": a.monster_damage_multiplier,
                "monster_count_multiplier": a.monster_count_multiplier,
                "xp_multiplier": a.xp_multiplier,
            }
            for a in affixes
        ]
    )


@bp_dungeon.route("/api/dungeon/combat/<int:combat_id>")
@login_required
def get_combat_session(combat_id: int):
    """Fetch a combat session by id (only if owned by current user).

    Response: { id, status, monster, archived }
    404 if not found / not owned.
    """
    try:
        from app.models.models import CombatSession

        row = CombatSession.query.filter_by(id=combat_id, user_id=current_user.id).first()
        if not row:
            return jsonify({"error": "not found"}), 404
        limit = request.args.get("log_limit", type=int)
        data = row.to_dict()
        if limit and isinstance(data.get("log"), list) and limit > 0:
            data["log"] = data["log"][-limit:]
        return jsonify(data)
    except Exception:
        return jsonify({"error": "lookup failed"}), 500


@bp_dungeon.route("/api/dungeon/combat/<int:combat_id>/action", methods=["POST"])
@login_required
def combat_action(combat_id: int):
    """Perform a combat action (attack, flee) with optimistic locking.

    Body JSON: { action: 'attack'|'flee', version: <int> }
    Response: { ok: bool, state: <session dict>, ... } or { error: str, state?: <session dict> }
    """
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").lower()
    version = payload.get("version")
    if not isinstance(version, int):
        return jsonify({"error": "version_required"}), 400
    from app.models.models import CombatSession

    session_row = CombatSession.query.filter_by(id=combat_id, user_id=current_user.id).first()
    if not session_row:
        return jsonify({"error": "not_found"}), 404
    # Delegate to combat service
    from app.services import combat_service as _combat

    actor_id = payload.get("actor_id")
    if action == "attack":
        result = _combat.player_attack(combat_id, current_user.id, version, actor_id=actor_id)
    elif action == "flee":
        result = _combat.player_flee(combat_id, current_user.id, version, actor_id=actor_id)
    elif action == "defend":
        result = _combat.player_defend(combat_id, current_user.id, version, actor_id=actor_id)
    elif action == "use_item":
        slug = (payload.get("slug") or "").strip()
        result = _combat.player_use_item(combat_id, current_user.id, version, slug, actor_id=actor_id)
    elif action == "cast_spell":
        spell = (payload.get("spell") or "").strip()
        result = _combat.player_cast_spell(combat_id, current_user.id, version, spell, actor_id=actor_id)
    else:
        return jsonify({"error": "bad_action"}), 400
    # If monster's turn now, auto-progress once (simple AI) and refresh state
    if result.get("ok"):
        _combat.progress_monster_turn_if_needed(combat_id)
        # Reload to show updated state including monster action if any
        fresh = CombatSession.query.filter_by(id=combat_id).first()
        if fresh:
            result["state"] = fresh.to_dict()
    return jsonify(result)


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

    unlocked_doors = instance.get_unlocked_doors()
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {char_to_type(tile_char)}."
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if dungeon.is_walkable(nx, ny, unlocked_doors):
            exits_map.append(d)
    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        desc += " Exits: " + ", ".join(cardinal_full[e].capitalize() for e in exits_map) + "."
    # Non-destructive check: if this coordinate was already noticed and still has unclaimed loot,
    # surface the recall message so the client can render inline Search controls after reload.
    noticed_flag = False
    # Use helper to see if current coord is among noticed ones
    coords_tmp = []
    try:
        coords_tmp = _get_noticed_coords_helper(instance)
    except Exception:
        coords_tmp = []
    for cx, cy in coords_tmp:
        if cx == x and cy == y:
            noticed_flag = True
            desc = (desc + "\n" + "You recall a suspicious spot here.").strip()
    resp = {
        "pos": [x, y, z],
        "desc": desc,
        "exits": exits_map,
        "noticed_loot": noticed_flag,
        "unlocked_doors": list(instance.get_unlocked_doors()),  # Return as list of [x,y] for JSON
    }

    # Add dungeon progress information
    try:
        resp["progress"] = {
            "bosses_defeated": instance.bosses_defeated,
            "bosses_total": instance.bosses_total,
            "elites_defeated": instance.elites_defeated,
            "monsters_defeated": instance.monsters_defeated,
            "extraction_available": instance.extraction_available,
            "tier": instance.tier or 1,
        }
    except Exception:
        pass

    # Add party HP/MP for UI display during exploration
    try:
        party_chars = Character.query.filter_by(user_id=current_user.id).order_by(Character.id.asc()).limit(4).all()
        party_data = []
        for char in party_chars:
            try:
                stats = json.loads(char.stats) if char.stats else {}
                level = getattr(char, "level", 1) or 1
                con = int(stats.get("con", stats.get("CON", 10)))
                intelligence = int(stats.get("int", stats.get("INT", 10)))

                # Calculate max values (same formula as combat_service)
                max_hp = 50 + con * 2 + level * 5
                max_mana = 20 + intelligence * 2

                # Read current values
                hp = int(stats.get("hp", max_hp))
                mana = int(stats.get("current_mana", stats.get("mana", max_mana)))

                party_data.append(
                    {
                        "char_id": char.id,
                        "name": char.name,
                        "char_class": stats.get("class", "unknown"),
                        "level": level,
                        "hp": hp,
                        "max_hp": max_hp,
                        "mana": mana,
                        "max_mana": max_mana,
                    }
                )
            except Exception:
                continue
        resp["party"] = party_data
    except Exception:
        pass

    return jsonify(resp)


@bp_dungeon.route("/api/dungeon/search_tile", methods=["POST"])
@login_required
def dungeon_search_tile():
    """Perform a search action on the player's current tile to reveal hidden caches.

    Returns 200 with { revealed_caches: int, noticed_loot: bool }.
    Hidden treasure entities (data.hidden==True) at current position are flipped to hidden False.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    rows = DungeonEntity.query.filter_by(
        instance_id=instance.id, x=instance.pos_x, y=instance.pos_y, z=instance.pos_z
    ).all()
    revealed = 0
    for r in rows:
        if r.type == "treasure" and r.data:
            try:
                meta = json.loads(r.data)
                if isinstance(meta, dict) and meta.get("hidden"):
                    meta["hidden"] = False
                    r.data = json.dumps(meta)
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
    resp = {"revealed_caches": revealed, "noticed_loot": noticed_loot}
    try:
        patrol_resp = {}
        tick_val = advance_non_combat_time(instance, tick_amount=2, resp=patrol_resp)
        if tick_val is not None:
            resp["game_tick"] = int(tick_val)
        if "encounter" in patrol_resp:
            resp["encounter"] = patrol_resp["encounter"]
    except Exception:
        pass
    return jsonify(resp)


@bp_dungeon.route("/api/dungeon/entities")
@login_required
def dungeon_entities():
    """Return current persistent entities for this dungeon instance.

    Response: { entities: [ {id,type,slug,name,x,y,z,hp_current}, ... ] }
    404 if no active instance.
    Hidden treasure entities are excluded.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Dungeon instance not found"}), 404
    rows = DungeonEntity.query.filter_by(instance_id=instance.id).all()

    # Filter out hidden treasures
    visible_entities = []
    for r in rows:
        # Include all non-treasure entities
        if r.type != "treasure":
            visible_entities.append(r.to_dict())
        else:
            # For treasure, check if it's hidden
            hidden = False
            if r.data:
                try:
                    meta = json.loads(r.data)
                    if isinstance(meta, dict):
                        hidden = bool(meta.get("hidden", False))
                except Exception:
                    pass
            # Only include if not hidden
            if not hidden:
                visible_entities.append(r.to_dict())

    return jsonify({"entities": visible_entities, "count": len(visible_entities)})


@bp_dungeon.route("/api/dungeon/treasure/claim/<int:entity_id>", methods=["POST"])
@login_required
def claim_treasure(entity_id: int):
    """Claim a treasure entity and convert it into rolled loot.

    Behavior:
      * Validates the entity exists, belongs to current user's instance & is type 'treasure'.
      * Rolls loot using existing loot service (single roll via lightweight monster-like proxy or generic table).
      * Removes the treasure entity row (idempotent: second call returns not_found).
      * Returns awarded items list (slugs) & count.

    Response:
      200 { claimed: true, items: [...], count: <int> }
      404 { error: 'not_found' }
      400 { error: 'wrong_type' }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    # Re-fetch instance to avoid stale positional data if tests or other processes mutated coordinates directly.
    try:
        db.session.refresh(instance)
    except Exception:
        pass
    status, payload = _claim_treasure_entity(entity_id, instance)
    try:
        patrol_resp = {}
        tick_val = advance_non_combat_time(instance, tick_amount=2, resp=patrol_resp)
        if tick_val is not None:
            payload["game_tick"] = int(tick_val)
        if "encounter" in patrol_resp:
            payload["encounter"] = patrol_resp["encounter"]
    except Exception:
        pass
    return jsonify(payload), status


@bp_dungeon.route("/api/dungeon/cache/open/<int:entity_id>", methods=["POST"])
@login_required
def open_locked_cache(entity_id: int):
    """Open a locked/hidden cache represented as a treasure entity.

    Semantics mirror claim_treasure but enforces the entity slug/kind
    corresponds to a cache (slug 'treasure-cache' or data.kind == 'cache').

    Response:
      200 { opened: true, items: [...], count: <int>, entity_id: <id> }
      400 { error: 'wrong_type'|'not_cache' }
      404 { error: 'not_found'|'no_instance' }
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    from app.models import DungeonEntity as _DE

    row = _DE.query.filter_by(id=entity_id, instance_id=instance.id).first()
    if not row:
        return jsonify({"error": "not_found"}), 404
    if row.type != "treasure":
        return jsonify({"error": "wrong_type"}), 400
    # Validate cache-ness via slug or embedded data.kind
    import json as _json

    is_cache = False
    try:
        meta = _json.loads(row.data) if row.data else {}
        if isinstance(meta, dict) and meta.get("kind") == "cache":
            is_cache = True
    except Exception:
        meta = {}
    if row.slug == "treasure-cache" or row.name == "Hidden Cache":
        is_cache = True
    if not is_cache:
        return jsonify({"error": "not_cache"}), 400
    status, payload = _claim_treasure_entity(entity_id, instance)
    if status == 200:
        payload = {
            "opened": True,
            "items": payload.get("items", []),
            "count": payload.get("count", 0),
            "entity_id": entity_id,
        }
    try:
        patrol_resp = {}
        tick_val = advance_non_combat_time(instance, tick_amount=2, resp=patrol_resp)
        if tick_val is not None:
            payload["game_tick"] = int(tick_val)
        if "encounter" in patrol_resp:
            payload["encounter"] = patrol_resp["encounter"]
    except Exception:
        pass
    return jsonify(payload), status


# _char_to_type moved to app.dungeon.api_helpers.tiles.char_to_type


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


@bp_dungeon.route("/api/dungeon/notices", methods=["GET"])
@login_required
def get_noticed_coords():
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"notices": []})
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"notices": []})
    coords = _get_noticed_coords_helper(instance)
    return jsonify({"notices": coords})


@bp_dungeon.route("/api/dungeon/search", methods=["POST"])
@login_required
def dungeon_search():
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"found": False, "message": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"found": False, "message": "Dungeon instance not found"}), 404
    success, payload, status = _search_current_tile_helper(instance)
    try:
        patrol_resp = {}
        tick_val = advance_non_combat_time(instance, tick_amount=2, resp=patrol_resp)
        if tick_val is not None and isinstance(payload, dict):
            payload["game_tick"] = int(tick_val)
        if "encounter" in patrol_resp and isinstance(payload, dict):
            payload["encounter"] = patrol_resp["encounter"]
    except Exception:
        pass
    return jsonify(payload), status


@bp_dungeon.route("/api/dungeon/camp", methods=["POST"])
@login_required
def dungeon_camp():
    """Make camp to rest and recover HP/mana.

    Advances time by 8 ticks, restores HP/mana for all party characters,
    and has a chance to trigger a random encounter.

    Returns:
        200: {message: str, restored_hp_total: int, encounter?: dict, game_tick?: int}
        404: no dungeon instance
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    # Restore HP/mana for party characters
    party_chars = Character.query.filter_by(user_id=current_user.id).all()
    total_restored = 0

    for char in party_chars:
        if not char.stats:
            continue
        try:
            stats = json.loads(char.stats)
            current_hp = int(stats.get("hp", 0))
            max_hp = int(stats.get("max_hp", 100))
            current_mana = int(stats.get("mana", 0))
            max_mana = int(stats.get("max_mana", 50))

            # Restore 30% of max HP and 50% of max mana
            hp_restore = int(max_hp * 0.3)
            mana_restore = int(max_mana * 0.5)

            new_hp = min(max_hp, current_hp + hp_restore)
            new_mana = min(max_mana, current_mana + mana_restore)

            total_restored += new_hp - current_hp

            stats["hp"] = new_hp
            stats["mana"] = new_mana
            char.stats = json.dumps(stats)
            db.session.add(char)
        except Exception as e:
            logger.error(event="camp_heal_failed", char_id=char.id, error=str(e))
            continue

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Advance time
    tick_val = None
    patrol_resp = {}
    try:
        tick_val = advance_non_combat_time(instance, tick_amount=8, resp=patrol_resp)
    except Exception:
        pass

    # Apply a "well-rested" regen buff on top of the instant restore above --
    # replace-not-stack, same shape the regen potion uses, just longer/weaker.
    # Applied after advance_non_combat_time (which decrements all active
    # CharacterStatusEffect rows via apply_tick_decay) so the buff starts at
    # its full remaining=10 instead of being immediately decremented.
    try:
        for char in party_chars:
            CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").delete()
            db.session.add(
                CharacterStatusEffect(
                    character_id=char.id,
                    name="regen_buff",
                    remaining=10,
                    data=json.dumps({"hp_mult": 2.0, "mp_mult": 2.0}),
                )
            )
        db.session.commit()
    except Exception:
        db.session.rollback()

    response = {
        "message": "Your party makes camp and rests. The fire crackles softly in the darkness.",
        "restored_hp_total": total_restored,
    }

    if tick_val is not None:
        response["game_tick"] = int(tick_val)

    if patrol_resp.get("encounter"):
        response["encounter"] = patrol_resp["encounter"]
        response["message"] += " But your rest is interrupted!"

    return jsonify(response)


@bp_dungeon.route("/api/dungeon/hearth", methods=["POST"])
@login_required
def dungeon_hearth():
    """Use hearthstone to extract from dungeon early.

    Applies penalties for incomplete run:
    - 50% XP penalty
    - Clears the dungeon instance

    Returns:
        200: {message: str, penalty_applied: bool}
        404: no dungeon instance
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    # Apply XP penalty to all party characters
    party_chars = Character.query.filter_by(user_id=current_user.id).all()
    for char in party_chars:
        if not char.stats:
            continue
        try:
            stats = json.loads(char.stats)
            current_xp = int(stats.get("xp", 0))
            # Reduce XP by 50% as penalty
            penalty_xp = int(current_xp * 0.5)
            stats["xp"] = max(0, current_xp - penalty_xp)
            char.stats = json.dumps(stats)
            db.session.add(char)
        except Exception:
            continue

    # Delete the dungeon instance to end the run
    try:
        db.session.delete(instance)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "failed to extract"}), 500

    # Clear session
    session.pop("dungeon_instance_id", None)

    return jsonify(
        {
            "message": "You activate your hearthstone and escape the dungeon. The early extraction cost you dearly.",
            "penalty_applied": True,
        }
    )


@bp_dungeon.route("/api/dungeon/extract", methods=["POST"])
@login_required
def dungeon_extract():
    """Extract from the dungeon after completing objectives.

    Requirements:
    - All bosses defeated (extraction_available = True)
    - Grants full rewards with completion bonus
    - No XP penalty
    - Dungeon completion XP bonus applied

    Returns:
        200: Successful extraction with rewards
        400: Extraction not available (bosses not defeated)
        404: No active dungeon instance
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404

    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    # Check extraction requirements
    if not instance.extraction_available:
        bosses_left = instance.bosses_total - instance.bosses_defeated
        return (
            jsonify(
                {
                    "error": "extraction_locked",
                    "message": f"Defeat all bosses to unlock extraction. ({bosses_left} remaining)",
                    "bosses_defeated": instance.bosses_defeated,
                    "bosses_total": instance.bosses_total,
                }
            ),
            400,
        )

    # Calculate completion rewards
    tier = instance.tier or 1
    completion_xp = 1000 * tier  # Base completion XP

    # Bonus XP for elites and monsters
    elite_bonus = instance.elites_defeated * 50
    monster_bonus = min(instance.monsters_defeated * 10, 500)  # Cap at 500
    total_bonus_xp = completion_xp + elite_bonus + monster_bonus

    # Grant rewards to all party characters
    party_chars = Character.query.filter_by(user_id=current_user.id).all()
    rewards_granted = []

    for char in party_chars:
        if not char.stats:
            continue
        try:
            stats = json.loads(char.stats)

            # Grant completion XP
            current_xp = int(stats.get("xp", 0))
            new_xp = current_xp + total_bonus_xp
            stats["xp"] = new_xp

            # Check for level ups
            from app.services.combat_service import _xp_required

            old_level = char.level
            while char.xp + total_bonus_xp >= _xp_required(char.level + 1):
                char.level += 1

            char.xp += total_bonus_xp
            char.stats = json.dumps(stats)
            db.session.add(char)

            rewards_granted.append(
                {
                    "character": char.name,
                    "xp_gained": total_bonus_xp,
                    "level_ups": char.level - old_level,
                }
            )
        except Exception:
            continue

    # Delete the dungeon instance (run complete)
    try:
        db.session.delete(instance)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "failed to extract"}), 500

    # Clear session
    session.pop("dungeon_instance_id", None)

    return jsonify(
        {
            "success": True,
            "message": "🎉 Dungeon completed! You extract safely with full rewards.",
            "rewards": {
                "completion_xp": completion_xp,
                "elite_bonus": elite_bonus,
                "monster_bonus": monster_bonus,
                "total_xp": total_bonus_xp,
                "characters": rewards_granted,
            },
            "stats": {
                "tier": tier,
                "bosses_defeated": instance.bosses_defeated,
                "elites_defeated": instance.elites_defeated,
                "monsters_defeated": instance.monsters_defeated,
            },
        }
    )


@bp_dungeon.route("/api/test/teleport", methods=["POST"])
@login_required
def test_teleport():  # pragma: no cover - only used inside tests
    """Test-only helper to reposition the player's instance coordinates.

    Body: {"x": int, "y": int, "z": optional int}
    Only active when app.config['TESTING'] is true. Returns 200 {pos:[x,y,z]} or 403 outside tests.
    """
    if not current_app.config.get("TESTING"):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    try:
        x = int(data.get("x"))
        y = int(data.get("y"))
        z = int(data.get("z", 0))
    except Exception:
        return jsonify({"error": "bad_coords"}), 400
    inst_id = session.get("dungeon_instance_id")
    if not inst_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, inst_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    instance.pos_x, instance.pos_y, instance.pos_z = x, y, z
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "persist_fail"}), 500
    return jsonify({"pos": [instance.pos_x, instance.pos_y, instance.pos_z]})


@bp_dungeon.route("/api/test/clear_perception_markers", methods=["POST"])
@login_required
def clear_perception_markers():  # pragma: no cover - test/debug helper
    """Clear all perception markers for the current seed and clean up orphaned loot.

    This removes stale markers from old game logic and deletes non-container loot
    that should have been removed on failed perception checks.
    Only active when app.config['TESTING'] or app.config['DEBUG'] is true.
    """
    if not (current_app.config.get("TESTING") or current_app.config.get("DEBUG")):
        return jsonify({"error": "forbidden"}), 403

    inst_id = session.get("dungeon_instance_id")
    if not inst_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, inst_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404

    from app.dungeon.api_helpers.perception import _session_noticed_key

    # Clear session markers
    key = _session_noticed_key(instance.seed)
    old_markers = session.get(key) or {}
    marker_count = len(old_markers)

    session[key] = {}
    try:
        session.modified = True
    except Exception:
        pass

    # Note: We don't delete loot here anymore - the new perception logic
    # will handle failed checks properly going forward. Clearing markers
    # allows fresh perception checks to happen naturally.

    return jsonify(
        {
            "cleared_markers": marker_count,
            "message": f"Cleared {marker_count} perception markers - fresh perception checks will now occur",
        }
    )


@bp_dungeon.route("/adventure")
@login_required
def adventure():
    """
    Render the adventure UI with the current party and dungeon state.
    GET only. Renders adventure.html with party, seed, and position.
    """
    raw_party = session.get("party")
    party = raw_party
    # Normalize edge cases: JSON string, tuple, set, or list of ids instead of dict entries.
    try:
        if isinstance(party, str):  # JSON encoded party
            try:
                loaded = json.loads(party)
                if isinstance(loaded, list):
                    party = loaded
            except Exception:
                pass
        if isinstance(party, tuple):
            party = list(party)
        if isinstance(party, (set,)):  # pragma: no cover - defensive
            party = list(party)
    except Exception:
        pass
    reconstructed = False
    # If party is a list of non-dicts (likely ids) attempt DB reconstruction
    if isinstance(party, list) and party and not any(isinstance(m, dict) for m in party):
        try:
            from app.models.models import Character as _Char

            ids = []
            for v in party:
                try:
                    ids.append(int(v))
                except Exception:
                    continue
            ids = list({i for i in ids if i > 0})
            if ids:
                rows = _Char.query.filter(_Char.id.in_(ids), _Char.user_id == current_user.id).all()
                norm = []
                for c in rows:
                    try:
                        stats_s = getattr(c, "stats", "{}") or "{}"
                        cls_name = None
                        try:
                            data_tmp = json.loads(stats_s)
                            cls_name = (data_tmp.get("class") or "adventurer").capitalize()
                        except Exception:
                            cls_name = "Adventurer"
                        norm.append(
                            {
                                "id": c.id,
                                "name": c.name,
                                "class": cls_name,
                                "level": getattr(c, "level", 1),
                                "xp": getattr(c, "xp", 0),
                                "stats": stats_s,
                            }
                        )
                    except Exception:
                        continue
                if norm:
                    party = norm
                    reconstructed = True
        except Exception:
            pass
    # If party is missing or empty, redirect back to dashboard to select party
    if not party:
        flash("Please select a party before starting your adventure.", "warning")
        return redirect(url_for("dashboard.dashboard"))
    from app.services.combat_service import party_is_wiped

    if party_is_wiped(current_user.id):
        flash("Your party has been defeated. Select a new party to continue.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    seed = session.get("dungeon_seed")
    pos = None
    dungeon_instance_id = session.get("dungeon_instance_id")
    # Optional explicit instance restore via query param (e.g., return from combat snapshot)
    requested_instance_id = request.args.get("instance", type=int)
    if requested_instance_id:
        inst = db.session.get(DungeonInstance, requested_instance_id)
        # Only switch if the instance belongs to the user
        try:
            if inst and inst.user_id == current_user.id:
                # Store in session for subsequent map/state calls
                session["dungeon_instance_id"] = inst.id
                dungeon_instance_id = inst.id
        except Exception:
            pass
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)
        if instance and instance.user_id == current_user.id:
            pos = (instance.pos_x, instance.pos_y, instance.pos_z)
            seed = instance.seed
    from app.models import GameClock

    clock = None
    try:
        clock = GameClock.get()
    except Exception:
        clock = None
    # Enrich party members with derived stats for progress bars
    enriched_party = []
    try:
        if isinstance(party, list):
            for m in party:
                try:
                    stats_raw = m.get("stats") if isinstance(m, dict) else getattr(m, "stats", "{}")
                    import json as _json

                    stats_data = {}
                    if isinstance(stats_raw, str):
                        try:
                            stats_data = _json.loads(stats_raw)
                        except Exception:
                            stats_data = {}
                    elif isinstance(stats_raw, dict):
                        stats_data = stats_raw
                    hp = stats_data.get("hp") or stats_data.get("HP") or 0
                    mana = stats_data.get("mana") or stats_data.get("mp") or 0
                    level = m.get("level") if isinstance(m, dict) else getattr(m, "level", 1)
                    hp_max = int(stats_data.get("hp_max") or (hp if hp else 10 + (level - 1) * 5))
                    mana_max = int(stats_data.get("mana_max") or (mana if mana else 5 + (level - 1) * 3))
                    xp_cur = m.get("xp") if isinstance(m, dict) else getattr(m, "xp", 0)
                    xp_level = level if isinstance(level, int) else 1
                    xp_next_total = int(100 * (xp_level**1.5)) or 100
                    xp_prev_total = int(100 * ((max(1, xp_level - 1)) ** 1.5)) if xp_level > 1 else 0
                    xp_into = max(0, xp_cur - xp_prev_total)
                    xp_span = max(1, xp_next_total - xp_prev_total)
                    xp_pct = min(100, max(0, (xp_into / xp_span) * 100))
                    if isinstance(m, dict):
                        em = dict(m)
                    else:
                        em = {
                            "id": getattr(m, "id", None),
                            "name": getattr(m, "name", "?"),
                            "class": getattr(m, "class", "Unknown"),
                            "level": level,
                            "xp": xp_cur,
                        }
                    em.update(
                        {
                            "hp": hp,
                            "hp_max": hp_max,
                            "mana": mana,
                            "mana_max": mana_max,
                            "xp_pct": xp_pct,
                            "xp_into": xp_into,
                            "xp_need": xp_span,
                            "stats_map": stats_data,
                        }
                    )
                    enriched_party.append(em)
                except Exception as e:
                    # Log the error but try to add the member with minimal data
                    print(f"[adventure] Error enriching party member: {e}")
                    try:
                        # Fallback: add with minimal data
                        enriched_party.append(
                            {
                                "id": m.get("id") if isinstance(m, dict) else getattr(m, "id", None),
                                "name": m.get("name") if isinstance(m, dict) else getattr(m, "name", "Unknown"),
                                "class": m.get("class") if isinstance(m, dict) else getattr(m, "class", "Adventurer"),
                                "level": m.get("level") if isinstance(m, dict) else getattr(m, "level", 1),
                                "xp": m.get("xp") if isinstance(m, dict) else getattr(m, "xp", 0),
                                "hp": 10,
                                "hp_max": 10,
                                "mana": 5,
                                "mana_max": 5,
                                "xp_pct": 0,
                                "xp_into": 0,
                                "xp_need": 100,
                                "stats_map": {},
                            }
                        )
                    except Exception:
                        continue
        else:
            enriched_party = party or []
    except Exception as e:
        print(f"[adventure] Error during party enrichment: {e}")
        enriched_party = party or []
    # Only redirect if we truly have no party data at all
    if not enriched_party and not raw_party:
        flash("No party selected. Please select your party on the dashboard.", "warning")
        return redirect(url_for("dashboard.dashboard"))
    try:
        print(
            f"[adventure] raw_party_type={type(raw_party).__name__} reconstructed={reconstructed} raw_len={len(raw_party) if isinstance(raw_party, list) else 'n/a'} enriched_len={len(enriched_party) if isinstance(enriched_party, list) else 'n/a'}"
        )
    except Exception:
        pass
    return render_template("adventure.html", party=enriched_party, seed=seed, pos=pos, game_clock=clock)


# ---- Non-combat time advancement ----
# Each discrete player action (movement attempt, search, cache/treasure interaction, generic search endpoint)
# advances the shared non-combat GameClock and triggers possible monster patrol movement.
# We only advance when not currently flagged in combat (future: integrate with combat->dungeon restore).


def advance_non_combat_time(instance, *, tick_amount: int = 1, resp: dict | None = None) -> int | None:
    """Advance global non-combat time and run patrol updates.

    Parameters:
        instance: DungeonInstance (player's current dungeon instance row)
        tick_amount: How many ticks to add for this action (default 1). Could scale for longer actions later.
        resp: Optional dict to receive patrol side effects -- currently just
            an "encounter" key if a chasing monster reached the player this
            tick (see encounters.trigger_collision_combat). Callers that
            don't care can omit it entirely; it defaults to a throwaway dict.
    Side effects:
        * Increments GameClock.tick if not in combat
        * Invokes run_monster_patrols to adjust monster positions (which can emit websocket updates)
    Failures are swallowed to avoid interrupting player flow.
    """
    try:
        clock = GameClock.get()
        if clock.combat:
            return
        clock.tick += int(tick_amount)

        # Acquire dungeon object to pass into patrols (mirrors movement logic)
        MAP_SIZE = 75
        dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
        run_monster_patrols(dungeon, instance, resp=resp if resp is not None else {}, tick_amount=tick_amount)
        db.session.add(clock)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            from app.services.status_effects import apply_tick_decay

            party_ids = [c.id for c in Character.query.filter_by(user_id=instance.user_id).all()]
            apply_tick_decay(int(tick_amount), character_ids=party_ids)
        except Exception:
            pass
    except Exception:
        return None
    return clock.tick


# Add other dungeon/gameplay routes here


## Endpoints /api/dungeon/seen*, /api/dungeon/seen/clear, /api/dungeon/seen/metrics removed.


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
