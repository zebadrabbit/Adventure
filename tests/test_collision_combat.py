"""Tests for the shared monster-at-player-tile collision-combat trigger."""

from app import db
from app.dungeon.api_helpers.encounters import trigger_collision_combat
from app.models.entities import DungeonEntity
from tests.factories import create_instance, create_user


def test_trigger_collision_combat_starts_combat_and_removes_entity(test_app):
    with test_app.app_context():
        user = create_user("collision_" + "1")
        inst = create_instance(user, seed=555)
        inst.pos_x, inst.pos_y, inst.pos_z = 3, 4, 0
        db.session.commit()

        entity = DungeonEntity(
            user_id=user.id,
            instance_id=inst.id,
            seed=inst.seed,
            type="monster",
            slug="test-grunt",
            name="Test Grunt",
            x=3,
            y=4,
            z=0,
            hp_current=20,
            data='{"hp": 20, "damage": 4, "speed": 8}',
        )
        db.session.add(entity)
        db.session.commit()
        entity_id = entity.id

        result = trigger_collision_combat(inst)

        assert result is not None
        assert result["monster"]["slug"] == "test-grunt"
        assert "combat_id" in result
        assert db.session.get(DungeonEntity, entity_id) is None


def test_trigger_collision_combat_returns_none_when_nothing_there(test_app):
    with test_app.app_context():
        user = create_user("collision_" + "2")
        inst = create_instance(user, seed=556)
        inst.pos_x, inst.pos_y, inst.pos_z = 1, 1, 0
        db.session.commit()

        assert trigger_collision_combat(inst) is None


def _mob(user, inst, slug, x, y):
    ent = DungeonEntity(
        user_id=user.id,
        instance_id=inst.id,
        seed=inst.seed,
        type="monster",
        slug=slug,
        name=slug.title(),
        x=x,
        y=y,
        z=0,
        hp_current=20,
        data='{"hp": 20, "damage": 4, "speed": 8}',
    )
    db.session.add(ent)
    return ent


def test_the_neighbouring_pack_joins_the_fight(test_app, monkeypatch):
    """Walking into one monster of a cluster fights the cluster.

    Spawning already groups monsters, so resolving only the one you stepped on
    turned what looks like four-on-three into three separate four-on-ones --
    the "its not fun fighting 1 mob at a time" complaint, structurally.

    combat_pack_max ships at 1, so this opts in explicitly: the engine is what
    is under test here, not the balance decision of whether to switch it on.
    """
    from app.dungeon.api_helpers import encounters
    from app.models.models import CombatSession
    from app.services import combat_service

    monkeypatch.setattr(encounters, "combat_pack_cap", lambda: 6)

    with test_app.app_context():
        user = create_user("collision_pack")
        inst = create_instance(user, seed=556)
        inst.pos_x, inst.pos_y, inst.pos_z = 5, 5, 0
        db.session.commit()

        trigger = _mob(user, inst, "trigger-grunt", 5, 5)
        adjacent = _mob(user, inst, "adjacent-grunt", 5, 6)
        diagonal = _mob(user, inst, "diagonal-grunt", 6, 6)
        far = _mob(user, inst, "far-grunt", 12, 12)
        db.session.commit()
        ids = (trigger.id, adjacent.id, diagonal.id, far.id)

        result = trigger_collision_combat(inst)

        session = db.session.get(CombatSession, result["combat_id"])
        slugs = {m["slug"] for m in combat_service._monsters(session)}
        assert slugs == {"trigger-grunt", "adjacent-grunt", "diagonal-grunt"}, slugs

        # Everyone in the fight leaves the map; the distant one stays put.
        assert db.session.get(DungeonEntity, ids[0]) is None
        assert db.session.get(DungeonEntity, ids[1]) is None
        assert db.session.get(DungeonEntity, ids[2]) is None
        assert db.session.get(DungeonEntity, ids[3]) is not None, "a monster across the map was dragged in"

        # The trigger is still what the caller is told about.
        assert result["monster"]["slug"] == "trigger-grunt"


def test_a_lone_monster_is_still_a_solo_fight(test_app, monkeypatch):
    from app.dungeon.api_helpers import encounters
    from app.models.models import CombatSession
    from app.services import combat_service

    monkeypatch.setattr(encounters, "combat_pack_cap", lambda: 6)

    with test_app.app_context():
        user = create_user("collision_lone")
        inst = create_instance(user, seed=557)
        inst.pos_x, inst.pos_y, inst.pos_z = 2, 2, 0
        db.session.commit()
        _mob(user, inst, "lonely-grunt", 2, 2)
        db.session.commit()

        result = trigger_collision_combat(inst)

        session = db.session.get(CombatSession, result["combat_id"])
        assert len(combat_service._monsters(session)) == 1


def test_the_pack_pull_in_is_off_by_default(test_app):
    """combat_pack_max ships at 1: you fight the monster you stepped on, and its
    neighbours wait their turn. The engine can field six, but switching it on
    wipes the party in tests/test_full_run_e2e.py -- every monster is costed for
    a solo appearance -- so it is a balance decision, deliberately not taken."""
    from app.models.models import CombatSession
    from app.services import combat_service

    with test_app.app_context():
        user = create_user("collision_default")
        inst = create_instance(user, seed=558)
        inst.pos_x, inst.pos_y, inst.pos_z = 7, 7, 0
        db.session.commit()
        _mob(user, inst, "trigger-grunt", 7, 7)
        neighbour = _mob(user, inst, "neighbour-grunt", 7, 8)
        db.session.commit()
        neighbour_id = neighbour.id

        result = trigger_collision_combat(inst)

        session = db.session.get(CombatSession, result["combat_id"])
        assert len(combat_service._monsters(session)) == 1
        assert db.session.get(DungeonEntity, neighbour_id) is not None, "the neighbour was dragged in"
