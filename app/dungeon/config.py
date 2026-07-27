from dataclasses import dataclass
from typing import Optional


@dataclass
class DungeonConfig:
    width: int = 75
    height: int = 75
    min_rooms: int = 10
    max_rooms: int = 26
    min_size: int = 5
    max_size: int = 11
    seed: Optional[int] = None
    # chance to open an extra (loop) connector between already-joined regions
    extra_connection_chance: float = 0.04
    # maze carving: hard cap on straight corridor runs (tiles) and how much of
    # each dead-end branch survives culling
    straight_max: int = 10
    dead_end_keep: float = 0.1
    # multi-floor: which floor this grid is (0-based) and how many the dungeon has
    floor: int = 0
    num_floors: int = 1
    # legacy knobs (pre rooms-and-mazes generator); accepted but unused
    irregular_chance: float = 0.0
    blob_room_chance: float = 0.0


__all__ = ["DungeonConfig"]
