"""Spell outcome tests covering miss (nat1), crit (nat20), and resistance application.

Relies on monkeypatching random.randint sequence. We craft sequences so that:
- Initiative rolls first (for each party member + monster). We only need stable values.
- Then spell accuracy d20 roll is consumed.
- Then damage dice (2d8) if the spell hits.

We'll supply sequences accordingly.
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service


@pytest.fixture()
def user_with_char(test_app):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="spelltester").first()
        if not user:
            user = User(username="spelltester", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        char = Character.query.filter_by(user_id=user.id).first()
        if not char:
            cstats = json.dumps({"str": 10, "dex": 10, "int": 14, "con": 10, "mana": 40})
            char = Character(user_id=user.id, name="Mage", stats=cstats, gear="{}", items="[]")
            db.session.add(char)
            db.session.commit()
    return user


def _monster(resist=None):
    return {
        "slug": "spell-mob",
        "name": "Spell Dummy",
        "level": 1,
        "hp": 120,
        "damage": 4,
        "armor": 0,
        "speed": 5,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": resist or {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 5,
        "boss": False,
    }


def _start(user_id, monkeypatch, seq):
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    session = combat_service.start_session(user_id, _monster())
    return session


def test_firebolt_fizzle_natural_one(user_with_char, monkeypatch):
    user = user_with_char
    # Sequence: initiative rolls (player, monster) then spell accuracy=1
    # Initiative needs two d20-like calls: player speed+roll, monster speed+roll
    seq = [10, 10, 1]  # initiative player, monster, then acc_roll=1
    session = _start(user.id, monkeypatch, seq)
    init = session.to_dict()["initiative"]
    actor_id = init[session.active_index]["id"]
    resp = combat_service.player_cast_spell(session.id, user.id, session.version, "firebolt", actor_id=actor_id)
    assert resp.get("ok")
    assert resp.get("miss"), resp
    # Mana spent even on fizzle; ensure damage not applied
    st = resp["state"]
    assert st["monster_hp"] == session.monster_hp  # monster_hp not decremented inside returned state snapshot


def test_firebolt_crit_natural_twenty(user_with_char, monkeypatch):
    user = user_with_char
    # Sequence: initiative (player, monster) then acc_roll=20 then damage dice (e.g., 4,5)
    seq = [10, 10, 20, 4, 5]
    session = _start(user.id, monkeypatch, seq)
    monster_hp_before = session.monster_hp
    init = session.to_dict()["initiative"]
    actor_id = init[session.active_index]["id"]
    resp = combat_service.player_cast_spell(session.id, user.id, session.version, "firebolt", actor_id=actor_id)
    assert resp.get("ok")
    assert resp.get("crit") is True
    dmg = resp.get("damage")
    # Base damage pre-crit: roll(4+5)=9 + int*0.6 (14*0.6=8.4 -> int() 8) => 17, crit 1.5x => 25 (int)
    assert dmg == 25, dmg
    st = resp["state"]
    assert st["monster_hp"] == monster_hp_before - dmg


def test_firebolt_fire_resistance_halves_damage(user_with_char, monkeypatch):
    user = user_with_char

    # Create monster with 50% fire resistance via resistances mapping
    def start_with_resist(seq):
        it = iter(seq)
        monkeypatch.setattr(random, "randint", lambda a, b: next(it))
        session = combat_service.start_session(user.id, _monster(resist={"fire": 0.5}))
        return session

    seq = [10, 10, 10, 3, 5]  # initiative player, monster, acc_roll=10 (hit), damage dice 3 & 5
    session = start_with_resist(seq)
    monster_hp_before = session.monster_hp
    actor_id = session.to_dict()["initiative"][session.active_index]["id"]
    resp = combat_service.player_cast_spell(session.id, user.id, session.version, "firebolt", actor_id=actor_id)
    assert resp.get("ok")
    dmg = resp.get("damage")
    # Raw (before resist) would be (3+5)=8 + INT(14)*0.6=8 =>16, resist 50% => 8 (int)
    assert dmg == 8, dmg
    st = resp["state"]
    assert st["monster_hp"] == monster_hp_before - dmg
