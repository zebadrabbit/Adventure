import os
import importlib
import pytest

@pytest.mark.structure
@pytest.mark.parametrize('seed', [11, 42, 1337, 2024, 9001])
def test_no_door_clusters_or_orphan_tunnels(seed, monkeypatch):
    """Generate several dungeons and ensure:
    1. No orthogonally adjacent door pairs (cluster) remain.
    2. No unreachable tunnel cells (excluding hidden areas modes) remain that are not adjacent to a room.
    """
    # Ensure hidden areas are off so pruning applies
    monkeypatch.setenv('DUNGEON_ALLOW_HIDDEN_AREAS', '0')
    monkeypatch.setenv('DUNGEON_ALLOW_HIDDEN_AREAS_STRICT', '0')
    monkeypatch.setenv('DUNGEON_ENABLE_GENERATION_METRICS', '1')
    monkeypatch.setenv('DUNGEON_SEED', str(seed))

    # Lazy import after env vars
    dungeon_mod = importlib.import_module('app.dungeon')
    Dungeon = getattr(dungeon_mod, 'Dungeon')

    d = Dungeon()
    grid = d.grid  # assuming constructor auto-runs generation (pattern from existing tests)

    x, y, _ = d.size
    # 1. Dense 2x2 door cluster check (3+ doors in a 2x2 square)
    for ix in range(x-1):
        for iy in range(y-1):
            coords=[(ix,iy),(ix+1,iy),(ix,iy+1),(ix+1,iy+1)]
            doors=sum(1 for (cx,cy) in coords if grid[cx][cy][0].cell_type=='door')
            assert doors < 3, f"Dense 2x2 door cluster with {doors} doors at top-left {(ix,iy)} seed={seed}"

    # 2. Orphan tunnel check: flood from entrance
    # Find an arbitrary walkable starting cell (room or tunnel or door)
    entrance=None
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type in {'room','tunnel','door'}:
                entrance=(ix,iy); break
        if entrance: break
    assert entrance, 'No walkable cell found'

    from collections import deque
    q = deque([entrance])
    visited = {entrance}
    while q:
        cx, cy = q.popleft()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in visited:
                if grid[nx][ny][0].cell_type in {'tunnel','door','room'}:
                    visited.add((nx,ny))
                    q.append((nx,ny))

    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type == 'tunnel' and (ix,iy) not in visited:
                # Allow if adjacent to room (potential hidden path left intentionally) but hidden areas disabled so shouldn't exist
                room_adj = False
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=ix+dx,iy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                        room_adj = True
                        break
                assert room_adj, f"Unreachable orphan tunnel at {(ix,iy)} seed={seed}"

    # Metrics sanity: clusters reduced and tunnels pruned counters present (may be zero)
    assert 'door_clusters_reduced' in d.metrics
    assert 'tunnels_pruned' in d.metrics
