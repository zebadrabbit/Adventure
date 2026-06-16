"""Tests for the starter skill seeder."""

from app.models.skill import Skill, SkillTree
from app.seed_skills import seed_skills


def test_seed_skills_idempotent_and_valid():
    n1 = seed_skills(verbose=False)
    n2 = seed_skills(verbose=False)
    assert n1 == n2
    # No duplicate trees/skills after two runs
    assert SkillTree.query.filter_by(name="Combat").count() == 1
    assert Skill.query.filter_by(name="Toughness").count() == 1
    # Every skill references a real tree
    tree_ids = {t.id for t in SkillTree.query.all()}
    for s in Skill.query.all():
        assert s.tree_id in tree_ids


def test_seed_skills_resolves_prerequisites():
    seed_skills(verbose=False)
    second_wind = Skill.query.filter_by(name="Second Wind").first()
    toughness = Skill.query.filter_by(name="Toughness").first()
    assert second_wind is not None and toughness is not None
    assert second_wind.required_skill_id == toughness.id


def test_unlock_a_seeded_skill_end_to_end(client):
    import uuid

    from app import db
    from app.models.skill import CharacterSkill, CharacterTalentPoints
    from tests.factories import create_character, create_user

    seed_skills(verbose=False)
    toughness = Skill.query.filter_by(name="Toughness").first()

    user = create_user("e2e_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=[])
    char.level = 3
    db.session.add(CharacterTalentPoints(character_id=char.id, total_earned=2, total_spent=0, available=2))
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id

    resp = client.post(f"/api/characters/{char.id}/skills", json={"skill_id": toughness.id})
    assert resp.status_code == 200, resp.get_json()
    assert CharacterSkill.query.filter_by(character_id=char.id, skill_id=toughness.id).first() is not None
