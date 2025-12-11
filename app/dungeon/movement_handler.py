"""Shared dungeon movement logic for both REST and WebSocket handlers.

This module consolidates the movement, encounter, and perception logic
that was previously duplicated between dungeon_api.py and websockets/game.py.
"""

import json as _json
from typing import Any, Dict, Tuple

from flask_login import current_user

from app import db
from app.dungeon.api_helpers.encounters import maybe_spawn_encounter
from app.dungeon.api_helpers.perception import (
    get_noticed_coords as _get_noticed_coords_helper,
)
from app.dungeon.api_helpers.perception import (
    maybe_perceive_and_mark_loot,
)
from app.dungeon.tiles import DOOR, ROOM, TUNNEL
from app.logging_utils import get_logger
from app.models.dungeon_instance import DungeonInstance
from app.models.entities import DungeonEntity

logger = get_logger(__name__)


def get_cached_dungeon(seed: int, size_tuple: tuple[int, int, int]):
    """Import and delegate to the actual implementation in dungeon_api."""
    from app.routes.dungeon_api import get_cached_dungeon as _get_cached

    return _get_cached(seed, size_tuple)


def char_to_type(c: str) -> str:
    """Convert grid character to room type description."""
    if c == ROOM:
        return "room"
    if c == TUNNEL:
        return "tunnel"
    if c == DOOR:
        return "doorway"
    if c in ("P", "T"):
        return "teleporter"
    return "area"


