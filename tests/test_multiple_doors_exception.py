from app.dungeon import Dungeon, DungeonCell


def count_room_adjacent_doors(grid):
    """Return max number of door cells adjacent to any single room tile."""
    x = len(grid)
    y = len(grid[0])
    max_doors = 0
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type == 'room':
                doors = 0
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = ix+dx, iy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'door':
                        doors += 1
                if doors > max_doors:
                    max_doors = doors
    return max_doors


def test_multiple_doors_possible():
    """Regression: generation should allow rooms to have more than one door when distinct corridors connect.

    We generate with several seeds to increase likelihood; at least one should yield a room that ends up
    with 2+ doors. (If this flakes rarely, consider broadening seed range or relaxing threshold.)
    """
    found_multi = False
    # Try a range of deterministic seeds; break early if condition satisfied
    for s in range(50, 120):
        d = Dungeon(seed=s, size=(45,45,1))  # moderate size for faster test
        m = count_room_adjacent_doors(d.grid)
        if m >= 2:
            found_multi = True
            break
    assert found_multi, "Expected at least one generated dungeon to produce a room with multiple door connections"
