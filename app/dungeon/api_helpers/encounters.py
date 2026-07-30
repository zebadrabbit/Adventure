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

import structlog

from app import db

logger = structlog.get_logger(__name__)

__all__ = ["trigger_collision_combat", "run_monster_patrols"]


def combat_pack_cap() -> int:
    """How many monsters a single encounter may field.

    Reads the live ``GameConfig`` row ``combat_pack_max`` first, so packs can be
    turned on and off during a play session without a restart -- this is a
    balance knob whose right value is a playtest verdict, not a constant. Falls
    back to ``SpawnConfig.combat_pack_max`` (1) when the row is absent or junk.

    One seam rather than a bare read at the call site, so tests can opt in
    without reaching into a dataclass's captured field defaults.
    """
    try:
        from app.models.models import GameConfig

        raw = GameConfig.get("combat_pack_max")
        if raw is not None:
            return max(1, int(str(raw).strip().strip('"')))
    except Exception:
        logger.debug("suppressed_exception", where="combat_pack_cap", exc_info=True)
    try:
        from app.dungeon.spawn_manager import SpawnConfig

        return max(1, int(SpawnConfig().combat_pack_max))
    except Exception:
        return 1


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

    def _payload(ent):
        """Carry the whole spawn payload into combat: archetype drives boss/elite
        kill tracking (and with it the extraction unlock), and xp/loot_table/
        resistances all live here too. Only the live entity fields override it."""
        data = {}
        try:
            if ent.data:
                data = json.loads(ent.data)
        except Exception:
            data = {}
        return {
            **data,
            "slug": ent.slug,
            "name": ent.name or ent.slug,
            "hp": ent.hp_current or data.get("hp", 30),
            "damage": data.get("damage", 6),
            "speed": data.get("speed", 10),
        }

    # The pack, not just the one you walked into. Spawning already clusters
    # monsters, so the ones standing next to the trigger are the group the
    # design means by "zoom into the tile you are on" -- pulling them in is what
    # stops a fight that looks like four-on-one from being resolved as four
    # separate four-on-ones. Capped by SpawnConfig.combat_pack_max -- which is 1
    # today, so this is dormant until the monster numbers are ready for it (see
    # that field for why). Neighbours are ordered by id, so a given seed always
    # fights the same pack.
    fighters = [monster_ent]
    cap = combat_pack_cap()
    if cap > 1:
        try:
            neighbours = (
                DungeonEntity.query.filter(
                    DungeonEntity.instance_id == instance.id,
                    DungeonEntity.type == "monster",
                    DungeonEntity.z == instance.pos_z,
                    DungeonEntity.id != monster_ent.id,
                    DungeonEntity.x.between(instance.pos_x - 1, instance.pos_x + 1),
                    DungeonEntity.y.between(instance.pos_y - 1, instance.pos_y + 1),
                )
                .order_by(DungeonEntity.id)
                .limit(cap - 1)
                .all()
            )
            fighters.extend(neighbours)
        except Exception:
            logger.debug("suppressed_exception", where="_start_encounter_neighbours", exc_info=True)

    from app.services import combat_service

    payloads = [_payload(e) for e in fighters]
    monster_payload = payloads[0]  # the trigger, for the caller's response
    session_row = combat_service.start_session(instance.user_id, payloads)
    combat_id = session_row.id

    try:
        # Every monster now in the fight leaves the map, not just the trigger --
        # otherwise the pack would still be standing there after the fight.
        for ent in fighters:
            db.session.delete(ent)
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
