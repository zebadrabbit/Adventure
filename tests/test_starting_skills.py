"""Tests for grant_starting_skill: new characters start with a free tier-1 active."""

import uuid

import pytest

from app import db
from app.models.skill import CharacterSkill, CharacterTalentPoints, SkillTree
from app.seed_skills import seed_skills
from app.services import progression
from tests.factories import create_character, create_user

# Canonical class -> expected starting skill name, per the content plan.
EXPECTED_STARTING_SKILL = {
    "fighter": "Crushing Blow",
    "barbarian": "Crushing Blow",
    "monk": "Crushing Blow",
    "mage": "Firebolt",
    "sorcerer": "Firebolt",
    "cleric": "Smite",
    "paladin": "Smite",
    "druid": "Thorn Lash",
    "ranger": "Thorn Lash",
    "rogue": "Backstab",
    "bard": "Backstab",
    "warlock": "Eldritch Bolt",
}


@pytest.fixture(autouse=True)
def _ensure_tables(test_app):
    with test_app.app_context():
        db.create_all()


def _char(char_class):
    user = create_user("ss_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", char_class=char_class, items=[])
    return char


@pytest.mark.parametrize("char_class,expected_name", sorted(EXPECTED_STARTING_SKILL.items()))
def test_grants_expected_class_skill(char_class, expected_name):
    seed_skills(verbose=False)
    char = _char(char_class)

    skill = progression.grant_starting_skill(char)

    assert skill is not None
    assert skill.name == expected_name

    cs = CharacterSkill.query.filter_by(character_id=char.id).all()
    assert len(cs) == 1
    assert cs[0].skill_id == skill.id
    assert cs[0].skill_rank == 1

    assert skill.skill_type == "active"
    assert skill.tier == 1

    tree = db.session.get(SkillTree, skill.tree_id)
    assert tree.allows_class(char_class)

    tp = CharacterTalentPoints.query.filter_by(character_id=char.id).first()
    assert tp is None or tp.total_spent == 0


def test_idempotent_second_call_grants_nothing_new():
    seed_skills(verbose=False)
    char = _char("fighter")

    first = progression.grant_starting_skill(char)
    second = progression.grant_starting_skill(char)

    assert first is not None
    assert second is None
    assert CharacterSkill.query.filter_by(character_id=char.id).count() == 1


def test_unknown_class_falls_back_to_universal_combat_tree():
    seed_skills(verbose=False)
    char = _char("fighter")
    import json as _json

    stats = _json.loads(char.stats)
    stats["class"] = "totally-unknown-class"
    char.stats = _json.dumps(stats)
    db.session.commit()

    skill = progression.grant_starting_skill(char)

    assert skill is not None
    tree = db.session.get(SkillTree, skill.tree_id)
    assert tree.name == "Combat"
    assert skill.skill_type == "active"
    assert skill.tier == 1


def test_no_seeded_skills_returns_none_without_raising():
    # No seed_skills() call: fresh test DB has no skill trees/skills.
    char = _char("fighter")

    skill = progression.grant_starting_skill(char)

    assert skill is None
    assert CharacterSkill.query.filter_by(character_id=char.id).count() == 0
