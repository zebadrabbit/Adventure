"""Downed (hp<=0) characters must not be able to act.

player_attack already guards against this (skips the turn with an
"is unconscious" log line instead of executing the action). The other five
action handlers (flee, defend, use_item, cast_spell, cast_skill) historically
had no equivalent check at all.
"""

import json
import random

from app import db
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster():
    return {
        "slug": "unconscious-test-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": 500,
        "damage": 10,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 0,
        "boss": False,
    }


def _downed_session(test_app, monkeypatch):
    """Start a single-character combat session, then knock that character to 0 hp."""
    user = User(username=f"downed-{random.randint(1, 10**9)}", email=None)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    stats = json.dumps({"str": 14, "dex": 12, "int": 10, "con": 12, "mana": 40})
    char = Character(user_id=user.id, name="Faller", stats=stats, gear="{}", items="[]")
    db.session.add(char)
    db.session.commit()

    # Player acts first (high roll), monster low, so active_index starts on the player.
    init_seq = iter([20, 1])
    monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
    session = combat_service.start_session(user.id, _simple_monster())

    party = json.loads(session.party_snapshot_json)
    char_id = party["members"][0]["char_id"]
    party["members"][0]["hp"] = 0
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()
    return session, user, char_id


def test_player_flee_rejects_downed_character(test_app, monkeypatch):
    with test_app.app_context():
        session, user, char_id = _downed_session(test_app, monkeypatch)
        result = combat_service.player_flee(session.id, user.id, session.version, actor_id=char_id)
        # The single party member is downed (full wipe), so _check_end correctly ends
        # combat as a side effect — that's separate, correct existing behavior. What
        # this test asserts is that the flee logic itself never ran (no 50/50 roll, no
        # "flees successfully"/"attempt failed" log) — the character was skipped, not
        # processed as a flee attempt.
        assert result.get("skipped") is True, result
        log_messages = " ".join(e["m"] for e in result["state"]["log"])
        assert "flee" not in log_messages.lower(), log_messages


def test_player_defend_rejects_downed_character(test_app, monkeypatch):
    with test_app.app_context():
        session, user, char_id = _downed_session(test_app, monkeypatch)
        result = combat_service.player_defend(session.id, user.id, session.version, actor_id=char_id)
        assert result.get("skipped") is True, result
        session = combat_service._load_session(session.id)
        party = json.loads(session.party_snapshot_json)
        assert party["members"][0]["defending"] is False, "downed character must not gain the defend buff"


def test_player_use_item_rejects_downed_character(test_app, monkeypatch):
    with test_app.app_context():
        session, user, char_id = _downed_session(test_app, monkeypatch)
        result = combat_service.player_use_item(
            session.id, user.id, session.version, "potion-healing", actor_id=char_id
        )
        assert result.get("skipped") is True, result
        session = combat_service._load_session(session.id)
        party = json.loads(session.party_snapshot_json)
        assert party["members"][0]["hp"] == 0, "a downed character must not be able to heal themselves"


def test_player_cast_spell_rejects_downed_character(test_app, monkeypatch):
    with test_app.app_context():
        session, user, char_id = _downed_session(test_app, monkeypatch)
        result = combat_service.player_cast_spell(session.id, user.id, session.version, "firebolt", actor_id=char_id)
        assert result.get("skipped") is True, result


def test_player_cast_skill_rejects_downed_character(test_app, monkeypatch):
    with test_app.app_context():
        session, user, char_id = _downed_session(test_app, monkeypatch)
        # No real Skill/CharacterSkill row exists for char_id; the downed check must fire
        # before the "skill_not_unlocked" lookup, so we still expect "skipped", not an error.
        result = combat_service.player_cast_skill(session.id, user.id, session.version, skill_id=1, actor_id=char_id)
        assert result.get("skipped") is True, result
