"""
project: Adventure MUD
module: dungeon_api.py
https://github.com/zebadrabbit/Adventure
License: MIT

Dungeon map, movement, and adventure API routes for Adventure MUD.

This module provides endpoints for dungeon map retrieval, player movement,
and the adventure UI. All routes require authentication.
"""
from flask import Blueprint, jsonify, session, render_template, request
from flask_login import login_required, current_user
from app.dungeon import Dungeon, ROOM, TUNNEL, DOOR, WALL, CAVE
from functools import lru_cache
import threading
import json, time, os
from collections import deque
from app.utils.tile_compress import compress_tiles, decompress_tiles
from functools import wraps

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role', 'user') != 'admin':
            return jsonify({'error': 'admin only'}), 403
        return fn(*args, **kwargs)
    return wrapper

# Simple in-process cache (seed,size)->Dungeon instance. Thread-safe with a lock because Flask-SocketIO/eventlet may interleave greenlets.
_dungeon_cache = {}
_dungeon_cache_lock = threading.Lock()
_DUNGEON_CACHE_MAX = 8  # small LRU-ish manual cap

def get_cached_dungeon(seed: int, size_tuple: tuple[int,int,int]):
    import os
    if os.environ.get('DUNGEON_DISABLE_CACHE') == '1':
        return Dungeon(seed=seed, size=size_tuple)
    key = (seed, size_tuple)
    with _dungeon_cache_lock:
        dungeon = _dungeon_cache.get(key)
        if dungeon is not None:
            # Ensure final cleanup ran (older cached instances may predate added pass)
            if not getattr(dungeon, 'structural_cleaned', False):
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
from app.models.dungeon_instance import DungeonInstance
from app import db

bp_dungeon = Blueprint('dungeon', __name__)

# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory) & request metrics for seen tiles endpoint
# ---------------------------------------------------------------------------
_SEEN_POST_WINDOW_SECONDS = 10  # sliding window size per user
_SEEN_POST_MAX_REQUESTS = 8     # max requests in window
_SEEN_POST_LIMIT_TILES_PER_REQUEST = 4000  # reject excessively large payloads
_SEEN_SEED_TILE_CAP = 20000               # per-seed tile hard cap after merge
_SEEN_GLOBAL_SEED_CAP = 12                # max distinct seeds stored per user
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


@bp_dungeon.route('/api/dungeon/map')
@login_required
def dungeon_map():
    """
    Return the current dungeon map and player position for the session's dungeon instance.
    Response: { 'grid': <2d array>, 'player_pos': [x, y, z] }
    """
    dungeon_instance_id = session.get('dungeon_instance_id')
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)
        if instance:
            # Seed is now managed exclusively via POST /api/dungeon/seed
            # Use Dungeon class to generate the dungeon
            MAP_SIZE = 75  # 75x75 grid
            dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
            # Simplified entrance: first room center (if any)
            entrance = None
            if getattr(dungeon, 'rooms', None):
                r0 = dungeon.rooms[0]
                entrance = (r0.center[0], r0.center[1], 0)
            walkable_chars = {ROOM, TUNNEL, DOOR}
            player_pos = [instance.pos_x, instance.pos_y, instance.pos_z]
            # Check if player's current position is valid (walkable and connected to entrance)
            px, py, pz = player_pos
            is_valid = (
                0 <= px < MAP_SIZE and 0 <= py < MAP_SIZE and 0 <= pz < 1 and
                dungeon.grid[px][py] in walkable_chars
            )
            # Flood fill from entrance to get all connected tiles
            connected = set()
            if entrance:
                from collections import deque
                queue = deque([(entrance[0], entrance[1])])
                connected.add((entrance[0], entrance[1]))
                while queue:
                    cx, cy = queue.popleft()
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = cx+dx, cy+dy
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
            grid = [[ _char_to_type(dungeon.grid[x][y]) for x in range(MAP_SIZE)] for y in range(MAP_SIZE)]
            entities_json=[]
            if hasattr(dungeon, 'spawn_manager'):
                try:
                    entities_json = dungeon.spawn_manager.to_json()
                except Exception:
                    entities_json = []
            return jsonify({
                'grid': grid,
                'player_pos': player_pos,
                'height': MAP_SIZE,
                'width': MAP_SIZE,
                'seed': instance.seed,
                'entities': entities_json
            })
    return jsonify({'error': 'No dungeon instance found'}), 404


