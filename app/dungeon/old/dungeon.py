import random
from typing import List, Tuple, Dict, Any
from .tiles import CAVE, ROOM, WALL, TUNNEL, DOOR
from .config import DungeonConfig
from .rooms import Room, place_rooms
from .tunnels import connect_rooms_with_tunnels


class Dungeon:
    def __init__(self, config: DungeonConfig | None = None, *, seed: int | None = None, size: Tuple[int,int,int] | None = None, **legacy):
        """Dungeon generator.

        Preferred usage:
            Dungeon(DungeonConfig(...))

        Legacy supported usage (for existing route/tests):
            Dungeon(seed=1234, size=(width,height,depth))

        Depth is ignored (always 1) in the simplified generator.
        Additional unused legacy kwargs are accepted & ignored to avoid breaking callers.
        """
        if config is None:
            # Map legacy args to DungeonConfig
            width = 75; height = 75
            if size is not None and len(size) >= 2:
                width, height = size[0], size[1]
            config = DungeonConfig(width=width, height=height, seed=seed)
        else:
            # If both provided, explicit config wins; optionally override seed if given
            if seed is not None:
                config.seed = seed
        self.config = config
        if self.config.seed is None:
            self.config.seed = random.randint(1, 1_000_000)
        random.seed(self.config.seed)
        self.grid: List[List[str]] = [[CAVE for _ in range(self.config.height)] for _ in range(self.config.width)]
        self.rooms: List[Room] = []
        self.metrics: Dict[str, Any] = {"seed": self.config.seed}
        self._generate()

    # Public API
    def to_ascii(self) -> str:
        return "\n".join("".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height))

    def to_json(self) -> Dict[str, Any]:
        return {
            "seed": self.config.seed,
            "width": self.config.width,
            "height": self.config.height,
            "grid": ["".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)],
            "metrics": self.metrics,
        }

    # Generation steps
    def _generate(self):
        self._place_rooms()
        self._build_wall_rings()
        self._connect_rooms_with_tunnels()
        self._validate()
        self._collect_metrics()

    def _place_rooms(self):
        rooms, target, placed = place_rooms(self.grid, self.config)
        self.rooms.extend(rooms)
        self.metrics['rooms_attempted'] = target
        self.metrics['rooms_placed'] = placed

    def _build_wall_rings(self):
        w = self.config.width; h = self.config.height
        for r in self.rooms:
            for ix in range(r.x - 1, r.x + r.w + 1):
                for iy in range(r.y - 1, r.y + r.h + 1):
                    if 0 <= ix < w and 0 <= iy < h:
                        # If it's already room skip; else if adjacent (4-way) to a room interior, mark wall.
                        if self.grid[ix][iy] == ROOM:
                            continue
                        # Check if any orthogonal neighbor is room
                        if any(0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == ROOM for nx, ny in ((ix+1,iy),(ix-1,iy),(ix,iy+1),(ix,iy-1))):
                            if self.grid[ix][iy] == CAVE:  # don't overwrite tunnels/doors later
                                self.grid[ix][iy] = WALL

    def _connect_rooms_with_tunnels(self):
        connect_rooms_with_tunnels(self.grid, self.rooms, self.config)

    def _validate(self):
        # Connectivity: BFS from first room interior through R/T/D should reach all room interiors
        if not self.rooms:
            return
        from collections import deque
        start = self.rooms[0].center
        q=deque([start]); seen={start}
        walkable={ROOM,TUNNEL,DOOR}
        while q:
            cx,cy=q.popleft()
            for nx,ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                if 0<=nx<self.config.width and 0<=ny<self.config.height and (nx,ny) not in seen and self.grid[nx][ny] in walkable:
                    seen.add((nx,ny)); q.append((nx,ny))
        unreachable=0
        for r in self.rooms:
            if all((ix,iy) not in seen for ix,iy in r.cells()):
                unreachable+=1
        self.metrics['unreachable_rooms']=unreachable
        # Wall thickness: each wall must border at least one room and not have another outward wall layer with no room adjacency
        bad=0
        for x in range(self.config.width):
            for y in range(self.config.height):
                if self.grid[x][y]==WALL:
                    if not any(0<=nx<self.config.width and 0<=ny<self.config.height and self.grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
                        bad+=1
        self.metrics['wall_anomalies']=bad

    def _collect_metrics(self):
        counts={CAVE:0, ROOM:0, WALL:0, TUNNEL:0, DOOR:0}
        for x in range(self.config.width):
            for y in range(self.config.height):
                t=self.grid[x][y]
                counts[t]=counts.get(t,0)+1
        self.metrics.update({
            'rooms': len(self.rooms),
            'tiles_cave': counts[CAVE],
            'tiles_room': counts[ROOM],
            'tiles_wall': counts[WALL],
            'tiles_tunnel': counts[TUNNEL],
            'tiles_door': counts[DOOR],
        })

if __name__ == '__main__':
    d = Dungeon(DungeonConfig(seed=1234))
    print(d.to_ascii())
    print(d.metrics)
