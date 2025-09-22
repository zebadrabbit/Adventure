import pytest
from app.dungeon.dungeon import Dungeon
from app.dungeon.config import DungeonConfig
from app.dungeon.tiles import ROOM, WALL, TUNNEL, DOOR

def walls_adjacent_to_multiple_tunnels(grid, w, h):
    violations = []
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                # Count tunnels touching wall (orthogonal)
                t_neighbors = 0
                for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if 0<=nx<w and 0<=ny<h and grid[nx][ny] == TUNNEL:
                        t_neighbors += 1
                # If a wall has 2+ tunnel neighbors, that means corridor carved through wall instead of a single door cell.
                if t_neighbors >= 2:
                    violations.append((x,y))
    return violations

def door_clusters(grid, w, h):
    clusters = []
    for x in range(w):
        for y in range(h):
            if grid[x][y] == DOOR:
                # If directly adjacent to another door, treat cluster.
                if any(0<=nx<w and 0<=ny<h and grid[nx][ny]==DOOR for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
                    clusters.append((x,y))
    return clusters

@pytest.mark.parametrize("seed", [35446, 354476, 12345])
def test_no_wall_overwrite(seed):
    cfg = DungeonConfig(seed=seed, width=75, height=75)
    d = Dungeon(cfg)
    grid = d.grid
    w = cfg.width; h = cfg.height
    # 1. No wall cell should have 2+ tunnel neighbors (indicates wall segment replaced rather than doorway punched)
    wall_violations = walls_adjacent_to_multiple_tunnels(grid, w, h)
    assert not wall_violations, f"Wall overwrite violations detected at {wall_violations[:10]} (showing up to 10)"
    # 2. Doors should not appear in orthogonally adjacent clusters >1 (multi-door segments) along straight corridor entry
    clusters = door_clusters(grid, w, h)
    assert not clusters, f"Adjacent door cluster(s) detected at {clusters[:10]} (showing up to 10)"