@bp_dungeon.route('/api/dungeon/move', methods=['POST'])
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
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'error': 'No dungeon instance found'}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({'error': 'Dungeon instance not found'}), 404
    data = request.get_json(silent=True) or {}
    direction = (data.get('dir') or '').lower()
    # Regenerate / fetch dungeon for this seed from cache
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable_chars = {ROOM, TUNNEL, DOOR}
    # Treat x as column (horizontal, east/west), y as row (vertical, north visually increases y index as returned to client)
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z

    # --- Normalize starting position (mirrors logic in /api/dungeon/map) ---
    entrance = None
    if getattr(dungeon, 'rooms', None):
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
    deltas = {'n': (0,1), 's': (0,-1), 'e': (1,0), 'w': (-1,0)}
    if direction in deltas:
        dx, dy = deltas[direction]
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            db.session.commit()
            x, y = nx, ny
    # Describe current cell
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {_char_to_type(tile_char)}."
    # Compute exits
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            exits_map.append(d)
    # Human readable exits portion for legacy parser in client (Exits: North, ...) pattern
    cardinal_full = {'n':'north','s':'south','e':'east','w':'west'}
    exits_words = [cardinal_full[e] for e in exits_map]
    if exits_words:
        desc += " Exits: " + ', '.join(word.capitalize() for word in exits_words) + '.'
    pos = [x, y, z]
    return jsonify({'pos': pos, 'desc': desc, 'exits': exits_map})


@bp_dungeon.route('/api/dungeon/state')
@login_required
def dungeon_state():
    """Return current dungeon cell state (position, description, exits) without moving.
    Response: { 'pos': [x,y,z], 'desc': str, 'exits': [dir...] }
    Uses same coordinate and description logic as movement endpoint but performs no movement.
    """
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'error': 'No dungeon instance found'}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({'error': 'Dungeon instance not found'}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable_chars = {ROOM, TUNNEL, DOOR}
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    deltas = {'n': (0,1), 's': (0,-1), 'e': (1,0), 'w': (-1,0)}
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {_char_to_type(tile_char)}."
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            exits_map.append(d)
    if exits_map:
        cardinal_full = {'n':'north','s':'south','e':'east','w':'west'}
        desc += " Exits: " + ', '.join(cardinal_full[e].capitalize() for e in exits_map) + '.'
    return jsonify({'pos': [x,y,z], 'desc': desc, 'exits': exits_map})


def _char_to_type(ch: str) -> str:
    if ch == ROOM: return 'room'
    if ch == TUNNEL: return 'tunnel'
    if ch == DOOR: return 'door'
    if ch == WALL: return 'wall'
    return 'cave'


@bp_dungeon.route('/adventure')
@login_required
def adventure():
    """
    Render the adventure UI with the current party and dungeon state.
    GET only. Renders adventure.html with party, seed, and position.
    """
    party = session.get('party')
    seed = session.get('dungeon_seed')
    pos = None
    dungeon_instance_id = session.get('dungeon_instance_id')
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)
        if instance:
            pos = (instance.pos_x, instance.pos_y, instance.pos_z)
            seed = instance.seed
    return render_template('adventure.html', party=party, seed=seed, pos=pos)

# Add other dungeon/gameplay routes here

@bp_dungeon.route('/api/dungeon/seen', methods=['GET'])
@login_required
def get_seen_tiles():
    """Return persisted seen tiles for the current user & seed.
    Response: { seed: <int>, tiles: "x,y;x,y;..." }
    """
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'error': 'No dungeon instance'}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({'error': 'Instance not found'}), 404
    seed = instance.seed
    tiles_compact = ''
    user = current_user
    # Defensive: if column was just added and old connection/schema cached, guard attribute access
    try:
        explored_raw = getattr(user, 'explored_tiles', None)
    except Exception:
        explored_raw = None
    if explored_raw:
        try:
            data = json.loads(explored_raw)
            tiles_compact = data.get(str(seed), '')
        except Exception:
            tiles_compact = ''
    # If compressed form stored, decompress
    # New format may store dict with {'v': value, 'ts': ...}
    if isinstance(tiles_compact, dict):
        raw_val = tiles_compact.get('v','')
    else:
        raw_val = tiles_compact
    if isinstance(raw_val, str) and raw_val.startswith('D:'):
        try:
            raw_val = decompress_tiles(raw_val)
        except Exception:
            raw_val = ''
    tiles_compact = raw_val if isinstance(raw_val, str) else ''
    return jsonify({'seed': seed, 'tiles': tiles_compact})

