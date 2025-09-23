import random
from typing import List, Tuple, Deque, Optional
from collections import deque
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
    _finalize_tunnel_cleanup(grid, config)


def carve_tunnel_between(grid, a: Tuple[int,int], b: Tuple[int,int], config: DungeonConfig):
    """Carve a tunnel between two room centers using BFS pathfinding that preserves wall rings.

    Strategy:
      - Compute shortest path through CAVE/ROOM tiles treating WALL as non-traversable.
      - Allow entering the destination room interior.
      - When the path transitions from corridor space (CAVE/TUNNEL) into a room (ROOM) through a WALL boundary,
        convert exactly one WALL tile into a DOOR.
      - If no path exists without breaking walls (rooms isolated), we fallback to minimal Manhattan carving (legacy behavior).
    """
    path = _bfs_path(grid, a, b, config)
    if not path:
        # fallback legacy L-shaped carve (still uses door punching with overwrite) – extremely rare
        ax,ay=a; bx,by=b
        if random.random()<0.5:
            _carve_leg(grid, ax, ay, bx, ay, config, allow_wall_break=True)
            _carve_leg(grid, bx, ay, bx, by, config, allow_wall_break=True)
        else:
            _carve_leg(grid, ax, ay, ax, by, config, allow_wall_break=True)
            _carve_leg(grid, ax, by, bx, by, config, allow_wall_break=True)
        return
    # Carve along path excluding start (inside room) but including end transition
    prev: Optional[Tuple[int,int]] = None
    for idx, (x,y) in enumerate(path):
        if idx == 0:
            prev = (x,y)
            continue  # start is inside room
        _carve_path_tile(grid, x, y, prev, config)
        prev = (x,y)
    _post_process_wall_flanks(grid, config)


def _bfs_path(grid, start: Tuple[int,int], goal: Tuple[int,int], config: DungeonConfig) -> List[Tuple[int,int]]:
    w,h = config.width, config.height
    sx,sy = start; gx,gy = goal
    walkable = {CAVE, ROOM, TUNNEL}
    # We do a BFS but push neighbors that would create a "flanked wall" later to the back (soft penalty)
    q: Deque[Tuple[int,int]] = deque([start])
    parent = {start: None}
    while q:
        x,y = q.popleft()
        if (x,y)==goal:
            break
        primary=[]; secondary=[]
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0<=nx<w and 0<=ny<h and (nx,ny) not in parent:
                t = grid[nx][ny]
                if t in walkable:
                    # If moving here would make an adjacent WALL have 2 corridor neighbors (x,y) plus (nx,ny) then penalize
                    penalize=False
                    for wx,wy in ((nx+1,ny),(nx-1,ny),(nx,ny+1),(nx,ny-1)):
                        if 0<=wx<w and 0<=wy<h and grid[wx][wy]==WALL:
                            tn=0
                            for tx,ty in ((wx+1,wy),(wx-1,wy),(wx,wy+1),(wx,wy-1)):
                                if (tx,ty)==(x,y) or (tx,ty)==(nx,ny):
                                    tn+=1
                                elif 0<=tx<w and 0<=ty<h and grid[tx][ty]==TUNNEL:
                                    tn+=1
                            if tn>=2:
                                penalize=True
                                break
                    (secondary if penalize else primary).append((nx,ny))
        # enqueue primaries first
        for p in primary:
            parent[p]=(x,y); q.append(p)
        for s in secondary:
            parent[s]=(x,y); q.append(s)
    if goal not in parent:
        return []
    # reconstruct
    path: List[Tuple[int,int]] = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def _carve_leg(grid, x1:int, y1:int, x2:int, y2:int, config: DungeonConfig, allow_wall_break=False):
    dx = 1 if x2>x1 else -1 if x2<x1 else 0
    dy = 1 if y2>y1 else -1 if y2<y1 else 0
    x,y = x1,y1
    steps = abs(x2-x1)+abs(y2-y1)
    prev = None
    for _ in range(steps):
        _carve_legacy_tile(grid, x, y, config, prev, allow_wall_break=allow_wall_break)
        prev = (x,y)
        x += dx; y += dy
    _carve_legacy_tile(grid, x, y, config, prev, allow_wall_break=allow_wall_break)


