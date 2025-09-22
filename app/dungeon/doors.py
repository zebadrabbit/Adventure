"""Door logic: validation, repair, collapsing linear runs.

Migrated from legacy monolith. Functions mutate the dungeon.grid in-place and
update provided metrics dict when enabled.
"""
from __future__ import annotations
from typing import Dict, Any
import random

from .cells import DungeonCell

def repair_and_validate_doors(dungeon: "Dungeon", metrics: Dict[str, Any], *, carve_probability: float = 1.0, allow_wall_downgrade: bool = True) -> None:
    """Validate each door ensuring exactly one adjacent room and at least one adjacent walkable (tunnel/door).

    If a door lacks a non-room walkable neighbor, optionally carve one outward (subject to carve_probability) by
    converting the first candidate wall/cave cell to tunnel. If invalid (0 or >1 room neighbors) downgrade to wall
    or tunnel (preference: wall if multiple rooms to avoid merging; tunnel if no rooms). Downgrade to wall only
    if allow_wall_downgrade is True.
    Mirrors logic from legacy _repair_and_validate_doors.
    """
    grid = dungeon.grid
    x, y, _ = dungeon.size
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type != 'door':
                continue
            room_neighbors = 0
            has_walk = False
            carve_candidate = None
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = ix+dx, iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct = grid[nx][ny][0].cell_type
                    if ct == 'room':
                        room_neighbors += 1
                    elif ct in {'tunnel','door'}:
                        has_walk = True
                    elif ct in {'wall','cave'} and carve_candidate is None:
                        carve_candidate = (nx, ny)
            # Invalid: not exactly one room neighbor
            if room_neighbors != 1:
                if not allow_wall_downgrade:
                    grid[ix][iy][0] = DungeonCell('tunnel')
                else:
                    grid[ix][iy][0] = DungeonCell('wall') if room_neighbors > 1 else DungeonCell('tunnel')
                if dungeon.enable_metrics:
                    metrics['doors_downgraded'] += 1
                continue
            # Lacks walkable non-room side
            if not has_walk:
                carved=False
                if carve_candidate:
                    # deterministic carve attempt first; probability gates only if carving would expand into large area
                    if random.random() < carve_probability or carve_probability >= 1.0:
                        cx,cy=carve_candidate
                        grid[cx][cy][0]=DungeonCell('tunnel')
                        carved=True
                if not carved:
                    grid[ix][iy][0] = DungeonCell('wall') if allow_wall_downgrade else DungeonCell('tunnel')
                    if dungeon.enable_metrics:
                        metrics['doors_downgraded'] += 1

