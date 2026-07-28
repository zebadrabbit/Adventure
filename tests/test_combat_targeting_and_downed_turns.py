"""Two things playtesting surfaced about whose turn it is and who gets hit.

1. Monsters focused a single character. The basic-attack path sorted the party
   by HP and always swung at the lowest, so one member absorbed the whole fight
   while the rest watched.
2. A downed character's turn still became the active turn. Every action handler
   refused to act, but the client had already offered the buttons, so the player
   spent a click burning a turn for a corpse.
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service


@pytest.fixture()
def party_of_four(test_app):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="targetparty").first()
    if not user:
        user = User(username="targetparty", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    existing = Character.query.filter_by(user_id=user.id).order_by(Character.id.asc()).all()
    if len(existing) < 4:
        for i in range(4 - len(existing)):
            stats = json.dumps({"str": 10, "dex": 10 + i, "int": 10, "con": 10, "mana": 30})
            db.session.add(Character(user_id=user.id, name=f"Hero{i}", stats=stats, gear="{}", items="[]"))
        db.session.commit()
    return user


def _monster(hp=500):
    return {"slug": "target-dummy", "name": "Target Dummy", "level": 3, "hp": hp, "damage": 6, "speed": 1, "xp": 5}


def test_monster_spreads_its_attacks_across_the_party():
    members = [
        {"char_id": 1, "name": "A", "hp": 100, "max_hp": 100},
        {"char_id": 2, "name": "B", "hp": 100, "max_hp": 100},
        {"char_id": 3, "name": "C", "hp": 100, "max_hp": 100},
        {"char_id": 4, "name": "D", "hp": 100, "max_hp": 100},
    ]
    rng = random.Random(7)
    hits = {m["char_id"]: 0 for m in members}
    for _ in range(200):
        idx, target = combat_service._pick_monster_target(members, rng=rng)
        hits[target["char_id"]] += 1

    assert all(count > 0 for count in hits.values()), f"someone was never targeted: {hits}"
    # No one should soak up the whole fight.
    assert max(hits.values()) < 120, hits


def test_wounded_members_are_likelier_but_not_certain():
    members = [
        {"char_id": 1, "name": "Hurt", "hp": 5, "max_hp": 100},
        {"char_id": 2, "name": "Fine", "hp": 100, "max_hp": 100},
    ]
    rng = random.Random(11)
    hits = {1: 0, 2: 0}
    for _ in range(400):
        _, target = combat_service._pick_monster_target(members, rng=rng)
        hits[target["char_id"]] += 1

    assert hits[1] > hits[2], "the wounded should draw more attention"
    assert hits[2] > 60, "but the healthy must not be ignored entirely"


def test_downed_members_are_never_targeted():
    members = [
        {"char_id": 1, "name": "Down", "hp": 0, "max_hp": 100},
        {"char_id": 2, "name": "Up", "hp": 100, "max_hp": 100},
    ]
    rng = random.Random(3)
    for _ in range(50):
        _, target = combat_service._pick_monster_target(members, rng=rng)
        assert target["char_id"] == 2


def test_no_target_when_everyone_is_down():
    members = [{"char_id": 1, "hp": 0, "max_hp": 100}]
    idx, target = combat_service._pick_monster_target(members)
    assert target is None and idx == 0


def test_turn_order_skips_downed_characters(party_of_four, monkeypatch):
    """The active turn must never land on a character who cannot act."""
    user = party_of_four
    # Deterministic initiative: players first, monster last.
    seq = iter([20, 19, 18, 17, 1])
    monkeypatch.setattr(random, "randint", lambda a, b: next(seq))
    session = combat_service.start_session(user.id, _monster())

    party = json.loads(session.party_snapshot_json)
    initiative = json.loads(session.initiative_json)
    player_ids = [e["id"] for e in initiative if e["type"] == "player"]

    # Drop everyone except the last player in the order.
    survivor = player_ids[-1]
    for member in party["members"]:
        if member["char_id"] != survivor:
            member["hp"] = 0
    session.party_snapshot_json = json.dumps(party)
    session.active_index = 0
    db.session.commit()

    combat_service._advance_turn(session)

    actor = json.loads(session.initiative_json)[session.active_index]
    if actor["type"] == "player":
        assert actor["id"] == survivor, "advanced onto a downed character's turn"
