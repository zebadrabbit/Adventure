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
from app.models.dungeon_instance import DungeonInstance

WALKABLE_EXTRA = {"P"}  # Portal char


def effective_unlocked_doors(instance: DungeonInstance, dungeon) -> set:
    """Doors passable for this party: individually unlocked ones, plus the
    loot room's sealed doors once the final boss is down (extraction)."""
    unlocked = instance.get_unlocked_doors()
    if getattr(instance, "extraction_available", False):
        unlocked = unlocked | getattr(dungeon, "loot_room_doors", set())
    return unlocked


def normalize_position(dungeon, instance: DungeonInstance, map_size: int) -> tuple[int, int, int]:
    """Ensure the player's position is valid & connected; relocate to entrance if needed.

    Returns (x,y,z) after potential relocation. Commits DB if changed.
    """
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    entrance = None
    if getattr(dungeon, "rooms", None):
        try:
            ex, ey = dungeon.entry_point
            entrance = (ex, ey, z)
        except Exception:
            entrance = None

    unlocked_doors = effective_unlocked_doors(instance, dungeon)

    def _is_walkable(px, py):
        return dungeon.is_walkable(px, py, unlocked_doors)

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
    unlocked_doors = effective_unlocked_doors(instance, dungeon)
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    x, y = instance.pos_x, instance.pos_y
    moved = False
    if direction in deltas:
        dx, dy = deltas[direction]
        nx, ny = x + dx, y + dy
        if dungeon.is_walkable(nx, ny, unlocked_doors):
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


def describe_cell_and_exits(dungeon, instance: DungeonInstance, x: int, y: int, map_size: int) -> tuple[str, List[str]]:
    """Return (description, exits_list) for current coordinates."""
    unlocked_doors = effective_unlocked_doors(instance, dungeon)
    tile_char = dungeon.grid[x][y]
    from app.dungeon.api_helpers.tiles import char_to_type

    desc = f"You are in a {char_to_type(tile_char)}."
    deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
    exits_map: List[str] = []
    for d, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if dungeon.is_walkable(nx, ny, unlocked_doors):
            exits_map.append(d)
    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        exits_words = [cardinal_full[e] for e in exits_map]
        if exits_words:
            desc += " Exits: " + ", ".join(w.capitalize() for w in exits_words) + "."
    return desc, exits_map


# _char_to_type moved to tiles.char_to_type; legacy import removed to avoid circular dependency
