"""Rooms-and-mazes connectivity (Nystrom style).

Pure functions over the column-major grid (grid[x][y]):

    fill_maze       -- flood every uncarved odd-aligned cell with winding TUNNEL
                       mazes (hard cap on straight runs).
    connect_regions -- open one connector between every pair of adjacent
                       walkable regions (union-find) plus a few loop
                       connectors; room<->corridor connectors become DOORs.
    cull_dead_ends  -- retract most maze dead ends so remaining corridors all
                       lead somewhere.
    derive_walls    -- CAVE orthogonally adjacent to ROOM becomes WALL.

Connectivity is guaranteed by construction: union-find runs until a single
region remains, and dead-end culling only ever removes degree-1 cells.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .tiles import CAVE, DOOR, ROOM, TUNNEL, WALL

Point = Tuple[int, int]
_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _ortho(x: int, y: int):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def fill_maze(grid, rng, straight_max: int = 10) -> None:
    """Carve winding mazes through every uncarved odd-aligned cell.

    Growing-tree carver stepping 2 cells at a time. A straight run longer than
    `straight_max` tiles is forbidden: the carver must turn or backtrack.
    """
    w, h = len(grid), len(grid[0])
    for sx in range(1, w - 1, 2):
        for sy in range(1, h - 1, 2):
            if grid[sx][sy] == CAVE:
                _grow_maze(grid, sx, sy, rng, straight_max)


def _run_behind(grid, x: int, y: int, d: Tuple[int, int]) -> int:
    """Length of the existing straight TUNNEL run ending at (x, y) along axis d
    (looking backwards). Measured from the grid, not the carve path, so
    backtracked re-extensions can't sneak past the straight cap."""
    n = 0
    while grid[x][y] == TUNNEL:
        n += 1
        x, y = x - d[0], y - d[1]
        if not (0 <= x < len(grid) and 0 <= y < len(grid[0])):
            break
    return n


def _grow_maze(grid, sx: int, sy: int, rng, straight_max: int) -> None:
    w, h = len(grid), len(grid[0])
    grid[sx][sy] = TUNNEL
    # stack entries: (x, y, dir_in)
    stack: List[Tuple[int, int, Tuple[int, int] | None]] = [(sx, sy, None)]
    while stack:
        x, y, dir_in = stack[-1]
        options = []
        for d in _DIRS:
            nx, ny = x + 2 * d[0], y + 2 * d[1]
            if (
                1 <= nx < w - 1
                and 1 <= ny < h - 1
                and grid[nx][ny] == CAVE
                and _run_behind(grid, x, y, d) + 2 <= straight_max
            ):
                options.append(d)
        if not options:
            stack.pop()
            continue
        if dir_in in options and rng.random() < 0.35:
            d = dir_in  # mild straight bias; capped above
        else:
            d = rng.choice(options)
        grid[x + d[0]][y + d[1]] = TUNNEL
        grid[x + 2 * d[0]][y + 2 * d[1]] = TUNNEL
        stack.append((x + 2 * d[0], y + 2 * d[1], d))


def _label_regions(grid) -> Dict[Point, int]:
    """Flood-fill contiguous walkable (ROOM/TUNNEL) areas into region ids."""
    w, h = len(grid), len(grid[0])
    region: Dict[Point, int] = {}
    rid = 0
    for x in range(w):
        for y in range(h):
            if grid[x][y] not in (ROOM, TUNNEL) or (x, y) in region:
                continue
            stack = [(x, y)]
            region[(x, y)] = rid
            while stack:
                cx, cy = stack.pop()
                for nx, ny in _ortho(cx, cy):
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] in (ROOM, TUNNEL) and (nx, ny) not in region:
                        region[(nx, ny)] = rid
                        stack.append((nx, ny))
            rid += 1
    return region


def _straight_through(grid, x: int, y: int) -> int:
    """Longest straight TUNNEL run that would pass through (x, y) if it were
    carved as TUNNEL."""
    w, h = len(grid), len(grid[0])
    best = 0
    for dx, dy in ((1, 0), (0, 1)):
        n = 1
        for s in (1, -1):
            k = 1
            while (
                0 <= x + s * k * dx < w and 0 <= y + s * k * dy < h and grid[x + s * k * dx][y + s * k * dy] == TUNNEL
            ):
                n += 1
                k += 1
        best = max(best, n)
    return best


