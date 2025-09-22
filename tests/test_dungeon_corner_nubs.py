import importlib
import pytest

@pytest.mark.structure
@pytest.mark.parametrize('seed', [7, 19, 42, 73, 2025])
def test_no_corner_tunnel_nubs(seed, monkeypatch):
    """Ensure no tunnel cell exists that:
      * Has zero orthogonal room neighbors
      * Has at most one orthogonal walkable (room/door/tunnel) neighbor (isolated or dead-end)
      * Has at least one diagonal room neighbor
    Such cells are cosmetic corner 'nubs' and should be converted to wall by pruning pass.
    """
    monkeypatch.setenv('DUNGEON_ALLOW_HIDDEN_AREAS', '0')
    monkeypatch.setenv('DUNGEON_ALLOW_HIDDEN_AREAS_STRICT', '0')
    monkeypatch.setenv('DUNGEON_ENABLE_GENERATION_METRICS', '1')
    monkeypatch.setenv('DUNGEON_SEED', str(seed))

    # Force a fresh import each parametrized run to avoid cached grid influencing subsequent seeds
    if 'app.dungeon' in list(importlib.sys.modules.keys()):
        del importlib.sys.modules['app.dungeon']
    dungeon_mod = importlib.import_module('app.dungeon')
    Dungeon = getattr(dungeon_mod, 'Dungeon')
    d = Dungeon()
    g = d.grid
    x, y, _ = d.size

    for ix in range(x):
        for iy in range(y):
            # Only evaluate current tunnels
            if g[ix][iy][0].cell_type != 'tunnel':
                continue
            room_orth = 0
            walk_orth = 0
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny = ix+dx, iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct = g[nx][ny][0].cell_type
                    if ct == 'room':
                        room_orth += 1
                    if ct in {'room','tunnel','door'}:
                        walk_orth += 1
            if room_orth != 0 or walk_orth > 1:
                continue
            diag_room = False
            for dx,dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                nx,ny = ix+dx, iy+dy
                if 0 <= nx < x and 0 <= ny < y and g[nx][ny][0].cell_type == 'room':
                    diag_room = True
                    break
            if diag_room:
                # Re-check the cell type (could have been converted by a late pass; if still tunnel it's a failure)
                if g[ix][iy][0].cell_type == 'tunnel':
                    assert False, f"Corner tunnel nub at {(ix,iy)} seed={seed}"

    # Metric presence
    assert 'corner_nubs_pruned' in d.metrics
