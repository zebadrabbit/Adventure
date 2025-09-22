"""Connectivity and structural consolidation utilities.

Migrated from the legacy monolith: flood fill, separation enforcement,
door guarantee, connectivity repair, and consolidation pass.
"""
from __future__ import annotations
from typing import Tuple, Set, Dict, Any, List
from .cells import DungeonCell
from .doors import repair_and_validate_doors, collapse_linear_door_runs

Coord2D = Tuple[int,int]

def flood_accessibility(dungeon: "Dungeon") -> Set[Coord2D]:
    grid = dungeon.grid
    x,y,_ = dungeon.size
    from collections import deque
    entrance_tile=None
    for i in range(x):
        for j in range(y):
            if any(f=='entrance' for f in grid[i][j][0].features):
                entrance_tile=(i,j); break
        if entrance_tile: break
    visited=set()
    if entrance_tile:
        q=deque([entrance_tile]); visited.add(entrance_tile)
        while q:
            cx,cy=q.popleft()
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=cx+dx,cy+dy
                if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in visited:
                    if grid[nx][ny][0].cell_type in {'room','door','tunnel'}:
                        visited.add((nx,ny)); q.append((nx,ny))
    dungeon._final_accessible = visited
    return visited

def enforce_room_tunnel_separation(dungeon: "Dungeon") -> None:
    grid = dungeon.grid
    x,y,_ = dungeon.size
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type != 'tunnel':
                continue
            room_neighbors = 0
            walk_dirs = []
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = ix+dx, iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct = grid[nx][ny][0].cell_type
                    if ct == 'room':
                        room_neighbors += 1
                    elif ct in {'tunnel','door'}:
                        walk_dirs.append((dx,dy))
            if room_neighbors == 0:
                continue
            if room_neighbors > 1:
                grid[ix][iy][0] = DungeonCell('wall')
                continue
            wc = len(walk_dirs)
            promote = False
            if wc == 0:
                promote = True
            elif wc == 1:
                promote = True
            elif wc == 2:
                (dx1,dy1),(dx2,dy2)=walk_dirs
                if not (dx1 == -dx2 and dy1 == -dy2):
                    promote = True
            else:
                promote = True
            if promote:
                grid[ix][iy][0] = DungeonCell('door')
            else:
                grid[ix][iy][0] = DungeonCell('wall')

def guarantee_room_doors(dungeon: "Dungeon") -> None:
    grid = dungeon.grid
    room_id_grid = dungeon.room_id_grid
    x,y,_ = dungeon.size
    room_tiles_by_id: Dict[int,List[Tuple[int,int]]] = {}
    for rx in range(x):
        for ry in range(y):
            if grid[rx][ry][0].cell_type == 'room':
                rid = room_id_grid[rx][ry]
                if rid < 0: continue
                room_tiles_by_id.setdefault(rid, []).append((rx,ry))
    entrance_room_id=None
    # Identify entrance room id for prioritization
    for rx in range(x):
        for ry in range(y):
            if 'entrance' in grid[rx][ry][0].features:
                entrance_room_id=room_id_grid[rx][ry]
                break
        if entrance_room_id is not None:
            break

    for rid, tiles in room_tiles_by_id.items():
        has_door=False; perimeter=[]
        for (tx,ty) in tiles:
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                wx,wy=tx+dx,ty+dy
                if 0 <= wx < x and 0 <= wy < y:
                    ctype=grid[wx][wy][0].cell_type
                    if ctype=='door': has_door=True
                    elif ctype in {'wall','cave'}:
                        ox,oy=wx+dx,wy+dy
                        perimeter.append((wx,wy,ox,oy))
        if has_door:
            continue
        # Prioritize entrance room if applicable by shuffling perimeter ordering
        if rid == entrance_room_id:
            # Simple heuristic: sort perimeter bringing positions with outward non-room cells first
            perimeter.sort(key=lambda t: (0 if (0 <= t[2] < x and 0 <= t[3] < y and grid[t[2]][t[3]][0].cell_type != 'room') else 1))
        for (wx,wy,ox,oy) in perimeter:
            if 0 <= ox < x and 0 <= oy < y and grid[ox][oy][0].cell_type != 'room':
                grid[wx][wy][0]=DungeonCell('door')
                # Ensure outward path is carved; if outward still solid after carve, turn into tunnel
                if grid[ox][oy][0].cell_type in {'wall','cave'}:
                    grid[ox][oy][0]=DungeonCell('tunnel')
                else:
                    # If outward already tunnel/door that's fine; if it's room (shouldn't) skip
                    pass
                break

def eliminate_tunnel_room_adjacency(dungeon: "Dungeon") -> None:
    grid = dungeon.grid
    x,y,_ = dungeon.size
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type!='tunnel':
                continue
            room_neighbors=[]; walk=False
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct=grid[nx][ny][0].cell_type
                    if ct=='room': room_neighbors.append((nx,ny))
                    elif ct in {'tunnel','door'}: walk=True
            if room_neighbors:
                if len(room_neighbors)==1 and walk:
                    grid[ix][iy][0]=DungeonCell('door')
                else:
                    grid[ix][iy][0]=DungeonCell('wall')

