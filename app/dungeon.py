"""
project: Adventure MUD
module: dungeon.py
https://github.com/zebadrabbit/Adventure
License: MIT

Procedural dungeon generator and grid logic for Adventure MUD.
"""

import random
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
        self.grid = self._generate_dungeon()

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
                if 'entrance' in grid[i][j][0].features:
                    entrance_tile=(i,j); break
            if entrance_tile: break
        visited=set();
        if entrance_tile:
            q=deque([entrance_tile]); visited.add(entrance_tile)
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
        # Rule refinement (2025-09-21): We want strict separation so that a room is only
        # accessible via explicit door cells, BUT we allow an exception where multiple
        # distinct tunnels may legitimately connect to different sides of (or points on)
        # the same room. Instead of sealing every tunnel cell adjacent to a room into a
        # wall (original behavior), we now promote qualifying tunnel endpoints into doors.
        # Qualifying tunnel endpoint criteria:
        #   - Cell type is 'tunnel'.
        #   - Adjacent to exactly one room cell (prevents ambiguous multi-room joins).
        #   - Has at least one other neighboring tunnel/door so it is part of a corridor.
        # Otherwise the tunnel cell is converted to a wall to preserve visual separation.
        for ix in range(x):
            for iy in range(y):
                if grid[ix][iy][0].cell_type != 'tunnel':
                    continue
                room_neighbors = 0
                tunnel_link = False
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = ix+dx, iy+dy
                    if 0 <= nx < x and 0 <= ny < y:
                        ct = grid[nx][ny][0].cell_type
                        if ct == 'room':
                            room_neighbors += 1
                        elif ct in {'tunnel','door'}:
                            tunnel_link = True
                if room_neighbors == 1 and tunnel_link:
                    # Promote to door (allows multiple doors if multiple corridors terminate here)
                    grid[ix][iy][0] = DungeonCell('door')
                elif room_neighbors > 0:
                    # Adjacent to room(s) but not a proper corridor endpoint -> seal
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
                    else:
                        grid[ix][iy][0] = DungeonCell('wall') if room_neighbors > 1 else DungeonCell('tunnel')
                    continue
                # Lacks walkable non-room side
                if not has_walk:
                    if carve_candidate and random.random() < carve_probability:
                        grid[carve_candidate[0]][carve_candidate[1]][0] = DungeonCell('tunnel')
                    else:
                        # Degrade: door to wall (keeps separation) or tunnel (if wall not allowed)
                        grid[ix][iy][0] = DungeonCell('wall') if allow_wall_downgrade else DungeonCell('tunnel')

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

    def _run_generation_pipeline(self):
        grid = self._init_grid()
        leaves, Rect = self._bsp_partition(grid)
        rooms, room_id_grid = self._place_rooms(grid, leaves, Rect)
        centers, corridors = self._build_room_graph(rooms)
        self._carve_corridors(grid, centers, corridors, room_id_grid)
        self._normalize_doors_and_clean(grid, room_id_grid)
        self._assign_features(grid, rooms)
        # Accessibility + conversion of unreachable rooms -> tunnels
        visited = self._flood_accessibility(grid)
        x, y, _ = self.size
        for i in range(x):
            for j in range(y):
                if grid[i][j][0].cell_type in {'room','door'} and (i,j) not in visited:
                    grid[i][j][0] = DungeonCell('tunnel')
        self._enforce_room_tunnel_separation(grid)
        self._guarantee_room_doors(grid, room_id_grid)
        # Connectivity repair may reintroduce adjacency; run after capture of initial door guarantees
        room_tiles_by_id_initial={}
        for rx in range(x):
            for ry in range(y):
                if grid[rx][ry][0].cell_type=='room':
                    rid=room_id_grid[rx][ry]
                    if rid>=0: room_tiles_by_id_initial.setdefault(rid, []).append((rx,ry))
        self._connectivity_repair(grid, room_id_grid, room_tiles_by_id_initial)
        self._final_separation_and_door_pass(grid, room_id_grid)
        return grid
        random.seed(self.seed)
        x, y, z = self.size
        # Initialize all as cave
        grid = [[[DungeonCell('cave') for _ in range(z)] for _ in range(y)] for _ in range(x)]

        # ---------------- BSP Partitioning -----------------
        from collections import namedtuple
        Rect = namedtuple("Rect", "x y w h")
        bsp_min_leaf = 18
        leaves = [Rect(1, 1, x-2, y-2)]

        def split_rect(r: Rect):
            # Decide split orientation by aspect (slight randomness)
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

        # ---------------- Place Rooms -----------------
        min_room, max_room = 5, 12
        rooms: List[Rect] = []
        room_tiles_sets: List[set] = []
        # Track room id for each tile (-1 for non-room) to assist in controlled door placement
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
                        room_id_grid[xx][yy] = len(rooms) - 1  # zero-based room id
            room_tiles_sets.append(tiles)
        # build walls around rooms
        for tiles in room_tiles_sets:
            for (tx, ty) in tiles:
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx, wy = tx+dx, ty+dy
                    if 0 <= wx < x and 0 <= wy < y and grid[wx][wy][0].cell_type == 'cave':
                        grid[wx][wy][0] = DungeonCell('wall')

        # ---------------- Graph Creation (k nearest) -----------------
        centers = [(r.x + r.w//2, r.y + r.h//2) for r in rooms]
        edges = []
        k = 4
        for i, (cx1, cy1) in enumerate(centers):
            dists = []
            for j, (cx2, cy2) in enumerate(centers):
                if i == j:
                    continue
                d = abs(cx1 - cx2) + abs(cy1 - cy2)
                dists.append((d, i, j))
            for d, a, b in sorted(dists)[:k]:
                edges.append((d, a, b))

        # ---------------- Kruskal MST -----------------
        parent = list(range(len(rooms)))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
                return True
            return False

        mst = []
        for d, a, b in sorted(edges, key=lambda e: e[0]):
            if union(a, b):
                mst.append((a, b))

        # extra loops
        loop_chance = 0.12
        corridors = mst[:]
        seen_pairs = set((min(a,b), max(a,b)) for a,b in mst)
        for _d, a, b in edges:
            key = (min(a,b), max(a,b))
            if key not in seen_pairs and random.random() < loop_chance:
                corridors.append((a, b))
                seen_pairs.add(key)

        # ---------------- Corridor Carving -----------------
        def carve_line(x1, y1, x2, y2, door_flags, endpoints):
            dx = 1 if x2 >= x1 else -1
            dy = 1 if y2 >= y1 else -1
            if x1 == x2:
                for yy in range(y1, y2 + dy, dy):
                    carve_cell(x1, yy, door_flags, endpoints)
            elif y1 == y2:
                for xx in range(x1, x2 + dx, dx):
                    carve_cell(xx, y1, door_flags, endpoints)

        def carve_cell(cx, cy, door_flags, endpoints):
            if not (0 <= cx < x and 0 <= cy < y):
                return
            current = grid[cx][cy][0].cell_type
            if current == 'room':
                return  # do not overwrite rooms
            if current == 'wall':
                # Potential doorway if adjacent to exactly one room
                adjacent_room_ids = []
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                        rid = room_id_grid[nx][ny]
                        if rid not in adjacent_room_ids:
                            adjacent_room_ids.append(rid)
                if len(adjacent_room_ids) == 1:
                    rid = adjacent_room_ids[0]
                    # endpoints are the two room indices this corridor aims to connect.
                    if rid in endpoints and not door_flags.get(rid, False):
                        grid[cx][cy][0] = DungeonCell('door')
                        door_flags[rid] = True
                        return
                    # Otherwise carve as tunnel to continue path but do not create extra doors
                    grid[cx][cy][0] = DungeonCell('tunnel')
                    return
                else:
                    # Multiple room adjacencies (corner) or none -> just carve tunnel for connectivity
                    grid[cx][cy][0] = DungeonCell('tunnel')
                    return
            if current == 'cave':
                grid[cx][cy][0] = DungeonCell('tunnel')

        def enforce_endpoint_door(room_index, center, door_flags):
            """If a door was not placed for this endpoint room, promote the closest wall tile along straight line to a door."""
            if door_flags.get(room_index, False):
                return
            cx, cy = center
            # radial search outward (Manhattan radius) until hitting a wall adjacent to the room interior
            max_radius = 30  # safety bound
            for r_step in range(1, max_radius+1):
                for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]:
                    wx, wy = cx + dx * r_step, cy + dy * r_step
                    if not (0 <= wx < x and 0 <= wy < y):
                        continue
                    if grid[wx][wy][0].cell_type == 'wall':
                        # verify adjacent unique room id equals this room_index
                        adj_room_ids = set()
                        for ax, ay in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nx, ny = wx+ax, wy+ay
                            if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type == 'room':
                                adj_room_ids.add(room_id_grid[nx][ny])
                        if len(adj_room_ids) == 1 and room_index in adj_room_ids:
                            # place door
                            grid[wx][wy][0] = DungeonCell('door')
                            door_flags[room_index] = True
                            return

        def carve_irregular(a, b, door_flags, endpoints):
            (sx, sy) = centers[a]
            (tx, ty) = centers[b]
            cx, cy = sx, sy
            steps = 0
            max_steps = (abs(tx - sx) + abs(ty - sy)) * 3  # allow wander
            while (cx, cy) != (tx, ty) and steps < max_steps:
                steps += 1
                # Bias toward target but add jitter
                options = []
                if cx < tx: options.append((1,0))
                if cx > tx: options.append((-1,0))
                if cy < ty: options.append((0,1))
                if cy > ty: options.append((0,-1))
                # add lateral noise
                if random.random() < 0.35:
                    options.extend([(1,0),(-1,0),(0,1),(0,-1)])
                if not options:
                    break
                dx, dy = random.choice(options)
                nx, ny = cx + dx, cy + dy
                carve_cell(nx, ny, door_flags, endpoints)
                cx, cy = nx, ny
            # finalize by direct straight segments if not arrived
            if cx != tx:
                carve_line(cx, cy, tx, cy, door_flags, endpoints)
            if cy != ty:
                carve_line(tx, cy, tx, ty, door_flags, endpoints)

        def carve_corridor(a, b):
            (x1c, y1c) = centers[a]
            (x2c, y2c) = centers[b]
            door_flags = {a: False, b: False}
            endpoints = {a, b}
            # Choose between classic L and irregular path
            style_rand = random.random()
            if style_rand < 0.55:
                if random.random() < 0.5:
                    carve_line(x1c, y1c, x2c, y1c, door_flags, endpoints)
                    carve_line(x2c, y1c, x2c, y2c, door_flags, endpoints)
                else:
                    carve_line(x1c, y1c, x1c, y2c, door_flags, endpoints)
                    carve_line(x1c, y2c, x2c, y2c, door_flags, endpoints)
            else:
                carve_irregular(a, b, door_flags, endpoints)
            # Enforce exactly one door per endpoint room if not already placed (Option A logic)
            enforce_endpoint_door(a, centers[a], door_flags)
            enforce_endpoint_door(b, centers[b], door_flags)

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
