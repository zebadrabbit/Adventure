"""Pruning passes for dungeon cleanup.

This module will host functions that operate on the carved dungeon grid to remove
undesirable artifacts (door clusters, orphan tunnels, corner nubs, etc.).

During transitional refactor it will import legacy logic from the monolith
until each function is migrated cleanly.
"""
from __future__ import annotations
from typing import Dict, Any
from .cells import DungeonCell

# Placeholder signatures (to be implemented by migrating from legacy code)

def prune_door_clusters(dungeon: "Dungeon") -> int:  # returns number reduced
    """Remove tight door clusters (3+ doors in 2x2 window bordering same room).
    Mirrors legacy _prune_door_clusters. Returns number of doors removed.
    """
    grid = dungeon.grid
    x, y, _ = dungeon.size
    reduced = 0
    for ix in range(x-1):
        for iy in range(y-1):
            coords=[(ix,iy),(ix+1,iy),(ix,iy+1),(ix+1,iy+1)]
            doors=[(cx,cy) for (cx,cy) in coords if grid[cx][cy][0].cell_type=='door']
            if len(doors) < 3:
                continue
            room_id=None; consistent=True
            for (dx_,dy_) in doors:
                local_room_ids=set()
                for ddx,ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=dx_+ddx,dy_+ddy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                        local_room_ids.add((nx,ny))
                if len(local_room_ids)==1:
                    rid=list(local_room_ids)[0]
                    if room_id is None:
                        room_id=rid
                    elif room_id!=rid:
                        consistent=False; break
                else:
                    consistent=False; break
            if consistent and len(doors)>1:
                keep=min(doors)
                for d in doors:
                    if d!=keep:
                        grid[d[0]][d[1]][0]=DungeonCell('wall'); reduced+=1
    return reduced

def prune_orphan_tunnels(dungeon: "Dungeon") -> int:
    """Remove tunnels not reachable from entrance (and not adjacent to rooms) unless hidden areas enabled."""
    if dungeon.allow_hidden_areas or dungeon.allow_hidden_areas_strict:
        return 0
    grid = dungeon.grid
    x,y,_ = dungeon.size
    reachable = getattr(dungeon, '_final_accessible', None)
    if reachable is None:
        reachable = flood_accessibility_cache(dungeon)  # compute & cache
    pruned=0
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type!='tunnel' or (ix,iy) in reachable:
                continue
            room_adj=False
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                    room_adj=True; break
            if not room_adj:
                # Safeguard: if this tunnel is the ONLY walkable neighbor of a door, keep it
                support_door=False
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=ix+dx,iy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='door':
                        # count walkables around that door except this tunnel
                        walk=0
                        for ddx,ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
                            px,py=nx+ddx,ny+ddy
                            if 0 <= px < x and 0 <= py < y and (px,py)!=(ix,iy):
                                if grid[px][py][0].cell_type in {'tunnel','door'}:
                                    walk+=1
                        if walk==0:
                            support_door=True; break
                if support_door:
                    continue
                grid[ix][iy][0]=DungeonCell('wall'); pruned+=1
    return pruned

def prune_corner_tunnel_nubs(dungeon: "Dungeon") -> int:
    """Remove cosmetic corner tunnel nubs (matching test definition)."""
    grid = dungeon.grid
    x,y,_=dungeon.size
    pruned=0
    for ix in range(x):
        for iy in range(y):
            cell = grid[ix][iy][0]
            if cell.cell_type != 'tunnel':
                continue
            room_orth=0; walk_orth=0; walk_neighbors=[]
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct=grid[nx][ny][0].cell_type
                    if ct=='room': room_orth+=1
                    if ct in {'room','tunnel','door'}:
                        walk_orth+=1; walk_neighbors.append(ct)
            if room_orth != 0 or walk_orth > 1:
                continue
            if walk_orth == 0:
                grid[ix][iy][0]=DungeonCell('wall'); pruned+=1; continue
            # Preserve a single-cell walkway that only connects to a door (supports door invariant carving)
            if walk_orth == 1 and walk_neighbors and walk_neighbors[0] == 'door':
                continue
            # Additional safeguard: if removing this would orphan an adjacent door (leave it with no walk neighbor)
            door_adj=False
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='door':
                    # Count walkable neighbors the door would have if this tunnel converted to wall
                    walk=0
                    for ddx,ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        px,py=nx+ddx,ny+ddy
                        if 0 <= px < x and 0 <= py < y:
                            if (px,py)!=(ix,iy) and grid[px][py][0].cell_type in {'tunnel','door'}:
                                walk+=1
                    if walk==0:
                        door_adj=True; break
            if door_adj:
                continue
            diagonal_room=False
            for dx,dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                    diagonal_room=True; break
            if not diagonal_room:
                continue
            grid[ix][iy][0]=DungeonCell('wall'); pruned+=1
    return pruned

def run_all_pruning_passes(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:
    """Execute each pruning pass updating metrics in-place.
    Order matters; matches legacy sequencing once migrated.
    """
    dcr = prune_door_clusters(dungeon)
    if dungeon.enable_metrics: metrics['door_clusters_reduced'] += dcr
    tp = prune_orphan_tunnels(dungeon)
    if dungeon.enable_metrics: metrics['tunnels_pruned'] += tp
    cnp = prune_corner_tunnel_nubs(dungeon)
    if dungeon.enable_metrics: metrics['corner_nubs_pruned'] += cnp

# Helper to compute and cache accessibility used by orphan tunnel pruning
def flood_accessibility_cache(dungeon: "Dungeon"):
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
