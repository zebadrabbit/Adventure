"""Tests for bounded wandering respawns in SpawnManager.update_spawns.

Pure unit tests against SpawnManager (no Flask/db context needed) --
mirrors the _StubInstance approach in tests/test_spawn_aggro.py.
"""

from app.dungeon.dungeon import Dungeon
from app.dungeon.room_events import EVENT_TUNING
from app.dungeon.spawn_manager import SpawnBehavior, SpawnConfig, SpawnEntry, SpawnManager

INTERVAL = EVENT_TUNING["respawn_interval_ticks"]
MIN_DIST = EVENT_TUNING["respawn_min_player_distance"]


class _StubInstance:
    """Minimal stand-in for DungeonInstance."""

    def __init__(self, seed=42, pos_x=0, pos_y=0, bosses_defeated=0, bosses_total=1):
        self.seed = seed
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.bosses_defeated = bosses_defeated
        self.bosses_total = bosses_total


def _big_dungeon(seed=42):
    # Large enough to have plenty of walkable tiles >= MIN_DIST from any corner.
    return Dungeon(seed=seed, size=(60, 60, 1))


def _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0):
    return SpawnManager(
        dungeon,
        instance,
        config=SpawnConfig(),
        initial_ambient_count=initial_ambient_count,
        respawns_done=respawns_done,
    )


def _depleted_spawns(count=1):
    """A handful of living ambient spawns, deliberately below 40% of 10."""
    return [SpawnEntry(x=1, y=1, behavior=SpawnBehavior.AMBIENT) for _ in range(count)]


def test_respawn_fires_on_interval_tick_when_depleted():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0)
    manager.spawns = _depleted_spawns(2)  # 2 < 40% of 10 -> below threshold

    manager.update_spawns(current_tick=INTERVAL)

    assert manager.respawns_done == 1
    assert manager.last_respawn is not None
    assert manager.last_respawn.behavior == SpawnBehavior.WANDERER
    assert any(s is manager.last_respawn for s in manager.spawns)


def test_respawn_does_not_fire_off_interval_tick():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0)
    manager.spawns = _depleted_spawns(2)

    manager.update_spawns(current_tick=INTERVAL + 1)

    assert manager.respawns_done == 0
    assert manager.last_respawn is None


def test_respawn_does_not_fire_above_threshold():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0)
    # 5 living ambients == 50% >= 40% threshold -> no respawn
    manager.spawns = _depleted_spawns(5)

    manager.update_spawns(current_tick=INTERVAL)

    assert manager.respawns_done == 0
    assert manager.last_respawn is None


def test_respawn_stops_at_cap():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    # cap = int(10 * 0.5) == 5; already at cap
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=5)
    manager.spawns = _depleted_spawns(1)

    manager.update_spawns(current_tick=INTERVAL)

    assert manager.respawns_done == 5
    assert manager.last_respawn is None


def test_respawn_never_fires_when_bosses_all_defeated():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0, bosses_defeated=1, bosses_total=1)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0)
    manager.spawns = _depleted_spawns(1)

    manager.update_spawns(current_tick=INTERVAL)

    assert manager.respawns_done == 0
    assert manager.last_respawn is None


def test_respawn_tile_is_never_within_min_distance_of_player():
    dungeon = _big_dungeon()
    walkable = SpawnManager(dungeon, _StubInstance())._get_walkable_tiles()
    assert len(walkable) > 20, "test dungeon too small/empty"
    player_x, player_y = walkable[0]

    instance = _StubInstance(pos_x=player_x, pos_y=player_y)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=0)
    manager.spawns = _depleted_spawns(1)

    manager.update_spawns(current_tick=INTERVAL)

    assert manager.last_respawn is not None
    dist = max(abs(manager.last_respawn.x - player_x), abs(manager.last_respawn.y - player_y))
    assert dist >= MIN_DIST


def test_counters_survive_to_dict_from_dict_round_trip():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    manager = _manager(dungeon, instance, initial_ambient_count=10, respawns_done=3)
    manager.spawns = _depleted_spawns(2)

    data = manager.to_dict()
    assert data["initial_ambient_count"] == 10
    assert data["respawns_done"] == 3

    restored = SpawnManager.from_dict(dungeon, instance, data)
    assert restored.initial_ambient_count == 10
    assert restored.respawns_done == 3


def test_initialize_spawns_records_initial_ambient_count():
    dungeon = _big_dungeon()
    instance = _StubInstance(pos_x=0, pos_y=0)
    # min_spawns high enough that boss/elite allocation leaves ambients --
    # the default config's density on this dungeon size produces mostly
    # boss/elite spawns with none left over for ambients.
    manager = SpawnManager(dungeon, instance, config=SpawnConfig(min_spawns=20, max_spawns=40))
    manager.initialize_spawns(party_level=1)

    ambient_tier = (
        SpawnBehavior.PATROL,
        SpawnBehavior.WANDERER,
        SpawnBehavior.GUARD,
        SpawnBehavior.AMBIENT,
    )
    actual_ambient_count = sum(1 for s in manager.spawns if s.behavior in ambient_tier)
    assert manager.initial_ambient_count == actual_ambient_count
    assert manager.initial_ambient_count > 0
