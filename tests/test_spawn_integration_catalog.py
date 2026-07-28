"""Every spawn takes its identity from the real MonsterCatalog.

Ambient spawns are drawn from the catalog outright. Boss/elite spawns keep the
archetype system for their *stats* (tier and affix scaling) but borrow a
catalogued creature's name, family and traits -- otherwise the set piece at the
bottom of the dungeon announces itself as "Boss (L12)".
"""

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
        # Pin the theme: the real catalogue is seeded here too, so without this
        # the pick is whatever else happens to cover level 1.
        inst.monster_family = "test"
        db.session.commit()

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.slug == "test-grunt"
        assert spawn.name == "Test Grunt"
        assert spawn.hp_current == 20


def test_boss_spawn_borrows_a_catalogue_identity(test_app):
    """Archetype stats, catalogue name."""
    with test_app.app_context():
        _seed_boss_archetype()
        _seed_test_monster()
        user = create_user("catalogspawn_2")
        inst = create_instance(user, seed=902)
        inst.monster_family = "test"
        db.session.commit()

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.BOSS, archetype="Boss", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.name == "Test Grunt", "a boss must not be called 'Boss (L1)'"
        assert spawn.slug == "test-grunt"
        # Stats still come from the archetype, not the 20 hp catalogue row.
        assert spawn.hp_current > 100
        assert spawn.data["archetype"] == "Boss"


def test_boss_above_the_catalogue_ceiling_still_gets_a_real_name(test_app):
    """Past the catalogue's top band, borrow from the deepest band that exists.

    Level 40 is beyond the catalogue's ceiling of 20 (characters reach 50).
    That used to yield nothing, so the spawn fell back to a bare "Boss (L40)"
    label with no family, loot table or resistances. _eligible_monsters now
    clamps to the deepest band instead -- see test_catalogue_level_ceiling.
    """
    with test_app.app_context():
        _seed_boss_archetype()
        user = create_user("catalogspawn_3")
        inst = create_instance(user, seed=903)
        spawn_service._ELIGIBLE_CACHE.clear()

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.BOSS, archetype="Boss", level=40)
        populate_spawn_stats(spawn, party_level=40, instance=inst)

        assert "(L" not in spawn.name, "a high-level boss should not be a bare archetype label"
        assert spawn.slug != "boss"


def test_boss_falls_back_to_the_label_when_nothing_is_catalogued(test_app, monkeypatch):
    """The genuine empty case still degrades to a label rather than crashing.

    Driven by forcing the identity lookup to come back empty, because that is
    the actual trigger. An empty *family* is not enough: the lookup deliberately
    widens from the dungeon's family to any family before giving up, so with any
    catalogue at all a boss finds something to be.
    """
    with test_app.app_context():
        _seed_boss_archetype()
        user = create_user("catalogspawn_4")
        inst = create_instance(user, seed=904)
        db.session.commit()
        monkeypatch.setattr(spawn_service, "_identity_for_archetype", lambda *a, **k: None)

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.BOSS, archetype="Boss", level=40)
        populate_spawn_stats(spawn, party_level=40, instance=inst)

        assert "(L" in spawn.name
        assert spawn.slug == "boss"


def test_ordinary_spawn_never_wears_a_bosses_name(test_app):
    """Otherwise a trash mob reads as the dungeon boss and unlocks extraction."""
    from app.services import boss_abilities

    with test_app.app_context():
        if not MonsterCatalog.query.filter_by(slug="test-tyrant").first():
            db.session.add(
                MonsterCatalog(
                    slug="test-tyrant",
                    name="Test Tyrant",
                    level_min=1,
                    level_max=10,
                    base_hp=900,
                    base_damage=60,
                    family="test",
                    rarity="boss",
                    boss=True,
                    xp_base=2000,
                )
            )
            db.session.commit()
        spawn_service._ELIGIBLE_CACHE.clear()
        if not EnemyArchetype.query.filter_by(archetype="Trash").first():
            db.session.add(
                EnemyArchetype(
                    archetype="Trash",
                    rank="Normal",
                    base_hp=25,
                    hp_per_level=10,
                    base_damage=4,
                    damage_per_level=2.0,
                    armor_class_base=10,
                    armor_class_per_level=0.3,
                    xp_base=15,
                    xp_per_level=5,
                    loot_multiplier=1.0,
                )
            )
            db.session.commit()

        monster = spawn_service.choose_archetype_monster(level=5, archetype_name="Trash", tier=1)

        assert monster["name"] != "Test Tyrant"
        assert boss_abilities.is_boss(monster) is False


def test_set_piece_prefers_the_dungeons_own_family(test_app):
    with test_app.app_context():
        _seed_boss_archetype()
        for fam in ("moss", "cinder"):
            if not MonsterCatalog.query.filter_by(slug=f"{fam}-thing").first():
                db.session.add(
                    MonsterCatalog(
                        slug=f"{fam}-thing",
                        name=f"{fam.title()} Thing",
                        level_min=1,
                        level_max=10,
                        base_hp=30,
                        base_damage=5,
                        family=fam,
                        rarity="common",
                        boss=False,
                        xp_base=10,
                    )
                )
        db.session.commit()
        spawn_service._ELIGIBLE_CACHE.clear()

        monster = spawn_service.choose_archetype_monster(level=3, archetype_name="Boss", tier=1, family="cinder")
        assert monster["name"] == "Cinder Thing"
