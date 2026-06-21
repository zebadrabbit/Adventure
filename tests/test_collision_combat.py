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
