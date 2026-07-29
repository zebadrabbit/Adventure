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
from app.models.models import Character, CombatSession, User
from app.services import combat_service


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["_user_id"] = str(user_id)


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


def test_old_session_backfill_is_persisted_not_just_patched_into_one_response(client, monkeypatch):
    """A session started before item_counts existed must keep its item panel
    for the whole fight, not only on the load that backfilled it.

    /api/combat/<id>/state patched a throwaway row.to_dict(). Every other
    response path -- the dungeon action route, the sibling combat routes, the
    combat_update emit -- returns to_dict() straight off party_snapshot_json,
    unpatched. So a mid-deploy session rendered its potions on load and lost
    them from the first attack onward, and with the two fixed buttons gone
    there was no way to drink anything for the rest of that fight short of
    reloading the page.
    """
    session, user, first, _second = _two_character_session(monkeypatch)
    combat_id = session.id

    # Age the session: strip what a pre-branch snapshot never had.
    party = json.loads(session.party_snapshot_json)
    party.pop("item_counts", None)
    party.pop("item_meta", None)
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    _login_as(client, user.id)
    resp = client.get(f"/api/combat/{combat_id}/state")
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["state"]["party"]["item_counts"]["potion-healing"][str(first.id)] == 3

    # The fix: it was written back, so the next response from any other path
    # carries it too.
    row = db.session.get(CombatSession, combat_id)
    db.session.refresh(row)
    later = row.to_dict()["party"]
    assert "item_counts" in later, "the first attack after loading would have lost the item panel"
    assert "item_meta" in later, "without kind/name the panel falls back to raw slugs"
    assert later["item_counts"]["potion-healing"][str(first.id)] == 3

    # Only the backfill is persisted -- hp_pct/mana_pct are recomputed per
    # response and would go stale the moment anything took damage.
    assert all("hp_pct" not in m for m in later.get("members", [])), later.get("members")


def _two_character_mana_session(monkeypatch):
    user = User(username=f"mana-potions-{random.randint(1, 10**9)}", email=None)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()

    stats = json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12})
    first = Character(
        user_id=user.id, name="Front", stats=stats, gear="{}", items=json.dumps([{"slug": "potion-mana", "qty": 3}])
    )
    second = Character(
        user_id=user.id, name="Back", stats=stats, gear="{}", items=json.dumps([{"slug": "potion-mana", "qty": 1}])
    )
    db.session.add_all([first, second])
    db.session.commit()

    init_seq = iter([1, 20, 5])
    monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
    session = combat_service.start_session(user.id, _simple_monster())
    return session, user, first, second


def test_mana_potion_counts_are_per_character_at_session_start(test_app, monkeypatch):
    with test_app.app_context():
        session, _user, first, second = _two_character_mana_session(monkeypatch)
        party = json.loads(session.party_snapshot_json)
        counts = party["item_counts"]["potion-mana"]
        assert counts[str(first.id)] == 3, counts
        assert counts[str(second.id)] == 1, counts


def test_using_mana_potion_deducts_from_the_actors_own_inventory_only_and_restores_mana(test_app, monkeypatch):
    with test_app.app_context():
        session, user, first, second = _two_character_mana_session(monkeypatch)
        party = json.loads(session.party_snapshot_json)
        initiative = json.loads(session.initiative_json)
        active = initiative[session.active_index]
        actor_id = active["id"]

        # Drain the actor's mana below max so the restore is observable, and cap
        # the restore's ceiling below max_mana too (asserted below).
        for m in party["members"]:
            if m.get("char_id") == actor_id:
                m["mana"] = 0
                mana_max = m.get("mana_max", 0)
        session.party_snapshot_json = json.dumps(party)
        db.session.commit()

        result = combat_service.player_use_item(session.id, user.id, session.version, "potion-mana", actor_id=actor_id)
        assert result.get("ok") is True, result

        new_party = result["state"]["party"]
        actor_member = next(m for m in new_party["members"] if m.get("char_id") == actor_id)
        assert actor_member["mana"] == min(mana_max, 5), actor_member

        db.session.refresh(first)
        db.session.refresh(second)
        first_qty = next((e.get("qty", 1) for e in json.loads(first.items) if e.get("slug") == "potion-mana"), 0)
        second_qty = next((e.get("qty", 1) for e in json.loads(second.items) if e.get("slug") == "potion-mana"), 0)

        if actor_id == first.id:
            assert first_qty == 2, "the acting character's own mana potion should be consumed"
            assert second_qty == 1, "the non-acting character's mana potions must be untouched"
        else:
            assert second_qty == 0, "the acting character's own mana potion should be consumed"
            assert first_qty == 3, "the non-acting character's mana potions must be untouched"


def test_using_mana_potion_caps_restore_at_mana_max(test_app, monkeypatch):
    with test_app.app_context():
        session, user, first, second = _two_character_mana_session(monkeypatch)
        party = json.loads(session.party_snapshot_json)
        initiative = json.loads(session.initiative_json)
        active = initiative[session.active_index]
        actor_id = active["id"]

        # Set mana to 1 below max so a flat restore of 5 would overshoot without a cap.
        for m in party["members"]:
            if m.get("char_id") == actor_id:
                mana_max = m.get("mana_max", 0)
                m["mana"] = max(0, mana_max - 1)
        session.party_snapshot_json = json.dumps(party)
        db.session.commit()

        result = combat_service.player_use_item(session.id, user.id, session.version, "potion-mana", actor_id=actor_id)
        assert result.get("ok") is True, result

        new_party = result["state"]["party"]
        actor_member = next(m for m in new_party["members"] if m.get("char_id") == actor_id)
        assert actor_member["mana"] == mana_max, actor_member
