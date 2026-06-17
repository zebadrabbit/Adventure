"""Tests for passive skill effect aggregation + combat stat integration."""

import json
import uuid

from app import db
from app.models.skill import CharacterSkill, Skill, SkillTree
from app.services import combat_service
from app.services.skill_effects import passive_bonuses
from tests.factories import create_character, create_user


def _skill(effect, skill_type="passive"):
    tree = SkillTree(name="T_" + uuid.uuid4().hex[:6], max_tier=5)
    db.session.add(tree)
    db.session.flush()
    s = Skill(
        tree_id=tree.id,
        name="S_" + uuid.uuid4().hex[:6],
        description="x",
        tier=1,
        cost=1,
        effect_json=json.dumps(effect),
        skill_type=skill_type,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _char():
    user = create_user("se_" + uuid.uuid4().hex[:8])
    return create_character(user, name="H", items=[])


def test_passive_bonuses_sums_unlocked_passives():
    char = _char()
    s1 = _skill({"con": 2})
    s2 = _skill({"con": 1, "str": 3})
    db.session.add(CharacterSkill(character_id=char.id, skill_id=s1.id, skill_rank=1))
    db.session.add(CharacterSkill(character_id=char.id, skill_id=s2.id, skill_rank=1))
    db.session.commit()
    assert passive_bonuses(char.id) == {"con": 3, "str": 3}


def test_active_skills_excluded():
    char = _char()
    active = _skill({"damage": 5}, skill_type="active")
    db.session.add(CharacterSkill(character_id=char.id, skill_id=active.id, skill_rank=1))
    db.session.commit()
    assert passive_bonuses(char.id) == {}


def test_locked_skills_not_counted():
    char = _char()
    _skill({"int": 5})  # exists but not unlocked for this char
    db.session.commit()
    assert passive_bonuses(char.id) == {}


def test_passive_bonus_raises_derived_combat_stat():
    char = _char()
    # baseline derived CON
    base = combat_service._derive_stats(char)
    s = _skill({"con": 4})
    db.session.add(CharacterSkill(character_id=char.id, skill_id=s.id, skill_rank=1))
    db.session.commit()
    after = combat_service._derive_stats(char)
    # max_hp = ... + CON*2; +4 CON => +8 max_hp
    assert after["max_hp"] == base["max_hp"] + 8