def collapse_linear_door_runs(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:
    """Collapse chains of consecutive doors along straight lines sharing the same room adjacency direction.

    Keeps the first door in the run and converts the rest to wall (preserving separation). Also performs orphan
    door repair (attempt carve outward or downgrade) and final tunnel-room adjacency purge consistent with legacy.
    """
    grid = dungeon.grid
    x, y, _ = dungeon.size

    def room_dir(ix,iy):
        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx,ny=ix+dx,iy+dy
            if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                return (dx,dy)
        return None

    def door_has_walk(ix,iy):
        walk=0; rooms=0
        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx,ny=ix+dx,iy+dy
            if 0 <= nx < x and 0 <= ny < y:
                ct=grid[nx][ny][0].cell_type
                if ct in {'tunnel','door'}: walk+=1
                elif ct=='room': rooms+=1
        return rooms==1 and walk>0

    # Horizontal runs
    for iy in range(y):
        run=[]
        for ix in range(x+1):
            if ix < x and grid[ix][iy][0].cell_type=='door':
                run.append(ix)
            else:
                if len(run)>1:
                    dirs=[room_dir(rx,iy) for rx in run]
                    if all(d is not None and d==dirs[0] for d in dirs):
                        if door_has_walk(run[0],iy):
                            for rx in run[1:]:
                                grid[rx][iy][0]=DungeonCell('wall')
                            if dungeon.enable_metrics:
                                metrics['chains_collapsed'] += len(run)-1
                run=[]

    # Secondary strict sweep: remove any remaining 2-length runs
    def strict_prune():
        # Horizontal
        for iy in range(y):
            ix=0
            while ix < x-1:
                if grid[ix][iy][0].cell_type=='door' and grid[ix+1][iy][0].cell_type=='door':
                    d1=room_dir(ix,iy); d2=room_dir(ix+1,iy)
                    if d1 and d2 and d1==d2:
                        grid[ix+1][iy][0]=DungeonCell('wall')
                        ix+=2; continue
                ix+=1
        # Vertical
        for ix in range(x):
            iy=0
            while iy < y-1:
                if grid[ix][iy][0].cell_type=='door' and grid[ix][iy+1][0].cell_type=='door':
                    d1=room_dir(ix,iy); d2=room_dir(ix,iy+1)
                    if d1 and d2 and d1==d2:
                        grid[ix][iy+1][0]=DungeonCell('wall')
                        iy+=2; continue
                iy+=1
    strict_prune()

    # Orphan door cleanup
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type!='door':
                continue
            rooms=0; walk=0; carve_target=None
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct=grid[nx][ny][0].cell_type
                    if ct=='room': rooms+=1
                    elif ct in {'tunnel','door'}: walk+=1
                    elif ct in {'wall','cave'} and carve_target is None:
                        carve_target=(nx,ny)
            if rooms==1 and walk==0:
                carved=False
                if carve_target:
                    tx,ty=carve_target
                    room_adj=0
                    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx,ny=tx+dx,ty+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room': room_adj+=1
                    if room_adj <= 1:
                        grid[tx][ty][0]=DungeonCell('tunnel'); carved=True
                if carved:
                    if dungeon.enable_metrics: metrics['orphan_fixes'] += 1
                else:
                    grid[ix][iy][0]=DungeonCell('wall')
                    if dungeon.enable_metrics: metrics['orphan_fixes'] += 1

    # Final strict tunnel-room adjacency purge
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type=='tunnel':
                adj_rooms=0; has_walk=False
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=ix+dx,iy+dy
                    if 0 <= nx < x and 0 <= ny < y:
                        ct=grid[nx][ny][0].cell_type
                        if ct=='room': adj_rooms+=1
                        elif ct in {'tunnel','door'}: has_walk=True
                if adj_rooms>0:
                    if adj_rooms==1 and has_walk:
                        grid[ix][iy][0]=DungeonCell('door')
                    else:
                        grid[ix][iy][0]=DungeonCell('wall')

def enforce_door_invariants(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:
    """Final safety sweep to ensure all doors have exactly one adjacent room and at least one walkable non-room neighbor.

    Strategy:
    - For each door: count room neighbors and walkable neighbors (tunnel/door).
    - If room_neighbors != 1 -> downgrade (multiple rooms => wall, zero rooms => tunnel).
    - Else if no walkable: attempt to carve one outward (wall/cave) if doing so doesn't touch a second room.
      If carving fails -> downgrade to wall (cannot satisfy invariant cleanly).
    Metrics updated (doors_downgraded, orphan_fixes) for transparency.
    """
    grid = dungeon.grid
    x,y,_ = dungeon.size
    for ix in range(x):
        for iy in range(y):
            if grid[ix][iy][0].cell_type != 'door':
                continue
            room_neighbors=0; walk=0
            candidates=[]
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct=grid[nx][ny][0].cell_type
                    if ct=='room': room_neighbors+=1
                    elif ct in {'tunnel','door'}: walk+=1
                    elif ct in {'wall','cave'}: candidates.append((nx,ny))
            if room_neighbors != 1:
                # Downgrade
                grid[ix][iy][0] = DungeonCell('wall') if room_neighbors > 1 else DungeonCell('tunnel')
                if dungeon.enable_metrics:
                    metrics['doors_downgraded'] += 1
                continue
            if walk==0:
                carved=False
                # Try each candidate outward cell (allow multiple attempts)
                for cx,cy in candidates:
                    adj_rooms=0
                    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx,ny=cx+dx,cy+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room': adj_rooms+=1
                    # Skip carving into a lone cave pocket unless it will connect to an existing tunnel farther out.
                    if adj_rooms <= 1:
                        # If candidate is a cave, only accept if any orthogonal neighbor (besides the door cell) is already tunnel/door to avoid creating door->dead-cave.
                        if grid[cx][cy][0].cell_type == 'cave':
                            neighbor_walk=False
                            for dx2,dy2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                                nx2,ny2=cx+dx2,cy+dy2
                                if 0 <= nx2 < x and 0 <= ny2 < y and not (nx2==ix and ny2==iy):
                                    if grid[nx2][ny2][0].cell_type in {'tunnel','door'}:
                                        neighbor_walk=True; break
                            if not neighbor_walk:
                                continue  # try another candidate; carving would produce door->isolated tunnel in cave sea
                        grid[cx][cy][0]=DungeonCell('tunnel'); carved=True
                        if dungeon.enable_metrics: metrics['orphan_fixes'] += 1
                        break
                # Two-step carve: if still not carved, attempt carving a wall two cells out (cx->mid->far)
                if not carved and candidates:
                    for cx,cy in candidates:
                        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                            mx,my=cx+dx,cy+dy
                            fx,fy=mx+dx,my+dy
                            if 0 <= fx < x and 0 <= fy < y and 0 <= mx < x and 0 <= my < y:
                                if grid[cx][cy][0].cell_type in {'wall','cave'} and grid[mx][my][0].cell_type in {'wall','cave'} and grid[fx][fy][0].cell_type in {'tunnel'}:
                                    # carve corridor outward toward existing tunnel
                                    grid[cx][cy][0]=DungeonCell('tunnel'); grid[mx][my][0]=DungeonCell('tunnel'); carved=True
                                    if dungeon.enable_metrics: metrics['orphan_fixes'] += 1
                                    break
                        if carved: break
                if not carved:
                    # Fallback: carve first candidate regardless of additional room adjacency constraints
                    if candidates:
                        cx,cy=candidates[0]
                        # Only carve fallback if it's not an isolated cave pocket (same logic as above)
                        isolated_cave = (grid[cx][cy][0].cell_type=='cave')
                        if isolated_cave:
                            neighbor_walk=False
                            for dx2,dy2 in [(-1,0),(1,0),(0,-1),(0,1)]:
                                nx2,ny2=cx+dx2,cy+dy2
                                if 0 <= nx2 < x and 0 <= ny2 < y and not (nx2==ix and ny2==iy):
                                    if grid[nx2][ny2][0].cell_type in {'tunnel','door'}:
                                        neighbor_walk=True; break
                            if not neighbor_walk:
                                isolated_cave=True
                            else:
                                isolated_cave=False
                        if not isolated_cave:
                            grid[cx][cy][0]=DungeonCell('tunnel')
                            if dungeon.enable_metrics: metrics['orphan_fixes'] += 1
                            carved=True
                if not carved:
                    # Last resort: convert door to tunnel (neutral) instead of leaving invalid or sealing with wall
                    grid[ix][iy][0]=DungeonCell('tunnel')
                    if dungeon.enable_metrics: metrics['doors_downgraded'] += 1

def infer_missing_doors(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:
    """Final micro-pass: promote tunnel cells that should logically be doors but were missed.

    Criteria:
      * Cell is 'tunnel'
      * Exactly one orthogonal neighbor is a 'room'
      * At least one orthogonal neighbor is walkable ('tunnel' or 'door') not counting that room
      * No adjacent door already occupying the interface (avoid recreating chains)

    This runs after pruning/collapse/invariant passes, so changes are minimal. Deterministic.
    """
    grid = dungeon.grid
    x,y,_ = dungeon.size
    promoted=0
    for ix in range(x):
        for iy in range(y):
            cell = grid[ix][iy][0]
            if cell.cell_type != 'tunnel':
                continue
            room_neighbors=0; walk=False; door_adj=False
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=ix+dx,iy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    ct = grid[nx][ny][0].cell_type
                    if ct=='room': room_neighbors += 1
                    elif ct in {'tunnel','door'}: walk=True
                    if ct=='door': door_adj=True
            if room_neighbors==1 and walk and not door_adj:
                grid[ix][iy][0]=DungeonCell('door'); promoted+=1
    if promoted and dungeon.enable_metrics:
        metrics['doors_inferred'] += promoted
