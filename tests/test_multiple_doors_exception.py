import pytest
from app.dungeon import Dungeon, DungeonConfig, ROOM, DOOR


def _max_room_tile_adjacent_doors(d):
    w = d.config.width; h = d.config.height
    max_doors = 0
    for x in range(w):
        for y in range(h):
            if d.grid[x][y] == ROOM:
                doors = 0
                for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if 0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] == DOOR:
                        doors += 1
                if doors > max_doors:
                    max_doors = doors
    return max_doors


def test_multiple_doors_possible():
    """At least one seed in a range should produce a room tile with 2+ adjacent doors.
    This ensures tunnels can connect to rooms at multiple distinct points."""
    found = False
    for s in range(50, 120):
        cfg = DungeonConfig(width=55, height=55, seed=s, min_rooms=6, max_rooms=12)
        d = Dungeon(cfg)
        if _max_room_tile_adjacent_doors(d) >= 2:
            found = True
            break
    assert found, "Expected a room with at least two door adjacencies across tested seeds"
