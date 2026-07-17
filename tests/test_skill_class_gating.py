"""Tests for class-gated skill trees: SkillTree.allows_class and the
class check enforced server-side by the unlock endpoint."""

import json

from app import db
from app.models.models import Character
from app.models.skill import CharacterSkill, CharacterTalentPoints, Skill, SkillTree
from app.seed_skills import seed_skills


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def test_allows_class():
    t = SkillTree(name="x", class_requirement="mage,sorcerer")
    assert t.allows_class("sorcerer") and t.allows_class("MAGE")
    assert not t.allows_class("fighter") and not t.allows_class(None)
    u = SkillTree(name="y", class_requirement=None)
    assert u.allows_class("fighter") and u.allows_class(None)


def test_allows_class_whitespace_tolerant():
    t = SkillTree(name="z", class_requirement="mage, sorcerer , warlock")
    assert t.allows_class("sorcerer")
    assert t.allows_class(" Warlock ".strip())


def test_unlock_rejects_wrong_class(auth_client, test_app):
    seed_skills(verbose=False)

    # auth_client's fixture user "tester" owns character "Hero"; force its
    # class to fighter (Arcana requires mage/sorcerer) and give it points.
    char = Character.query.filter_by(name="Hero").first()
    stats = json.loads(char.stats) if char.stats else {}
    stats["class"] = "fighter"
    char.stats = json.dumps(stats)
    char.level = 5
    db.session.add(char)

    tp = CharacterTalentPoints.query.filter_by(character_id=char.id).first()
    if not tp:
        tp = CharacterTalentPoints(character_id=char.id, total_earned=5, total_spent=0, available=5)
        db.session.add(tp)
    else:
        tp.available = 5
    db.session.commit()

    arcana_tree = SkillTree.query.filter_by(name="Arcana").first()
    arcana_skill = Skill.query.filter_by(tree_id=arcana_tree.id, name="Focus").first()

    combat_tree = SkillTree.query.filter_by(name="Combat").first()
    combat_skill = Skill.query.filter_by(tree_id=combat_tree.id, name="Toughness").first()

    resp = auth_client.post(f"/api/characters/{char.id}/skills", json={"skill_id": arcana_skill.id})
    assert resp.status_code == 403, resp.get_json()
    body = resp.get_json()
    assert "Arcana" in body["error"]
    assert "mage" in body["error"] and "sorcerer" in body["error"]
    assert CharacterSkill.query.filter_by(character_id=char.id, skill_id=arcana_skill.id).first() is None

    # A universal (Combat) skill still unlocks fine for the same character.
    resp2 = auth_client.post(f"/api/characters/{char.id}/skills", json={"skill_id": combat_skill.id})
    assert resp2.status_code == 200, resp2.get_json()
    assert CharacterSkill.query.filter_by(character_id=char.id, skill_id=combat_skill.id).first() is not None
