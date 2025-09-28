from app.dungeon import DOOR, ROOM, TUNNEL, LOCKED_DOOR, Dungeon, DungeonConfig


def _max_room_tile_adjacent_doors(d):
    w = d.config.width
    h = d.config.height
    max_doors = 0
    for x in range(w):
        for y in range(h):
            if d.grid[x][y] == ROOM:
                doors = 0
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] == DOOR:
                        doors += 1
                if doors > max_doors:
                    max_doors = doors
    return max_doors


def test_no_adjacent_door_clusters_and_door_sanity():
    """Assert current invariants:

    1. No orthogonally adjacent door tiles remain after generation (clusters eliminated).
    2. Every door (including locked variants) has at least one adjacent ROOM and one adjacent walkable (ROOM/TUNNEL/DOOR/LOCKED_DOOR).

    We sample a range of seeds to guard against edge-case regressions.
    """
    for s in range(50, 70):  # modest range for speed; deterministic carving should be stable
        cfg = DungeonConfig(width=55, height=55, seed=s, min_rooms=6, max_rooms=12)
        d = Dungeon(cfg)
        w, h = d.config.width, d.config.height
        for x in range(w):
            for y in range(h):
                if d.grid[x][y] in (DOOR, LOCKED_DOOR):
                    # Invariant 1: no orthogonal neighbor also a door variant
                    assert not any(
                        0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] in (DOOR, LOCKED_DOOR)
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    ), f"Adjacent door cluster at {(x, y)} seed={s}"
                    # Invariant 2: has a ROOM neighbor
                    assert any(
                        0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] == ROOM
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    ), f"Door at {(x, y)} lacks room neighbor seed={s}"
                    # and at least one walkable neighbor (ROOM/TUNNEL/DOOR/LOCKED_DOOR)
                    assert any(
                        0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] in (ROOM, TUNNEL, DOOR, LOCKED_DOOR)
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    ), f"Door at {(x, y)} lacks walkable neighbor seed={s}"
