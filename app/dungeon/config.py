from dataclasses import dataclass
from typing import Optional


@dataclass
class DungeonConfig:
    width: int = 75
    height: int = 75
    min_rooms: int = 8
    max_rooms: int = 14
    min_size: int = 5
    max_size: int = 12
    irregular_chance: float = 0.25
    seed: Optional[int] = None
    extra_connection_chance: float = 0.15


__all__ = ["DungeonConfig"]
