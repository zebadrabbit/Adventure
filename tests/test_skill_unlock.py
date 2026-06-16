"""Tests for the skill-unlock endpoint: spend talent points, validate auth."""

import uuid

from app import db
from app.models.skill import CharacterSkill, CharacterTalentPoints, Skill, SkillTree
from tests.factories import create_character, create_user


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def _setup_skill(cost=1, required_level=1):
    tree = SkillTree(name="T_" + uuid.uuid4().hex[:6], max_tier=5)
    db.session.add(tree)
    db.session.flush()
    skill = Skill(
        tree_id=tree.id,
        name="S_" + uuid.uuid4().hex[:6],
        description="x",
        tier=1,
        required_level=required_level,
        cost=cost,
        effect_json="{}",
        skill_type="passive",
    )
    db.session.add(skill)
    db.session.flush()
    return skill


def _char_with_points(points, level=5):
    user = create_user("sk_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=[])
    char.level = level
    db.session.add(CharacterTalentPoints(character_id=char.id, total_earned=points, total_spent=0, available=points))
    db.session.commit()
    return user, char


def test_unlock_succeeds_and_spends_points(client):
    user, char = _char_with_points(2)
    skill = _setup_skill(cost=1)
    db.session.commit()
    _login(client, user)
    resp = client.post(f"/api/characters/{char.id}/skills", json={"skill_id": skill.id})
    assert resp.status_code == 200, resp.get_json()
    assert CharacterSkill.query.filter_by(character_id=char.id, skill_id=skill.id).first() is not None
    tp = CharacterTalentPoints.query.filter_by(character_id=char.id).first()
    assert tp.available == 1
    assert tp.total_spent == 1


def test_unlock_rejects_other_users_character(client):
    user, char = _char_with_points(2)
    skill = _setup_skill(cost=1)
    attacker = create_user("atk_" + uuid.uuid4().hex[:8])
    db.session.commit()
    _login(client, attacker)
    resp = client.post(f"/api/characters/{char.id}/skills", json={"skill_id": skill.id})
    assert resp.status_code in (403, 404), resp.get_json()
    assert CharacterSkill.query.filter_by(character_id=char.id, skill_id=skill.id).first() is None


def test_unlock_rejects_insufficient_points(client):
    user, char = _char_with_points(0)
    skill = _setup_skill(cost=2)
    db.session.commit()
    _login(client, user)
    resp = client.post(f"/api/characters/{char.id}/skills", json={"skill_id": skill.id})
    assert resp.status_code == 400
