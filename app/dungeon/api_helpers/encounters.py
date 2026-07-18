"""Encounter triggering and patrol helpers.

Public functions:
- trigger_collision_combat(instance) -> dict | None (starts combat if a
  monster entity occupies the player's current tile; deletes that
  entity so the finite spawn pool never regenerates)
- run_monster_patrols(dungeon, instance, resp: dict) -> None (moves
  spawns, including proximity-aggro chasing; also calls
  trigger_collision_combat after moving them, writing into resp if a
  chasing monster reached the player)

Design choices:
- Functions swallow exceptions to avoid blocking player movement
"""

from __future__ import annotations

import json

from app import db

__all__ = ["trigger_collision_combat", "run_monster_patrols"]


def trigger_collision_combat(instance) -> dict | None:
    """If a monster entity occupies the player's current tile, start
    combat and permanently remove that entity (finite pool -- it never
    regenerates).

    Used both when the player walks onto a monster
    (movement_handler.process_movement) and when a chasing monster
    reaches the player (run_monster_patrols, below).

    Returns {"monster": <payload dict>, "combat_id": <int>} if combat
    started, else None.
    """
    from app.models.entities import DungeonEntity

    try:
        monster_ent = DungeonEntity.query.filter_by(
            instance_id=instance.id,
            type="monster",
            x=instance.pos_x,
            y=instance.pos_y,
            z=instance.pos_z,
        ).first()
    except Exception:
        return None

    if not monster_ent:
        return None

    mdata = {}
    try:
        if monster_ent.data:
            mdata = json.loads(monster_ent.data)
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

    session_row = combat_service.start_session(instance.user_id, monster_payload)
    combat_id = session_row.id

    try:
        db.session.delete(monster_ent)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return {"monster": monster_payload, "combat_id": combat_id}


def run_monster_patrols(dungeon, instance, resp: dict, *, tick_amount: int = 1):
    """Update monster positions based on game clock using new spawn system.

    Args:
        dungeon: Dungeon layout object
        instance: DungeonInstance context
        resp: Response dict (reserved for future use)
        tick_amount: Number of ticks elapsed
    """
    try:
        from app.dungeon.spawn_integration import (
            load_spawns_from_db,
            populate_spawn_stats,
            spawn_to_entity,
        )
        from app.dungeon.spawn_manager import SpawnManager
        from app.models.entities import DungeonEntity as _DE
        from app.models.models import GameClock

        clock = GameClock.get()

        # Load spawn manager for this instance. SpawnManager is rebuilt
        # fresh every request -- the two respawn counters aren't durable
        # on the object itself, so they're restored from the instance's
        # JSON metadata column (see dungeon_api.py's _initialize_spawn_system,
        # which writes spawn_initial_ambient_count there once at generation
        # time; spawn_respawns_done is updated below whenever a respawn fires).
        meta = instance.dungeon_metadata or {}
        spawn_manager = SpawnManager(
            dungeon,
            instance,
            initial_ambient_count=meta.get("spawn_initial_ambient_count", 0),
            respawns_done=meta.get("spawn_respawns_done", 0),
        )
        spawns = load_spawns_from_db(instance, spawn_manager)

        if not spawns:
            # No spawns loaded, skip patrol
            return

        levels = [s.level for s in spawns if s.level]
        if levels:
            spawn_manager.party_level = max(1, sum(levels) // len(levels))

        # Update spawn positions based on game clock
        moved_spawns = spawn_manager.update_spawns(clock.tick)

        # A bounded wandering respawn fired this tick -- give it real
        # monster stats via the same creation path ambush rooms use
        # (populate_spawn_stats + spawn_to_entity), persist its
        # DungeonEntity row, and save the incremented counter.
        if spawn_manager.last_respawn is not None:
            try:
                populate_spawn_stats(spawn_manager.last_respawn, spawn_manager.party_level, instance)
                db.session.add(spawn_to_entity(spawn_manager.last_respawn, instance, instance.user_id))
                new_meta = dict(instance.dungeon_metadata or {})
                new_meta["spawn_respawns_done"] = spawn_manager.respawns_done
                new_meta.setdefault("spawn_initial_ambient_count", spawn_manager.initial_ambient_count)
                instance.dungeon_metadata = new_meta
                db.session.add(instance)
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Persist changes to database
        if moved_spawns:
            try:
                # Update entity positions for moved spawns
                for spawn in moved_spawns:
                    # Find entity by slug and original position
                    entity = _DE.query.filter_by(instance_id=instance.id, type="monster", slug=spawn.slug).first()

                    if entity:
                        entity.x = spawn.x
                        entity.y = spawn.y
                        # Update data with movement state
                        if entity.data:
                            import json as _json_patrol

                            try:
                                data = _json_patrol.loads(entity.data)
                                data["last_move_tick"] = spawn.last_move_tick
                                data["behavior"] = spawn.behavior.value
                                entity.data = _json_patrol.dumps(data)
                            except Exception:
                                pass

                db.session.commit()

                # Broadcast movement via websocket
                try:
                    from app import socketio

                    # Build full monster list for client update
                    monster_list = []
                    for spawn in spawn_manager.spawns:
                        monster_list.append({"slug": spawn.slug, "x": spawn.x, "y": spawn.y, "name": spawn.name})

                    socketio.emit(
                        "entities_update", {"monsters": monster_list, "instance_id": instance.id}, namespace="/game"
                    )
                except Exception:
                    pass

            except Exception:
                db.session.rollback()

        # After monsters move, check whether a chasing spawn reached the
        # player's tile this tick -- mirrors the player-onto-monster
        # check in movement_handler.process_movement, just triggered by
        # monster movement instead of player movement. Runs every call,
        # not just when something moved this tick, so a spawn that was
        # already standing on the player's tile from a prior tick is
        # still caught.
        try:
            collision = trigger_collision_combat(instance)
            if collision:
                resp["encounter"] = collision
        except Exception:
            pass

    except Exception:
        # Swallow exceptions to avoid blocking player actions
        pass
