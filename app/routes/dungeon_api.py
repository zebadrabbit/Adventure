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

from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app import db  # moved up to satisfy E402
from app.dungeon import DOOR, ROOM, TUNNEL, Dungeon
from app.dungeon.api_helpers.encounters import (
    maybe_spawn_encounter,
    run_monster_patrols,
)
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
from app.loot.generator import LootConfig, generate_loot_for_seed  # added
from app.models import DungeonEntity
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, GameClock
from app.services import spawn_service  # monster spawning
from app.services.loot_service import roll_loot
from app.services.rate_limiter import (
    rate_limit as rate_limit_decorator,  # route-level custom limits
)

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
    # Response Extras (dynamic):
    #   combat_started: bool (present only when a monster collision triggered a new combat session)
    #   combat_id: int (id of the newly created CombatSession)
    # Client Strategy: if combat_started=true, immediately navigate to combat UI (e.g., /combat/<combat_id>)
    # after optionally showing a brief encounter banner. The monster entity is deleted from dungeon entities
    # to avoid duplicate encounters on refresh.
    data = request.get_json(silent=True) or {}
    direction = (data.get("dir") or "").lower()
    # Tests expect: empty string (noop) => 200 success (no movement), unknown like '?' => 200 success (no movement)
    noop = False
    if direction == "":
        noop = True
    elif direction not in ("n", "s", "e", "w"):
        # Treat unknown direction as noop (legacy tests expect 200)
        noop = True
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "no_instance"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "no_instance"}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}
    moved = False
    if not noop:
        deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
        dx, dy = deltas[direction]
        nx, ny = instance.pos_x + dx, instance.pos_y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            moved = True
        else:
            # If intended direction blocked, attempt a deterministic fallback to still count as movement attempt
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
    # If we successfully moved (or remained on a tile) check for a monster entity at current location.
    if moved:
        # Collision-based encounter (existing monster entity on tile)
        try:
            monster_ent = DungeonEntity.query.filter_by(
                instance_id=instance.id, type="monster", x=instance.pos_x, y=instance.pos_y, z=instance.pos_z
            ).first()
            if monster_ent:
                mdata = {}
                try:
                    if monster_ent.data:
                        mdata = json.loads(monster_ent.data)
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
    # Roll for random encounter if movement attempted (moved flag) and no collision encounter already started
    encounter_debug = {}
    if (moved or not noop) and not combat_started:
        maybe_spawn_encounter(instance, bool(moved or not noop), resp := {})
        if "encounter" in resp:
            combat_started = True
            combat_id = resp["encounter"].get("combat_id")
            encounter_payload = resp["encounter"]
            # Preserve debug fields if present
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
        else:
            encounter_payload = None
            # No encounter this move: propagate debug fields if enabled
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
    else:
        encounter_payload = None
    # Build description & exits mirroring dungeon_state
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
        # Backward compatible flags
        resp["combat_started"] = True
        resp["combat_id"] = combat_id
        # New unified structure expected by older client code paths
        if encounter_payload is not None:
            resp["encounter"] = encounter_payload
        else:
            resp["encounter"] = {"combat_id": combat_id}
        try:
            print(f"[collision] user={current_user.id} pos=({x},{y}) combat_started id={combat_id}")
        except Exception:
            pass
    else:
        # Advance time only when no combat triggered (so patrols don't shift mid-encounter start)
        try:
            tick_val = advance_non_combat_time(instance, tick_amount=1)
            if tick_val is not None:
                resp["game_tick"] = int(tick_val)
        except Exception:
            pass
    return jsonify(resp)


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
            grid = [[char_to_type(dungeon.grid[x][y]) for x in range(MAP_SIZE)] for y in range(MAP_SIZE)]

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

            # Persistent entity seeding (monsters/NPCs/treasure) – per (instance,seed).
            entities_rows = DungeonEntity.query.filter_by(instance_id=instance.id, seed=instance.seed).all()

            def _seed_entities():
                created_local = []
                try:
                    import random as _r

                    from app.services import spawn_service as _spawn

                    _r.seed(instance.seed ^ 0xE7717)
                    max_monsters = min(12, max(4, len(walkables) // 250))
                    chosen_tiles = (
                        _r.sample(walkables, k=max_monsters + 2 if len(walkables) > max_monsters else len(walkables))
                        if walkables
                        else []
                    )
                    avg_level_seed = 1
                    try:
                        chars = Character.query.filter_by(user_id=current_user.id).all()
                        if chars:
                            avg_level_seed = max(1, sum(c.level for c in chars) // len(chars))
                    except Exception:
                        pass
                    # Monsters
                    for tx, ty in chosen_tiles[:max_monsters]:
                        try:
                            if not _is_walkable_tile(tx, ty):
                                continue
                            inst_mon = _spawn.choose_monster(level=avg_level_seed, party_size=1)
                            ent = DungeonEntity(
                                user_id=current_user.id,
                                instance_id=instance.id,
                                seed=instance.seed,
                                type="monster",
                                slug=inst_mon.get("slug"),
                                name=inst_mon.get("name"),
                                x=tx,
                                y=ty,
                                z=0,
                                hp_current=inst_mon.get("hp"),
                                data=json.dumps(inst_mon),
                            )
                            db.session.add(ent)
                            created_local.append(ent)
                        except Exception:
                            continue
                    # Treasure caches
                    treasure_tables = [
                        "potion-healing, potion-mana, iron-dagger, leather-armor",
                        "potion-healing, short-sword, chain-armor",
                        "potion-healing, dagger, dagger, cloak-common",
                    ]
                    for idx, (tx, ty) in enumerate(chosen_tiles[max_monsters : max_monsters + 2]):
                        try:
                            if not _is_walkable_tile(tx, ty):
                                continue
                            meta = {
                                "loot_table": treasure_tables[idx % len(treasure_tables)],
                                "kind": "cache",
                                "tier": 1,
                                "hidden": True,
                                # When revealed by search, client will display locked_chest.svg icon.
                            }
                            meta_json = json.dumps(meta)
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
                                data=meta_json,
                            )
                            db.session.add(ent)
                            created_local.append(ent)
                        except Exception:
                            continue
                    if created_local:
                        db.session.commit()
                except Exception:
                    db.session.rollback()
                return created_local

            if not entities_rows:
                try:
                    entities_rows = _seed_entities()
                except Exception:
                    db.session.rollback()
                    entities_rows = []
            else:
                # Validate pre-existing entities every fetch (cheap vs map size) to fix legacy invalid placements.
                try:
                    entities_rows, _changed = _validate_entities(entities_rows)
                    if not entities_rows:  # All invalid & removed -> reseed for current seed
                        entities_rows = _seed_entities()
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

    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {char_to_type(tile_char)}."
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
    }
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
    try:
        tick_val = advance_non_combat_time(instance, tick_amount=2)
    except Exception:
        pass
    resp = {"revealed_caches": revealed, "noticed_loot": noticed_loot}
    if tick_val is not None:
        resp["game_tick"] = int(tick_val)
    # Roll for encounter after search action (non-movement) if no combat already
    try:
        maybe_spawn_encounter(instance, True, enc_dbg := {})
        if enc_dbg.get("encounter") and "encounter" not in resp:
            resp["encounter"] = enc_dbg["encounter"]
        if "encounter_chance" in enc_dbg:
            resp["encounter_chance"] = enc_dbg["encounter_chance"]
            resp["encounter_roll"] = enc_dbg.get("encounter_roll")
    except Exception:
        pass
    return jsonify(resp)


@bp_dungeon.route("/api/dungeon/entities")
@login_required
def dungeon_entities():
    """Return current persistent entities for this dungeon instance.

    Response: { entities: [ {id,type,slug,name,x,y,z,hp_current}, ... ] }
    404 if no active instance.
    """
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"error": "No dungeon instance found"}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({"error": "Dungeon instance not found"}), 404
    rows = DungeonEntity.query.filter_by(instance_id=instance.id).all()
    return jsonify({"entities": [r.to_dict() for r in rows], "count": len(rows)})


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
        tick_val = advance_non_combat_time(instance, tick_amount=2)
        if tick_val is not None:
            payload["game_tick"] = int(tick_val)
    except Exception:
        pass
    # Encounter attempt
    try:
        maybe_spawn_encounter(instance, True, enc_dbg := {})
        if enc_dbg.get("encounter") and "encounter" not in payload:
            payload["encounter"] = enc_dbg["encounter"]
        if "encounter_chance" in enc_dbg:
            payload["encounter_chance"] = enc_dbg["encounter_chance"]
            payload["encounter_roll"] = enc_dbg.get("encounter_roll")
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
        tick_val = advance_non_combat_time(instance, tick_amount=2)
        if tick_val is not None:
            payload["game_tick"] = int(tick_val)
    except Exception:
        pass
    try:
        maybe_spawn_encounter(instance, True, enc_dbg := {})
        if enc_dbg.get("encounter") and "encounter" not in payload:
            payload["encounter"] = enc_dbg["encounter"]
        if "encounter_chance" in enc_dbg:
            payload["encounter_chance"] = enc_dbg["encounter_chance"]
            payload["encounter_roll"] = enc_dbg.get("encounter_roll")
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
        tick_val = advance_non_combat_time(instance, tick_amount=2)
        if tick_val is not None and isinstance(payload, dict):
            payload["game_tick"] = int(tick_val)
    except Exception:
        pass
    try:
        maybe_spawn_encounter(instance, True, enc_dbg := {})
        if enc_dbg.get("encounter") and isinstance(payload, dict) and "encounter" not in payload:
            payload["encounter"] = enc_dbg["encounter"]
        if isinstance(payload, dict) and "encounter_chance" in enc_dbg:
            payload["encounter_chance"] = enc_dbg["encounter_chance"]
            payload["encounter_roll"] = enc_dbg.get("encounter_roll")
    except Exception:
        pass
    return jsonify(payload), status


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
    # Fallback: if party missing or empty, populate from all user characters so UI still shows panels.
    if not party:
        try:
            from app.models.models import Character as _Char

            chars = _Char.query.filter_by(user_id=current_user.id).all()
            tmp = []
            for c in chars:
                cls_name = None
                stats_raw_s = getattr(c, "stats", "{}") or "{}"
                try:
                    stats_tmp = json.loads(stats_raw_s)
                    cls_name = (stats_tmp.get("class") or "adventurer").capitalize()
                except Exception:
                    cls_name = "Adventurer"
                tmp.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "class": cls_name,
                        "level": c.level,
                        "xp": c.xp,
                        "stats": stats_raw_s,
                    }
                )
            if tmp:
                party = tmp
        except Exception:
            pass
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
                except Exception:
                    continue
        else:
            enriched_party = party or []
    except Exception:
        enriched_party = party or []
    # Secondary reconstruction attempt if still empty but we had a raw party value.
    if not enriched_party and raw_party:
        try:
            from app.models.models import Character as _Char

            rows = _Char.query.filter_by(user_id=current_user.id).all()
            for c in rows:
                stats_s = getattr(c, "stats", "{}") or "{}"
                cls_name = "Adventurer"
                try:
                    tmp_stats = json.loads(stats_s)
                    cls_name = (tmp_stats.get("class") or "adventurer").capitalize()
                except Exception:
                    pass
                enriched_party.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "class": cls_name,
                        "level": getattr(c, "level", 1),
                        "xp": getattr(c, "xp", 0),
                        "hp": tmp_stats.get("hp", 0) if "tmp_stats" in locals() else 0,
                        "hp_max": tmp_stats.get("hp", 0) if "tmp_stats" in locals() else 0,
                        "mana": tmp_stats.get("mana", 0) if "tmp_stats" in locals() else 0,
                        "mana_max": tmp_stats.get("mana", 0) if "tmp_stats" in locals() else 0,
                        "xp_pct": 0,
                        "xp_into": 0,
                        "xp_need": 1,
                        "stats_map": tmp_stats if "tmp_stats" in locals() else {},
                    }
                )
        except Exception:
            pass
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


def advance_non_combat_time(instance, *, tick_amount: int = 1) -> int | None:
    """Advance global non-combat time and run patrol updates.

    Parameters:
        instance: DungeonInstance (player's current dungeon instance row)
        tick_amount: How many ticks to add for this action (default 1). Could scale for longer actions later.
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
        run_monster_patrols(dungeon, instance, resp={}, tick_amount=tick_amount)
        db.session.add(clock)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
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
