import pytest
from app.dungeon import Dungeon
from tests.dungeon_test_utils import iter_doors, door_adjacency_counts

@pytest.mark.parametrize('seed', range(30, 60))
def test_no_orphan_doors(seed):
    d = Dungeon(seed=seed)
    grid = d.grid
    for x,y in iter_doors(grid):
        room_adj, walk_adj = door_adjacency_counts(grid, x, y)
        assert room_adj == 1, f"Door at {(x,y)} seed={seed} room_adj={room_adj}"
        assert walk_adj >= 1, f"Door at {(x,y)} seed={seed} has no walkable approach"