def connect_regions(grid, rng, loop_chance: float = 0.04, straight_max: int = 10) -> None:
    """Open connectors between adjacent regions until the map is one region.

    A connector is a CAVE cell whose opposite orthogonal neighbors are walkable
    cells of different regions. Room<->corridor connectors open as DOOR (unless
    that would create adjacent doors); everything else opens as TUNNEL.
    Already-merged pairs may still open with `loop_chance` to create loops.

    Connectors whose TUNNEL opening would splice two collinear corridors into a
    straight run longer than `straight_max` are deferred; they open only if no
    other connector merges their regions (connectivity beats aesthetics).
    """
    w, h = len(grid), len(grid[0])
    region = _label_regions(grid)
    if not region:
        return
    connectors = []
    for x in range(1, w - 1):
        for y in range(1, h - 1):
            if grid[x][y] != CAVE:
                continue
            for (ax, ay), (bx, by) in (((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1))):
                ra, rb = region.get((ax, ay)), region.get((bx, by))
                if ra is not None and rb is not None and ra != rb:
                    connectors.append((x, y, ra, rb))
                    break
    rng.shuffle(connectors)

    parent = list(range(max(region.values()) + 1))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def would_be_door(x: int, y: int) -> bool:
        room_adj = sum(1 for nx, ny in _ortho(x, y) if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM)
        return room_adj == 1

    deferred = []
    for x, y, ra, rb in connectors:
        fa, fb = find(ra), find(rb)
        if fa == fb:
            if rng.random() < loop_chance and (would_be_door(x, y) or _straight_through(grid, x, y) <= straight_max):
                _open_connector(grid, x, y)
            continue
        if not would_be_door(x, y) and _straight_through(grid, x, y) > straight_max:
            deferred.append((x, y, ra, rb))
            continue
        _open_connector(grid, x, y)
        parent[fa] = fb
    for x, y, ra, rb in deferred:
        fa, fb = find(ra), find(rb)
        if fa != fb:
            _open_connector(grid, x, y)
            parent[fa] = fb


def _open_connector(grid, x: int, y: int) -> None:
    w, h = len(grid), len(grid[0])
    room_adj = sum(1 for nx, ny in _ortho(x, y) if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM)
    door_adj = any(0 <= nx < w and 0 <= ny < h and grid[nx][ny] == DOOR for nx, ny in _ortho(x, y))
    # DOOR only for a clean room<->corridor junction; room<->room and
    # corridor<->corridor openings stay TUNNEL, as does anything that would
    # violate the no-adjacent-doors invariant.
    grid[x][y] = DOOR if room_adj == 1 and not door_adj else TUNNEL


def cull_dead_ends(grid, rng, keep_chance: float = 0.2) -> None:
    """Retract maze dead ends; each dead-end cell survives with `keep_chance`.

    Only TUNNEL cells with at most one walkable neighbor are removed, so
    connectivity of everything else is preserved. Cells adjacent to a DOOR are
    never removed (a door must keep its corridor approach).
    """
    w, h = len(grid), len(grid[0])
    walkable = (ROOM, TUNNEL, DOOR)
    protected = set()
    changed = True
    while changed:
        changed = False
        for x in range(1, w - 1):
            for y in range(1, h - 1):
                if grid[x][y] != TUNNEL or (x, y) in protected:
                    continue
                deg = 0
                door_adj = False
                for nx, ny in _ortho(x, y):
                    t = grid[nx][ny]
                    if t in walkable:
                        deg += 1
                    if t == DOOR:
                        door_adj = True
                if deg > 1 or door_adj:
                    continue
                if rng.random() < keep_chance:
                    protected.add((x, y))
                else:
                    grid[x][y] = CAVE
                    changed = True


def derive_walls(grid) -> None:
    """Convert each CAVE cell orthogonally adjacent to a ROOM into a WALL.
    Tunnels remain bare corridors through solid CAVE; doors are untouched."""
    w, h = len(grid), len(grid[0])
    to_wall = []
    for x in range(w):
        for y in range(h):
            if grid[x][y] != CAVE:
                continue
            for nx, ny in _ortho(x, y):
                if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM:
                    to_wall.append((x, y))
                    break
    for x, y in to_wall:
        grid[x][y] = WALL
