"""Tests that ambient-tier spawns draw from the real MonsterCatalog,
while boss/elite spawns keep the existing archetype-label system."""

from app import db
from app.dungeon.spawn_integration import populate_spawn_stats
from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry
from app.models.enemy_archetype import EnemyArchetype
from app.models.models import MonsterCatalog
from app.services import spawn_service
from tests.factories import create_instance, create_user


def _seed_test_monster():
    if MonsterCatalog.query.filter_by(slug="test-grunt").first():
        return
    db.session.add(
        MonsterCatalog(
            slug="test-grunt",
            name="Test Grunt",
            level_min=1,
            level_max=10,
            base_hp=20,
            base_damage=3,
            family="test",
            rarity="common",
            boss=False,
            xp_base=10,
        )
    )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def _seed_boss_archetype():
    # Test environment does not auto-load sql/enemy_archetypes_seed.sql, so
    # the archetype path needs a "Boss" row to exercise the unchanged
    # branch rather than falling back to the generic fallback stats.
    if EnemyArchetype.query.filter_by(archetype="Boss").first():
        return
    db.session.add(
        EnemyArchetype(
            archetype="Boss",
            rank="Boss",
            base_hp=400,
            hp_per_level=70,
            base_damage=26,
            damage_per_level=8.5,
            armor_class_base=16,
            armor_class_per_level=0.8,
            xp_base=400,
            xp_per_level=70,
            loot_multiplier=4.0,
        )
    )
    db.session.commit()


def test_ambient_spawn_uses_real_catalog_monster(test_app):
    with test_app.app_context():
        _seed_test_monster()
        user = create_user("catalogspawn_1")
        inst = create_instance(user, seed=901)

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.slug == "test-grunt"
        assert spawn.name == "Test Grunt"
        assert spawn.hp_current == 20


def test_boss_spawn_still_uses_archetype_label(test_app):
    with test_app.app_context():
        _seed_boss_archetype()
        user = create_user("catalogspawn_2")
        inst = create_instance(user, seed=902)

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.BOSS, archetype="Boss", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.name is not None and "(L" in spawn.name
        assert spawn.slug == "boss"
