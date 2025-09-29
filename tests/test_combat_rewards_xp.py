"""Tests for XP distribution metadata in combat rewards with multi-character party.

Ensures rewards['xp'] contains total and per_member mapping with correct shares.
"""

import random

from app import db
from app.models.models import Character, User
from app.services import combat_service


def _monster():
    return {
        "slug": "xp-mob",
        "name": "XP Mob",
        "level": 1,
        "hp": 5,  # low to end quickly
        "damage": 0,
        "armor": 0,
        "speed": 1,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 40,
        "boss": False,
    }


def test_rewards_xp_shape_and_split(monkeypatch, test_app):
    from werkzeug.security import generate_password_hash

    # Create user and two characters to test split
    user = User.query.filter_by(username="xp_tester").first()
    if not user:
        user = User(username="xp_tester", password=generate_password_hash("pass"))
        db.session.add(user)
        db.session.commit()
    # Ensure two characters
    chars = Character.query.filter_by(user_id=user.id).order_by(Character.id.asc()).all()
    needed = 2 - len(chars)
    for i in range(needed):
        stats = '{"str":12, "dex":10, "int":10, "con":10, "mana":30}'
        c = Character(user_id=user.id, name=f"Char{i}", stats=stats, gear="{}", items="[]")
        db.session.add(c)
    if needed:
        db.session.commit()
    # Deterministic initiative: high rolls for both players then monster to simplify ordering
    seq = [20, 19, 1, 15, 0]  # player1 init, player2 init, monster init, first attack roll, variance
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))
    session = combat_service.start_session(user.id, _monster())
    # First player attack should kill monster (hp 5, attack base >=8)
    res = combat_service.player_attack(session.id, user.id, session.version)
    assert res.get("ok")
    session = combat_service._load_session(session.id)
    data = session.to_dict()
    assert data["status"] == "complete"
    rewards = data.get("rewards")
    assert isinstance(rewards, dict)
    assert "xp" in rewards, rewards
    xp_meta = rewards["xp"]
    assert xp_meta.get("total") == 40
    per = xp_meta.get("per_member")
    assert isinstance(per, dict) and len(per) == 2
    # Each member should have 20
    assert set(per.values()) == {20}
    # DB rows reflect increment
    for c in Character.query.filter_by(user_id=user.id).all():
        assert c.xp >= 20
