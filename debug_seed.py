"""Debug helper to inspect deterministic monster seeding for a given dungeon seed.

Run: python debug_seed.py [seed]
Defaults to seed 287259 if not provided.
Outputs walkable tile count, calculated max_monsters, sampled tile coordinates that would
be used for entity placement, and the first N designated monster slots.

This reproduces the logic in dungeon_api.dungeon_map without mutating the database.
"""

from __future__ import annotations

import sys

from app import app
from app.routes.dungeon_api import DOOR, ROOM, TUNNEL, get_cached_dungeon

MAP_SIZE = 75
DEFAULT_SEED = 287259


def analyze(seed: int):
    with app.app_context():
        dungeon = get_cached_dungeon(seed, (MAP_SIZE, MAP_SIZE, 1))
        walkable_chars = {ROOM, TUNNEL, DOOR}
        walkables = [(x, y) for x in range(MAP_SIZE) for y in range(MAP_SIZE) if dungeon.grid[x][y] in walkable_chars]
        import random as _r

        _r.seed(seed ^ 0xE7717)
        max_monsters = min(12, max(4, len(walkables) // 250))
        if walkables:
            k = max_monsters + 2 if len(walkables) > max_monsters else len(walkables)
            chosen_tiles = _r.sample(walkables, k=k)
        else:
            chosen_tiles = []
        monster_tiles = chosen_tiles[:max_monsters]
        print(f"Seed: {seed}")
        print(f"Walkable tiles: {len(walkables)}")
        print(f"max_monsters heuristic: {max_monsters}")
        print(f"Sampled slots (monster+treasure): {len(chosen_tiles)}")
        print(f"Monster tile coordinates ({len(monster_tiles)}): {monster_tiles}")


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED
    analyze(seed)
