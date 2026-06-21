"""Tests for SpawnManager's proximity-aggro movement (PATROL/WANDERER/
GUARD/AMBIENT spawns moving toward a nearby player instead of their
normal behavior)."""

from app.dungeon.dungeon import Dungeon
from app.dungeon.spawn_manager import SpawnBehavior, SpawnConfig, SpawnEntry, SpawnManager


class _StubInstance:
    """Minimal stand-in for DungeonInstance -- SpawnManager only reads
    .seed, .pos_x, .pos_y, and (via getattr with a default) .tier."""

    def __init__(self, seed, pos_x, pos_y):
        self.seed = seed
        self.pos_x = pos_x
        self.pos_y = pos_y


def _small_dungeon(seed=42):
    return Dungeon(seed=seed, size=(30, 30, 1))


def _manager(dungeon, instance):
    return SpawnManager(dungeon, instance, config=SpawnConfig(aggro_radius=5))


def test_patrol_spawn_within_radius_moves_toward_player():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=0, pos_y=0))
    walkable = manager._get_walkable_tiles()
    assert len(walkable) >= 2, "test dungeon too small/empty to place two tiles"

    spawn_tile = walkable[0]
    player_tile = walkable[-1]
    manager.instance.pos_x, manager.instance.pos_y = player_tile

    spawn = SpawnEntry(x=spawn_tile[0], y=spawn_tile[1], behavior=SpawnBehavior.PATROL)
    # Force "within radius" regardless of the two tiles' actual distance,
    # by using a huge radius -- this test is about aggro overriding
    # normal movement, not about the radius boundary itself (see the
    # next test for that).
    manager.config.aggro_radius = 10_000
    manager.spawns = [spawn]

    before = max(abs(spawn.x - player_tile[0]), abs(spawn.y - player_tile[1]))
    manager.update_spawns(current_tick=1)
    after = max(abs(spawn.x - player_tile[0]), abs(spawn.y - player_tile[1]))

    assert after < before, (before, after, spawn.x, spawn.y, player_tile)


def test_spawn_outside_radius_does_not_aggro():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=0, pos_y=0))
    walkable = manager._get_walkable_tiles()
    assert len(walkable) >= 2

    spawn_tile = walkable[0]
    player_tile = walkable[-1]
    manager.instance.pos_x, manager.instance.pos_y = player_tile

    spawn = SpawnEntry(x=spawn_tile[0], y=spawn_tile[1], behavior=SpawnBehavior.GUARD)
    manager.config.aggro_radius = 0  # nothing is ever in range
    manager.spawns = [spawn]

    assert manager._is_aggroed(spawn, player_tile[0], player_tile[1]) is False
    # GUARD never moves on its own (matches existing _should_move behavior) --
    # confirms aggro=False doesn't accidentally grant movement it shouldn't have.
    before = (spawn.x, spawn.y)
    manager.update_spawns(current_tick=1)
    assert (spawn.x, spawn.y) == before


def test_boss_and_elite_never_aggro():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=5, pos_y=5))
    spawn = SpawnEntry(x=5, y=6, behavior=SpawnBehavior.BOSS)
    manager.config.aggro_radius = 10_000
    assert manager._is_aggroed(spawn, 5, 5) is False

    spawn2 = SpawnEntry(x=5, y=6, behavior=SpawnBehavior.ELITE)
    assert manager._is_aggroed(spawn2, 5, 5) is False
