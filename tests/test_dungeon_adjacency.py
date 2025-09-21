import pytest

from app.dungeon import Dungeon


def test_no_tunnel_adjacent_to_room():
    d = Dungeon(seed=12345, size=(40,40,1))
    data = d.grid
    x = len(data)
    y = len(data[0])
    for i in range(x):
        for j in range(y):
            ct = data[i][j][0].cell_type
            if ct == 'tunnel':
                # ensure no orth room adjacency
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = i+dx, j+dy
                    if 0 <= nx < x and 0 <= ny < y:
                        assert data[nx][ny][0].cell_type != 'room', f"Tunnel at {(i,j)} touches room at {(nx,ny)}"
