import random
from collections import deque

from app.dungeon import Dungeon
from app.dungeon.config import DungeonConfig
from app.dungeon.connect import (
    carve_corridor,
    derive_doors,
    derive_walls,
    extra_edges,
    mst_edges,
)
from app.dungeon.rooms import place_rooms
from app.dungeon.tiles import CAVE, DOOR, ROOM, TELEPORT, TUNNEL, WALL


def _blank(cfg):
    return [[CAVE for _ in range(cfg.height)] for _ in range(cfg.width)]


def _ortho(grid, x, y):
    w, h = len(grid), len(grid[0])
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield grid[nx][ny]


# ---------------- Task 3: room placement ----------------


def test_rooms_have_min_spacing():
    cfg = DungeonConfig(width=60, height=60, seed=7)
    grid = _blank(cfg)
    rooms, _, placed = place_rooms(grid, cfg, rng=random.Random(cfg.seed))
    assert placed >= cfg.min_rooms
    # No two rooms overlap
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            sep_x = a.x - (b.x + b.w) if a.x > b.x else b.x - (a.x + a.w)
            sep_y = a.y - (b.y + b.h) if a.y > b.y else b.y - (a.y + a.h)
            assert sep_x >= 0 or sep_y >= 0  # not overlapping


def test_rooms_stay_in_bounds_with_border():
    cfg = DungeonConfig(width=50, height=50, seed=3)
    grid = _blank(cfg)
    rooms, _, _ = place_rooms(grid, cfg, rng=random.Random(cfg.seed))
    for r in rooms:
        assert r.x >= 1 and r.y >= 1
        assert r.x + r.w <= cfg.width - 1
        assert r.y + r.h <= cfg.height - 1


# ---------------- Task 4: MST graph ----------------


def test_mst_spans_all_rooms():
    centers = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)]
    edges = mst_edges(centers)
    assert len(edges) == len(centers) - 1
    seen = set()
    for a, b in edges:
        seen.add(a)
        seen.add(b)
    assert seen == set(range(len(centers)))


def test_extra_edges_are_new_and_bounded():
    centers = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)]
    base = mst_edges(centers)
    extra = extra_edges(centers, base, random.Random(1), chance=1.0)
    base_set = {tuple(sorted(e)) for e in base}
    for e in extra:
        assert tuple(sorted(e)) not in base_set
    assert len(extra) <= len(centers)


# ---------------- Task 5: corridor carving ----------------


def test_carve_corridor_connects_two_points():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    grid[2][2] = ROOM
    grid[15][15] = ROOM
    carve_corridor(grid, (2, 2), (15, 15), random.Random(0))
    q = deque([(2, 2)])
    seen = {(2, 2)}
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and grid[nx][ny] in (ROOM, TUNNEL):
                seen.add((nx, ny))
                q.append((nx, ny))
    assert (15, 15) in seen


def test_carve_corridor_does_not_touch_room_interior_tiles():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    grid[2][2] = ROOM
    grid[15][15] = ROOM
    carve_corridor(grid, (2, 2), (15, 15), random.Random(0))
    assert grid[2][2] == ROOM and grid[15][15] == ROOM


# ---------------- Task 6: derive doors + walls ----------------


def test_derive_doors_between_room_and_tunnel():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    for ix in range(2, 6):
        for iy in range(2, 6):
            grid[ix][iy] = ROOM
    grid[12][3] = ROOM
    carve_corridor(grid, (4, 4), (12, 3), random.Random(0))
    derive_doors(grid)
    doors = [(x, y) for x in range(w) for y in range(h) if grid[x][y] == DOOR]
    assert doors, "expected at least one door"
    for x, y in doors:
        neigh = list(_ortho(grid, x, y))
        assert ROOM in neigh, f"door {(x, y)} has no room neighbor"
        assert TUNNEL in neigh, f"door {(x, y)} has no tunnel neighbor"
    for x, y in doors:
        assert DOOR not in list(_ortho(grid, x, y)), f"adjacent doors at {(x, y)}"


def test_derive_walls_only_around_rooms():
    w = h = 12
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    for ix in range(3, 7):
        for iy in range(3, 7):
            grid[ix][iy] = ROOM
    derive_walls(grid)
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                assert ROOM in list(_ortho(grid, x, y)), f"wall {(x, y)} not adjacent to room"


# ---------------- Task 8: connectivity guarantee, no teleports ----------------


def test_every_room_reachable_no_teleports_across_seeds():
    walkable = {ROOM, TUNNEL, DOOR, "L"}  # locked doors traversable for connectivity check
    for seed in range(0, 120):
        d = Dungeon(seed=seed, size=(60, 60, 1))
        assert d.metrics["unreachable_rooms"] == 0, f"seed {seed} has unreachable rooms"
        tp = sum(1 for x in range(d.config.width) for y in range(d.config.height) if d.grid[x][y] == TELEPORT)
        assert tp == 0, f"seed {seed} placed teleports (crutch); count={tp}"
        start = d.rooms[0].center
        q = deque([start])
        seen = {start}
        w, h = d.config.width, d.config.height
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and d.grid[nx][ny] in walkable:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        for r in d.rooms:
            assert any((ix, iy) in seen for ix, iy in r.cells()), f"seed {seed} room unreachable by BFS"
