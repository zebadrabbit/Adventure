"""Room events: shrines, traps, and ambushes seeded per dungeon instance.

Seeding is deterministic from the instance seed (mirrors how treasure caches
are seeded in app/routes/dungeon_api.py) so re-deriving an instance
reproduces the same placements. `trap` and `ambush` entities must NEVER be
serialized to clients -- callers that list DungeonEntity rows for the client
(REST and websocket) must filter `type in ("trap", "ambush")`.
"""

from __future__ import annotations

import json
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


def _party_chars(instance):
    """All characters belonging to the instance's owner, ordered by id.

    The first row is treated as the party leader for single-target events
    (traps). Uses instance.user_id rather than the request session so the
    resolution is testable outside a live request.
    """
    from app.models.models import Character

    return Character.query.filter_by(user_id=instance.user_id).order_by(Character.id).all()


def _is_alive(char) -> bool:
    try:
        return int(json.loads(char.stats).get("hp", 0)) > 0
    except Exception:
        return False


def _resolve_shrine(instance, ent) -> dict:
    """Restore party mana and grant the well-rested regen_buff (same shape
    dungeon_camp grants). Mirrors camp's replace-not-stack CharacterStatusEffect
    handling."""
    from app.models.status_effect import CharacterStatusEffect

    pct = EVENT_TUNING["shrine_mana_restore_pct"]
    ticks = EVENT_TUNING["shrine_regen_ticks"]

    for char in _party_chars(instance):
        if not _is_alive(char):
            continue
        try:
            stats = json.loads(char.stats)
            max_mana = int(stats.get("max_mana", stats.get("mana", 0)))
            cur_mana = int(stats.get("mana", 0))
            stats["mana"] = min(max_mana, cur_mana + int(max_mana * pct))
            char.stats = json.dumps(stats)
            db.session.add(char)
        except Exception:
            continue
        # replace-not-stack: drop any existing regen_buff row, add a fresh one.
        CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").delete()
        db.session.add(
            CharacterStatusEffect(
                character_id=char.id,
                name="regen_buff",
                remaining=ticks,
                data=json.dumps({"hp_mult": 2.0, "mp_mult": 2.0}),
            )
        )

    return {
        "kind": "shrine",
        "message": "You touch the Ancient Shrine -- the party feels invigorated.",
    }


def _resolve_trap(instance, ent, x, y) -> dict:
    """d20 + party leader perception vs DC. Failure deals floored max_hp% damage
    plus persistent poison. Deterministic via the tile-keyed seed."""
    from app.dungeon.api_helpers.perception import _perception_mod_from_stats
    from app.models.status_effect import CharacterStatusEffect

    party = _party_chars(instance)
    leader = party[0] if party else None
    mod = _perception_mod_from_stats(leader.stats) if leader else 0

    rng = random.Random(instance.seed ^ (x << 8) ^ y)
    roll = rng.randint(1, 20)

    if roll + mod >= EVENT_TUNING["trap_perception_dc"]:
        return {"kind": "trap_avoided", "message": "You spot and disarm a hidden trap."}

    if leader is not None:
        try:
            stats = json.loads(leader.stats)
            max_hp = int(stats.get("max_hp", stats.get("hp", 0)))
            cur_hp = int(stats.get("hp", 0))
            damage = int(max_hp * EVENT_TUNING["trap_damage_pct"])
            # Traps never kill outright -- floor at 1 hp (mirrors the
            # out-of-combat poison floor).
            stats["hp"] = max(1, cur_hp - damage)
            leader.stats = json.dumps(stats)
            db.session.add(leader)
            CharacterStatusEffect.query.filter_by(character_id=leader.id, name="poison").delete()
            db.session.add(
                CharacterStatusEffect(
                    character_id=leader.id,
                    name="poison",
                    remaining=EVENT_TUNING["trap_poison_ticks"],
                    data=json.dumps({"damage": 5}),
                )
            )
        except Exception:
            pass

    return {"kind": "trap_hit", "message": "A hidden trap springs -- you are wounded and poisoned!"}


def _resolve_ambush(instance, ent, x, y, dungeon) -> dict:
    """Spawn 2-3 family-themed ambient monsters on walkable tiles adjacent to
    (x, y), created as both SpawnEntry and DungeonEntity rows exactly like
    normal ambients. Proximity-aggro then takes over."""
    from app.dungeon.spawn_integration import populate_spawn_stats, spawn_to_entity
    from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry

    if dungeon is None:
        from app.dungeon.movement_handler import get_cached_dungeon

        dungeon = get_cached_dungeon(instance.seed, (75, 75, 1))

    from app.dungeon.tiles import DOOR, ROOM, TUNNEL

    walkable_chars = {ROOM, TUNNEL, DOOR}
    width = len(dungeon.grid)
    height = len(dungeon.grid[0]) if width else 0

    occupied = {(e.x, e.y) for e in DungeonEntity.query.filter_by(instance_id=instance.id).all()}

    neighbors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and dungeon.grid[nx][ny] in walkable_chars:
                if (nx, ny) not in occupied:
                    neighbors.append((nx, ny))

    rng = random.Random(instance.seed ^ (x << 8) ^ y)
    rng.shuffle(neighbors)

    pack_size = rng.randint(*EVENT_TUNING["ambush_pack_size"])
    tiles = neighbors[:pack_size]

    party = _party_chars(instance)
    party_level = 1
    if party:
        try:
            party_level = max(1, int(sum(int(c.level) for c in party) / len(party)))
        except Exception:
            party_level = 1

    spawned = 0
    for nx, ny in tiles:
        spawn = SpawnEntry(x=nx, y=ny, behavior=SpawnBehavior.AMBIENT, archetype="Trash", level=party_level)
        populate_spawn_stats(spawn, party_level, instance)
        db.session.add(spawn_to_entity(spawn, instance, instance.user_id))
        spawned += 1

    return {"kind": "ambush", "message": "It's an ambush!", "count": spawned}


def resolve_events_at(instance, x, y, dungeon=None) -> list[dict]:
    """Resolve any shrine/trap/ambush entities on tile (x, y) for this instance.

    Each triggered entity is consumed (its row deleted). Returns a list of
    event dicts, each shaped ``{"kind": ..., "message": str, ...}``. Empty
    list when the tile holds no room event.
    """
    ents = DungeonEntity.query.filter(
        DungeonEntity.instance_id == instance.id,
        DungeonEntity.type.in_(ROOM_EVENT_TYPES),
        DungeonEntity.x == x,
        DungeonEntity.y == y,
    ).all()

    if not ents:
        return []

    events = []
    for ent in ents:
        if ent.type == "shrine":
            events.append(_resolve_shrine(instance, ent))
        elif ent.type == "trap":
            events.append(_resolve_trap(instance, ent, x, y))
        elif ent.type == "ambush":
            events.append(_resolve_ambush(instance, ent, x, y, dungeon))
        db.session.delete(ent)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return events
