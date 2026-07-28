"""Monsters arrive as separated packs, not confetti.

Playtest finding (2026-07-27): "i also spawned in a room next to 6 lvl 2 mobs
all at once, it'd be better if there were groups of 1~5 mobs much more spread
out; also the map size increase to 27 ish rooms means we should add more fights".

Ambient spawns were a uniform `rng.sample()` over every walkable tile, so
clumping was pure chance: nothing kept two spawns apart and nothing grouped
them deliberately. Combined with an aggro radius of 5, a chance clump of six
meant six monsters woke at once -- and since combat is one-on-one, that is six
sequential fights.

Spawns are now placed as packs around anchors kept `min_group_separation` apart.
Pack size is capped at 3 for now because combat can only field one monster at a
time; the cap exists to be raised once it can field a whole pack.
"""

import json

import pytest

from app import db
from app.dungeon.dungeon import Dungeon
from app.dungeon.spawn_manager import SpawnBehavior, SpawnConfig, SpawnManager
from app.models.models import GameConfig

AMBIENT = (SpawnBehavior.PATROL, SpawnBehavior.WANDERER, SpawnBehavior.GUARD, SpawnBehavior.AMBIENT)
SEEDS = (733064, 424242, 90210)


class _Instance:
    """Minimal stand-in; SpawnManager only reads these attributes."""

    def __init__(self, seed, floor=0):
        self.id = 1
        self.user_id = 1
        self.seed = seed
        self.pos_z = floor
        self.tier = 1
        self.dungeon_metadata = {}


def _spawn_floor(seed, floor=0, config=None):
    dungeon = Dungeon(seed=seed, size=(75, 75, 2), floor=floor, num_floors=2)
    manager = SpawnManager(dungeon, _Instance(seed, floor), config=config or SpawnConfig())
    manager.initialize_spawns(party_level=2)
    return manager


def _chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _ambient(manager):
    return [(s.x, s.y) for s in manager.spawns if s.behavior in AMBIENT]


def _packs(points, radius=3):
    """Group points into clusters of mutual proximity."""
    packs, seen = [], set()
    for p in points:
        if p in seen:
            continue
        group = [q for q in points if _chebyshev(p, q) <= radius]
        seen.update(group)
        packs.append(group)
    return packs


@pytest.mark.parametrize("seed", SEEDS)
def test_no_pack_exceeds_the_configured_size(seed):
    """The reported case was six in one room."""
    manager = _spawn_floor(seed)
    cap = manager.config.group_size_max
    for pack in _packs(_ambient(manager)):
        assert len(pack) <= cap, f"seed {seed}: pack of {len(pack)} exceeds cap {cap}"


@pytest.mark.parametrize("seed", SEEDS)
def test_monsters_never_share_a_tile(seed):
    points = [(s.x, s.y) for s in _spawn_floor(seed).spawns]
    assert len(points) == len(set(points)), f"seed {seed}: two spawns on one tile"


@pytest.mark.parametrize("seed", SEEDS)
def test_aggro_radius_cannot_wake_a_crowd(seed):
    """With combat one-on-one, everything inside aggro_radius is a queue."""
    manager = _spawn_floor(seed)
    points = _ambient(manager)
    radius = manager.config.aggro_radius
    for p in points:
        nearby = sum(1 for q in points if _chebyshev(p, q) <= radius)
        assert nearby <= manager.config.group_size_max + 1, f"seed {seed}: {nearby} monsters within aggro radius of {p}"


@pytest.mark.parametrize("seed", SEEDS)
def test_packs_are_spread_across_the_floor(seed):
    """Several distinct encounters, not one blob."""
    manager = _spawn_floor(seed)
    packs = _packs(_ambient(manager))
    assert len(packs) >= 3, f"seed {seed}: only {len(packs)} encounter(s) on the whole floor"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_floor_is_populated(seed):
    """The other half of the ask: more fights on the bigger map."""
    manager = _spawn_floor(seed)
    assert len(_ambient(manager)) >= 8, f"seed {seed}: only {len(_ambient(manager))} ambient spawns"


def test_generation_is_deterministic_for_a_seed():
    a = [(s.x, s.y, s.behavior) for s in _spawn_floor(733064).spawns]
    b = [(s.x, s.y, s.behavior) for s in _spawn_floor(733064).spawns]
    assert a == b


def test_a_cramped_floor_still_gets_its_spawns():
    """Separation is a preference, not a reason to leave a floor empty."""
    config = SpawnConfig()
    config.min_group_separation = 60  # impossible on a 75x75 map
    manager = _spawn_floor(733064, config=config)
    assert len(_ambient(manager)) >= 8, "separation was honoured at the cost of populating the floor"


# ------------------------------------------------------------------ tuning


def test_game_config_overrides_spawn_tuning(test_app):
    GameConfig.set("spawns", json.dumps({"group_size_max": 5, "aggro_radius": 9, "ambient_density": 0.02}))
    try:
        cfg = SpawnConfig.from_game_config()
        assert cfg.group_size_max == 5
        assert cfg.aggro_radius == 9
        assert cfg.ambient_density == 0.02
    finally:
        GameConfig.query.filter_by(key="spawns").delete()
        db.session.commit()


def test_bad_tuning_values_fall_back_to_defaults(test_app):
    GameConfig.set("spawns", json.dumps({"group_size_max": "lots", "nonsense_key": 1}))
    try:
        cfg = SpawnConfig.from_game_config()
        assert cfg.group_size_max == SpawnConfig().group_size_max
    finally:
        GameConfig.query.filter_by(key="spawns").delete()
        db.session.commit()


def test_larger_packs_can_be_enabled_when_combat_supports_them(test_app):
    """The cap is a dial, not a hard rule -- raising it must actually work."""
    config = SpawnConfig()
    config.group_size_min = 4
    config.group_size_max = 5
    manager = _spawn_floor(733064, config=config)
    biggest = max((len(p) for p in _packs(_ambient(manager))), default=0)
    assert biggest >= 4, f"largest pack was {biggest} with a 4-5 group size"
