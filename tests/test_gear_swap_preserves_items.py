"""Equipping over an occupied slot must not destroy what was in it.

``gear`` slots hold two shapes -- a legacy slug string, or a procedural gear
instance dict -- and the two equip paths each used to move the displaced value
back into the bag their own way. Neither survived a round trip:

  * the legacy slug path called ``add_item(inv, <instance dict>, 1)``, storing
    ``{"slug": {...}, "qty": 1}``; ``load_inventory`` drops that on the next
    read because ``slug`` is not a str;
  * the uid path appended a bare slug string to a list of dicts, which
    ``load_inventory``'s canonical branch skips for not being a dict.

Both are one click and the item is gone, so these assert against a reload
through ``load_inventory`` -- the shape the rest of the app actually sees --
rather than against the raw JSON column.
"""

import json

import pytest

from app import db
from app.inventory.utils import load_inventory
from app.models.models import Character, Item, User

INSTANCE = {
    "uid": "loot1",
    "slot": "weapon",
    "name": "Brutal Shortsword",
    "rarity": "rare",
    "affixes": [{"stat": "dex", "val": 5}],
}


def _setup(app, gear, items):
    """Seed one character with a known gear/bag pair and a catalogue sword."""
    with app.app_context():
        u = User.query.filter_by(username="swapper").first()
        if not u:
            u = User(username="swapper", password="x")
            db.session.add(u)
            db.session.commit()
        if not Item.query.filter_by(slug="long-sword").first():
            db.session.add(Item(slug="long-sword", name="Long Sword", type="weapon", description="", value_copper=10))
        c = Character.query.filter_by(user_id=u.id).first()
        if not c:
            c = Character(user_id=u.id, name="SW", stats='{"dex":10}')
            db.session.add(c)
        c.gear = json.dumps(gear)
        c.items = json.dumps(items)
        db.session.commit()
        return c.id, u.id


def _login(client, uid):
    with client.session_transaction() as s:
        s["user_id"] = uid
        s["_user_id"] = str(uid)


def _bag(app, cid):
    with app.app_context():
        return load_inventory(db.session.get(Character, cid).items)


def test_legacy_equip_over_an_instance_keeps_the_instance(client, test_app):
    """The click-reachable one: loot a sword, equip it, then equip a catalogue
    sword into the same slot. The looted one must come back to the bag."""
    cid, uid = _setup(test_app, {"weapon": INSTANCE}, [{"slug": "long-sword", "qty": 1}])
    _login(client, uid)

    r = client.post(f"/api/characters/{cid}/equip", json={"slug": "long-sword", "slot": "weapon"})
    assert r.status_code == 200, r.get_json()

    bag = _bag(test_app, cid)
    assert any(o.get("uid") == "loot1" for o in bag), f"displaced instance was destroyed: {bag}"


def test_uid_equip_over_a_legacy_slug_keeps_the_slug(client, test_app):
    """The mirror case: a legacy slug in the slot, displaced by a uid equip.

    The bag must still hold a dict after the equipped instance leaves it --
    otherwise the leftover list is all strings, load_inventory takes its
    legacy-aggregate branch, and the appended slug survives by accident.
    """
    cid, uid = _setup(test_app, {"weapon": "long-sword"}, [INSTANCE, {"slug": "potion-healing", "qty": 1}])
    _login(client, uid)

    r = client.post(f"/api/characters/{cid}/equip", json={"uid": "loot1"})
    assert r.status_code == 200, r.get_json()

    bag = _bag(test_app, cid)
    assert any(o.get("slug") == "long-sword" for o in bag), f"displaced slug was destroyed: {bag}"


def test_unequip_instance_returns_it_to_the_bag(client, test_app):
    """Seeded with a legacy list-of-slugs bag: appending an instance dict to
    one made load_inventory take its aggregate branch and skip the dict."""
    cid, uid = _setup(test_app, {"weapon": INSTANCE}, ["potion-healing"])
    _login(client, uid)

    r = client.post(f"/api/characters/{cid}/unequip", json={"slot": "weapon"})
    assert r.status_code == 200, r.get_json()

    bag = _bag(test_app, cid)
    assert any(o.get("uid") == "loot1" for o in bag), f"unequipped instance was destroyed: {bag}"


def test_unequip_uidless_dict_is_recovered_not_dropped(client, test_app):
    """Nothing in app/ writes a slot value without a uid, but legacy rows may
    hold one. It must survive with a minted uid rather than vanish."""
    cid, uid = _setup(test_app, {"weapon": {"slot": "weapon", "name": "Old Blade"}}, [])
    _login(client, uid)

    r = client.post(f"/api/characters/{cid}/unequip", json={"slot": "weapon"})
    assert r.status_code == 200, r.get_json()

    bag = _bag(test_app, cid)
    assert any(o.get("name") == "Old Blade" and o.get("uid") for o in bag), f"malformed value was dropped: {bag}"


@pytest.mark.parametrize(
    "endpoint,body,code",
    [
        ("equip", {"uid": "nope"}, "not_in_inventory"),
        ("equip", {"slug": ""}, "missing slug"),
        ("equip", {"slug": "no-such-item"}, "item not found"),
        ("equip", {"slug": "long-sword", "slot": "elbow"}, "invalid slot"),
        ("unequip", {"slot": "elbow"}, "invalid slot"),
        ("unequip", {"slot": "head"}, "empty slot"),
    ],
)
def test_refusals_carry_player_prose(client, test_app, endpoint, body, code):
    """The bag grid shows the player whatever ``message`` comes back, so a
    refusal without one puts a machine code on screen."""
    cid, uid = _setup(test_app, {}, [{"slug": "long-sword", "qty": 1}])
    _login(client, uid)

    r = client.post(f"/api/characters/{cid}/{endpoint}", json=body)
    assert r.status_code >= 400
    d = r.get_json()
    assert d["error"] == code, d
    assert d.get("message"), f"{code} answered with a bare machine code: {d}"
    assert d["message"] != code
    assert d["message"][0].isupper() and d["message"].endswith(".")
