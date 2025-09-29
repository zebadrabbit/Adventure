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

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app import db  # moved up to satisfy E402
from app.dungeon import DOOR, ROOM, TUNNEL, Dungeon
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
from app.models.models import Character
from app.services import spawn_service  # monster spawning
from app.services.loot_service import roll_loot

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


bp_dungeon = Blueprint("dungeon", __name__)

## Seen tiles subsystem removed: rate limiting constants & helpers deleted.


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
            # Persistent entity seeding (monsters/NPCs/treasure) – only seed once per instance.
            entities_rows = DungeonEntity.query.filter_by(instance_id=instance.id).all()
            if not entities_rows:
                try:
                    # Basic seeding heuristic: place a handful of monsters and treasure on walkable tiles.
                    import random as _r

                    from app.services import spawn_service as _spawn

                    _r.seed(instance.seed ^ 0xE7717)  # deterministic per seed (xor to decouple from dungeon gen)
                    max_monsters = min(12, max(4, len(walkables) // 250))
                    chosen_tiles = (
                        _r.sample(walkables, k=max_monsters + 2 if len(walkables) > max_monsters else len(walkables))
                        if walkables
                        else []
                    )
                    # Determine avg level for scaling monster instances
                    avg_level_seed = 1
                    try:
                        chars = Character.query.filter_by(user_id=current_user.id).all()
                        if chars:
                            avg_level_seed = max(1, sum(c.level for c in chars) // len(chars))
                    except Exception:
                        pass
                    created = []
                    for tx, ty in chosen_tiles[:max_monsters]:
                        try:
                            inst = _spawn.choose_monster(level=avg_level_seed, party_size=1)
                            ent = DungeonEntity(
                                user_id=current_user.id,
                                instance_id=instance.id,
                                seed=instance.seed,
                                type="monster",
                                slug=inst.get("slug"),
                                name=inst.get("name"),
                                x=tx,
                                y=ty,
                                z=0,
                                hp_current=inst.get("hp"),
                                data=json.dumps(inst),
                            )
                            db.session.add(ent)
                            created.append(ent)
                        except Exception:
                            continue
                    # Treasure markers with embedded loot table metadata (per-entity customization)
                    treasure_tables = [
                        "potion-healing, potion-mana, iron-dagger, leather-armor",
                        "potion-healing, short-sword, chain-armor",
                        "potion-healing, dagger, dagger, cloak-common",
                    ]
                    for idx, (tx, ty) in enumerate(chosen_tiles[max_monsters : max_monsters + 2]):
                        table = treasure_tables[idx % len(treasure_tables)] if treasure_tables else "potion-healing"
                        meta = {"loot_table": table, "kind": "cache", "tier": 1}
                        try:
                            meta_json = json.dumps(meta)
                        except Exception:
                            meta_json = None
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
                        created.append(ent)
                    if created:
                        db.session.commit()
                    entities_rows = created
                except Exception:
                    db.session.rollback()
                    entities_rows = []
            entities_json = [e.to_dict() for e in entities_rows]
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
    return jsonify(payload), status


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
