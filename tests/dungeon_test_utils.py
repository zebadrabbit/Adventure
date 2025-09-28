from collections import deque

# Tile character constants expected from app.dungeon import but we
# keep them duplicated lightly for test independence.
ROOM = "R"
TUNNEL = "T"
DOOR = "D"
WALL = "W"
CAVE = "C"
WALKABLE = {
    ROOM,
    TUNNEL,
    DOOR,
    "L",
    "P",
}  # include locked doors and teleport pads as walkable


def first_room_center(dungeon):
    """Return (x,y) center of first placed room if any, else None.
    Relies on dungeon.rooms list introduced in refactored generator.
    """
    rooms = getattr(dungeon, "rooms", []) or []
    if not rooms:
        return None
    r0 = rooms[0]
    try:
        return (r0.center[0], r0.center[1])
    except Exception:
        return None


def bfs_reachable(grid, start):
    """Return set of (x,y) walkable reachable tiles from start over WALKABLE."""
    if start is None:
        return set()
    w = len(grid)
    h = len(grid[0])
    sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h):
        return set()
    if grid[sx][sy] not in WALKABLE:
        return set()
    q = deque([start])
    vis = {start}
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in vis:
                if grid[nx][ny] in WALKABLE:
                    vis.add((nx, ny))
                    q.append((nx, ny))
    return vis


def iter_doors(grid):
    w = len(grid)
    h = len(grid[0])
    for x in range(w):
        for y in range(h):
            if grid[x][y] == DOOR:
                yield x, y


def door_adjacency_counts(grid, x, y):
    """Return (room_adj, walk_adj) counts for door at x,y."""
    w = len(grid)
    h = len(grid[0])
    room_adj = 0
    walk_adj = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            t = grid[nx][ny]
            if t == ROOM:
                room_adj += 1
            elif t in WALKABLE:
                walk_adj += 1
    return room_adj, walk_adj


def door_has_approach(grid, x, y):
    """A door with exactly one adjacent room must have a walkable tile directly opposite that room to approach from."""
    w = len(grid)
    h = len(grid[0])
    room_dirs = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM:
            room_dirs.append((dx, dy))
    if len(room_dirs) != 1:
        return True  # Only enforce when exactly one room neighbor
    rdx, rdy = room_dirs[0]
    ox, oy = x - rdx, y - rdy
    if not (0 <= ox < w and 0 <= oy < h):
        return False
    return grid[ox][oy] in WALKABLE
