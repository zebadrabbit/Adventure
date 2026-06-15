from app.dungeon.config import DungeonConfig
from app.dungeon.rooms import place_rooms
from app.dungeon.tiles import CAVE
import random


def _blank(cfg):
    return [[CAVE for _ in range(cfg.height)] for _ in range(cfg.width)]


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
