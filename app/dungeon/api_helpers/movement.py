"""Movement-related helper functions extracted from `dungeon_api.py`.

These helpers encapsulate:
- Normalizing player starting position (entrance fallback)
- Computing exits and cell description
- Performing movement with teleport handling

They operate on a dungeon instance (with .grid, .rooms, etc.) and a DungeonInstance ORM row.
"""

from __future__ import annotations

from typing import List

from app import db
from app.dungeon import DOOR, ROOM, TUNNEL
from app.models.dungeon_instance import DungeonInstance

WALKABLE_EXTRA = {"P"}  # Teleport placeholder char


def normalize_position(dungeon, instance: DungeonInstance, map_size: int) -> tuple[int, int, int]:
    """Ensure the player's position is valid & connected; relocate to entrance if needed.

    Returns (x,y,z) after potential relocation. Commits DB if changed.
    """
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    entrance = None
    if getattr(dungeon, "rooms", None):
        try:
            r0 = dungeon.rooms[0]
            entrance = (r0.center[0], r0.center[1], 0)
        except Exception:
            entrance = None

    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), *WALKABLE_EXTRA}

    def _is_walkable(px, py):
        return 0 <= px < map_size and 0 <= py < map_size and dungeon.grid[px][py] in walkable_chars

    if entrance and (not _is_walkable(x, y) or (x, y, z) == (0, 0, 0)):
        x, y, z = entrance
        if (instance.pos_x, instance.pos_y, instance.pos_z) != entrance:
            instance.pos_x, instance.pos_y, instance.pos_z = x, y, z
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    return x, y, z


def attempt_move(dungeon, instance: DungeonInstance, direction: str, map_size: int) -> tuple[int, int, bool]:
    """Attempt to move in direction; returns (x,y,moved). Handles teleport pads."""
    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), *WALKABLE_EXTRA}
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    x, y = instance.pos_x, instance.pos_y
    moved = False
    if direction in deltas:
        dx, dy = deltas[direction]
        nx, ny = x + dx, y + dy
        if 0 <= nx < map_size and 0 <= ny < map_size and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            x, y = nx, ny
            moved = True
            # Teleport pads
            if dungeon.grid[x][y] in ("P", getattr(dungeon, "TELEPORT", "P")):
                tp_lookup = getattr(dungeon, "metrics", {}).get("teleport_lookup") or {}
                dest = tp_lookup.get((x, y))
                if dest:
                    tx, ty = dest
                    instance.pos_x, instance.pos_y = tx, ty
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    x, y = tx, ty
    return x, y, moved


def describe_cell_and_exits(dungeon, x: int, y: int, map_size: int) -> tuple[str, List[str]]:
    """Return (description, exits_list) for current coordinates."""
    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), *WALKABLE_EXTRA}
    tile_char = dungeon.grid[x][y]
    from app.dungeon.api_helpers.tiles import char_to_type

    desc = f"You are in a {char_to_type(tile_char)}."
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    exits_map: List[str] = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if 0 <= nx < map_size and 0 <= ny < map_size and dungeon.grid[nx][ny] in walkable_chars:
            exits_map.append(d)
    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        exits_words = [cardinal_full[e] for e in exits_map]
        if exits_words:
            desc += " Exits: " + ", ".join(w.capitalize() for w in exits_words) + "."
    return desc, exits_map


# _char_to_type moved to tiles.char_to_type; legacy import removed to avoid circular dependency