@bp_dungeon.route('/api/dungeon/seen', methods=['POST'])
@login_required
def post_seen_tiles():
    """Persist seen tiles for current user & seed.
    Request JSON: { tiles: "x,y;x,y;..." } (semicolon separated list)
    Merges with existing (union). Returns { stored: <int> } count after merge.
    Size guard: silently truncate if > 50k tiles.
    """
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'error': 'No dungeon instance'}), 404
    instance = db.session.get(DungeonInstance, dungeon_instance_id)
    if not instance:
        return jsonify({'error': 'Instance not found'}), 404
    seed = instance.seed
    payload = request.get_json(silent=True) or {}

    # Rate limit check
    # Allow tests / admins to disable via env or app config
    disable_rl = False
    try:
        from flask import current_app
        disable_rl = bool(current_app.config.get('TESTING')) or bool(os.getenv('DISABLE_SEEN_RATE_LIMIT'))
    except Exception:
        pass
    # Allow per-request override to enforce during tests
    if payload.get('enforce_rate_limit'):
        disable_rl = False
    if not disable_rl and _rate_limited(current_user.id):
        return jsonify({'error': 'rate limit exceeded', 'retry_after': _SEEN_POST_WINDOW_SECONDS}), 429

    tiles_compact = (payload.get('tiles') or '').strip()
    if tiles_compact and not all(part.count(',')==1 for part in tiles_compact.split(';') if part):
        return jsonify({'error': 'Bad tiles format'}), 400
    new_tiles = set([p for p in tiles_compact.split(';') if p]) if tiles_compact else set()
    if len(new_tiles) > _SEEN_POST_LIMIT_TILES_PER_REQUEST:
        return jsonify({'error': 'too many tiles in one request', 'limit': _SEEN_POST_LIMIT_TILES_PER_REQUEST}), 413
    user = current_user
    existing = {}
    try:
        if getattr(user, 'explored_tiles', None):
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
        prior_raw_value = prior_entry.get('v', '')
    elif isinstance(prior_entry, str):
        prior_raw_value = prior_entry
    else:
        prior_raw_value = ''
    prior_value = prior_raw_value
    if isinstance(prior_value, str) and prior_value.startswith('D:'):
        # decompress for merge
        try:
            prior_value = decompress_tiles(prior_value)
        except Exception:
            prior_value = ''
    prior = set(prior_value.split(';')) if prior_value else set()
    merged = prior | new_tiles
    # Per-seed truncation
    if len(merged) > _SEEN_SEED_TILE_CAP:
        merged = set(list(sorted(merged))[:_SEEN_SEED_TILE_CAP])
    merged_str = ';'.join(sorted(merged))
    raw_size = len(merged_str)
    stored_value = compress_tiles(merged_str)
    compressed_flag = stored_value != merged_str
    stored_size = len(stored_value)
    compression_ratio = round((1 - (stored_size / raw_size)) * 100, 2) if raw_size else 0.0
    # Update entry with metadata (last update timestamp) for LRU management
    existing[str(seed)] = {'v': stored_value, 'ts': time.time()}

    # Global seed pruning (simple LRU by 'ts')
    if len(existing) > _SEEN_GLOBAL_SEED_CAP:
        # Keep newest N seeds
        try:
            sorted_seeds = sorted(
                [k for k in existing.keys()],
                key=lambda k: existing[k]['ts'] if isinstance(existing[k], dict) and 'ts' in existing[k] else 0,
                reverse=True
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
        return jsonify({
            'stored': len(merged),
            'compressed': compressed_flag,
            'raw_size': raw_size,
            'stored_size': stored_size,
            'compression_saved_pct': compression_ratio
        })
    except Exception:
        # Column missing or commit failed; don't break gameplay.
        return jsonify({'stored': 0, 'warning': 'explored_tiles persistence unavailable'}), 202


@bp_dungeon.route('/api/dungeon/seen/clear', methods=['POST'])
@login_required
@admin_required
def clear_seen_tiles():
    """Admin-only: Clear seen tiles for a specified user and/or seed.
    Request JSON: { username?: str, seed?: int }
    If username omitted, operates on current user. If seed omitted, removes all seeds.
    Response: { cleared: bool, scope: 'all'|'seed', user: <username> }
    """
    payload = request.get_json(silent=True) or {}
    username = payload.get('username') or current_user.username
    seed_filter = payload.get('seed')
    from app.models.models import User as UserModel
    target = db.session.query(UserModel).filter_by(username=username).first()
    if not target:
        return jsonify({'error': 'user not found'}), 404
    changed = False
    try:
        data = json.loads(target.explored_tiles) if target.explored_tiles else {}
    except Exception:
        data = {}
    if not data:
        return jsonify({'cleared': False, 'user': username, 'scope': 'none'})
    if seed_filter is None:
        target.explored_tiles = None
        changed = True
        scope = 'all'
    else:
        if str(seed_filter) in data:
            data.pop(str(seed_filter), None)
            target.explored_tiles = json.dumps(data) if data else None
            changed = True
        scope = 'seed'
    if changed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'commit failed'}), 500
    return jsonify({'cleared': changed, 'user': username, 'scope': scope})


