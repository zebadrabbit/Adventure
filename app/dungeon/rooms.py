import random
from dataclasses import dataclass
from typing import List, Tuple
from .tiles import CAVE, ROOM
from .config import DungeonConfig

@dataclass
class Room:
    x: int
    y: int
    w: int
    h: int
    def cells(self):
        for ix in range(self.x, self.x + self.w):
            for iy in range(self.y, self.y + self.h):
                yield ix, iy
    @property
    def center(self) -> Tuple[int,int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


def place_rooms(grid, config: DungeonConfig):
    """Place non-overlapping rooms onto the grid.

    Returns (rooms, target_attempted, placed_count).
    Mirrors previous in-class logic to preserve behavior.
    """
    target = random.randint(config.min_rooms, config.max_rooms)
    attempts = target * 15
    placed = 0
    rooms: List[Room] = []
    while placed < target and attempts > 0:
        attempts -= 1
        w = random.randint(config.min_size, config.max_size)
        h = random.randint(config.min_size, config.max_size)
        x = random.randint(1, config.width - w - 2)
        y = random.randint(1, config.height - h - 2)
        new_room = Room(x, y, w, h)
        if _room_overlaps(new_room, rooms):
            continue
        if random.random() < config.irregular_chance:
            _perturb_room(new_room, grid)
        # carve interior
        for (ix, iy) in new_room.cells():
            grid[ix][iy] = ROOM
        rooms.append(new_room)
        placed += 1
    return rooms, target, placed


def _room_overlaps(room: Room, existing: List[Room]) -> bool:
    pad = 2  # ensure space for wall ring (1) and a gap
    for r in existing:
        if (room.x - pad < r.x + r.w and room.x + room.w + pad > r.x and
            room.y - pad < r.y + r.h and room.y + room.h + pad > r.y):
            return True
    return False


def _perturb_room(room: Room, grid):
    interior = [(ix, iy) for ix, iy in room.cells()]
    perimeter = [c for c in interior if (c[0] in (room.x, room.x + room.w - 1) or c[1] in (room.y, room.y + room.h - 1))]
    removable = [c for c in perimeter if c not in ((room.x, room.y), (room.x + room.w - 1, room.y), (room.x, room.y + room.h - 1), (room.x + room.w - 1, room.y + room.h - 1))]
    random.shuffle(removable)
    remove_count = max(0, int(len(removable) * 0.1))
    for i in range(remove_count):
        rx, ry = removable[i]
        grid[rx][ry] = CAVE
