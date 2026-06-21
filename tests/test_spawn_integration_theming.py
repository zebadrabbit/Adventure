"""Tests that populate_spawn_stats restricts ambient-tier spawns to the
instance's assigned monster_family theme."""

from app import db
from app.dungeon.spawn_integration import populate_spawn_stats
from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry
from app.models.models import MonsterCatalog
from app.services import spawn_service
from tests.factories import create_instance, create_user


def _seed_two_families():
    for slug, family in (("themespawn-undead", "undead"), ("themespawn-beast", "beast")):
        if MonsterCatalog.query.filter_by(slug=slug).first():
            continue
        db.session.add(
            MonsterCatalog(
                slug=slug,
                name=slug,
                level_min=1,
                level_max=10,
                base_hp=20,
                base_damage=3,
                family=family,
                rarity="common",
                boss=False,
                xp_base=10,
            )
        )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def test_ambient_spawn_respects_instance_theme(test_app):
    with test_app.app_context():
        _seed_two_families()
        user = create_user("spawntheme_1")
        inst = create_instance(user, seed=701)
        inst.monster_family = "undead"
        db.session.commit()

        for _ in range(10):
            spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
            populate_spawn_stats(spawn, party_level=1, instance=inst)
            assert spawn.slug == "themespawn-undead"


def test_ambient_spawn_unrestricted_when_theme_is_none(test_app):
    with test_app.app_context():
        _seed_two_families()
        user = create_user("spawntheme_2")
        inst = create_instance(user, seed=702)
        assert inst.monster_family is None

        seen = set()
        for _ in range(30):
            spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
            populate_spawn_stats(spawn, party_level=1, instance=inst)
            seen.add(spawn.slug)
        assert seen & {"themespawn-undead", "themespawn-beast"}
