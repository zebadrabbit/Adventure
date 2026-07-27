"""Shared tile utility helpers for dungeon API and movement helpers.

Isolated to avoid circular imports between `dungeon_api` and helper modules.
"""

from app.dungeon import DOOR, LOCKED_DOOR, ROOM, SECRET_DOOR, STAIRS_DOWN, STAIRS_UP, TELEPORT, TUNNEL, WALL


def char_to_type(ch: str) -> str:
    if ch == STAIRS_UP:
        return "stairs_up"
    if ch == STAIRS_DOWN:
        return "stairs_down"
    if ch == ROOM:
        return "room"
    if ch == TUNNEL:
        return "tunnel"
    if ch == DOOR:
        return "door"
    if ch == WALL:
        return "wall"
    if ch == SECRET_DOOR:
        return "secret_door"
    if ch == LOCKED_DOOR:
        return "locked_door"
    if ch == TELEPORT or ch == "P":
        return "teleporter"
    return "cave"
