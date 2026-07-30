"""Handing an item from one of your characters to another.

There is no shared party container in this game -- bags are per-character, and
per-character encumbrance only binds if every item sits in somebody's bag. This
endpoint is the sanctioned way an item moves between two of your own heroes,
and it is deliberately hedged: not in a fight, not to or from a corpse, not to
a mule that never entered the run, and not past the receiver's carry cap.
"""

import json

import pytest

from app import db
from app.inventory.utils import load_inventory
from app.models.models import Character, CombatSession, Item, User

INSTANCE = {
    "uid": "giveinst1",
    "slot": "weapon",
    "name": "Brutal Shortsword",
    "rarity": "rare",
    "weight": 3.0,
}


@pytest.fixture
def pair(client, test_app):
    """Two co-owned characters, logged in. Giver holds a potion and an instance."""
    with test_app.app_context():
        u = User.query.filter_by(username="giver_user").first()
        if not u:
            u = User(username="giver_user", password="x")
            db.session.add(u)
            db.session.commit()
        if not Item.query.filter_by(slug="potion-heal-l1").first():
            db.session.add(
                Item(slug="potion-heal-l1", name="Draught of Healing", type="potion", description="", value_copper=10)
            )
        Character.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        giver = Character(
            user_id=u.id,
            name="Thora",
            stats=json.dumps({"str": 10}),
            gear="{}",
            items=json.dumps([{"slug": "potion-heal-l1", "qty": 2}, INSTANCE]),
        )
        receiver = Character(user_id=u.id, name="Renn", stats=json.dumps({"str": 10}), gear="{}", items=json.dumps([]))
        db.session.add_all([giver, receiver])
        db.session.commit()
        ids = (giver.id, receiver.id, u.id)
    with client.session_transaction() as s:
        s["user_id"] = ids[2]
        s["_user_id"] = str(ids[2])
    return ids


def _bag(test_app, cid):
    with test_app.app_context():
        return load_inventory(db.session.get(Character, cid).items)


def _give(client, frm, body):
    return client.post(f"/api/characters/{frm}/give", json=body)


# ----------------------------------------------------------------- happy path


def test_give_a_stacked_item_moves_exactly_one(client, test_app, pair):
    giver, receiver, _ = pair

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"})

    assert r.status_code == 200, r.get_json()
    giver_bag = _bag(test_app, giver)
    recv_bag = _bag(test_app, receiver)
    assert [o["qty"] for o in giver_bag if o.get("slug") == "potion-heal-l1"] == [1], giver_bag
    assert [o["qty"] for o in recv_bag if o.get("slug") == "potion-heal-l1"] == [1], recv_bag


def test_give_a_gear_instance_moves_it_whole(client, test_app, pair):
    giver, receiver, _ = pair

    r = _give(client, giver, {"to_character_id": receiver, "uid": "giveinst1"})

    assert r.status_code == 200, r.get_json()
    assert not any(o.get("uid") == "giveinst1" for o in _bag(test_app, giver))
    landed = [o for o in _bag(test_app, receiver) if o.get("uid") == "giveinst1"]
    assert landed, "the instance did not arrive"
    # Verbatim, affixes and all -- not flattened into a slug stack.
    assert landed[0]["name"] == "Brutal Shortsword"


def test_giving_into_an_existing_stack_merges(client, test_app, pair):
    giver, receiver, _ = pair
    with test_app.app_context():
        ch = db.session.get(Character, receiver)
        ch.items = json.dumps([{"slug": "potion-heal-l1", "qty": 3}])
        db.session.commit()

    assert _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"}).status_code == 200

    recv = [o for o in _bag(test_app, receiver) if o.get("slug") == "potion-heal-l1"]
    assert len(recv) == 1 and recv[0]["qty"] == 4, recv


# -------------------------------------------------------------------- refusals


