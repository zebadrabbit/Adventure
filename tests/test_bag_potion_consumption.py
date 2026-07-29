"""Out-of-combat consumption, end to end through the bag payload.

The character panel's only route to drinking a potion was deleted once
already, silently: the panel that carried a `Use` button on every potion was
replaced by one that had no consume path at all, and because the route itself
stayed live and tested, nothing failed. Clicking a potion tried to *equip* it
and earned a 400.

`test_regen_potion_out_of_combat.py` covers what the effect does. This covers
the round trip the panel actually makes, which is the part that went missing:
a potion the bag payload reports (typed `potion`, which is what the UI keys
off to offer drinking rather than equipping) can be consumed, and the bag it
reports afterwards has one fewer.
"""

import json

from app import db
from app.models.models import Character, Item, User


def _ensure_healing_potion():
    item = Item.query.filter_by(slug="potion-healing").first()
    if item:
        return item
    item = Item(
        slug="potion-healing",
        name="Potion of Healing",
        type="potion",
        description="A draught of red glass.",
        value_copper=50,
    )
    db.session.add(item)
    db.session.commit()
    return item


def _bag_entry(payload, slug):
    return next((entry for entry in payload["bag"] if entry.get("slug") == slug), None)


def test_potion_in_the_bag_can_be_drunk_and_the_count_drops(test_app, auth_client):
    with test_app.app_context():
        _ensure_healing_potion()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-healing", "qty": 2}])
        db.session.commit()
        char_id = char.id

    # What the panel renders from. `type` is load-bearing: it is how the bag
    # grid decides a cell drinks instead of equips.
    before = auth_client.get(f"/api/characters/{char_id}").get_json()
    entry = _bag_entry(before, "potion-healing")
    assert entry is not None, before["bag"]
    assert entry["type"] == "potion"
    assert entry["qty"] == 2

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-healing"})
    assert resp.status_code == 200, resp.get_json()

    after = auth_client.get(f"/api/characters/{char_id}").get_json()
    entry = _bag_entry(after, "potion-healing")
    assert entry is not None, "the second potion vanished with the first"
    assert entry["qty"] == 1

    # The last one leaves the bag entirely rather than lingering at qty 0.
    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-healing"})
    assert resp.status_code == 200, resp.get_json()

    empty = auth_client.get(f"/api/characters/{char_id}").get_json()
    assert _bag_entry(empty, "potion-healing") is None, empty["bag"]


def test_drinking_a_healing_potion_out_of_combat_restores_hp(test_app, auth_client):
    """The point of the affordance: healing between fights, without Camp.

    Camp is the only other out-of-combat recovery and it costs a supply kit
    and a cooldown, so losing this quietly turned every potion in the party's
    bags into dead weight.
    """
    with test_app.app_context():
        _ensure_healing_potion()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        stats = json.loads(char.stats) if char.stats else {}
        stats["hp"] = 7
        char.stats = json.dumps(stats)
        char.items = json.dumps([{"slug": "potion-healing", "qty": 1}])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-healing"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["effects"]["hp"] > 0

    with test_app.app_context():
        char = db.session.get(Character, char_id)
        assert json.loads(char.stats)["hp"] > 7


_GEAR_INSTANCE = {
    "uid": "0f1e2d3c4b5a",
    "base": "sword",
    "slot": "weapon",
    "name": "Rusty Sword",
    "rarity": "common",
    "ilvl": 1,
    "affixes": [],
    "value": 12,
    "durability": 50,
    "max_durability": 50,
}


def test_a_potion_sitting_behind_looted_gear_can_still_be_drunk(test_app, auth_client):
    """The ownership check subscripted ``o["slug"]`` on every bag entry, and a
    procedural gear instance carries a uid and no slug at all -- so the check
    raised a KeyError, a 500, whose non-JSON body reached the player as the
    panel's generic "Nothing happens." ``any()`` short-circuits, which is why a
    starter potion at the front of the bag hid this: it only bit a potion
    acquired *after* the character had looted gear.
    """
    with test_app.app_context():
        _ensure_healing_potion()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([_GEAR_INSTANCE, {"slug": "potion-healing", "qty": 1}])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-healing"})
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        char = db.session.get(Character, char_id)
        remaining = json.loads(char.items)
        assert any(o.get("uid") == _GEAR_INSTANCE["uid"] for o in remaining), "the gear must survive the draught"
        assert not any(o.get("slug") == "potion-healing" for o in remaining)


def test_equipping_behind_looted_gear_refuses_rather_than_erroring(test_app, auth_client):
    """The same subscript, in the legacy slug-based equip path. A slug the
    character does not hold must earn a 400, not a 500, when there is gear in
    the bag ahead of it."""
    with test_app.app_context():
        _ensure_healing_potion()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([_GEAR_INSTANCE])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(f"/api/characters/{char_id}/equip", json={"slug": "potion-healing", "slot": "weapon"})
    assert resp.status_code == 400, resp.get_json()


def test_equipping_a_potion_is_refused_with_a_sentence_not_a_code(test_app, auth_client):
    """Why the bag grid routes potions to /consume rather than /equip.

    A potion has no slot; /equip's own answer is a 400. The panel used to send
    them here anyway (its slot lookup falls back to "weapon" for anything it
    does not recognise) and showed the player the raw `error` string.
    """
    with test_app.app_context():
        _ensure_healing_potion()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-healing", "qty": 1}])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(
        f"/api/characters/{char_id}/equip",
        json={"slug": "potion-healing", "slot": "weapon"},
    )
    assert resp.status_code == 400, resp.get_json()
