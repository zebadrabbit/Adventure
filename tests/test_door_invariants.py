import random
import pytest
from app.dungeon import Dungeon

@pytest.mark.structure
def test_doors_have_walk_neighbor_and_single_room():
    seeds = [random.randint(1,1_000_000) for _ in range(5)]
    for seed in seeds:
        d = Dungeon(seed=seed)
        W,H = d.width,d.height
        for x in range(W):
            for y in range(H):
                if d.grid[x][y][0].cell_type=='door':
                    room=0; walk=0
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=x+dx,y+dy
                        if 0<=nx<W and 0<=ny<H:
                            ct=d.grid[nx][ny][0].cell_type
                            if ct=='room': room+=1
                            elif ct in {'tunnel','door'}: walk+=1
                    assert room==1, f"Door at {(x,y)} seed={seed} has room_neighbors={room}"
                    assert walk>0, f"Door at {(x,y)} seed={seed} has no walk neighbors"

@pytest.mark.structure
def test_entrance_room_has_door():
    d = Dungeon(seed=random.randint(1,1_000_000))
    (ex,ey,_) = d.entrance_pos
    # find its room id by scanning
    rid = d.room_id_grid[ex][ey]
    W,H = d.width,d.height
    has_door=False
    for x in range(W):
        for y in range(H):
            if d.room_id_grid[x][y]==rid and d.grid[x][y][0].cell_type=='room':
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny=x+dx,y+dy
                    if 0<=nx<W and 0<=ny<H and d.grid[nx][ny][0].cell_type=='door':
                        has_door=True; break
                if has_door: break
        if has_door: break
    assert has_door, "Entrance room lacked a door after generation"
