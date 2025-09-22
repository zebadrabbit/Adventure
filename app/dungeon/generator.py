"""Core structural generation phases: grid init, BSP partitioning, room placement, corridor graph & carving."""
from __future__ import annotations
import random
from typing import List, NamedTuple, Tuple
from .cells import DungeonCell, Grid3D, Size3D

class Rect(NamedTuple):
    x: int; y: int; w: int; h: int

class StructuralOutputs(NamedTuple):
    grid: Grid3D
    rooms: List[Rect]
    room_id_grid: List[List[int]]
    centers: List[Tuple[int,int]]
    corridors: List[Tuple[int,int]]

class Generator:
    def __init__(self, size: Size3D, seed: int):
        self.size = size
        self.seed = seed

    def init_grid(self) -> Grid3D:
        x,y,z = self.size
        return [[[DungeonCell('cave') for _ in range(z)] for _ in range(y)] for _ in range(x)]

    def bsp_partition(self) -> List[Rect]:
        random.seed(self.seed)
        x, y, _ = self.size
        leaves = [Rect(1,1,x-2,y-2)]
        bsp_min_leaf = 18
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
            changed=False
            new=[]
            for r in leaves:
                parts = split_rect(r)
                if len(parts)==2: changed=True
                new.extend(parts)
            leaves=new
        return leaves

    def place_rooms(self, grid, leaves: List[Rect]):
        x,y,_=self.size
        min_room,max_room = 5,12
        rooms=[]; room_tiles_sets=[]
        room_id_grid=[[ -1 for _ in range(y)] for _ in range(x)]
        for L in leaves:
            if L.w < 3 or L.h < 3: continue
            rw = random.randint(min_room, min(max_room, max(3, L.w - 2)))
            rh = random.randint(min_room, min(max_room, max(3, L.h - 2)))
            rx = random.randint(L.x + 1, max(L.x + 1, L.x + L.w - rw - 1)) if (L.w - rw - 2) >= 0 else L.x + 1
            ry = random.randint(L.y + 1, max(L.y + 1, L.y + L.h - rh - 1)) if (L.h - rh - 2) >= 0 else L.y + 1
            room = Rect(rx, ry, rw, rh); rooms.append(room)
            tiles=set()
            for yy in range(ry, ry+rh):
                for xx in range(rx, rx+rw):
                    if 0 <= xx < x and 0 <= yy < y:
                        grid[xx][yy][0] = DungeonCell('room'); tiles.add((xx,yy)); room_id_grid[xx][yy]=len(rooms)-1
            room_tiles_sets.append(tiles)
        # Surround with walls
        for tiles in room_tiles_sets:
            for (tx,ty) in tiles:
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    wx,wy=tx+dx,ty+dy
                    if 0 <= wx < x and 0 <= wy < y and grid[wx][wy][0].cell_type=='cave':
                        grid[wx][wy][0]=DungeonCell('wall')
        return rooms, room_id_grid

    def build_room_graph(self, rooms: List[Rect]):
        centers=[(r.x + r.w//2, r.y + r.h//2) for r in rooms]
        k=4; edges=[]
        for i,(cx1,cy1) in enumerate(centers):
            dists=[]
            for j,(cx2,cy2) in enumerate(centers):
                if i==j: continue
                d=abs(cx1-cx2)+abs(cy1-cy2)
                dists.append((d,i,j))
            for d,a,b in sorted(dists)[:k]: edges.append((d,a,b))
        parent=list(range(len(rooms)))
        def find(a):
            while parent[a]!=a:
                parent[a]=parent[parent[a]]; a=parent[a]
            return a
        def union(a,b):
            ra,rb=find(a),find(b)
            if ra!=rb: parent[rb]=ra; return True
            return False
        mst=[]
        for d,a,b in sorted(edges, key=lambda e:e[0]):
            if union(a,b): mst.append((a,b))
        corridors=mst[:]; seen_pairs=set((min(a,b),max(a,b)) for a,b in mst)
        loop_chance=0.12
        for _d,a,b in edges:
            key=(min(a,b),max(a,b))
            if key not in seen_pairs and random.random()<loop_chance:
                corridors.append((a,b)); seen_pairs.add(key)
        return centers, corridors

    def carve_corridors(self, grid, centers, corridors, room_id_grid):
        x,y,_=self.size
        def carve_cell(cx,cy,door_flags,endpoints):
            if not (0 <= cx < x and 0 <= cy < y): return
            current=grid[cx][cy][0].cell_type
            if current=='room': return
            if current=='wall':
                adjacent_room_ids=[]
                for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx,ny=cx+dx,cy+dy
                    if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                        rid=room_id_grid[nx][ny]
                        if rid not in adjacent_room_ids: adjacent_room_ids.append(rid)
                if len(adjacent_room_ids)==1:
                    rid=adjacent_room_ids[0]
                    if rid in endpoints and not door_flags.get(rid, False):
                        grid[cx][cy][0]=DungeonCell('door'); door_flags[rid]=True; return
                    grid[cx][cy][0]=DungeonCell('tunnel'); return
                else:
                    grid[cx][cy][0]=DungeonCell('tunnel'); return
            if current=='cave': grid[cx][cy][0]=DungeonCell('tunnel')
        def carve_line(x1,y1,x2,y2,door_flags,endpoints):
            dx = 1 if x2 >= x1 else -1
            dy = 1 if y2 >= y1 else -1
            if x1==x2:
                for yy in range(y1, y2+dy, dy): carve_cell(x1,yy,door_flags,endpoints)
            elif y1==y2:
                for xx in range(x1, x2+dx, dx): carve_cell(xx,y1,door_flags,endpoints)
        def enforce_endpoint_door(room_index, center, door_flags):
            if door_flags.get(room_index, False): return
            cx,cy=center; max_radius=30
            for r_step in range(1, max_radius+1):
                for dx,dy in [(0,1),(1,0),(0,-1),(-1,0)]:
                    wx,wy=cx+dx*r_step, cy+dy*r_step
                    if not (0 <= wx < x and 0 <= wy < y): continue
                    if grid[wx][wy][0].cell_type=='wall':
                        adj_room_ids=set()
                        for ax,ay in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nx,ny=wx+ax,wy+ay
                            if 0 <= nx < x and 0 <= ny < y and grid[nx][ny][0].cell_type=='room':
                                adj_room_ids.add(room_id_grid[nx][ny])
                        if len(adj_room_ids)==1 and room_index in adj_room_ids:
                            grid[wx][wy][0]=DungeonCell('door'); door_flags[room_index]=True; return
        def carve_irregular(a,b,door_flags,endpoints):
            (sx,sy)=centers[a]; (tx,ty)=centers[b]
            cx,cy=sx,sy; steps=0; max_steps=(abs(tx-sx)+abs(ty-sy))*3
            while (cx,cy)!=(tx,ty) and steps<max_steps:
                steps+=1; options=[]
                if cx<tx: options.append((1,0))
                if cx>tx: options.append((-1,0))
                if cy<ty: options.append((0,1))
                if cy>ty: options.append((0,-1))
                if random.random()<0.35: options.extend([(1,0),(-1,0),(0,1),(0,-1)])
                if not options: break
                dx,dy=random.choice(options); nx,ny=cx+dx,cy+dy
                carve_cell(nx,ny,door_flags,endpoints); cx,cy=nx,ny
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

    def run(self) -> StructuralOutputs:
        grid = self.init_grid()
        leaves = self.bsp_partition()
        rooms, room_id_grid = self.place_rooms(grid, leaves)
        centers, corridors = self.build_room_graph(rooms)
        self.carve_corridors(grid, centers, corridors, room_id_grid)
        return StructuralOutputs(grid, rooms, room_id_grid, centers, corridors)
