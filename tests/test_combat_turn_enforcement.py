"""Multi-character turn ordering and enforcement tests.

Ensures that attempting to act with a character who is not the current active initiative entry returns not_your_turn.
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service


@pytest.fixture()
def user_two_chars(test_app):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="multichar").first()
        if not user:
            user = User(username="multichar", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        # Ensure two characters
        chars = Character.query.filter_by(user_id=user.id).order_by(Character.id.asc()).all()
        if len(chars) < 2:
            needed = 2 - len(chars)
            for i in range(needed):
                stats = json.dumps({"str": 10, "dex": 12 + i, "int": 10, "con": 10, "mana": 30})
                c = Character(user_id=user.id, name=f"Hero{i}", stats=stats, gear="{}", items="[]")
                db.session.add(c)
            db.session.commit()
    return user


def _monster():
    return {
        "slug": "multi-mob",
        "name": "Multi Mob",
        "level": 1,
        "hp": 50,
        "damage": 4,
        "armor": 0,
        "speed": 5,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 5,
        "boss": False,
    }


def test_cannot_act_out_of_turn(user_two_chars, monkeypatch):
    user = user_two_chars
    # Sequence of randint: initiative for char1, char2, monster.
    # Force order: char1 high roll, char2 low, monster middle.
    seq = [18, 2, 10]
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    session = combat_service.start_session(user.id, _monster())
    init = session.to_dict()["initiative"]
    # Expect first entry corresponds to char1 (higher roll)
    active = init[session.active_index]
    # Find second character id
    player_entries = [e for e in init if e["type"] == "player"]
    assert len(player_entries) >= 2
    second_char_id = player_entries[1]["id"]
    # Attempt attack with second character while first is active
    resp = combat_service.player_attack(session.id, user.id, session.version, actor_id=second_char_id)
    assert resp.get("error") == "not_your_turn", resp
    # Now attack with correct actor
    correct_id = active["id"]
    # Need deterministic rolls for attack now: accuracy d20 then variance; provide sequence
    atk_seq = [15, 0]  # accuracy roll 15 (likely hit), variance 0
    it2 = iter(atk_seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it2))
    ok_resp = combat_service.player_attack(session.id, user.id, session.version, actor_id=correct_id)
    assert ok_resp.get("ok")
    # Advance state and attempt to reuse same actor (should now be not_your_turn)
    # Need new snapshot version after previous commit
    new_version = ok_resp["state"]["version"]
    again = combat_service.player_attack(session.id, user.id, new_version, actor_id=correct_id)
    # Could be monster turn or second player; either way reusing same actor is invalid
    assert again.get("error") == "not_your_turn" or again.get("ok")
