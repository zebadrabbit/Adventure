import json
import random

import pytest

from app import db
from app.models.models import Character, GameConfig, User
from app.services import combat_service


@pytest.fixture()
def user_with_char(test_app, client):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="ai_tester").first()
        if not user:
            user = User(username="ai_tester", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        char = Character.query.filter_by(user_id=user.id).first()
        if not char:
            cstats = '{"str":12, "dex":11, "int":12, "con":10, "mana":40}'
            char = Character(user_id=user.id, name="AITester", stats=cstats, gear="{}", items="[]")
            db.session.add(char)
            db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["_user_id"] = str(user.id)
    return user, client


def _monster_base(**overrides):
    base = {
        "slug": "ai-mob",
        "name": "AI Mob",
        "level": 1,
        "hp": 50,
        "damage": 6,
        "armor": 0,
        "speed": 8,
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
    base.update(overrides)
    return base


def _start_session(user_id, monster, monkeypatch, randint_seq=None, random_seq=None):
    if randint_seq is None:
        randint_seq = [10] * 50
    it = iter(randint_seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it, 10))
    if random_seq is not None:
        r_it = iter(random_seq)
        monkeypatch.setattr(random, "random", lambda: next(r_it, 0.5))
    return combat_service.start_session(user_id, monster)


def test_flee_disabled_without_flag(user_with_char, monkeypatch):
    user, _client = user_with_char
    # Force low HP so flee condition would trigger if flag enabled
    m = _monster_base(hp=10, enable_monster_flee=False, ai_enabled=True)
    # Configure high flee chance to prove flag gating; chance won't matter if flag off
    GameConfig.set("monster_ai", json.dumps({"flee_threshold": 0.9, "flee_chance": 1.0}))
    session = _start_session(user.id, m, monkeypatch, random_seq=[0.0] * 5)
    # Advance to monster turn if needed
    if not combat_service._is_monster_turn(session):  # type: ignore
        combat_service._advance_turn(session)  # type: ignore
    combat_service.monster_auto_turn(session)
    db.session.commit()
    assert session.status == "active", "Monster should not flee when flag disabled"


def test_spell_cast_path_when_enabled(user_with_char, monkeypatch):
    user, _client = user_with_char
    m = _monster_base(hp=60, enable_monster_spells=True, ai_enabled=True, spells=["firebolt"])
    # Force spell chance to 100%
    GameConfig.set("monster_ai", json.dumps({"spell_chance": 1.0}))
    session = _start_session(user.id, m, monkeypatch, random_seq=[0.0] * 5)
    # Ensure monster turn
    if not combat_service._is_monster_turn(session):  # type: ignore
        combat_service._advance_turn(session)  # type: ignore
    prev_hp = session.monster_hp
    combat_service.monster_auto_turn(session)
    db.session.commit()
    # Monster used a spell against player; monster HP unchanged (no self-damage) but player HP reduced; ensure log contains 'casts Firebolt'
    assert session.monster_hp == prev_hp
    logs = json.loads(session.log_json)
    assert any("casts Firebolt" in entry.get("m", "") for entry in logs), "Expected Firebolt cast log entry"


def test_cooldown_prevents_back_to_back_actions(user_with_char, monkeypatch):
    user, _client = user_with_char
    m = _monster_base(hp=55, ai_enabled=True)
    GameConfig.set("monster_ai", json.dumps({"cooldown_turns": 2}))
    session = _start_session(user.id, m, monkeypatch, random_seq=[0.9] * 10)
    # Ensure monster acts once
    if not combat_service._is_monster_turn(session):  # type: ignore
        combat_service._advance_turn(session)  # type: ignore
    combat_service.monster_auto_turn(session)
    # Fast-forward initiative back to monster before cooldown expires (advance turns equal to party size + maybe 0)
    combat_service._advance_turn(session)  # type: ignore  # player turn
    # Return to monster turn next (since only one player + monster)
    if combat_service._is_monster_turn(session):  # type: ignore
        combat_service.monster_auto_turn(session)
    db.session.commit()
    # Version should have advanced only by one action (second turn should log cooldown and still advance but no attack?)
    logs = json.loads(session.log_json)
    cooldown_msgs = [entry for entry in logs if "cooldown" in entry.get("m", "").lower()]
    assert cooldown_msgs, "Expected cooldown log entry"


def test_vulnerability_increases_damage(user_with_char, monkeypatch):
    user, _client = user_with_char
    # Give player high STR to ensure noticeable base damage, set monster physical vulnerability 1.5
    m = _monster_base(hp=80, ai_enabled=False, resistances={"physical": 1.5})
    session = _start_session(user.id, m, monkeypatch, randint_seq=[10, 10, 10, 10])
    # Player attacks (ensure it's player's turn)
    st = session.to_dict()
    init = st.get("initiative", [])
    assert init[session.active_index]["type"] == "player"
    actor_id = init[session.active_index]["id"]
    before = session.monster_hp
    resp = combat_service.player_attack(session.id, user.id, session.version, actor_id=actor_id)
    assert resp.get("ok")
    after = combat_service._load_session(session.id)  # type: ignore
    dealt = before - after.monster_hp
    # With vulnerability 1.5, damage should be >= a threshold (base attack ~ 8+ STR//2 + level variance). Using >=9 as coarse check.
    assert dealt >= 9, f"Expected amplified damage with vulnerability, got {dealt}"
