import pytest
from app.dungeon import Dungeon


def rooms_reachable(dungeon):
    grid = dungeon.grid
    x = len(grid); y = len(grid[0])
    # locate entrance
    entrance = None
    for ix in range(x):
        for iy in range(y):
            if 'entrance' in grid[ix][iy][0].features:
                entrance = (ix, iy)
                break
        if entrance:
            break
    assert entrance is not None, 'No entrance feature placed'
    walk = {'room','door','tunnel'}
    from collections import deque
    q = deque([entrance])
    visited = {entrance}
    while q:
        cx, cy = q.popleft()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < x and 0 <= ny < y and (nx, ny) not in visited:
                if grid[nx][ny][0].cell_type in walk:
                    visited.add((nx, ny))
                    q.append((nx, ny))
    # Now ensure every room tile is in visited
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type == 'room':
                if (ix, iy) not in visited:
                    return False
    return True


@pytest.mark.parametrize('seed', [0,1,2,3,4,5,6,7,8,9,10,42,99,12345])
def test_all_rooms_reachable(seed):
    d = Dungeon(seed=seed)
    assert rooms_reachable(d), f"Unreachable room(s) detected for seed {seed}"