def validate_and_repair_connectivity(dungeon: "Dungeon", max_repairs: int = 15) -> None:
    # skip if hidden areas permitted
    if dungeon.allow_hidden_areas:
        return
    grid = dungeon.grid
    room_id_grid = dungeon.room_id_grid
    x,y,_ = dungeon.size
    from collections import deque
    entrance=None
    for ix in range(x):
        for iy in range(y):
            if 'entrance' in grid[ix][iy][0].features:
                entrance=(ix,iy); break
        if entrance: break
    if not entrance: return
    walk={'room','door','tunnel'}
    def flood(start):
        q=deque([start]); vis={start}
        while q:
            cx,cy=q.popleft()
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=cx+dx,cy+dy
                if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in vis:
                    if grid[nx][ny][0].cell_type in walk:
                        vis.add((nx,ny)); q.append((nx,ny))
        return vis
    reachable=flood(entrance)
    room_reps={}
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type=='room':
                rid=room_id_grid[ix][iy]
                if rid>=0 and rid not in room_reps:
                    room_reps[rid]=(ix,iy)
    def unreachable(): return [rid for rid,pos in room_reps.items() if pos not in reachable]
    missing=unreachable(); repairs=0; dynamic_cap=max(max_repairs, len(room_reps)*2)
    def carve_path(a,b):
        (x1,y1),(x2,y2)=a,b; cx,cy=x1,y1
        def promote(px,py):
            ct=grid[px][py][0].cell_type
            if ct in {'cave'}: grid[px][py][0]=DungeonCell('tunnel')
            elif ct=='wall':
                room_adj=0
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=px+dx,py+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room': room_adj+=1
                grid[px][py][0]=DungeonCell('door') if room_adj==1 else DungeonCell('tunnel')
        while cx!=x2:
            cx += 1 if x2>cx else -1; promote(cx,cy)
        while cy!=y2:
            cy += 1 if y2>cy else -1; promote(cx,cy)
    while missing and repairs < dynamic_cap:
        rid=missing.pop(); rep=room_reps[rid]
        nearest=None; best=10**9
        for (rx,ry) in reachable:
            d=abs(rx-rep[0])+abs(ry-rep[1])
            if d<best: best=d; nearest=(rx,ry)
        if not nearest: break
        carve_path(rep, nearest)
        # Ensure door on boundary
        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx,ny=rep[0]+dx,rep[1]+dy
            if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='wall':
                grid[nx][ny][0]=DungeonCell('door'); break
        reachable=flood(entrance)
        missing=unreachable(); repairs+=1
    if dungeon.enable_metrics and repairs:
        dungeon.metrics['repairs_performed'] += repairs
    if missing:
        # downgrade unreachable rooms to tunnels
        for rid in missing:
            (rx,ry)=room_reps[rid]
            for ix in range(x):
                for iy in range(y):
                    if room_id_grid[ix][iy]==rid and grid[ix][iy][0].cell_type=='room':
                        grid[ix][iy][0]=DungeonCell('tunnel')
        if dungeon.enable_metrics:
            dungeon.metrics['rooms_dropped'] += len(missing)
    # Final door normalization
    repair_and_validate_doors(dungeon, dungeon.metrics, carve_probability=0.0, allow_wall_downgrade=True)
    collapse_linear_door_runs(dungeon, dungeon.metrics)
    # Convert any newly unreachable rooms after repairs
    reachable=flood(entrance)
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type=='room' and (ix,iy) not in reachable:
                grid[ix][iy][0]=DungeonCell('tunnel')

def final_consolidation_pass(dungeon: "Dungeon") -> None:
    # Steps mirror legacy _final_consolidation_pass
    flood_accessibility(dungeon)  # initial snapshot (cached)
    enforce_room_tunnel_separation(dungeon)
    guarantee_room_doors(dungeon)
    validate_and_repair_connectivity(dungeon)
    eliminate_tunnel_room_adjacency(dungeon)
    # Post purge: ensure no unreachable rooms (unless hidden areas)
    if not dungeon.allow_hidden_areas:
        flood_accessibility(dungeon)
        x,y,_=dungeon.size
        for ix in range(x):
            for iy in range(y):
                if dungeon.grid[ix][iy][0].cell_type=='room' and (ix,iy) not in dungeon._final_accessible:
                    dungeon.grid[ix][iy][0]=DungeonCell('tunnel')
    repair_and_validate_doors(dungeon, dungeon.metrics, carve_probability=0.0, allow_wall_downgrade=True)
    collapse_linear_door_runs(dungeon, dungeon.metrics)

def post_generation_safety(dungeon: "Dungeon") -> None:
    if getattr(dungeon, 'allow_hidden_areas_strict', False):
        return
    flood_accessibility(dungeon)
    x,y,_ = dungeon.size
    changed=False
    for ix in range(x):
        for iy in range(y):
            if dungeon.grid[ix][iy][0].cell_type=='room' and (ix,iy) not in dungeon._final_accessible:
                dungeon.grid[ix][iy][0]=DungeonCell('tunnel'); changed=True
    if changed:
        repair_and_validate_doors(dungeon, dungeon.metrics, carve_probability=0.0, allow_wall_downgrade=True)
        collapse_linear_door_runs(dungeon, dungeon.metrics)

def repair_connectivity(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:  # backward compatibility placeholder
    # Already handled within consolidation pass; no-op here.
    return