@bp_dungeon.route('/api/dungeon/seen/metrics', methods=['GET'])
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
    username = request.args.get('username') or current_user.username
    from app.models.models import User as UserModel
    target = db.session.query(UserModel).filter_by(username=username).first()
    if not target:
        return jsonify({'error': 'user not found'}), 404
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
        if isinstance(entry, dict) and 'v' in entry:
            value = entry.get('v','')
            ts_val = entry.get('ts')
            if isinstance(ts_val, (int,float)):
                try:
                    ts = datetime.utcfromtimestamp(ts_val).isoformat() + 'Z'
                except Exception:
                    ts = None
        # decompress if needed
        raw_tiles_value = value
        compressed_flag = False
        if isinstance(raw_tiles_value, str) and raw_tiles_value.startswith('D:'):
            try:
                decompressed = decompress_tiles(raw_tiles_value)
                compressed_flag = True
                raw_tiles_value = decompressed
            except Exception:
                raw_tiles_value = ''
        tiles_list = [t for t in raw_tiles_value.split(';') if t]
        tiles_count = len(tiles_list)
        raw_size = len(raw_tiles_value)
        stored_size = len(value) if isinstance(value, str) else len(value.get('v','')) if isinstance(value, dict) else 0
        saved_pct = round((1 - (stored_size / raw_size)) * 100, 2) if raw_size else 0.0
        seeds_stats.append({
            'seed': int(seed_key) if seed_key.isdigit() else seed_key,
            'tiles': tiles_count,
            'compressed': compressed_flag,
            'raw_size': raw_size,
            'stored_size': stored_size,
            'saved_pct': saved_pct,
            'last_update': ts
        })
        total_tiles += tiles_count
        total_raw += raw_size
        total_stored += stored_size
    total_saved_pct = round((1 - (total_stored / total_raw)) * 100, 2) if total_raw else 0.0
    return jsonify({
        'user': username,
        'seeds': seeds_stats,
        'totals': {
            'tiles': total_tiles,
            'raw_size': total_raw,
            'stored_size': total_stored,
            'saved_pct': total_saved_pct
        }
    })


@bp_dungeon.route('/api/dungeon/gen/metrics', methods=['GET'])
@login_required
@admin_required
def dungeon_generation_metrics():
    """Admin-only: Return generation metrics for the active dungeon seed in session.

    Response: { seed: int, size: [w,h,levels], metrics: {...}, flags: { allow_hidden_areas: bool, enable_metrics: bool } }
    If metrics disabled, returns an empty metrics object.
    """
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'error': 'no active dungeon instance'}), 404
    from app.models.dungeon_instance import DungeonInstance
    inst = db.session.get(DungeonInstance, dungeon_instance_id)
    if not inst:
        return jsonify({'error': 'instance not found'}), 404
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(inst.seed, (MAP_SIZE, MAP_SIZE, 1))
    metrics = dungeon.metrics if getattr(dungeon, 'enable_metrics', True) else {}
    return jsonify({
        'seed': dungeon.seed,
        'size': list(dungeon.size),
        'metrics': metrics,
        'flags': {
            'allow_hidden_areas': getattr(dungeon, 'allow_hidden_areas', False),
            'enable_metrics': getattr(dungeon, 'enable_metrics', True)
        }
    })