def _carve_path_tile(grid, x:int, y:int, prev: Tuple[int,int] | None, config: DungeonConfig):
    tile = grid[x][y]
    if tile == ROOM:
        return  # already inside destination or intermediary irregular cavity
    if tile == CAVE:
        grid[x][y] = TUNNEL
        return
    if tile == WALL:
        # Only convert to door if adjacent to room interior on the *other* side and previous was a tunnel (corridor approaching).
        room_adj = any(0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
        prev_is_tunnel = prev is not None and grid[prev[0]][prev[1]] == TUNNEL
        if room_adj and prev_is_tunnel:
            grid[x][y] = DOOR
        # else leave wall intact (path should not have included this unless goal inside requires fallback)


def _carve_legacy_tile(grid, x:int, y:int, config: DungeonConfig, prev, allow_wall_break: bool):
    tile = grid[x][y]
    if tile == WALL and allow_wall_break:
        room_adj = any(0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
        prev_is_tunnel = prev is not None and grid[prev[0]][prev[1]] == TUNNEL
        if room_adj and prev_is_tunnel:
            grid[x][y] = DOOR
        else:
            grid[x][y] = TUNNEL
    elif tile == CAVE:
        grid[x][y] = TUNNEL


def _post_process_wall_flanks(grid, config: DungeonConfig):
    """Repair any walls that ended up with 2+ tunnel neighbors by converting one adjacent tunnel back to CAVE
    and turning the wall into a DOOR (single doorway) if adjacent to a room, else leave as wall.
    This keeps wall rings intact while avoiding double-corridor flanking artifacts.
    """
    w,h = config.width, config.height
    # 1. Resolve wall flank issues
    for x in range(w):
        for y in range(h):
            if grid[x][y]==WALL:
                t_neighbors=[]
                for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if 0<=nx<w and 0<=ny<h and grid[nx][ny]==TUNNEL:
                        t_neighbors.append((nx,ny))
                if len(t_neighbors)>=2:
                    room_adj = any(0<=nx<w and 0<=ny<h and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                    if room_adj:
                        grid[x][y]=DOOR
                    # revert all but one tunnel neighbor furthest from center to CAVE (naive heuristic)
                    for rx,ry in t_neighbors[1:]:
                        grid[rx][ry]=CAVE
    # 2. Collapse adjacent door clusters to single door (keep first)
    for x in range(w):
        for y in range(h):
            if grid[x][y]==DOOR:
                # if any neighbor door, convert this one to wall unless it is first in lexical order
                if any(0<=nx<w and 0<=ny<h and grid[nx][ny]==DOOR for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
                    # choose canonical keeper: smallest (x,y)
                    # If current is not canonical among its door cluster, revert to WALL
                    cluster=[(x,y)]
                    for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                        if 0<=nx<w and 0<=ny<h and grid[nx][ny]==DOOR:
                            cluster.append((nx,ny))
                    keeper=min(cluster)
                    if (x,y)!=keeper:
                        # restore wall ring if original neighbors include room
                        if any(0<=nx<w and 0<=ny<h and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
                            grid[x][y]=WALL
                        else:
                            grid[x][y]=CAVE


def _finalize_tunnel_cleanup(grid, config: DungeonConfig):
    """Global pass after all tunnels carved: eliminate any remaining walls with 2+ tunnel neighbors.
    Rule:
      - If wall has 2+ tunnel neighbors:
          * If not adjacent to a door already and not creating a door cluster, convert to DOOR and prune extra tunnels.
          * Else prune tunnels until only one remains (rest to CAVE) keeping wall (or existing door) intact.
    """
    w,h = config.width, config.height
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                t_neighbors=[(nx,ny) for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)) if 0<=nx<w and 0<=ny<h and grid[nx][ny]==TUNNEL]
                if len(t_neighbors) >= 2:
                    door_neighbor = any(0<=nx<w and 0<=ny<h and grid[nx][ny]==DOOR for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                    room_adj = any(0<=nx<w and 0<=ny<h and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                    if room_adj and not door_neighbor:
                        # Make this the door and prune extra tunnels
                        grid[x][y]=DOOR
                        for rx,ry in t_neighbors[1:]:
                            grid[rx][ry]=CAVE
                    else:
                        # Keep wall; reduce tunnels to one
                        for rx,ry in t_neighbors[1:]:
                            grid[rx][ry]=CAVE
            elif grid[x][y]==DOOR:
                # Ensure door has at least one tunnel and one room neighbor; otherwise downgrade
                has_room = any(0<=nx<w and 0<=ny<h and grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                has_tunnel = any(0<=nx<w and 0<=ny<h and grid[nx][ny]==TUNNEL for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                if not (has_room and has_tunnel):
                    # revert ambiguous door back to wall if room-adj else cave
                    if has_room:
                        grid[x][y]=WALL
                    else:
                        grid[x][y]=CAVE
