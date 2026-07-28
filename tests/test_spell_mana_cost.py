"""Casting a spell always costs mana, hit or miss.

Playtest finding (2026-07-27): "i dont think spell casting is using mana".

player_cast_spell deducted the cost from the in-memory party dict and then only
wrote `session.party_snapshot_json` on the path where the spell *hit*. The
fizzle (natural 1) and miss paths committed and returned without re-serialising
the party, so the deduction was discarded -- a missed spell was free, which at
low level (where misses are common) reads as "casting doesn't use mana".
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service

FIREBOLT_COST = 5


@pytest.fixture()
def mage(test_app):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="mana_mage").first()
    if not user:
        user = User(username="mana_mage", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Mana Mage",
        stats=json.dumps({"str": 10, "dex": 10, "int": 14, "con": 10, "mana": 40}),
        gear="{}",
        items="[]",
        level=1,
    )
    db.session.add(char)
    db.session.commit()
    return user


def _monster():
    return {
        "slug": "mana-dummy",
        "name": "Mana Dummy",
        "level": 1,
        "hp": 500,
        "damage": 0,
        "armor": 0,
        "speed": 1,
        "xp": 0,
        "resistances": {},
    }


def _cast(user, monkeypatch, rolls):
    """Start a session with scripted rolls and cast firebolt once.

    rolls: initiative (player, monster) then the spell's accuracy roll, then any
    damage dice.
    """
    it = iter(rolls)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    session = combat_service.start_session(user.id, _monster())
    initiative = json.loads(session.initiative_json)
    actor_id = initiative[session.active_index]["id"]

    before = json.loads(session.party_snapshot_json)["members"][0]["mana"]
    result = combat_service.player_cast_spell(session.id, user.id, session.version, "firebolt", actor_id=actor_id)

    fresh = combat_service._load_session(session.id)
    after = json.loads(fresh.party_snapshot_json)["members"][0]["mana"]
    return before, after, result


def test_a_hit_costs_mana(mage, monkeypatch):
    before, after, result = _cast(mage, monkeypatch, [10, 1, 15, 4, 5])
    assert result.get("ok")
    assert not result.get("miss")
    assert after == before - FIREBOLT_COST


def test_a_miss_still_costs_mana(mage, monkeypatch):
    """The regression: the spell was cast, so the mana is spent."""
    # acc_roll 2 with monster evasion 10 and int 14 would hit, so use a monster
    # the roll cannot beat -- simplest is the natural-1 fizzle below plus this
    # explicit miss via a high-armour dummy.
    it = iter([10, 1, 2])
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    monster = _monster()
    monster["armor"] = 60  # evasion 70; int(14) + roll(2) cannot reach it
    session = combat_service.start_session(mage.id, monster)
    initiative = json.loads(session.initiative_json)
    actor_id = initiative[session.active_index]["id"]
    before = json.loads(session.party_snapshot_json)["members"][0]["mana"]

    result = combat_service.player_cast_spell(session.id, mage.id, session.version, "firebolt", actor_id=actor_id)

    assert result.get("ok") and result.get("miss"), result
    after = json.loads(combat_service._load_session(session.id).party_snapshot_json)["members"][0]["mana"]
    assert after == before - FIREBOLT_COST, "a missed spell must still burn the mana"


def test_a_fizzle_still_costs_mana(mage, monkeypatch):
    """Natural 1 fizzles -- the spell was still cast."""
    before, after, result = _cast(mage, monkeypatch, [10, 1, 1])
    assert result.get("ok") and result.get("miss"), result
    assert after == before - FIREBOLT_COST, "a fizzled spell must still burn the mana"


def test_casting_without_enough_mana_is_refused_and_costs_nothing(mage, monkeypatch):
    it = iter([10, 1])
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    session = combat_service.start_session(mage.id, _monster())
    party = json.loads(session.party_snapshot_json)
    party["members"][0]["mana"] = 1
    party["members"][0]["current_mana"] = 1
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()
    initiative = json.loads(session.initiative_json)
    actor_id = initiative[session.active_index]["id"]

    result = combat_service.player_cast_spell(session.id, mage.id, session.version, "firebolt", actor_id=actor_id)

    assert result.get("error") == "no_mana"
    after = json.loads(combat_service._load_session(session.id).party_snapshot_json)["members"][0]["mana"]
    assert after == 1, "a refused cast must not spend anything"


def test_repeated_casting_drains_the_pool(mage, monkeypatch):
    """Mana is a resource across a fight, not just within one action."""
    monkeypatch.setattr(random, "randint", lambda a, b: 12)
    session = combat_service.start_session(mage.id, _monster())
    initiative = json.loads(session.initiative_json)
    player_ids = [e["id"] for e in initiative if e["type"] == "player"]
    actor_id = player_ids[0]
    start = json.loads(session.party_snapshot_json)["members"][0]["mana"]

    casts = 0
    for _ in range(4):
        fresh = combat_service._load_session(session.id)
        if fresh.status != "active":
            break
        init = json.loads(fresh.initiative_json)
        if init[fresh.active_index].get("id") != actor_id:
            fresh.active_index = next(i for i, e in enumerate(init) if e.get("id") == actor_id)
            db.session.commit()
            fresh = combat_service._load_session(session.id)
        res = combat_service.player_cast_spell(session.id, mage.id, fresh.version, "firebolt", actor_id=actor_id)
        if res.get("ok"):
            casts += 1

    assert casts >= 2, "test should have landed several casts"
    end = json.loads(combat_service._load_session(session.id).party_snapshot_json)["members"][0]["mana"]
    assert end == start - casts * FIREBOLT_COST
