import uuid

from app import db
from app.models.entities import DungeonEntity
from app.models.hoard import Hoard
from app.services import extraction_service
from tests.factories import create_character, create_instance, create_user


def _full_clear_instance(user, seed):
    inst = create_instance(user, seed=seed)
    inst.extraction_available = True  # no early-extraction penalty
    inst.bosses_total = 1
    inst.bosses_defeated = 1
    db.session.commit()
    return inst


def _add_monster(inst):
    ent = DungeonEntity(
        user_id=inst.user_id,
        instance_id=inst.id,
        seed=inst.seed,
        type="monster",
        slug="orc",
        name="Orc",
        x=5,
        y=5,
        z=0,
    )
    db.session.add(ent)
    db.session.commit()
    return ent


def test_is_full_clear_requires_boss_and_no_monsters():
    user = create_user("fc_flag_" + uuid.uuid4().hex[:8])
    inst = _full_clear_instance(user, seed=7001)

    # boss dead, no monster entities -> True
    assert extraction_service.is_full_clear(inst) is True

    # a monster entity remains -> False
    ent = _add_monster(inst)
    assert extraction_service.is_full_clear(inst) is False
    db.session.delete(ent)
    db.session.commit()

    # boss not yet defeated -> False
    inst.bosses_defeated = 0
    db.session.commit()
    assert extraction_service.is_full_clear(inst) is False

    # no boss generated (bosses_total=0) -> never trivially "won"
    inst.bosses_defeated = 0
    inst.bosses_total = 0
    db.session.commit()
    assert extraction_service.is_full_clear(inst) is False


def test_extract_party_applies_full_clear_bonus():
    user = create_user("fc_bonus_" + uuid.uuid4().hex[:8])
    inst = _full_clear_instance(user, seed=7002)
    char = create_character(user, name="Hero", items=[])
    char.gold = 400
    char.xp = 0
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok, msg
    assert result["full_clear"] is True
    # copper: 400 * 1.25 = 500 lands in the hoard and is reported
    assert result["secured"]["copper"] == 500
    hoard = Hoard.query.filter_by(user_id=user.id).first()
    assert hoard.copper == 500
    # xp: extraction_xp 50 * (1 + 0.5) = 75 granted
    db.session.refresh(char)
    assert char.xp == 75


def test_extract_party_non_full_clear_control():
    user = create_user("fc_ctrl_" + uuid.uuid4().hex[:8])
    inst = _full_clear_instance(user, seed=7003)
    _add_monster(inst)  # a monster remains -> not a full clear
    char = create_character(user, name="Hero", items=[])
    char.gold = 400
    char.xp = 0
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok, msg
    assert result["full_clear"] is False
    assert result["secured"]["copper"] == 400
    hoard = Hoard.query.filter_by(user_id=user.id).first()
    assert hoard.copper == 400
    db.session.refresh(char)
    assert char.xp == 50
