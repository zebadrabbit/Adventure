import random
from typing import List, Tuple
from .tiles import CAVE, ROOM, WALL, TUNNEL, DOOR
from .rooms import Room
from .config import DungeonConfig

def connect_rooms_with_tunnels(grid, rooms: List[Room], config: DungeonConfig):
    if not rooms:
        return
    centers = [r.center for r in rooms]
    edges = []
    for i in range(len(centers)):
        x1,y1 = centers[i]
        for j in range(i+1, len(centers)):
            x2,y2 = centers[j]
            dist = abs(x1-x2)+abs(y1-y2)
            edges.append((dist, i, j))
    edges.sort()
    parent = list(range(len(centers)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    mst = []
    for dist,i,j in edges:
        fi,fj = find(i), find(j)
        if fi != fj:
            parent[fi] = fj
            mst.append((i,j))
    for dist,i,j in edges:
        if random.random() < config.extra_connection_chance and (i,j) not in mst:
            mst.append((i,j))
    for (i,j) in mst:
        carve_tunnel_between(grid, centers[i], centers[j], config)


def carve_tunnel_between(grid, a: Tuple[int,int], b: Tuple[int,int], config: DungeonConfig):
    ax,ay = a; bx,by = b
    if random.random() < 0.5:
        _carve_leg(grid, ax, ay, bx, ay, config)
        _carve_leg(grid, bx, ay, bx, by, config)
    else:
        _carve_leg(grid, ax, ay, ax, by, config)
        _carve_leg(grid, ax, by, bx, by, config)


def _carve_leg(grid, x1:int, y1:int, x2:int, y2:int, config: DungeonConfig):
    dx = 1 if x2>x1 else -1 if x2<x1 else 0
    dy = 1 if y2>y1 else -1 if y2<y1 else 0
    x,y = x1,y1
    steps = abs(x2-x1)+abs(y2-y1)
    prev = None
    for _ in range(steps):
        _carve_tile(grid, x, y, config, prev)
        # Ensure any newly created DOOR has a tunnel neighbor; if not, convert previous cell to tunnel
        if grid[x][y] == DOOR and not any(0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == TUNNEL for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
            if prev is not None:
                px,py = prev
                if grid[px][py] in (CAVE, WALL):
                    grid[px][py] = TUNNEL
        prev = (x,y)
        x += dx; y += dy
    _carve_tile(grid, x, y, config, prev)
    if grid[x][y] == DOOR and not any(0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == TUNNEL for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
        if prev is not None:
            px,py = prev
            if grid[px][py] in (CAVE, WALL):
                grid[px][py] = TUNNEL


def _carve_tile(grid, x:int, y:int, config: DungeonConfig, prev):
    tile = grid[x][y]
    if tile == WALL:
        # Only create a door if adjacent to room AND previous cell already a tunnel (or will become one) to guarantee tunnel adjacency.
        room_adj = any(0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
        prev_is_tunnel = prev is not None and grid[prev[0]][prev[1]] == TUNNEL
        if room_adj and prev_is_tunnel:
            grid[x][y] = DOOR
        else:
            grid[x][y] = TUNNEL
    elif tile == CAVE:
        grid[x][y] = TUNNEL
