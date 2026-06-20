"""Healing potions must be tracked and consumed per-character, not pooled
from (and always deducted from) the first character in the party.

Root cause: _base_player_snapshot only ever read item_counts from chars[0],
and player_use_item always deducted from
Character.query.filter_by(user_id=...).first() regardless of which
character actually used the potion.
"""

import json
import random

from app import db
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster():
    return {
        "slug": "potion-test-mob",
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


def _two_character_session(monkeypatch):
    user = User(username=f"potions-{random.randint(1, 10**9)}", email=None)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()

    stats = json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12})
    # First character has 3 potions, second has 1 — distinct counts make the
    # bug ("always reads/writes char[0]") impossible to miss.
    first = Character(
        user_id=user.id, name="Front", stats=stats, gear="{}", items=json.dumps([{"slug": "potion-healing", "qty": 3}])
    )
    second = Character(
        user_id=user.id, name="Back", stats=stats, gear="{}", items=json.dumps([{"slug": "potion-healing", "qty": 1}])
    )
    db.session.add_all([first, second])
    db.session.commit()

    # Bias initiative so the SECOND character acts first — this is the case that
    # actually exposes the bug (player_use_item defaulting to "first character for
    # this user" regardless of who's acting would otherwise coincidentally look
    # correct whenever character #1 happens to act first).
    init_seq = iter([1, 20, 5])
    monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
    session = combat_service.start_session(user.id, _simple_monster())
    return session, user, first, second


def test_item_counts_are_per_character_at_session_start(test_app, monkeypatch):
    with test_app.app_context():
        session, _user, first, second = _two_character_session(monkeypatch)
        party = json.loads(session.party_snapshot_json)
        counts = party["item_counts"]["potion-healing"]
        assert counts[str(first.id)] == 3, counts
        assert counts[str(second.id)] == 1, counts


def test_using_potion_deducts_from_the_actors_own_inventory_only(test_app, monkeypatch):
    with test_app.app_context():
        session, user, first, second = _two_character_session(monkeypatch)
        initiative = json.loads(session.initiative_json)
        # Find whichever party member is actually first up (initiative order
        # may not match creation order) and use a potion as them.
        active = initiative[session.active_index]
        actor_id = active["id"]

        result = combat_service.player_use_item(
            session.id, user.id, session.version, "potion-healing", actor_id=actor_id
        )
        assert result.get("ok") is True, result

        db.session.refresh(first)
        db.session.refresh(second)
        first_qty = next((e.get("qty", 1) for e in json.loads(first.items) if e.get("slug") == "potion-healing"), 0)
        second_qty = next((e.get("qty", 1) for e in json.loads(second.items) if e.get("slug") == "potion-healing"), 0)

        if actor_id == first.id:
            assert first_qty == 2, "the acting character's own potion should be consumed"
            assert second_qty == 1, "the non-acting character's potions must be untouched"
        else:
            assert second_qty == 0, "the acting character's own potion should be consumed"
            assert first_qty == 3, "the non-acting character's potions must be untouched"
