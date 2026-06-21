"""Tests for GET /api/characters/<id>/skills."""

import json
import uuid

from app import db
from app.models.skill import CharacterSkill, Skill, SkillTree
from tests.factories import create_character, create_user


def _setup_unlocked_skill(char_id, skill_type="active", cooldown=12):
    tree = SkillTree(name="T_" + uuid.uuid4().hex[:6], max_tier=5)
    db.session.add(tree)
    db.session.flush()
    skill = Skill(
        tree_id=tree.id,
        name="S_" + uuid.uuid4().hex[:6],
        description="x",
        tier=1,
        required_level=1,
        cost=1,
        effect_json=json.dumps({"damage": 10}),
        skill_type=skill_type,
        cooldown=cooldown,
    )
    db.session.add(skill)
    db.session.flush()
    cs = CharacterSkill(character_id=char_id, skill_id=skill.id)
    db.session.add(cs)
    db.session.commit()
    return skill


def test_get_character_skills_includes_cooldown(client):
    user = create_user("skapi_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=[])
    db.session.commit()
    skill = _setup_unlocked_skill(char.id, cooldown=12)

    resp = client.get(f"/api/characters/{char.id}/skills")
    assert resp.status_code == 200
    body = resp.get_json()
    match = next(s for s in body if s["skill_id"] == skill.id)
    assert match["cooldown"] == 12


def test_get_character_skills_cooldown_null_when_unset(client):
    user = create_user("skapi2_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero2", items=[])
    db.session.commit()
    skill = _setup_unlocked_skill(char.id, cooldown=None)

    resp = client.get(f"/api/characters/{char.id}/skills")
    body = resp.get_json()
    match = next(s for s in body if s["skill_id"] == skill.id)
    assert match["cooldown"] is None
