import pytest
from app.dungeon.dungeon import Dungeon
from app.dungeon.config import DungeonConfig
from app.dungeon.tiles import DOOR, ROOM, TUNNEL

SEEDS = [724510, 35446, 354476, 12345]


def door_groups(d):
    cfg = d.config
    w,h = cfg.width, cfg.height
    # build tunnel component ids
    comp = [[-1]*h for _ in range(w)]
    cid=0
    for x in range(w):
        for y in range(h):
            if d.grid[x][y]==TUNNEL and comp[x][y]==-1:
                stack=[(x,y)]
                comp[x][y]=cid
                while stack:
                    cx,cy=stack.pop()
                    for nx,ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                        if 0<=nx<w and 0<=ny<h and d.grid[nx][ny]==TUNNEL and comp[nx][ny]==-1:
                            comp[nx][ny]=cid
                            stack.append((nx,ny))
                cid+=1
    groups={}
    for x in range(w):
        for y in range(h):
            if d.grid[x][y]==DOOR:
                room_neighbors=[(nx,ny) for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)) if 0<=nx<w and 0<=ny<h and d.grid[nx][ny]==ROOM]
                tunnel_neighbors=[(nx,ny) for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)) if 0<=nx<w and 0<=ny<h and d.grid[nx][ny]==TUNNEL]
                if not room_neighbors or not tunnel_neighbors:
                    # other invariant tests handle orphan doors
                    continue
                anchor=min(room_neighbors)
                t_comp=comp[tunnel_neighbors[0][0]][tunnel_neighbors[0][1]]
                ax,ay=anchor
                orient='H' if ay==y else 'V'
                key=(anchor, t_comp, orient)
                groups.setdefault(key, []).append((x,y))
    return groups


@pytest.mark.parametrize('seed', SEEDS)
def test_no_redundant_doors(seed):
    cfg = DungeonConfig(seed=seed,width=75,height=75)
    d = Dungeon(cfg)
    groups = door_groups(d)
    redundant=[k for k,v in groups.items() if len(v)>1]
    assert not redundant, f"Redundant door groups detected: {redundant}"
