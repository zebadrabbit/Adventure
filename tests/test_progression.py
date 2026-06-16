"""Tests for character progression: XP -> levels -> talent points."""

import uuid

from app import db
from app.models.skill import CharacterTalentPoints
from app.services import progression
from tests.factories import create_character, create_user


def _char(level=1, xp=0):
    user = create_user("prog_" + uuid.uuid4().hex[:8])
    c = create_character(user, name="Hero", items=[])
    c.level = level
    c.xp = xp
    db.session.commit()
    return c


def test_level_for_xp_thresholds():
    # D&D-5e cumulative table: L2=300, L3=900, L20=355000
    assert progression.level_for_xp(0) == 1
    assert progression.level_for_xp(299) == 1
    assert progression.level_for_xp(300) == 2
    assert progression.level_for_xp(899) == 2
    assert progression.level_for_xp(900) == 3
    assert progression.level_for_xp(355000) == 20


def test_grant_xp_no_level_change_below_threshold():
    c = _char(level=1, xp=0)
    result = progression.grant_xp(c, 100)
    db.session.commit()
    assert c.xp == 100
    assert c.level == 1
    assert result["levels_gained"] == 0
    assert result["talent_points_awarded"] == 0


def test_grant_xp_levels_up_and_awards_talent_points():
    c = _char(level=1, xp=0)
    result = progression.grant_xp(c, 300)  # exactly L2
    db.session.commit()
    assert c.level == 2
    assert result["levels_gained"] == 1
    assert result["talent_points_awarded"] == 1
    tp = CharacterTalentPoints.query.filter_by(character_id=c.id).first()
    assert tp is not None
    assert tp.available == 1
    assert tp.total_earned == 1


def test_grant_xp_multi_level_jump():
    c = _char(level=1, xp=0)
    result = progression.grant_xp(c, 900)  # L3 (skips through L2)
    db.session.commit()
    assert c.level == 3
    assert result["levels_gained"] == 2
    tp = CharacterTalentPoints.query.filter_by(character_id=c.id).first()
    assert tp.available == 2


def test_grant_xp_negative_is_ignored():
    c = _char(level=2, xp=300)
    progression.grant_xp(c, -50)
    db.session.commit()
    assert c.xp == 300
    assert c.level == 2


def test_extraction_grants_xp():
    from app.models.models import GameConfig
    from app.services import extraction_service
    from tests.factories import create_instance

    GameConfig.set("progression", '{"extraction_xp": 50}')
    user = create_user("progx_" + uuid.uuid4().hex[:8])
    inst = create_instance(user, seed=515151)
    inst.extraction_available = True  # no early-extraction penalty
    char = create_character(user, name="Extractor", items=[])
    char.xp = 0
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, _msg, _result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok
    db.session.refresh(char)
    assert char.xp == 50
