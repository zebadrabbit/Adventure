import json
import uuid

from werkzeug.security import generate_password_hash

from app import db
from app.models.models import Character, CombatSession, User
from app.services import combat_service


def _ensure_primary_user_and_char():
    """Create an isolated user with exactly one character.

    These tests assert that combat persistence writes back to the acting
    character. The shared "tester" user accumulates extra characters from other
    test modules (e.g. autofill), and party building orders by Character.id.asc()
    while the old helper used an unordered .first(); with >1 character the actor
    and the asserted character could diverge nondeterministically. A dedicated
    single-character user makes the actor unambiguous.
    """
    uname = "combat_persist_" + uuid.uuid4().hex[:10]
    user = User(username=uname, password=generate_password_hash("pass"))
    db.session.add(user)
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Hero",
        stats='{"str":12, "dex":11, "int":10, "con":10, "mana":30}',
        gear="{}",
        items="[]",
    )
    db.session.add(char)
    db.session.commit()
    return user, char


def test_persist_after_monster_defeat(auth_client):
    user, char = _ensure_primary_user_and_char()
    monster = {"slug": "slime", "name": "Slime", "hp": 1, "damage": 1, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    actor_id = party["members"][0]["char_id"]
    party["members"][0]["hp"] = 12
    party["members"][0]["mana"] = 7
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()
    combat_service.player_attack(session.id, user.id, session.version, actor_id=actor_id)
    fresh_char = db.session.get(Character, char.id)
    stats = json.loads(fresh_char.stats)
    # Some characters may not originally have an 'hp' field; persistence injects it.
    assert stats.get("hp") == 12
    # current_mana introduced; accept either legacy 'mana' or new field
    assert stats.get("current_mana", stats.get("mana")) == 7


def test_persist_after_player_flee(auth_client, monkeypatch):
    user, char = _ensure_primary_user_and_char()
    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    actor_id = party["members"][0]["char_id"]
    party["members"][0]["hp"] = 25
    party["members"][0]["mana"] = 3
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()
    import random as _random

    monkeypatch.setattr(_random, "random", lambda: 0.0)
    combat_service.player_flee(session.id, user.id, session.version, actor_id=actor_id)
    # Assert against the actual combat actor row (actor_id) rather than first character
    # to avoid ordering dependence if multiple characters exist for the user.
    fresh_actor = db.session.get(Character, actor_id)
    stats = json.loads(fresh_actor.stats)
    assert stats.get("hp") == 25
    assert stats.get("current_mana", stats.get("mana")) == 3


def test_action_codes_present(auth_client, monkeypatch):
    user, char = _ensure_primary_user_and_char()
    monster = {"slug": "dummy", "name": "Dummy", "hp": 50, "damage": 0, "speed": 5, "armor": 500}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    actor_id = party["members"][0]["char_id"]  # explicit actor id reference
    import random as _random

    def fake_randint(a, b):
        # Force the d20 attack roll to be 2 (non-crit, low) guaranteeing a miss vs high armor
        if a == 1 and b == 20:
            return 2
        return (a + b) // 2

    monkeypatch.setattr(_random, "randint", fake_randint)
    # Use dynamic version; if a rare version_conflict occurs (e.g., background turn advance) retry once.
    resp = combat_service.player_attack(session.id, user.id, session.version, actor_id=actor_id)
    if resp.get("error") == "version_conflict":  # pragma: no cover - defensive path
        fresh = db.session.get(CombatSession, session.id)
        resp = combat_service.player_attack(session.id, user.id, fresh.version, actor_id=actor_id)
    # Reload immediately; miss log should be first after initial encounter start
    fresh = db.session.get(CombatSession, session.id)
    logs = json.loads(fresh.log_json or "[]")
    # Provide helpful debugging context if missing
    codes = [e.get("code") for e in logs if isinstance(e, dict) and e.get("code")]
    assert "PLAYER_ATTACK_MISS" in codes, f"Expected PLAYER_ATTACK_MISS in log codes, saw: {codes}"
