"""Unit + property tests for the rooms-and-mazes generator.

Replaces the legacy MST/L-corridor unit tests: the generator now packs
odd-aligned rooms, floods the gaps with capped-windiness mazes, connects
regions via union-find and culls dead ends (see app/dungeon/connect.py).
"""

import random
from collections import deque

import pytest

from app.dungeon import Dungeon
from app.dungeon.config import DungeonConfig
from app.dungeon.connect import connect_regions, cull_dead_ends, derive_walls, fill_maze
from app.dungeon.dungeon import LOCKED_DOOR, SECRET_DOOR, floor_seed
from app.dungeon.rooms import place_rooms
from app.dungeon.tiles import CAVE, DOOR, ROOM, STAIRS_DOWN, STAIRS_UP, TELEPORT, TUNNEL

WALKABLE = {ROOM, TUNNEL, DOOR, TELEPORT, STAIRS_UP, STAIRS_DOWN, LOCKED_DOOR}


def _blank(cfg):
    return [[CAVE for _ in range(cfg.height)] for _ in range(cfg.width)]


# ---------------- room placement ----------------


def test_rooms_do_not_overlap_and_stay_in_bounds():
    cfg = DungeonConfig(width=75, height=75, seed=7)
    grid = _blank(cfg)
    rooms, _, placed = place_rooms(grid, cfg, rng=random.Random(cfg.seed))
    assert placed >= cfg.min_rooms
    for r in rooms:
        assert r.x >= 1 and r.y >= 1
        assert r.x + r.w <= cfg.width - 1
        assert r.y + r.h <= cfg.height - 1
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            sep_x = a.x - (b.x + b.w) if a.x > b.x else b.x - (a.x + a.w)
            sep_y = a.y - (b.y + b.h) if a.y > b.y else b.y - (a.y + a.h)
            assert sep_x >= 1 or sep_y >= 1  # at least one wall cell between rooms


# ---------------- maze + connectivity primitives ----------------


def test_fill_maze_carves_all_gaps():
    cfg = DungeonConfig(width=41, height=41, seed=3)
    grid = _blank(cfg)
    fill_maze(grid, random.Random(cfg.seed), straight_max=10)
    # every interior odd-aligned cell is carved
    for x in range(1, cfg.width - 1, 2):
        for y in range(1, cfg.height - 1, 2):
            assert grid[x][y] == TUNNEL


def test_connect_regions_yields_single_component():
    cfg = DungeonConfig(width=55, height=55, seed=11)
    grid = _blank(cfg)
    rng = random.Random(cfg.seed)
    place_rooms(grid, cfg, rng=rng)
    fill_maze(grid, rng, cfg.straight_max)
    connect_regions(grid, rng, cfg.extra_connection_chance, cfg.straight_max)
    cull_dead_ends(grid, rng, cfg.dead_end_keep)
    derive_walls(grid)
    walk = [(x, y) for x in range(cfg.width) for y in range(cfg.height) if grid[x][y] in (ROOM, TUNNEL, DOOR)]
    seen = {walk[0]}
    q = deque([walk[0]])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= nx < cfg.width
                and 0 <= ny < cfg.height
                and (nx, ny) not in seen
                and grid[nx][ny] in (ROOM, TUNNEL, DOOR)
            ):
                seen.add((nx, ny))
                q.append((nx, ny))
    assert len(seen) == len(walk)


# ---------------- whole-dungeon properties ----------------


def _max_straight_tunnel_run(d):
    best = 0
    w, h = d.config.width, d.config.height
    for y in range(h):
        run = 0
        for x in range(w):
            run = run + 1 if d.grid[x][y] == TUNNEL else 0
            best = max(best, run)
    for x in range(w):
        run = 0
        for y in range(h):
            run = run + 1 if d.grid[x][y] == TUNNEL else 0
            best = max(best, run)
    return best


@pytest.mark.parametrize("seed", range(120, 170))
def test_generation_properties(seed):
    d = Dungeon(seed=seed)
    assert d.metrics["unreachable_rooms"] == 0
    # corridor straight runs hard-capped
    assert _max_straight_tunnel_run(d) <= d.config.straight_max
    # dense map usage: walkable tiles alone cover a big share of the grid
    assert d.metrics["walkable_coverage"] >= 0.4
    used = d.metrics["walkable_coverage"] + d.metrics["tiles_wall"] / (d.config.width * d.config.height)
    assert used >= 0.5


@pytest.mark.parametrize("seed", [5, 77, 123456])
def test_multi_floor_stairs_and_loot(seed):
    num_floors = 3
    floors = [Dungeon(seed=seed, floor=z, num_floors=num_floors) for z in range(num_floors)]
    for z, d in enumerate(floors):
        assert (d.stairs_up is not None) == (z > 0)
        assert (d.stairs_down is not None) == (z < num_floors - 1)
        if d.stairs_up:
            x, y = d.stairs_up
            assert d.grid[x][y] == STAIRS_UP
        if d.stairs_down:
            x, y = d.stairs_down
            assert d.grid[x][y] == STAIRS_DOWN
    # boss + sealed loot room with portal only on the deepest floor
    for d in floors[:-1]:
        assert "boss" not in d.room_types and "treasure" not in d.room_types
        assert d.portal is None
    deepest = floors[-1]
    assert "boss" in deepest.room_types and "treasure" in deepest.room_types
    assert deepest.portal is not None and deepest.loot_room_doors
    px, py = deepest.portal
    assert deepest.grid[px][py] == TELEPORT


@pytest.mark.parametrize("seed", [9, 4242])
def test_loot_room_sealed_until_unlocked(seed):
    d = Dungeon(seed=seed, floor=2, num_floors=3)
    w, h = d.config.width, d.config.height
    loot_cells = set(d.rooms[d.room_types.index("treasure")].cells())

    def reachable(unlocked):
        start = d.entry_point
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and d.is_walkable(nx, ny, unlocked):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    assert not (reachable(set()) & loot_cells)
    assert d.portal in reachable(d.loot_room_doors)


def test_floor_seed_stable_and_distinct():
    assert floor_seed(12345, 0) == 12345  # floor 0 keeps legacy seed keying
    assert len({floor_seed(12345, z) for z in range(5)}) == 5


def test_determinism_same_seed_same_grid():
    a = Dungeon(seed=999, floor=1, num_floors=3)
    b = Dungeon(seed=999, floor=1, num_floors=3)
    assert a.to_json()["grid"] == b.to_json()["grid"]


def test_secret_doors_never_disconnect():
    for seed in range(200, 215):
        d = Dungeon(seed=seed)
        secrets = {(x, y) for x in range(d.config.width) for y in range(d.config.height) if d.grid[x][y] == SECRET_DOOR}
        # treat secret doors as walls; all rooms must still be reachable
        assert d._keeps_connectivity(secrets)
