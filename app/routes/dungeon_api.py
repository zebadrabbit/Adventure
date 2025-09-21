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
from app.dungeon import Dungeon
from functools import lru_cache
import threading

# Simple in-process cache (seed,size)->Dungeon instance. Thread-safe with a lock because Flask-SocketIO/eventlet may interleave greenlets.
_dungeon_cache = {}
_dungeon_cache_lock = threading.Lock()
_DUNGEON_CACHE_MAX = 8  # small LRU-ish manual cap

def get_cached_dungeon(seed: int, size_tuple: tuple[int,int,int]):
    key = (seed, size_tuple)
    with _dungeon_cache_lock:
        dungeon = _dungeon_cache.get(key)
        if dungeon is not None:
            return dungeon
    # Build outside lock (generation may be expensive)
    dungeon = Dungeon(seed=seed, size=size_tuple)
    with _dungeon_cache_lock:
        _dungeon_cache[key] = dungeon
        # Trim if oversized (FIFO removal of oldest key)
        if len(_dungeon_cache) > _DUNGEON_CACHE_MAX:
            # pop first inserted key
            first_key = next(iter(_dungeon_cache.keys()))
            if first_key != key:
                _dungeon_cache.pop(first_key, None)
    return dungeon
from app.models.dungeon_instance import DungeonInstance
from app import db

bp_dungeon = Blueprint('dungeon', __name__)


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
            # Use cached entrance position from generation if available
            entrance = getattr(dungeon, 'entrance_pos', None)
            # If entrance is a wall, find nearest walkable tile
            valid_types = {'room', 'tunnel', 'door'}
            if entrance and dungeon.grid[entrance[0]][entrance[1]][0].cell_type == 'wall':
                from collections import deque
                queue = deque()
                queue.append((entrance[0], entrance[1]))
                visited = set()
                visited.add((entrance[0], entrance[1]))
                found = None
                while queue and not found:
                    cx, cy = queue.popleft()
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = cx+dx, cy+dy
                        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and (nx, ny) not in visited:
                            if dungeon.grid[nx][ny][0].cell_type in valid_types:
                                found = (nx, ny, 0)
                                break
                            visited.add((nx, ny))
                            queue.append((nx, ny))
                if found:
                    entrance = found
            player_pos = [instance.pos_x, instance.pos_y, instance.pos_z]
            # Check if player's current position is valid (walkable and connected to entrance)
            px, py, pz = player_pos
            valid_types = {'room', 'tunnel', 'door'}
            is_valid = (
                0 <= px < MAP_SIZE and 0 <= py < MAP_SIZE and 0 <= pz < 1 and
                dungeon.grid[px][py][pz].cell_type in valid_types
            )
            # Flood fill from entrance to get all connected tiles
            connected = set()
            if entrance:
                from collections import deque
                queue = deque()
                queue.append((entrance[0], entrance[1]))
                connected.add((entrance[0], entrance[1]))
                while queue:
                    cx, cy = queue.popleft()
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = cx+dx, cy+dy
                        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and (nx, ny) not in connected:
                            if dungeon.grid[nx][ny][0].cell_type in valid_types:
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
            grid = [[dungeon.grid[x][y][0].cell_type for x in range(MAP_SIZE)] for y in range(MAP_SIZE)]
            return jsonify({
                'grid': grid,
                'player_pos': player_pos,
                'height': MAP_SIZE,
                'width': MAP_SIZE,
                'seed': instance.seed
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
    # Regenerate dungeon for this seed (optimization: could be cached later)
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable = {'room','tunnel','door'}
    # Treat x as column (horizontal, east/west), y as row (vertical, south increases)
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    # Movement deltas (row-major grid returned to client where visual "north" corresponds to increasing y index)
    deltas = {'n': (0,1), 's': (0,-1), 'e': (1,0), 'w': (-1,0)}
    if direction in deltas:
        dx, dy = deltas[direction]
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny][0].cell_type in walkable:
            # update position
            instance.pos_x, instance.pos_y = nx, ny
            db.session.commit()
            x, y = nx, ny
    # Describe current cell
    cell = dungeon.grid[x][y][0]
    features = ', '.join(cell.features) if cell.features else 'nothing remarkable'
    desc = f"You are in a {cell.cell_type}. You notice {features}."
    # Compute exits
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny][0].cell_type in walkable:
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
    walkable = {'room','tunnel','door'}
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    deltas = {'n': (0,1), 's': (0,-1), 'e': (1,0), 'w': (-1,0)}
    cell = dungeon.grid[x][y][0]
    features = ', '.join(cell.features) if cell.features else 'nothing remarkable'
    desc = f"You are in a {cell.cell_type}. You notice {features}."
    exits_map = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x+dx, y+dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny][0].cell_type in walkable:
            exits_map.append(d)
    if exits_map:
        cardinal_full = {'n':'north','s':'south','e':'east','w':'west'}
        desc += " Exits: " + ', '.join(cardinal_full[e].capitalize() for e in exits_map) + '.'
    return jsonify({'pos': [x,y,z], 'desc': desc, 'exits': exits_map})


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