def process_movement(instance: DungeonInstance, direction: str) -> Tuple[bool, Dict[str, Any]]:
    """Process a movement attempt and return (moved, response_dict).

    Args:
        instance: The dungeon instance
        direction: Movement direction ('n', 's', 'e', 'w') or '' for noop

    Returns:
        Tuple of (moved: bool, response: dict) where response contains:
        - ok: bool
        - moved: bool
        - pos: [x, y, z]
        - desc: str
        - exits: list of directions
        - noticed_loot: bool
        - combat_started: bool (if encounter triggered)
        - combat_id: int (if encounter triggered)
        - encounter: dict (if encounter triggered)
        - game_tick: int (if time advanced)
    """
    MAP_SIZE = 75
    dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
    walkable_chars = {ROOM, TUNNEL, DOOR, getattr(dungeon, "TELEPORT", "P"), "P"}

    # Determine if this is a no-op
    noop = direction == "" or direction not in ("n", "s", "e", "w")

    # Attempt movement
    moved = False
    if not noop:
        deltas = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}
        dx, dy = deltas[direction]
        nx, ny = instance.pos_x + dx, instance.pos_y + dy

        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and dungeon.grid[nx][ny] in walkable_chars:
            instance.pos_x, instance.pos_y = nx, ny
            moved = True
        else:
            # Fallback: try other directions
            for alt in ["n", "e", "s", "w"]:
                if alt == direction:
                    continue
                adx, ady = deltas[alt]
                tx, ty = instance.pos_x + adx, instance.pos_y + ady
                if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and dungeon.grid[tx][ty] in walkable_chars:
                    instance.pos_x, instance.pos_y = tx, ty
                    moved = True
                    break

        if moved:
            try:
                db.session.commit()
            except Exception as e:
                logger.error(event="movement_commit_failed", user_id=current_user.id, error=str(e))
                db.session.rollback()
                moved = False

    # Check for collision-based encounter (monster entity on tile)
    combat_started = False
    combat_id = None
    encounter_payload = None

    if moved:
        try:
            monster_ent = DungeonEntity.query.filter_by(
                instance_id=instance.id,
                type="monster",
                x=instance.pos_x,
                y=instance.pos_y,
                z=instance.pos_z,
            ).first()

            if monster_ent:
                mdata = {}
                try:
                    if monster_ent.data:
                        mdata = _json.loads(monster_ent.data)
                except Exception:
                    mdata = {}

                monster_payload = {
                    "slug": monster_ent.slug,
                    "name": monster_ent.name or monster_ent.slug,
                    "hp": monster_ent.hp_current or mdata.get("hp", 30),
                    "damage": mdata.get("damage", 6),
                    "speed": mdata.get("speed", 10),
                }

                from app.services import combat_service

                session_row = combat_service.start_session(current_user.id, monster_payload)
                combat_id = session_row.id
                combat_started = True
                encounter_payload = {"monster": monster_payload, "combat_id": combat_id}

                try:
                    db.session.delete(monster_ent)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            logger.error(event="monster_collision_error", error=str(e))

    # Roll for random encounter if no collision encounter
    encounter_debug = {}
    if (moved or not noop) and not combat_started:
        maybe_spawn_encounter(instance, bool(moved or not noop), resp := {})
        if "encounter" in resp:
            combat_started = True
            combat_id = resp["encounter"].get("combat_id")
            encounter_payload = resp["encounter"]
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
        else:
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]

    # Get current position and build description
    x, y, z = instance.pos_x, instance.pos_y, instance.pos_z
    tile_char = dungeon.grid[x][y]
    desc = f"You are in a {char_to_type(tile_char)}."

    # Find exits
    exits_map = []
    for d, (dx2, dy2) in {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}.items():
        tx, ty = x + dx2, y + dy2
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and dungeon.grid[tx][ty] in walkable_chars:
            exits_map.append(d)

    if exits_map:
        cardinal_full = {"n": "north", "s": "south", "e": "east", "w": "west"}
        desc += " Exits: " + ", ".join(cardinal_full[e].capitalize() for e in exits_map) + "."

    # Automatic perception check when entering a tile
    noticed_flag = False
    perception_msg = None

    if moved:
        try:
            noticed, msg, roll_info = maybe_perceive_and_mark_loot(instance, x, y)
            if noticed:
                noticed_flag = True
                perception_msg = msg
            elif msg:
                perception_msg = msg
        except Exception as e:
            logger.error(event="perception_error", x=x, y=y, error=str(e))

    # Also check previously noticed coords
    if not noticed_flag:
        try:
            coords_tmp = _get_noticed_coords_helper(instance)
            for cx, cy in coords_tmp:
                if cx == x and cy == y:
                    noticed_flag = True
                    if not perception_msg:
                        perception_msg = "You recall a suspicious spot here."
                    break
        except Exception:
            pass

    # Add perception message to description
    if perception_msg:
        desc = (desc + "\n" + perception_msg).strip()

    # Build response
    response = {
        "ok": True,
        "moved": moved,
        "pos": [x, y, z],
        "desc": desc,
        "exits": exits_map,
        "noticed_loot": noticed_flag,
    }

    # Add encounter info if combat started
    if combat_started and combat_id is not None:
        response["combat_started"] = True
        response["combat_id"] = combat_id
        if encounter_payload:
            response["encounter"] = encounter_payload

    # Add debug info if present
    if encounter_debug:
        response.update(encounter_debug)

    # Update explored tiles with visibility calculation
    if moved or not noop:
        try:
            # Import with alias to avoid shadowing the local function
            from app.dungeon.api_helpers.tiles import char_to_type as grid_char_to_type
            from app.dungeon.explored_tiles import update_explored_tiles
            from app.dungeon.visibility import calculate_visible_tiles

            # Calculate what the player can now see
            visible_tiles = calculate_visible_tiles(dungeon.grid, instance.pos_x, instance.pos_y)

            # Update explored tiles in database
            update_explored_tiles(instance.seed, visible_tiles)

            # Return newly visible tiles so client can render them
            # Format: [{x, y, type}, ...]
            new_tiles = []
            for tx, ty in visible_tiles:
                tile_type = grid_char_to_type(dungeon.grid[tx][ty])
                new_tiles.append({"x": tx, "y": ty, "type": tile_type})

            response["revealed_tiles"] = new_tiles
        except Exception as e:
            logger.error(event="visibility_update_error", error=str(e))

    # Advance game time if no combat
    if not combat_started:
        try:
            from app.routes.dungeon_api import advance_non_combat_time

            tick_val = advance_non_combat_time(instance, tick_amount=1)
            if tick_val is not None:
                response["game_tick"] = tick_val
        except Exception as e:
            logger.error(event="time_advance_error", error=str(e))

    return moved, response
