"""Tests for using unlocked active skills as combat actions."""

import json
import uuid

from app import db
from app.models.skill import CharacterSkill, Skill, SkillTree
from app.services import combat_service
from tests.factories import create_character, create_user


def _make_skill(effect, skill_type="active", cooldown=None, mana_cost=0):
    tree = SkillTree(name="T_" + uuid.uuid4().hex[:6], max_tier=5)
    db.session.add(tree)
    db.session.flush()
    s = Skill(
        tree_id=tree.id,
        name="Sk_" + uuid.uuid4().hex[:6],
        description="x",
        tier=1,
        cost=1,
        effect_json=json.dumps(effect),
        skill_type=skill_type,
        cooldown=cooldown,
        mana_cost=mana_cost,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _user_char_with_skill(monkeypatch, effect, skill_type="active", mana_cost=0):
    import random as _random

    # Deterministic: player wins initiative (patch BEFORE start_session).
    monkeypatch.setattr(_random, "randint", lambda a, b: b)
    user = create_user("cs_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", items=[])
    skill = _make_skill(effect, skill_type=skill_type, mana_cost=mana_cost)
    db.session.add(CharacterSkill(character_id=char.id, skill_id=skill.id, skill_rank=1))
    db.session.commit()
    return user, char, skill


def _set_member_mana(session, mana):
    """Force the sole party member's current mana to a known value."""
    party = json.loads(session.party_snapshot_json)
    party["members"][0]["mana"] = mana
    party["members"][0]["current_mana"] = mana
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()


def test_active_damage_skill_hits_monster(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"damage": 7})
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    before = session.monster_hp
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("ok"), res
    assert res.get("damage") == 7
    fresh = combat_service._load_session(session.id)
    assert fresh.monster_hp == before - 7


def test_active_heal_skill_restores_caster(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"heal": 10})
    # damage 0 so the monster's post-action retaliation doesn't perturb caster HP.
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 0, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    party["members"][0]["hp"] = 5  # wounded
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("ok"), res
    assert res.get("heal") == 10  # healed 5 -> 15 (capped at max_hp)
    fresh = combat_service._load_session(session.id)
    members = json.loads(fresh.party_snapshot_json)["members"]
    # Net HP is well above the wounded 5 (a minimum-1 monster retaliation may nick it).
    assert members[0]["hp"] > 5


def test_locked_skill_rejected(monkeypatch):
    import random as _random

    monkeypatch.setattr(_random, "randint", lambda a, b: b)
    user = create_user("cs2_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", items=[])
    skill = _make_skill({"damage": 5})  # exists but NOT unlocked for char
    db.session.commit()
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("error") == "skill_not_unlocked"


def test_passive_skill_not_castable(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"con": 2}, skill_type="passive")
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("error") == "not_active_skill"


def test_cast_rejected_when_not_enough_mana(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"spell_damage": 8}, mana_cost=10)
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 0, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    _set_member_mana(session, 4)  # can't afford 10
    before = session.monster_hp
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("error") == "not_enough_mana"
    assert res.get("required") == 10
    assert res.get("mana") == 4
    # Effect NOT applied.
    fresh = combat_service._load_session(session.id)
    assert fresh.monster_hp == before


def test_cast_deducts_mana(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"spell_damage": 8}, mana_cost=6)
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 0, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    _set_member_mana(session, 20)
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("ok"), res
    assert res.get("mana") == 14  # 20 - 6
    fresh = combat_service._load_session(session.id)
    members = json.loads(fresh.party_snapshot_json)["members"]
    assert members[0]["mana"] == 14
    # Log line notes the cost.
    assert any("(-6 mana)" in e.get("m", "") for e in json.loads(fresh.log_json or "[]"))


def test_zero_cost_skill_unaffected_by_mana(monkeypatch):
    user, char, skill = _user_char_with_skill(monkeypatch, {"damage": 7}, mana_cost=0)
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 0, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    _set_member_mana(session, 0)  # no mana, but skill is free
    res = combat_service.player_cast_skill(session.id, user.id, session.version, skill.id, actor_id=char.id)
    assert res.get("ok"), res
    assert res.get("damage") == 7
    fresh = combat_service._load_session(session.id)
    members = json.loads(fresh.party_snapshot_json)["members"]
    assert members[0]["mana"] == 0  # unchanged
    # No mana suffix in the log.
    assert not any("mana)" in e.get("m", "") for e in json.loads(fresh.log_json or "[]"))


def test_seed_mana_costs():
    from app.seed_skills import seed_skills

    seed_skills(verbose=False)
    # Caster-tree tier-1 active costs 4.
    firebolt = Skill.query.filter_by(name="Firebolt").first()
    assert firebolt is not None
    assert firebolt.mana_cost == 4
    # Caster-tree tier-2 active costs 8.
    frost = Skill.query.filter_by(name="Frost Lance").first()
    assert frost.mana_cost == 8
    # Physical-tree active is free.
    power_strike = Skill.query.filter_by(name="Power Strike").first()
    assert power_strike.mana_cost == 0
    # Passive is free.
    focus = Skill.query.filter_by(name="Focus").first()
    assert focus.mana_cost == 0
