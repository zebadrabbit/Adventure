import pytest
from app.dungeon import Dungeon


def door_invariant(grid):
    x = len(grid)
    y = len(grid[0])
    for ix in range(x):
        for iy in range(y):
            cell = grid[ix][iy][0]
            if cell.cell_type == 'door':
                room_adj = 0
                walk_adj = 0
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = ix+dx, iy+dy
                    if 0 <= nx < x and 0 <= ny < y:
                        ct = grid[nx][ny][0].cell_type
                        if ct == 'room':
                            room_adj += 1
                        elif ct in {'tunnel','door'}:
                            walk_adj += 1
                if room_adj != 1:
                    return False
                if walk_adj < 1:
                    return False
    return True


@pytest.mark.parametrize('seed', range(30, 60))
def test_no_orphan_doors(seed):
    dungeon = Dungeon(seed=seed)
    assert door_invariant(dungeon.grid), f"Door invariant failed for seed {seed}"
