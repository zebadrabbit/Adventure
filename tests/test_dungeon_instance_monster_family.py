"""Tests for DungeonInstance.monster_family (the per-instance enemy
theme column)."""

from app import db
from app.models.dungeon_instance import DungeonInstance
from tests.factories import create_user


def test_monster_family_defaults_to_none(test_app):
    with test_app.app_context():
        user = create_user("themecol_1")
        inst = DungeonInstance(user_id=user.id, seed=111, pos_x=0, pos_y=0, pos_z=0)
        db.session.add(inst)
        db.session.commit()

        assert inst.monster_family is None


def test_monster_family_can_be_set_and_persisted(test_app):
    with test_app.app_context():
        user = create_user("themecol_2")
        inst = DungeonInstance(user_id=user.id, seed=112, pos_x=0, pos_y=0, pos_z=0, monster_family="undead")
        db.session.add(inst)
        db.session.commit()
        inst_id = inst.id

        db.session.expire_all()
        reloaded = db.session.get(DungeonInstance, inst_id)
        assert reloaded.monster_family == "undead"
