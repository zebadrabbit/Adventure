"""Public dungeon package interface.

Backward-compatible import surface plus new door variants & helper constants.
"""

from .dungeon import (
    Dungeon,
    DungeonConfig,
    CAVE,
    ROOM,
    WALL,
    TUNNEL,
    DOOR,
    SECRET_DOOR,
    LOCKED_DOOR,
    TELEPORT,
)  # noqa: F401

__all__ = [
    "Dungeon",
    "DungeonConfig",
    "CAVE",
    "ROOM",
    "WALL",
    "TUNNEL",
    "DOOR",
    "SECRET_DOOR",
    "LOCKED_DOOR",
    "TELEPORT",
]
