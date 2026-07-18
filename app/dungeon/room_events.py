"""Room events: shrines, traps, and ambushes seeded per dungeon instance.

Seeding is deterministic from the instance seed (mirrors how treasure caches
are seeded in app/routes/dungeon_api.py) so re-deriving an instance
reproduces the same placements. `trap` and `ambush` entities must NEVER be
serialized to clients -- callers that list DungeonEntity rows for the client
(REST and websocket) must filter `type in ("trap", "ambush")`.
"""

from __future__ import annotations

import random

from app import db
from app.dungeon.spawn_manager import SpawnManager
from app.models.entities import DungeonEntity

# ponytail: flat constants for v1; move into GameConfig if playtesting demands live tuning
EVENT_TUNING = {
    "shrines_per_instance": 2,
    "traps_per_instance": 4,
    "ambushes_per_instance": 2,
    "shrine_mana_restore_pct": 0.5,  # instant, of max_mana
    "shrine_regen_ticks": 10,  # same well-rested buff camp grants
    "trap_damage_pct": 0.10,  # of max_hp, party leader
    "trap_poison_ticks": 5,
    "trap_perception_dc": 12,  # d20 + perception mod >= DC avoids
    "ambush_pack_size": (2, 3),  # inclusive range
    "respawn_interval_ticks": 20,
    "respawn_cap_fraction": 0.5,  # of initial ambient count
    "respawn_min_player_distance": 8,
}

# Entity types that must never be serialized to clients.
HIDDEN_ROOM_EVENT_TYPES = ("trap", "ambush")
ROOM_EVENT_TYPES = ("shrine",) + HIDDEN_ROOM_EVENT_TYPES

_SEED_XOR = 0xE7E47
_MIN_ENTRANCE_DISTANCE = 3


def _entrance(dungeon):
    """Return (x, y) of the dungeon entrance (first room's center), or None."""
    rooms = getattr(dungeon, "rooms", None)
    if not rooms:
        return None
    try:
        r0 = rooms[0]
        return (r0.center[0], r0.center[1])
    except Exception:
        return None


def seed_room_events(instance, dungeon) -> int:
    """Seed shrine/trap/ambush DungeonEntity rows for this instance.

    Places EVENT_TUNING-configured counts of shrine/trap/ambush entities on
    distinct walkable floor tiles at least 3 tiles from the entrance and not
    already occupied by another entity. Deterministic via
    random.Random(instance.seed ^ 0xE7E47).

    Idempotent: no-op (returns 0) if any shrine/trap/ambush row already
    exists for this instance.

    Returns the number of entities created.
    """
    existing = DungeonEntity.query.filter(
        DungeonEntity.instance_id == instance.id,
        DungeonEntity.type.in_(ROOM_EVENT_TYPES),
    ).first()
    if existing:
        return 0

    # Reuse SpawnManager's walkable-tile helper rather than re-deriving the
    # walkable char set here.
    walkable = SpawnManager(dungeon, instance)._get_walkable_tiles()
    entrance = _entrance(dungeon)

    occupied = {(e.x, e.y) for e in DungeonEntity.query.filter_by(instance_id=instance.id).all()}

    candidates = []
    for x, y in walkable:
        if (x, y) in occupied:
            continue
        if entrance is not None:
            dist = max(abs(x - entrance[0]), abs(y - entrance[1]))
            if dist < _MIN_ENTRANCE_DISTANCE:
                continue
        candidates.append((x, y))

    rng = random.Random(instance.seed ^ _SEED_XOR)
    rng.shuffle(candidates)

    plan = (
        [("shrine", "Ancient Shrine", "shrine")] * EVENT_TUNING["shrines_per_instance"]
        + [("trap", "Hidden Trap", None)] * EVENT_TUNING["traps_per_instance"]
        + [("ambush", None, None)] * EVENT_TUNING["ambushes_per_instance"]
    )

    created = 0
    for (etype, name, slug), (x, y) in zip(plan, candidates):
        ent = DungeonEntity(
            user_id=instance.user_id,
            instance_id=instance.id,
            seed=instance.seed,
            type=etype,
            slug=slug,
            name=name,
            x=x,
            y=y,
            z=0,
        )
        db.session.add(ent)
        created += 1

    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return 0

    return created
