"""Carve-floor-first connectivity: MST graph + corridor carving + door derivation.

Pure functions operating on the column-major grid (grid[x][y]). No teleports:
the MST spans every room, so corridors guarantee full reachability.
"""

from __future__ import annotations

from typing import List, Tuple

from .tiles import CAVE, DOOR, ROOM, TUNNEL, WALL

Point = Tuple[int, int]
Edge = Tuple[int, int]


def _dist(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def mst_edges(centers: List[Point]) -> List[Edge]:
    """Prim's algorithm over room-center points; returns list of (i, j) index edges."""
    n = len(centers)
    if n <= 1:
        return []
    in_tree = {0}
    edges: List[Edge] = []
    while len(in_tree) < n:
        best = None
        for i in in_tree:
            for j in range(n):
                if j in in_tree:
                    continue
                d = _dist(centers[i], centers[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        in_tree.add(j)
        edges.append((i, j))
    return edges


def extra_edges(centers: List[Point], base: List[Edge], rng, chance: float) -> List[Edge]:
    """Add up to len(centers) extra short edges (loops) not already in base."""
    n = len(centers)
    base_set = {tuple(sorted(e)) for e in base}
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            if tuple(sorted((i, j))) in base_set:
                continue
            candidates.append((_dist(centers[i], centers[j]), i, j))
    candidates.sort()
    out: List[Edge] = []
    for _, i, j in candidates:
        if rng.random() < chance:
            out.append((i, j))
        if len(out) >= n:
            break
    return out


def _l_path(src: Point, dst: Point, rng) -> List[Point]:
    """Ortho-stepped L-shaped path from src to dst (inclusive)."""
    (sx, sy), (dx, dy) = src, dst
    horizontal_first = rng.random() < 0.5
    path: List[Point] = [(sx, sy)]
    x, y = sx, sy
    if horizontal_first:
        step = 1 if dx > sx else -1
        while x != dx:
            x += step
            path.append((x, y))
        step = 1 if dy > sy else -1
        while y != dy:
            y += step
            path.append((x, y))
    else:
        step = 1 if dy > sy else -1
        while y != dy:
            y += step
            path.append((x, y))
        step = 1 if dx > sx else -1
        while x != dx:
            x += step
            path.append((x, y))
    return path


def carve_corridor(grid, src: Point, dst: Point, rng) -> None:
    """Carve a tunnel between two room centers. Cells already ROOM are left intact;
    CAVE cells become TUNNEL. Doors are derived later in derive_doors()."""
    for x, y in _l_path(src, dst, rng):
        if grid[x][y] == CAVE:
            grid[x][y] = TUNNEL


def _ortho_neighbors(x: int, y: int):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def derive_doors(grid) -> None:
    """Label tunnel cells that meet a room as DOOR, preserving:
      * each door has EXACTLY ONE room neighbor (single door per approach),
      * each door has a tunnel neighbor (a walkable approach),
      * no two doors are orthogonally adjacent.
    Tunnel cells touching two rooms (a corner) stay walkable tunnels rather than
    becoming a door with two room sides. Deterministic top-left scan."""
    w, h = len(grid), len(grid[0])
    for x in range(w):
        for y in range(h):
            if grid[x][y] != TUNNEL:
                continue
            neigh = [(nx, ny) for nx, ny in _ortho_neighbors(x, y) if 0 <= nx < w and 0 <= ny < h]
            room_count = sum(1 for nx, ny in neigh if grid[nx][ny] == ROOM)
            has_tunnel = any(grid[nx][ny] == TUNNEL for nx, ny in neigh)
            adj_door = any(grid[nx][ny] == DOOR for nx, ny in neigh)
            if room_count == 1 and has_tunnel and not adj_door:
                grid[x][y] = DOOR


def derive_walls(grid) -> None:
    """Convert each CAVE cell orthogonally adjacent to a ROOM into a WALL.
    Tunnels remain bare corridors through solid CAVE; doors are untouched."""
    w, h = len(grid), len(grid[0])
    to_wall = []
    for x in range(w):
        for y in range(h):
            if grid[x][y] != CAVE:
                continue
            for nx, ny in _ortho_neighbors(x, y):
                if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM:
                    to_wall.append((x, y))
                    break
    for x, y in to_wall:
        grid[x][y] = WALL