def test_cannot_give_to_yourself(client, test_app, pair):
    """The identity map returns the same object for both sides, so an unguarded
    give would read two lists off one character and lose or duplicate the item."""
    giver, _, _ = pair

    r = _give(client, giver, {"to_character_id": giver, "slug": "potion-heal-l1"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "same_character"
    assert [o["qty"] for o in _bag(test_app, giver) if o.get("slug") == "potion-heal-l1"] == [2]


def test_cannot_give_someone_elses_character(client, test_app, pair):
    giver, _, _ = pair
    with test_app.app_context():
        other = User.query.filter_by(username="giver_stranger").first()
        if not other:
            other = User(username="giver_stranger", password="x")
            db.session.add(other)
            db.session.commit()
        theirs = Character(user_id=other.id, name="Outsider", stats='{"str":10}', gear="{}", items="[]")
        db.session.add(theirs)
        db.session.commit()
        theirs_id = theirs.id

    r = _give(client, giver, {"to_character_id": theirs_id, "slug": "potion-heal-l1"})

    assert r.status_code == 404
    assert not _bag(test_app, theirs_id)


def test_cannot_give_what_you_do_not_carry(client, test_app, pair):
    giver, receiver, _ = pair

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-nonexistent"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "item not in bag"


def test_cannot_give_during_a_fight(client, test_app, pair):
    """In combat a character may only use their own inventory."""
    giver, receiver, uid = pair
    with test_app.app_context():
        db.session.add(
            CombatSession(
                user_id=uid,
                monster_json=json.dumps({"slug": "m", "name": "M", "hp": 10}),
                status="active",
                party_snapshot_json=json.dumps({"members": []}),
                monster_hp=10,
            )
        )
        db.session.commit()

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "in_combat"
    assert not _bag(test_app, receiver), "the item moved mid-fight"


def test_cannot_give_to_a_corpse(client, test_app, pair):
    giver, receiver, _ = pair
    with test_app.app_context():
        ch = db.session.get(Character, receiver)
        ch.is_dead = True
        db.session.commit()

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "character_downed"


def test_cannot_hand_the_haul_to_a_mule_outside_the_run(client, test_app, pair):
    """Same-run guard, mirroring loot-body: a character that never entered the
    dungeon must not be handed the run's loot, which is banking by another name."""
    giver, receiver, _ = pair
    with client.session_transaction() as s:
        s["last_party_ids"] = [giver]  # receiver was not on the delve

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"})

    assert r.status_code == 403
    assert r.get_json()["error"] == "not_in_party"


def test_a_give_between_two_of_the_run_party_is_allowed(client, test_app, pair):
    giver, receiver, _ = pair
    with client.session_transaction() as s:
        s["last_party_ids"] = [giver, receiver]

    assert _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"}).status_code == 200


def test_refused_when_the_receiver_cannot_carry_it(client, test_app, pair):
    """Encumbrance is per-character; a give must not be a way around it."""
    giver, receiver, _ = pair
    with test_app.app_context():
        ch = db.session.get(Character, receiver)
        # STR 0 -> capacity is base_capacity alone; pile on well past the cap.
        ch.stats = json.dumps({"str": 0})
        ch.items = json.dumps([{"slug": "potion-heal-l1", "qty": 400}])
        db.session.commit()

    r = _give(client, giver, {"to_character_id": receiver, "slug": "potion-heal-l1"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "encumbered"
    assert [o["qty"] for o in _bag(test_app, giver) if o.get("slug") == "potion-heal-l1"] == [2], "giver still paid"


def test_missing_target_is_refused_not_a_500(client, test_app, pair):
    giver, _, _ = pair

    for body in ({"slug": "potion-heal-l1"}, {"to_character_id": "seven", "slug": "potion-heal-l1"}):
        r = _give(client, giver, body)
        assert r.status_code == 400, body
        assert r.get_json()["error"] == "missing_target"


def test_every_refusal_answers_in_prose(client, test_app, pair):
    """The bag grid shows the player whatever `message` comes back."""
    giver, receiver, _ = pair

    for body in (
        {"slug": "potion-heal-l1"},
        {"to_character_id": giver, "slug": "potion-heal-l1"},
        {"to_character_id": receiver},
        {"to_character_id": receiver, "slug": "potion-nonexistent"},
    ):
        r = _give(client, giver, body)
        assert r.status_code >= 400, body
        msg = r.get_json().get("message")
        assert msg, f"bare machine code for {body}: {r.get_json()}"
        assert msg[0].isupper() and msg.endswith("."), msg
