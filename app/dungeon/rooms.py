"""Dense odd-aligned room packing for the rooms-and-mazes generator.

Rooms have odd sizes and odd top-left coordinates so a 1-cell wall grid always
separates rooms from each other and from the odd-aligned maze lattice carved
afterwards (see connect.fill_maze).
"""

import random
from dataclasses import dataclass
from typing import List, Tuple

from .config import DungeonConfig
from .tiles import ROOM


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
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


def _odd(rng, lo: int, hi: int) -> int:
    """Random odd int in [lo, hi]; lo must be odd."""
    return rng.randrange(lo, hi + 1, 2)


def place_rooms(grid, config: DungeonConfig, rng=None):
    """Pack non-overlapping odd-aligned rooms onto the grid.

    Returns (rooms, target_attempted, placed_count).
    """
    if rng is None:
        rng = random
    target = config.max_rooms
    attempts = target * 30
    lo = config.min_size | 1
    hi = max(lo, config.max_size if config.max_size % 2 else config.max_size - 1)
    rooms: List[Room] = []
    while len(rooms) < target and attempts > 0:
        attempts -= 1
        w = _odd(rng, lo, hi)
        h = _odd(rng, lo, hi)
        if config.width - w - 1 < 1 or config.height - h - 1 < 1:
            continue
        x = _odd(rng, 1, config.width - w - 1)
        y = _odd(rng, 1, config.height - h - 1)
        new_room = Room(x, y, w, h)
        if _room_overlaps(new_room, rooms):
            continue
        for ix, iy in new_room.cells():
            grid[ix][iy] = ROOM
        rooms.append(new_room)
    return rooms, target, len(rooms)


def _room_overlaps(room: Room, existing: List[Room]) -> bool:
    pad = 1  # one wall cell between rooms
    for r in existing:
        if (
            room.x - pad < r.x + r.w
            and room.x + room.w + pad > r.x
            and room.y - pad < r.y + r.h
            and room.y + room.h + pad > r.y
        ):
            return True
    return False
