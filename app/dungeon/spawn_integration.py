"""Spawn integration utilities.

Bridges the new spawn_manager system with existing dungeon entities and combat flow.
Provides helpers to:
- Convert SpawnEntry objects to DungeonEntity persistence
- Populate monster stats using archetype system
- Synchronize spawn manager state with database
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional

from app import db
from app.models.entities import DungeonEntity
from app.services import spawn_service

if TYPE_CHECKING:
    from app.dungeon.spawn_manager import SpawnEntry, SpawnManager
    from app.models.dungeon_instance import DungeonInstance

__all__ = ["populate_spawn_stats", "persist_spawns", "load_spawns_from_db", "spawn_to_entity"]


def populate_spawn_stats(spawn: "SpawnEntry", party_level: int, instance: "DungeonInstance") -> "SpawnEntry":
    """Populate a spawn with full monster stats using archetype system.

    Args:
        spawn: SpawnEntry to populate
        party_level: Average party level for scaling
        instance: DungeonInstance for tier/affix context

    Returns:
        SpawnEntry with populated stats
    """
    # Get tier and affixes from instance
    tier = getattr(instance, "tier", 1) or 1
    affix_ids_str = getattr(instance, "affix_ids", None)
    affix_ids = []
    if affix_ids_str:
        try:
            affix_ids = json.loads(affix_ids_str) if isinstance(affix_ids_str, str) else affix_ids_str
        except Exception:
            pass

    # Generate monster using archetype system
    try:
        monster_dict = spawn_service.choose_archetype_monster(
            level=spawn.level or party_level,
            archetype_name=spawn.archetype,
            tier=tier,
            affix_ids=affix_ids,
            party_size=1,  # Base stats, scale in combat as needed
        )

        # Populate spawn with generated stats
        spawn.slug = monster_dict.get("slug")
        spawn.name = monster_dict.get("name")
        spawn.hp_current = monster_dict.get("hp")
        spawn.hp_max = monster_dict.get("hp")
        spawn.data = monster_dict

    except Exception:
        # Fallback to basic stats if archetype system fails
        spawn.slug = f"{spawn.archetype.lower()}_monster"
        spawn.name = f"{spawn.archetype} Monster"
        spawn.hp_current = spawn.level * 20
        spawn.hp_max = spawn.level * 20
        spawn.data = {
            "hp": spawn.hp_current,
            "damage": spawn.level * 4,
            "level": spawn.level,
            "archetype": spawn.archetype,
        }

    return spawn


def spawn_to_entity(spawn: "SpawnEntry", instance: "DungeonInstance", user_id: int) -> DungeonEntity:
    """Convert SpawnEntry to DungeonEntity for persistence.

    Args:
        spawn: SpawnEntry to convert
        instance: DungeonInstance context
        user_id: User ID for isolation

    Returns:
        DungeonEntity ready for database insertion
    """
    return DungeonEntity(
        user_id=user_id,
        instance_id=instance.id,
        seed=instance.seed,
        type="monster",
        slug=spawn.slug,
        name=spawn.name,
        x=spawn.x,
        y=spawn.y,
        z=spawn.z,
        hp_current=spawn.hp_current,
        data=json.dumps(spawn.data),
    )


def persist_spawns(manager: "SpawnManager", instance: "DungeonInstance", user_id: int) -> int:
    """Persist spawn manager state to database.

    Args:
        manager: SpawnManager with spawns to persist
        instance: DungeonInstance context
        user_id: User ID for isolation

    Returns:
        Number of entities persisted
    """
    # Clear existing monster entities for this instance
    try:
        DungeonEntity.query.filter_by(instance_id=instance.id, type="monster").delete(synchronize_session=False)
    except Exception:
        pass

    # Create entities for all spawns
    created = 0
    for spawn in manager.spawns:
        try:
            entity = spawn_to_entity(spawn, instance, user_id)
            db.session.add(entity)
            created += 1
        except Exception:
            continue

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 0

    return created


def load_spawns_from_db(instance: "DungeonInstance", manager: "SpawnManager") -> Optional[List["SpawnEntry"]]:
    """Load spawns from database into spawn manager.

    Args:
        instance: DungeonInstance to load from
        manager: SpawnManager to populate

    Returns:
        List of loaded SpawnEntry objects or None if not found
    """
    from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry

    entities = DungeonEntity.query.filter_by(instance_id=instance.id, type="monster").all()

    if not entities:
        return None

    spawns = []
    for entity in entities:
        try:
            # Parse stored data
            data = {}
            if entity.data:
                try:
                    data = json.loads(entity.data)
                except Exception:
                    pass

            # Extract behavior and archetype from data or use defaults
            behavior_str = data.get("behavior", "ambient")
            try:
                behavior = SpawnBehavior(behavior_str)
            except ValueError:
                behavior = SpawnBehavior.AMBIENT

            archetype = data.get("archetype", "Trash")

            # Create spawn entry
            spawn = SpawnEntry(
                x=entity.x,
                y=entity.y,
                z=entity.z,
                behavior=behavior,
                archetype=archetype,
                level=data.get("level", 1),
                slug=entity.slug,
                name=entity.name,
                hp_current=entity.hp_current,
                hp_max=data.get("hp", entity.hp_current),
                data=data,
            )

            # Restore movement state if available
            spawn.spawn_x = data.get("spawn_x", entity.x)
            spawn.spawn_y = data.get("spawn_y", entity.y)
            spawn.last_move_tick = data.get("last_move_tick", 0)
            spawn.move_interval = data.get("move_interval", 5)
            spawn.in_combat = data.get("in_combat", False)

            spawns.append(spawn)

        except Exception:
            continue

    manager.spawns = spawns
    manager._initialized = True

    return spawns
