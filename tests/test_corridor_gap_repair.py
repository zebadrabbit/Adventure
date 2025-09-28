from app.dungeon.config import DungeonConfig
from app.dungeon.dungeon import DOOR, TUNNEL, WALL, Dungeon


def test_gap_repair_preserves_invariants_and_continuity():
    """Validate corridor gap repair heuristic via structural patterns (seed regression generalized).

    Checks:
      1. No orthogonally adjacent doors.
      2. No WALL tile has 2+ TUNNEL neighbors (should have been converted or pruned).
      3. There exists at least one horizontal tunnel span of length >= 4 and one vertical span >= 4.
    """
    seed = 611110
    cfg = DungeonConfig(seed=seed, width=75, height=75)
    d = Dungeon(cfg)
    w, h = cfg.width, cfg.height

    # 1. No adjacent doors
    for x in range(w):
        for y in range(h):
            if d.grid[x][y] == DOOR:
                assert not any(
                    0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] == DOOR
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                ), f"Adjacent doors at {(x,y)} seed={seed}"

    # 2. No wall with 2+ tunnel neighbors
    for x in range(w):
        for y in range(h):
            if d.grid[x][y] == WALL:
                t_neighbors = 0
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and d.grid[nx][ny] == TUNNEL:
                        t_neighbors += 1
                assert t_neighbors < 2, f"Wall at {(x,y)} flanked by {t_neighbors} tunnels seed={seed}"

    # 3. Tunnel span existence
    horizontal_ok = False
    vertical_ok = False
    # Horizontal spans
    for y in range(h):
        run = 0
        for x in range(w):
            if d.grid[x][y] == TUNNEL:
                run += 1
                if run >= 4:
                    horizontal_ok = True
                    break
            else:
                run = 0
        if horizontal_ok:
            break
    # Vertical spans
    for x in range(w):
        run = 0
        for y in range(h):
            if d.grid[x][y] == TUNNEL:
                run += 1
                if run >= 4:
                    vertical_ok = True
                    break
            else:
                run = 0
        if vertical_ok:
            break
    assert horizontal_ok and vertical_ok, "Expected at least one horizontal and vertical tunnel span >=4"
