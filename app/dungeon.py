"""
project: Adventure MUD
module: dungeon.py
https://github.com/zebadrabbit/Adventure
License: MIT

Procedural dungeon generator and grid logic for Adventure MUD.
"""

import random
import logging
from typing import List, Dict, Tuple, Optional

class DungeonCell:
    def __init__(self, cell_type: str, features: Optional[List[str]] = None):
        self.cell_type = cell_type  # 'room', 'wall', 'tunnel', 'door', 'cave', etc.
        self.features = features or []

    def to_dict(self):
        return {
            'cell_type': self.cell_type,
            'features': self.features
        }

class Dungeon:
    def __init__(self, seed: Optional[int] = None, size: Tuple[int, int, int] = (75, 75, 1)):
        # Accept 0 as a valid deterministic seed; only generate a random seed if None explicitly.
        self.seed = seed if seed is not None else random.randint(1, 1_000_000)
        self.size = size
        self.entrance_pos: Optional[Tuple[int,int,int]] = None
        # Feature flags (deterministic). We purposefully ignore environment overrides once an app context exists
        # to prevent cross-test or cross-request leakage. Outside a Flask app context we fall back to safe defaults.
        try:  # Flask context available
            from flask import current_app, has_app_context
            if has_app_context():
                cfg = current_app.config
                self.allow_hidden_areas = bool(cfg.get('DUNGEON_ALLOW_HIDDEN_AREAS', False))
                # Strict variant: skips ALL post-generation unreachable conversions (used only for manual debugging / secret areas)
                self.allow_hidden_areas_strict = bool(cfg.get('DUNGEON_ALLOW_HIDDEN_AREAS_STRICT', False))
                self.enable_metrics = bool(cfg.get('DUNGEON_ENABLE_GENERATION_METRICS', True))
            else:
                self.allow_hidden_areas = False
                self.allow_hidden_areas_strict = False
                self.enable_metrics = True
        except Exception:
            self.allow_hidden_areas = False
            self.allow_hidden_areas_strict = False
            self.enable_metrics = True
        self.metrics = {
            'doors_created': 0,
            'doors_downgraded': 0,
            'repairs_performed': 0,
            'chains_collapsed': 0,
            'orphan_fixes': 0,
            'rooms_dropped': 0,
            'door_clusters_reduced': 0,
            'tunnels_pruned': 0,
            'runtime_ms': 0.0
        }
        import time as _t
        _start = _t.time()
        self.grid = self._generate_dungeon()
        # Debug/diagnostic metrics (optional; always populated when metrics enabled for test introspection)
        if self.enable_metrics:
            self.metrics['debug_allow_hidden'] = self.allow_hidden_areas
            self.metrics['debug_allow_hidden_strict'] = self.allow_hidden_areas_strict
            # Count room cells pre and post safety sweep (post after _post_generation_safety call below)
            self.metrics['debug_room_count_initial'] = sum(
                1 for x in range(self.size[0]) for y in range(self.size[1]) if self.grid[x][y][0].cell_type == 'room'
            )
        self.metrics['runtime_ms'] = round((_t.time() - _start)*1000, 2) if self.enable_metrics else 0.0
        # Post-generation invariant enforcement: ensure no unreachable room tiles remain.
        self._post_generation_safety()
        if self.enable_metrics:
            self.metrics['debug_room_count_post_safety'] = sum(
                1 for x in range(self.size[0]) for y in range(self.size[1]) if self.grid[x][y][0].cell_type == 'room'
            )
        # Log a concise debug line (guarded by logger level)
        logging.getLogger(__name__).debug(
            "Dungeon init seed=%s hidden=%s strict=%s rooms_initial=%s rooms_post=%s runtime_ms=%s",
            self.seed,
            self.allow_hidden_areas,
            self.allow_hidden_areas_strict,
            self.metrics.get('debug_room_count_initial'),
            self.metrics.get('debug_room_count_post_safety'),
            self.metrics.get('runtime_ms')
        )

    def _generate_dungeon(self) -> List[List[List[DungeonCell]]]:
        """Monolithic original generation retained for reference; now delegates to helper passes."""
        return self._run_generation_pipeline()

    # ---------------- Modularized Generation Pipeline -----------------
    def _init_grid(self):
        x, y, z = self.size
        return [[[DungeonCell('cave') for _ in range(z)] for _ in range(y)] for _ in range(x)]

    def _bsp_partition(self, grid):
        random.seed(self.seed)
        x, y, _ = self.size
        from collections import namedtuple
        Rect = namedtuple("Rect", "x y w h")
        bsp_min_leaf = 18
        leaves = [Rect(1, 1, x-2, y-2)]
        def split_rect(r: Rect):
            split_h = (r.w / r.h) < random.uniform(0.8, 1.2)
            if r.w < bsp_min_leaf * 1.2 and r.h < bsp_min_leaf * 1.2:
                return [r]
            if split_h and r.h >= bsp_min_leaf * 2:
                cut = random.randint(bsp_min_leaf, r.h - bsp_min_leaf)
                return [Rect(r.x, r.y, r.w, cut), Rect(r.x, r.y + cut, r.w, r.h - cut)]
            if (not split_h) and r.w >= bsp_min_leaf * 2:
                cut = random.randint(bsp_min_leaf, r.w - bsp_min_leaf)
                return [Rect(r.x, r.y, cut, r.h), Rect(r.x + cut, r.y, r.w - cut, r.h)]
            return [r]
        changed = True
        while changed:
            changed = False
            new_leaves = []
            for r in leaves:
                parts = split_rect(r)
                if len(parts) == 2:
                    changed = True
                new_leaves.extend(parts)
            leaves = new_leaves
        return leaves, Rect

    def _place_rooms(self, grid, leaves, Rect):
        x, y, _ = self.size
        min_room, max_room = 5, 12
        rooms: List[Rect] = []
        room_tiles_sets: List[set] = []
        room_id_grid = [[-1 for _ in range(y)] for _ in range(x)]
        for L in leaves:
            if L.w < 3 or L.h < 3:
                continue
            rw = random.randint(min_room, min(max_room, max(3, L.w - 2)))
            rh = random.randint(min_room, min(max_room, max(3, L.h - 2)))
            rx = random.randint(L.x + 1, max(L.x + 1, L.x + L.w - rw - 1)) if (L.w - rw - 2) >= 0 else L.x + 1
            ry = random.randint(L.y + 1, max(L.y + 1, L.y + L.h - rh - 1)) if (L.h - rh - 2) >= 0 else L.y + 1
            room = Rect(rx, ry, rw, rh)
            rooms.append(room)
            tiles = set()
            for yy in range(ry, ry + rh):
                for xx in range(rx, rx + rw):
                    if 0 <= xx < x and 0 <= yy < y:
                        grid[xx][yy][0] = DungeonCell('room')
                        tiles.add((xx, yy))
                        room_id_grid[xx][yy] = len(rooms) - 1
            room_tiles_sets.append(tiles)
        # Walls surround rooms
        for tiles in room_tiles_sets:
            for (tx, ty) in tiles:
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx, wy = tx+dx, ty+dy
                    if 0 <= wx < x and 0 <= wy < y and grid[wx][wy][0].cell_type == 'cave':
                        grid[wx][wy][0] = DungeonCell('wall')
        return rooms, room_id_grid

    def _build_room_graph(self, rooms):
        centers = [(r.x + r.w//2, r.y + r.h//2) for r in rooms]
        edges = []
        k = 4
        for i, (cx1, cy1) in enumerate(centers):
            dists = []
            for j, (cx2, cy2) in enumerate(centers):
                if i == j: continue
                d = abs(cx1 - cx2) + abs(cy1 - cy2)
                dists.append((d, i, j))
            for d, a, b in sorted(dists)[:k]:
                edges.append((d, a, b))
        # Kruskal MST
        parent = list(range(len(rooms)))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        def union(a,b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
                return True
            return False
        mst = []
        for d,a,b in sorted(edges, key=lambda e:e[0]):
            if union(a,b):
                mst.append((a,b))
        loop_chance = 0.12
        corridors = mst[:]
        seen_pairs = set((min(a,b), max(a,b)) for a,b in mst)
        for _d,a,b in edges:
            key = (min(a,b), max(a,b))
            if key not in seen_pairs and random.random() < loop_chance:
                corridors.append((a,b))
                seen_pairs.add(key)
        return centers, corridors

    def _carve_corridors(self, grid, centers, corridors, room_id_grid):
        x, y, _ = self.size
        def carve_cell(cx, cy, door_flags, endpoints):
            if not (0 <= cx < x and 0 <= cy < y): return
            current = grid[cx][cy][0].cell_type
            if current == 'room': return
            if current == 'wall':
                adjacent_room_ids = []
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                        rid = room_id_grid[nx][ny]
                        if rid not in adjacent_room_ids:
                            adjacent_room_ids.append(rid)
                if len(adjacent_room_ids) == 1:
                    rid = adjacent_room_ids[0]
                    if rid in endpoints and not door_flags.get(rid, False):
                        grid[cx][cy][0] = DungeonCell('door'); door_flags[rid] = True; return
                    grid[cx][cy][0] = DungeonCell('tunnel'); return
                else:
                    grid[cx][cy][0] = DungeonCell('tunnel'); return
            if current == 'cave':
                grid[cx][cy][0] = DungeonCell('tunnel')
        def carve_line(x1,y1,x2,y2, door_flags, endpoints):
            dx = 1 if x2 >= x1 else -1
            dy = 1 if y2 >= y1 else -1
            if x1 == x2:
                for yy in range(y1, y2+dy, dy): carve_cell(x1, yy, door_flags, endpoints)
            elif y1 == y2:
                for xx in range(x1, x2+dx, dx): carve_cell(xx, y1, door_flags, endpoints)
        def enforce_endpoint_door(room_index, center, door_flags):
            if door_flags.get(room_index, False): return
            cx, cy = center
            max_radius = 30
            for r_step in range(1, max_radius+1):
                for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]:
                    wx, wy = cx+dx*r_step, cy+dy*r_step
                    if not (0 <= wx < x and 0 <= wy < y): continue
                    if grid[wx][wy][0].cell_type == 'wall':
                        adj_room_ids = set()
                        for ax, ay in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nx, ny = wx+ax, wy+ay
                            if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                                adj_room_ids.add(room_id_grid[nx][ny])
                        if len(adj_room_ids) == 1 and room_index in adj_room_ids:
                            grid[wx][wy][0] = DungeonCell('door'); door_flags[room_index] = True; return
        def carve_irregular(a,b, door_flags, endpoints):
            (sx, sy) = centers[a]; (tx, ty) = centers[b]
            cx, cy = sx, sy
            steps=0; max_steps=(abs(tx-sx)+abs(ty-sy))*3
            while (cx,cy)!=(tx,ty) and steps<max_steps:
                steps+=1
                options=[]
                if cx<tx: options.append((1,0))
                if cx>tx: options.append((-1,0))
                if cy<ty: options.append((0,1))
                if cy>ty: options.append((0,-1))
                if random.random()<0.35: options.extend([(1,0),(-1,0),(0,1),(0,-1)])
                if not options: break
                dx,dy = random.choice(options)
                nx,ny = cx+dx, cy+dy
                carve_cell(nx,ny,door_flags,endpoints)
                cx,cy = nx,ny
            if cx!=tx: carve_line(cx,cy,tx,cy,door_flags,endpoints)
            if cy!=ty: carve_line(tx,cy,tx,ty,door_flags,endpoints)
        def carve_corridor(a,b):
            (x1c,y1c)=centers[a]; (x2c,y2c)=centers[b]; door_flags={a:False,b:False}; endpoints={a,b}
            style_rand=random.random()
            if style_rand<0.55:
                if random.random()<0.5:
                    carve_line(x1c,y1c,x2c,y1c,door_flags,endpoints); carve_line(x2c,y1c,x2c,y2c,door_flags,endpoints)
                else:
                    carve_line(x1c,y1c,x1c,y2c,door_flags,endpoints); carve_line(x1c,y2c,x2c,y2c,door_flags,endpoints)
            else:
                carve_irregular(a,b,door_flags,endpoints)
            enforce_endpoint_door(a, centers[a], door_flags); enforce_endpoint_door(b, centers[b], door_flags)
        for a,b in corridors: carve_corridor(a,b)

    def _normalize_doors_and_clean(self, grid, room_id_grid):
        # Early normalization: use shared door validator with conservative carve probability
        self._repair_and_validate_doors(grid, carve_probability=1.0, allow_wall_downgrade=True)
        # Remove isolated tunnels (dead single cells)
        x, y, _ = self.size
        def walkable(nx,ny):
            return 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type in {'room','tunnel','door'}
        isolated=[]
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type=='tunnel':
                    neighbors=sum(1 for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)] if walkable(ix+dx,iy+dy))
                    if neighbors==0:
                        isolated.append((ix,iy))
        for (ix,iy) in isolated:
            grid[ix][iy][0]=DungeonCell('wall')
        # Final immediate door revalidation (no carving this time) to catch any new violations from tunnel pruning
        self._repair_and_validate_doors(grid, carve_probability=0.0, allow_wall_downgrade=True)

    def _assign_features(self, grid, rooms):
        x, y, _ = self.size
        special_types = ['jail', 'barracks', 'common', 'water', 'treasure']
        for i, r in enumerate(rooms):
            rx, ry, rw, rh = r.x, r.y, r.w, r.h
            if i == 0:
                cx, cy = rx + rw//2, ry + rh//2
                grid[cx][cy][0].features.append('entrance')
                self.entrance_pos = (cx, cy, 0)
            elif i == len(rooms)-1:
                grid[rx + rw//2][ry + rh//2][0].features.append('boss')
            else:
                if random.random() < 0.7 and special_types:
                    t = random.choice(special_types)
                    grid[rx + rw//2][ry + rh//2][0].features.append(t)
                    if t == 'water':
                        for dx in range(-1,2):
                            for dy in range(-1,2):
                                nx, ny = rx + rw//2 + dx, ry + rh//2 + dy
                                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                                    grid[nx][ny][0].features.append('water')

    def _flood_accessibility(self, grid):
        x, y, _ = self.size
        from collections import deque
        entrance_tile=None
        for i in range(x):
            for j in range(y):
                if grid[i][j][0].cell_type == 'room' and any('entrance' in grid[i][j][0].features for _ in [0]):
                    entrance_tile=(i,j); break
            if entrance_tile: break
        visited=set();
        if entrance_tile:
            q=deque([entrance_tile])
            visited.add(entrance_tile)
            # Cache final accessibility for later pruning phases (avoids extra BFS)
            self._final_accessible = visited
            while q:
                cx,cy=q.popleft()
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=cx+dx,cy+dy
                    if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in visited:
                        if grid[nx][ny][0].cell_type in {'room','door','tunnel'}:
                            visited.add((nx,ny)); q.append((nx,ny))
        return visited

    def _enforce_room_tunnel_separation(self, grid):
        x, y, _ = self.size
        # Rule refinement (2025-09-21, updated 2025-09-21b): Prevent strings of doors.
        # Original refinement promoted any tunnel endpoint adjacent to exactly one room
        # (with at least one tunnel/door neighbor) into a door. This produced long
        # chains of consecutive door cells when a corridor hugged a room wall.
        # Revised criteria for promoting a tunnel to a door:
        #   1. Cell type is 'tunnel'.
        #   2. Adjacent to exactly one room cell.
        #   3. Corridor context indicates an entry / junction, not an inline corridor.
        #      We classify corridor context via the set of tunnel/door neighbors:
        #        - If there are 0 walkable (tunnel/door) neighbors: ignore (becomes wall below).
        #        - If exactly 1 walkable neighbor: dead-end into the room -> promote to door.
        #        - If exactly 2 walkable neighbors:
        #              * If they are opposite (straight line) -> KEEP AS TUNNEL (avoid chain)
        #              * If they are orthogonal (turn / junction) -> promote to door.
        #        - If 3+ walkable neighbors -> intersection near room -> promote.
        #   4. Otherwise leave as tunnel (not wall) to preserve corridor continuity.
        # Any tunnel adjacent to one or more rooms that does not meet door criteria and
        # is NOT a straight inline corridor segment becomes a wall (seals improper adjacency).
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
                    continue  # untouched corridor
                if room_neighbors > 1:
                    # ambiguous / between rooms -> seal
                    grid[ix][iy][0] = DungeonCell('wall')
                    continue
                # Exactly one room neighbor: decide door vs wall
                wc = len(walk_dirs)
                promote = False
                if wc == 0:
                    promote = True  # stub endpoint directly against room
                elif wc == 1:
                    promote = True  # dead-end into room
                elif wc == 2:
                    (dx1,dy1),(dx2,dy2) = walk_dirs
                    # Opposite directions => inline corridor hugging wall -> become wall to enforce separation
                    if not (dx1 == -dx2 and dy1 == -dy2):
                        promote = True  # bend/junction
                else:  # 3+ neighbors -> intersection near room
                    promote = True
                if promote:
                    grid[ix][iy][0] = DungeonCell('door')
                else:
                    grid[ix][iy][0] = DungeonCell('wall')

    def _collapse_linear_door_runs(self, grid):
        """Collapse chains of consecutive doors along straight lines sharing the same room adjacency direction.

        Keeps the first door in the run and converts the rest to wall (preserving separation)."""
        x, y, _ = self.size
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
                            # Keep first door; convert others to wall only if it doesn't orphan the first
                            if door_has_walk(run[0],iy):
                                for rx in run[1:]:
                                    grid[rx][iy][0]=DungeonCell('wall')
                                if self.enable_metrics:
                                    self.metrics['chains_collapsed'] += len(run)-1
                    run=[]
        # Secondary strict sweep: remove any remaining 2-length runs missed because door_has_walk prevented collapse
        def strict_prune():
            # Horizontal
            for iy in range(y):
                ix=0
                while ix < x-1:
                    if grid[ix][iy][0].cell_type=='door' and grid[ix+1][iy][0].cell_type=='door':
                        d1=room_dir(ix,iy); d2=room_dir(ix+1,iy)
                        if d1 and d2 and d1==d2:
                            # Keep first
                            grid[ix+1][iy][0]=DungeonCell('wall')
                            ix+=2
                            continue
                    ix+=1
            # Vertical
            for ix in range(x):
                iy=0
                while iy < y-1:
                    if grid[ix][iy][0].cell_type=='door' and grid[ix][iy+1][0].cell_type=='door':
                        d1=room_dir(ix,iy); d2=room_dir(ix,iy+1)
                        if d1 and d2 and d1==d2:
                            grid[ix][iy+1][0]=DungeonCell('wall')
                            iy+=2
                            continue
                    iy+=1
        strict_prune()
        # Orphan door cleanup: ensure each door has at least one adjacent non-room walkable
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
                    # attempt carve outward if possible
                    if carve_target:
                        grid[carve_target[0]][carve_target[1]][0]=DungeonCell('tunnel')
                        if self.enable_metrics:
                            self.metrics['orphan_fixes'] += 1
                    else:
                        # degrade to wall to remove invalid door
                        grid[ix][iy][0]=DungeonCell('wall')
                        if self.enable_metrics:
                            self.metrics['orphan_fixes'] += 1
        # Final strict tunnel-room adjacency purge (safety)
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

    def _prune_door_clusters(self, grid):
        """Remove tight door clusters (doors touching other doors orthogonally or sharing the same room boundary).

        Strategy:
          We purposefully allow pairs of adjacent doors (can represent forked corridor junctions) to preserve multi-door variety.
          We only prune dense clusters:
            * 2x2 window containing 3 or 4 doors all bordering the same single room id: keep one (top-left) convert the rest.
        """
        x, y, _ = self.size
        # 2x2 windows
        for ix in range(x-1):
            for iy in range(y-1):
                coords=[(ix,iy),(ix+1,iy),(ix,iy+1),(ix+1,iy+1)]
                doors=[(cx,cy) for (cx,cy) in coords if grid[cx][cy][0].cell_type=='door']
                if len(doors) < 3:  # only prune dense (3+ doors) clusters
                    continue
                # Determine if all doors border the same single room id
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
                    # Keep the top-leftmost door
                    keep=min(doors)
                    for d in doors:
                        if d!=keep:
                            grid[d[0]][d[1]][0]=DungeonCell('wall')
                            if self.enable_metrics: self.metrics['door_clusters_reduced'] += 1

    def _prune_orphan_tunnels(self, grid):
        """Remove tunnels not reachable from entrance (after all repairs) that are not adjacent to any room.

        Converts them to wall to avoid visual noise. Hidden areas flags skip pruning (they're intentional).
        """
        if self.allow_hidden_areas or self.allow_hidden_areas_strict:
            return
        x,y,_=self.size
        # Reuse cached accessibility if available to avoid redundant BFS
        reachable = getattr(self, '_final_accessible', None)
        if reachable is None:
            reachable = self._flood_accessibility(grid)
        pruned=0
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type!='tunnel' or (ix,iy) in reachable:
                    continue
                # Skip if adjacent to a room (could be potential future connection)
                room_adj=False
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=ix+dx,iy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                        room_adj=True; break
                if not room_adj:
                    grid[ix][iy][0]=DungeonCell('wall'); pruned+=1
        if pruned and self.enable_metrics:
            self.metrics['tunnels_pruned'] += pruned

    def _eliminate_tunnel_room_adjacency(self, grid):
        """Final safety sweep: convert any tunnel directly adjacent to a room into a door (preferred) or wall.

        This guards against edge cases where later repair steps or carving introduced a tunnel hugging a room
        that earlier separation passes missed. Preference is given to converting to a door if exactly one
        adjacent room and at least one adjacent non-room walkable (tunnel/door) exists so connectivity is not
        reduced. Otherwise convert to wall to preserve separation."""
        x, y, _ = self.size
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type != 'tunnel':
                    continue
                room_neighbors = []
                walk = False
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny = ix+dx, iy+dy
                    if 0 <= nx < x and 0 <= ny < y:
                        ct = grid[nx][ny][0].cell_type
                        if ct == 'room':
                            rid = (nx,ny)
                            room_neighbors.append(rid)
                        elif ct in {'tunnel','door'}:
                            walk = True
                if room_neighbors:  # adjacency exists -> must eliminate
                    if len(room_neighbors) == 1 and walk:
                        grid[ix][iy][0] = DungeonCell('door')
                    else:
                        grid[ix][iy][0] = DungeonCell('wall')

    def _guarantee_room_doors(self, grid, room_id_grid):
        x, y, _ = self.size
        room_tiles_by_id = {}
        for rx in range(x):
            for ry in range(y):
                if grid[rx][ry][0].cell_type == 'room':
                    rid = room_id_grid[rx][ry]
                    if rid < 0: continue
                    room_tiles_by_id.setdefault(rid, []).append((rx, ry))
        for rid, tiles in room_tiles_by_id.items():
            has_door=False; perimeter=[]
            for (tx,ty) in tiles:
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx,wy=tx+dx,ty+dy
                    if 0 <= wx < x and 0 <= wy < y:
                        ctype=grid[wx][wy][0].cell_type
                        if ctype=='door': has_door=True
                        elif ctype=='wall': perimeter.append((wx,wy, wx+dx, wy+dy))
            if has_door: continue
            for (wx,wy,ox,oy) in perimeter:
                if 0 <= ox < x and 0 <= oy < y and grid[ox][oy][0].cell_type != 'room':
                    grid[wx][wy][0]=DungeonCell('door')
                    if grid[ox][oy][0].cell_type in {'wall','cave'}: grid[ox][oy][0]=DungeonCell('tunnel')
                    break

    def _connectivity_repair(self, grid, room_id_grid, room_tiles_by_id_initial):
        x, y, _ = self.size
        def flood_collect():
            from collections import deque
            walk={'room','door','tunnel'}
            entrance=None
            for ix in range(x):
                for iy in range(y):
                    if 'entrance' in grid[ix][iy][0].features:
                        entrance=(ix,iy); break
                if entrance: break
            if not entrance: return set()
            q=deque([entrance]); vis={entrance}
            while q:
                cx,cy=q.popleft()
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=cx+dx,cy+dy
                    if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in vis:
                        if grid[nx][ny][0].cell_type in walk:
                            vis.add((nx,ny)); q.append((nx,ny))
            return vis
        reachable=flood_collect()
        room_reps={rid:tiles[0] for rid,tiles in room_tiles_by_id_initial.items()}
        unreachable=[rid for rid,t in room_reps.items() if t not in reachable]
        def carve_path(a,b):
            (x1,y1),(x2,y2)=a,b; cx,cy=x1,y1
            def promote_or_carve(px,py):
                ct=grid[px][py][0].cell_type
                if ct in {'cave'}: grid[px][py][0]=DungeonCell('tunnel')
                elif ct=='wall':
                    room_adj=[]
                    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx,ny=px+dx,py+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                            rid=room_id_grid[nx][ny]
                            if rid not in room_adj: room_adj.append(rid)
                    if len(room_adj)==1: grid[px][py][0]=DungeonCell('door')
                    else: grid[px][py][0]=DungeonCell('tunnel')
            while cx!=x2: cx += 1 if x2>cx else -1; promote_or_carve(cx,cy)
            while cy!=y2: cy += 1 if y2>cy else -1; promote_or_carve(cx,cy)
        attempts=0; max_attempts=50
        while unreachable and attempts<max_attempts:
            attempts+=1
            rid=unreachable.pop(); rep=room_reps[rid]
            nearest=None; best_d=10**9
            for (rx_,ry_) in reachable:
                d=abs(rep[0]-rx_)+abs(rep[1]-ry_)
                if d<best_d: best_d=d; nearest=(rx_,ry_)
            if nearest:
                carve_path(rep, nearest)
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=rep[0]+dx,rep[1]+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='wall':
                        grid[nx][ny][0]=DungeonCell('door'); break
                reachable=flood_collect()
                unreachable=[rid for rid,t in room_reps.items() if t not in reachable]

    def _final_separation_and_door_pass(self, grid, room_id_grid):
        self._enforce_room_tunnel_separation(grid)
        self._guarantee_room_doors(grid, room_id_grid)
        # Final orphan repair using shared helper with limited carving probability to avoid runaway tunnels.
        self._repair_and_validate_doors(grid, carve_probability=0.4, allow_wall_downgrade=True)

    # ---------------- Shared Helpers (Refactored) -----------------
    def _repair_and_validate_doors(self, grid, carve_probability: float = 1.0, allow_wall_downgrade: bool = True):
        """Validate each door ensuring exactly one adjacent room and at least one adjacent walkable (tunnel/door).

        If a door lacks a non-room walkable neighbor, optionally carve one outward (subject to carve_probability) by
        converting the first candidate wall/cave cell to tunnel. If invalid (0 or >1 room neighbors) downgrade to wall
        or tunnel (preference: wall if multiple rooms to avoid merging; tunnel if no rooms). Downgrade to wall only
        if allow_wall_downgrade is True.
        """
        x, y, _ = self.size
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
                        # Convert to tunnel as neutral if wall not allowed
                        grid[ix][iy][0] = DungeonCell('tunnel')
                        if self.enable_metrics:
                            self.metrics['doors_downgraded'] += 1
                    else:
                        grid[ix][iy][0] = DungeonCell('wall') if room_neighbors > 1 else DungeonCell('tunnel')
                        if self.enable_metrics:
                            self.metrics['doors_downgraded'] += 1
                    continue
                # Lacks walkable non-room side
                if not has_walk:
                    if carve_candidate and random.random() < carve_probability:
                        grid[carve_candidate[0]][carve_candidate[1]][0] = DungeonCell('tunnel')
                    else:
                        # Degrade: door to wall (keeps separation) or tunnel (if wall not allowed)
                        grid[ix][iy][0] = DungeonCell('wall') if allow_wall_downgrade else DungeonCell('tunnel')
                        if self.enable_metrics:
                            self.metrics['doors_downgraded'] += 1

    def _door_debug_stats(self, grid) -> Dict[str,int]:
        """Return basic statistics about doors (for potential debugging / profiling)."""
        x, y, _ = self.size
        stats = {'doors':0, 'invalid_context':0}
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'door':
                    stats['doors'] += 1
                    room_neighbors=0; walk=False
                    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx,ny=ix+dx,iy+dy
                        if 0 <= nx < x and 0 <= ny < y:
                            ct=grid[nx][ny][0].cell_type
                            if ct=='room': room_neighbors+=1
                            elif ct in {'tunnel','door'}: walk=True
                    if not(room_neighbors==1 and walk):
                        stats['invalid_context'] += 1
        return stats

    def _validate_and_repair_connectivity(self, grid, room_id_grid, max_repairs: int = 15):
        """Final safety net: ensure every room is reachable from the entrance.

        We only require rooms (and implicitly their doors) to be on the main connected component. Unreachable
        tunnels are tolerated for now (they may represent secret / blocked future areas). If an unreachable room
        is found, we carve a minimal Manhattan path from that room's representative tile to the nearest reachable
        walkable tile, promoting any intervening wall that borders exactly one room to a door, otherwise a tunnel.
        """
        x, y, _ = self.size
        from collections import deque
        # If hidden areas are allowed, skip repairs entirely (we still could compute reachability if metrics wanted)
        if self.allow_hidden_areas:
            return
        # Find entrance
        entrance=None
        for ix in range(x):
            for iy in range(y):
                if 'entrance' in grid[ix][iy][0].features:
                    entrance=(ix,iy); break
            if entrance: break
        if not entrance:
            return
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
        # Collect rooms and choose representative tile per room_id
        room_reps={}
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type=='room':
                    rid=room_id_grid[ix][iy]
                    if rid >= 0 and rid not in room_reps:
                        room_reps[rid]=(ix,iy)
        def unreachable_rooms():
            return [rid for rid,pos in room_reps.items() if pos not in reachable]
        missing=unreachable_rooms()
        # Dynamic repair budget: at least len(room_reps) * 2 (upper bound allows connecting fragmented clusters)
        dynamic_cap = max(max_repairs, len(room_reps) * 2)
        repairs=0
        while missing and repairs < dynamic_cap:
            rid=missing.pop()
            rep=room_reps[rid]
            # Find nearest reachable walkable tile
            nearest=None; best_d=10**9
            for (rx,ry) in reachable:
                d=abs(rx-rep[0])+abs(ry-rep[1])
                if d < best_d:
                    best_d=d; nearest=(rx,ry)
            if not nearest:
                break
            (sx,sy)=rep; (tx,ty)=nearest
            cx,cy=sx,sy
            def promote(px,py):
                ct=grid[px][py][0].cell_type
                if ct in {'cave'}:
                    grid[px][py][0]=DungeonCell('tunnel')
                elif ct=='wall':
                    # Promote to door if exactly one adjacent room, else tunnel
                    room_adj=0
                    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx,ny=px+dx,py+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                            room_adj+=1
                    if room_adj==1:
                        grid[px][py][0]=DungeonCell('door')
                    else:
                        grid[px][py][0]=DungeonCell('tunnel')
            while cx!=tx:
                cx += 1 if tx>cx else -1
                promote(cx,cy)
            while cy!=ty:
                cy += 1 if ty>cy else -1
                promote(cx,cy)
            # Ensure at least one door on room boundary (if no door present after carving)
            has_door=False
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx,ny=sx+dx,sy+dy
                if 0 <= nx < x and 0 <= ny < y:
                    if grid[nx][ny][0].cell_type=='door':
                        has_door=True; break
            if not has_door:
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=sx+dx,sy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='wall':
                        grid[nx][ny][0]=DungeonCell('door'); break
            reachable=flood(entrance)
            missing=unreachable_rooms()
            repairs+=1
        if self.enable_metrics and repairs:
            self.metrics['repairs_performed'] += repairs
        # Fallback: if any rooms still unreachable, downgrade them to tunnels (record metric)
        if missing:
            # Recompute list explicitly (missing list may be stale) before fallback
            remaining_unreachable = [rid for rid,pos in room_reps.items() if pos not in reachable]
            rooms_dropped = 0
            if remaining_unreachable:
                for rid in remaining_unreachable:
                    (rx, ry) = room_reps[rid]
                    # Convert all tiles of that room id to tunnel
                    for ix in range(x):
                        for iy in range(y):
                            if room_id_grid[ix][iy] == rid and grid[ix][iy][0].cell_type == 'room':
                                grid[ix][iy][0] = DungeonCell('tunnel')
                    rooms_dropped += 1
            if rooms_dropped and self.enable_metrics:
                # Initialize metric if not present (retrofit safe)
                if 'rooms_dropped' not in self.metrics:
                    self.metrics['rooms_dropped'] = 0
                self.metrics['rooms_dropped'] += rooms_dropped
        # Post-repair: validate doors (no carving) to remove any orphan/invalid ones and collapse potential chains.
        self._repair_and_validate_doors(grid, carve_probability=0.0, allow_wall_downgrade=True)
        self._collapse_linear_door_runs(grid)
        # (7) Final safety: convert any newly unreachable rooms into tunnels (tests expect no unreachable rooms).
        # Hidden areas flag now only skips active carving repairs earlier, but unreachable rooms are still normalized.
        final_vis = self._flood_accessibility(grid)
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'room' and (ix,iy) not in final_vis:
                    grid[ix][iy][0] = DungeonCell('tunnel')
        # No return value; mutation in-place.

    def _run_generation_pipeline(self):
        grid = self._init_grid()
        leaves, Rect = self._bsp_partition(grid)
        rooms, room_id_grid = self._place_rooms(grid, leaves, Rect)
        centers, corridors = self._build_room_graph(rooms)
        self._carve_corridors(grid, centers, corridors, room_id_grid)
        self._normalize_doors_and_clean(grid, room_id_grid)
        self._assign_features(grid, rooms)
        # Consolidated final structural & connectivity normalization
        self._final_consolidation_pass(grid, room_id_grid)
        # New: prune door clusters and orphan tunnels for cleaner visuals
        self._prune_door_clusters(grid)
        self._prune_orphan_tunnels(grid)

        # Re-run door chain collapse lightly in case pruning created new trivial patterns
        self._collapse_linear_door_runs(grid)
        return grid

        for a, b in corridors:
            carve_corridor(a, b)

        # ---------------- Door & Wall Normalization Pass -----------------
        # Ensure that each door sits between exactly one room and one traversable (tunnel/room) space on opposite sides.
        # Fix cases where a door was created but corridor carved away adjacent wall producing an open gap, or where
        # a door is effectively inside a thick wall with no tunnel neighbor.
        def valid_door(xc, yc):
            room_dirs = []
            tunnel_dirs = []
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = xc+dx, yc+dy
                if 0 <= nx < x and 0 <= ny < y:
                    t = grid[nx][ny][0].cell_type
                    if t == 'room':
                        room_dirs.append((dx, dy))
                    if t in {'tunnel', 'door'}:
                        tunnel_dirs.append((dx, dy))
            return room_dirs, tunnel_dirs

        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'door':
                    room_dirs, tunnel_dirs = valid_door(ix, iy)
                    # Must have exactly one adjacent room side and at least one tunnel side not the same tile.
                    if len(room_dirs) != 1 or len(tunnel_dirs) == 0:
                        # If surrounded by rooms on two sides, convert to room (internalized connection)
                        if len(room_dirs) >= 2:
                            grid[ix][iy][0] = DungeonCell('room')
                        # If no room adjacency at all, degrade to tunnel (was misplaced)
                        elif len(room_dirs) == 0:
                            grid[ix][iy][0] = DungeonCell('tunnel')
                        else:
                            # One room but no tunnel -> carve one tunnel outward (pick first non-room cave/wall)
                            carved = False
                            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                                nx, ny = ix+dx, iy+dy
                                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type in {'cave','wall'}:
                                    grid[nx][ny][0] = DungeonCell('tunnel')
                                    carved = True
                                    break
                            if not carved:
                                # fallback degrade
                                grid[ix][iy][0] = DungeonCell('tunnel')

        # Remove stray wall gaps: if a tunnel directly touches a room with no intervening door and there is a wall candidate
        # we leave as-is (open arch) OR optionally insert a door. For now we keep open to avoid over-door creation.

        # ---------------- Clean-up: eliminate isolated 1x1 tunnels & doors into rock -----------------
        def walkable(nx, ny):
            if 0 <= nx < x and 0 <= ny < y:
                return grid[nx][ny][0].cell_type in {'room','tunnel','door'}
            return False

        # First pass: mark isolated tunnels (no other walkable neighbors)
        isolated = []
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'tunnel':
                    neighbors = 0
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        if walkable(ix+dx, iy+dy):
                            neighbors += 1
                    if neighbors == 0:  # isolated 1x1 tunnel
                        isolated.append((ix, iy))
        for (ix, iy) in isolated:
            grid[ix][iy][0] = DungeonCell('wall')  # convert to wall to visually close

        # Second pass: remove doors whose non-room side is not walkable (door opening into rock/cave)
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'door':
                    # Count room neighbors and collect non-room neighbor types
                    room_neighbors = 0
                    non_room_walkable = False
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = ix+dx, iy+dy
                        if 0 <= nx < x and 0 <= ny < y:
                            ct = grid[nx][ny][0].cell_type
                            if ct == 'room':
                                room_neighbors += 1
                            elif ct in {'tunnel','door'}:
                                non_room_walkable = True
                    # Valid door: exactly one room neighbor and at least one other walkable neighbor
                    if not (room_neighbors == 1 and non_room_walkable):
                        # degrade to wall (not a proper door)
                        grid[ix][iy][0] = DungeonCell('wall')

        # ---------------- Feature Assignment -----------------
        special_types = ['jail', 'barracks', 'common', 'water', 'treasure']
        for i, r in enumerate(rooms):
            rx, ry, rw, rh = r.x, r.y, r.w, r.h
            if i == 0:
                grid[rx + rw//2][ry + rh//2][0].features.append('entrance')
            elif i == len(rooms)-1:
                grid[rx + rw//2][ry + rh//2][0].features.append('boss')
            else:
                if random.random() < 0.7 and special_types:
                    t = random.choice(special_types)
                    grid[rx + rw//2][ry + rh//2][0].features.append(t)
                    if t == 'water':
                        for dx in range(-1,2):
                            for dy in range(-1,2):
                                nx, ny = rx + rw//2 + dx, ry + rh//2 + dy
                                if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                                    grid[nx][ny][0].features.append('water')

        # ---------------- Accessibility Flood Fill -----------------
        from collections import deque
        entrance_tile = None
        for i in range(x):
            for j in range(y):
                if 'entrance' in grid[i][j][0].features:
                    entrance_tile = (i, j)
                    break
            if entrance_tile:
                break
        visited = set()
        queue = deque()
        if entrance_tile:
            queue.append(entrance_tile)
            visited.add(entrance_tile)
            while queue:
                cx, cy = queue.popleft()
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < x and 0 <= ny < y and (nx, ny) not in visited:
                        if grid[nx][ny][0].cell_type in {'room', 'door', 'tunnel'}:
                            visited.add((nx, ny))
                            queue.append((nx, ny))
        for i in range(x):
            for j in range(y):
                if grid[i][j][0].cell_type in {'room', 'door'} and (i, j) not in visited:
                    grid[i][j][0] = DungeonCell('tunnel')
        # ---------------- Adjacency Rule: prevent tunnel directly touching room -----------------
        # New rule (2025-09-21): No tunnel cell may be orthogonally adjacent to a room; there must be a door OR a wall.
        # We perform a pass converting any tunnel that directly touches a room (without being a door already) back to wall.
        # This preserves existing doors (which are allowed) and isolates rooms behind walls/doors only.
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'tunnel':
                    touches_room = False
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = ix + dx, iy + dy
                        if 0 <= nx < x and 0 <= ny < y:
                            if grid[nx][ny][0].cell_type == 'room':
                                touches_room = True
                                break
                    if touches_room:
                        # Convert to wall to ensure separation. (Could consider promoting a single adjacent wall to door elsewhere.)
                        grid[ix][iy][0] = DungeonCell('wall')

        # ---------------- Guarantee: at least one door per room -----------------
        # After enforcing separation, some rooms might end up fully walled with no door. We ensure each room has >=1 door.
        # Strategy: For each room, scan its perimeter (adjacent wall cells). If none of those walls are doors already,
        # convert the first suitable wall that borders a non-room (cave/wall/tunnel) on the opposite side into a door and, if the
        # outward side isn't walkable yet, carve a tunnel cell there.
        # Build quick lookup for room tiles to minimize re-scanning.
        room_tiles_by_id = {}
        for rx in range(x):
            for ry in range(y):
                if grid[rx][ry][0].cell_type == 'room':
                    rid = room_id_grid[rx][ry]
                    if rid < 0:  # safety
                        continue
                    room_tiles_by_id.setdefault(rid, []).append((rx, ry))

        for rid, tiles in room_tiles_by_id.items():
            has_door = False
            perimeter_candidates = []
            for (tx, ty) in tiles:
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx, wy = tx+dx, ty+dy
                    if 0 <= wx < x and 0 <= wy < y:
                        ctype = grid[wx][wy][0].cell_type
                        if ctype == 'door':
                            has_door = True
                        elif ctype == 'wall':
                            # collect candidate wall and outward target
                            ox, oy = wx+dx, wy+dy  # outward cell beyond the wall
                            perimeter_candidates.append((wx, wy, ox, oy))
            if has_door:
                continue
            # Promote first viable wall to door
            for (wx, wy, ox, oy) in perimeter_candidates:
                # Ensure outward target inside bounds and not a room (prefer existing tunnel or carve new tunnel)
                if 0 <= ox < x and 0 <= oy < y:
                    out_type = grid[ox][oy][0].cell_type
                    if out_type in {'room'}:
                        continue  # do not door directly into another room; maintain separation
                    # place door
                    grid[wx][wy][0] = DungeonCell('door')
                    if out_type in {'wall','cave'}:
                        grid[ox][oy][0] = DungeonCell('tunnel')
                    break  # one door is enough
        # ---------------- Connectivity Repair -----------------
        # Final assurance: all room tiles must be reachable from entrance via walkable cells (room/door/tunnel).
        # If some rooms are isolated, carve a minimal Manhattan corridor from a random tile in the unreachable room
        # to the nearest reachable corridor/room/door.
        from collections import deque
        def flood_collect():
            walk = {'room','door','tunnel'}
            entrance = None
            for ix in range(x):
                for iy in range(y):
                    if 'entrance' in grid[ix][iy][0].features:
                        entrance = (ix, iy)
                        break
                if entrance: break
            if not entrance:
                return set()
            q = deque([entrance])
            vis = {entrance}
            while q:
                cx, cy = q.popleft()
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < x and 0 <= ny < y and (nx, ny) not in vis:
                        if grid[nx][ny][0].cell_type in walk:
                            vis.add((nx, ny))
                            q.append((nx, ny))
            return vis
        reachable = flood_collect()
        # Collect representative tile per room
        room_reps = {}
        for rid, tiles in room_tiles_by_id.items():
            room_reps[rid] = tiles[0]
        # Determine unreachable rooms
        unreachable = [rid for rid, t in room_reps.items() if t not in reachable]
        # helper to carve straight line (Manhattan) with doors at first wall adjacent to room
        def carve_path(a, b):
            (x1, y1), (x2, y2) = a, b
            cx, cy = x1, y1
            def promote_or_carve(px, py):
                ct = grid[px][py][0].cell_type
                if ct in {'cave'}:
                    grid[px][py][0] = DungeonCell('tunnel')
                elif ct == 'wall':
                    # If this wall borders exactly one room, make it a door, else tunnel
                    room_adj = []
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = px+dx, py+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                            rid = room_id_grid[nx][ny]
                            if rid not in room_adj:
                                room_adj.append(rid)
                    if len(room_adj) == 1:
                        grid[px][py][0] = DungeonCell('door')
                    else:
                        grid[px][py][0] = DungeonCell('tunnel')
            while cx != x2:
                cx += 1 if x2 > cx else -1
                promote_or_carve(cx, cy)
            while cy != y2:
                cy += 1 if y2 > cy else -1
                promote_or_carve(cx, cy)
        # For each unreachable room, connect it to nearest reachable tile center
        max_attempts = 50
        attempts = 0
        while unreachable and attempts < max_attempts:
            attempts += 1
            rid = unreachable.pop()
            rep = room_reps[rid]
            # find nearest reachable tile (Manhattan distance)
            nearest = None
            best_d = 10**9
            for (rx_, ry_) in reachable:
                d = abs(rep[0]-rx_) + abs(rep[1]-ry_)
                if d < best_d:
                    best_d = d
                    nearest = (rx_, ry_)
            if nearest:
                carve_path(rep, nearest)
                # ensure door on room boundary if needed
                # pick a wall between rep and nearest along initial direction if still wall
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = rep[0]+dx, rep[1]+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'wall':
                        grid[nx][ny][0] = DungeonCell('door')
                        break
                reachable = flood_collect()
                unreachable = [rid for rid, t in room_reps.items() if t not in reachable]
        # --------------- Final Separation & Door Guarantee Re-run ---------------
        # Re-apply tunnel-room separation in case connectivity carving introduced violations.
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type == 'tunnel':
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = ix+dx, iy+dy
                        if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                            grid[ix][iy][0] = DungeonCell('wall')
                            break
        # Rebuild room tiles (unchanged ids) and ensure each still has at least one door
        room_tiles_by_id_final = {}
        for rx in range(x):
            for ry in range(y):
                if grid[rx][ry][0].cell_type == 'room':
                    rid2 = room_id_grid[rx][ry]
                    if rid2 < 0:
                        continue
                    room_tiles_by_id_final.setdefault(rid2, []).append((rx, ry))
        for rid2, tiles in room_tiles_by_id_final.items():
            has_door = False
            perim = []
            for (tx, ty) in tiles:
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx, wy = tx+dx, ty+dy
                    if 0 <= wx < x and 0 <= wy < y:
                        ctype = grid[wx][wy][0].cell_type
                        if ctype == 'door':
                            has_door = True
                        elif ctype == 'wall':
                            ox, oy = wx+dx, wy+dy
                            perim.append((wx, wy, ox, oy))
            if has_door:
                continue
            for (wx, wy, ox, oy) in perim:
                if 0 <= ox < x and 0 <= oy < y and grid[ox][oy][0].cell_type != 'room':
                    grid[wx][wy][0] = DungeonCell('door')
                    if grid[ox][oy][0].cell_type in {'wall','cave'}:
                        grid[ox][oy][0] = DungeonCell('tunnel')
                    break
        return grid

    def to_dict(self):
        x, y, z = self.size
        return {
            'seed': self.seed,
            'size': self.size,
            'entrance': self.entrance_pos,
            'grid': [[[self.grid[i][j][k].to_dict() for k in range(z)] for j in range(y)] for i in range(x)]
        }

    def _post_generation_safety(self):
        try:
            if getattr(self, 'allow_hidden_areas_strict', False):
                return  # strict mode preserves unreachable rooms for manual debugging / secret areas
            vis = self._flood_accessibility(self.grid)
            x, y, _ = self.size
            changed = False
            for ix in range(x):
                for iy in range(y):
                    if self.grid[ix][iy][0].cell_type == 'room' and (ix,iy) not in vis:
                        self.grid[ix][iy][0] = DungeonCell('tunnel'); changed = True
            if changed:
                # Re-run door validation to clean up any orphan doors created by conversions
                self._repair_and_validate_doors(self.grid, carve_probability=0.0, allow_wall_downgrade=True)
                self._collapse_linear_door_runs(self.grid)
        except Exception:
            pass  # Safety function should never break generation

    # ---------------- Consolidation Pass -----------------
    def _final_consolidation_pass(self, grid, room_id_grid):
        """Merge late-generation cleanup into a single traversal sequence.

        Steps:
          1. Accessibility flood: convert unreachable rooms/doors into tunnels.
          2. Enforce room–tunnel separation, collapsing illegal adjacency and promoting valid doors.
          3. Guarantee at least one door per remaining room.
          4. Connectivity validation & repair (dynamic); may drop still unreachable rooms (metrics tracked).
          5. Eliminate any residual tunnel-room adjacency introduced by repair.
          6. Collapse linear door runs and validate doors (single final sweep).
        This reduces redundant multi-pass operations previously executed in sequence.
        """
        x, y, _ = self.size
        # (1) Initial accessibility snapshot (do not immediately downgrade rooms; allow repair to act first)
        initial_accessible = self._flood_accessibility(grid)
        # (2) Separation
        self._enforce_room_tunnel_separation(grid)
        # (3) Door guarantee
        self._guarantee_room_doors(grid, room_id_grid)
        # (4) Connectivity (with fallback + metrics) operates on current structure
        self._validate_and_repair_connectivity(grid, room_id_grid)
        # (5) Residual adjacency purge
        self._eliminate_tunnel_room_adjacency(grid)
        # Post-purge + post-repair accessibility sweep: convert any remaining unreachable rooms (unless hidden areas permitted)
        if not self.allow_hidden_areas:
            visited2 = self._flood_accessibility(grid)
            for ix in range(x):
                for iy in range(y):
                    if grid[ix][iy][0].cell_type == 'room' and (ix,iy) not in visited2:
                        grid[ix][iy][0] = DungeonCell('tunnel')
        # (6) Final door normalization & chain collapse
        self._repair_and_validate_doors(grid, carve_probability=0.0, allow_wall_downgrade=True)
        self._collapse_linear_door_runs(grid)
