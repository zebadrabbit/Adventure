"""Public dungeon package interface.

Backward-compatible import surface plus new door variants & helper constants.
"""

from .dungeon import (
    Dungeon,
    DungeonConfig,
    floor_seed,
    CAVE,
    ROOM,
    WALL,
    TUNNEL,
    DOOR,
    SECRET_DOOR,
    LOCKED_DOOR,
    TELEPORT,
    STAIRS_UP,
    STAIRS_DOWN,
)  # noqa: F401

__all__ = [
    "Dungeon",
    "DungeonConfig",
    "floor_seed",
    "CAVE",
    "ROOM",
    "WALL",
    "TUNNEL",
    "DOOR",
    "SECRET_DOOR",
    "LOCKED_DOOR",
    "TELEPORT",
    "STAIRS_UP",
    "STAIRS_DOWN",
]
