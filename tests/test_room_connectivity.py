import pytest
from app.dungeon import Dungeon, ROOM
from tests.dungeon_test_utils import first_room_center, bfs_reachable


def all_rooms_reachable(d):
    grid = d.grid
    start = first_room_center(d)
    # If no rooms (degenerate edge case) trivially pass
    if start is None:
        return True
    reachable = bfs_reachable(grid, start)
    w = len(grid); h = len(grid[0])
    for x in range(w):
        for y in range(h):
            if grid[x][y] == ROOM and (x,y) not in reachable:
                return False
    return True


@pytest.mark.parametrize('seed', [0,1,2,3,4,5,6,7,8,9,10,42,99,12345])
def test_all_rooms_reachable(seed):
    d = Dungeon(seed=seed)
    assert all_rooms_reachable(d), f"Unreachable room(s) detected for seed {seed}"
