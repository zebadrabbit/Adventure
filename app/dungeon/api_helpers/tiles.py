"""Shared tile utility helpers for dungeon API and movement helpers.

Isolated to avoid circular imports between `dungeon_api` and helper modules.
"""

from app.dungeon import DOOR, ROOM, TUNNEL, WALL


def char_to_type(ch: str) -> str:
    if ch == ROOM:
        return "room"
    if ch == TUNNEL:
        return "tunnel"
    if ch == DOOR:
        return "door"
    if ch == WALL:
        return "wall"
    return "cave"
