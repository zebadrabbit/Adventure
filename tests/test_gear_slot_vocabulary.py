"""There is exactly one gear-slot vocabulary: app.loot.data.archetypes.SLOTS.

Three producers used to write three different sets of slot names into the same
Character.gear dict:

  * auto_equip_for()            -> "armor"
  * inventory_api._slot_for_item -> "boots", "gloves", "ring1", "ring2", "legs"
  * the procedural loot path     -> the canonical eight

_SLOTS accepted all of them as a union, so all three writes succeeded and a
character could wear two pairs of gloves at once. Worse, "armor" is in neither
list, so unequip_item -- which rejects any slot outside _SLOTS -- could never
remove starter body armour.

The unit checks below pin each producer's output. The API tests at the end
drive the actual endpoints, because the bug was never inside one function: it
was a producer and a consumer disagreeing, and only running both catches them
drifting apart again.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import json

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.loot.data.archetypes import SLOTS
from app.models.models import Character, Item, User
from app.routes.inventory_api import _SLOTS, _slot_for_item
from app.services.auto_equip import AUTO_EQUIP_PREFS, auto_equip_for

BODY_ARMOUR = "leather-armor"


def test_canonical_vocabulary_is_the_eight_slots():
    assert set(SLOTS) == {
        "weapon",
        "offhand",
        "head",
        "chest",
        "hands",
        "feet",
        "ring",
        "amulet",
    }


def test_auto_equip_only_produces_canonical_slots():
    """Every class, given every item it might prefer, must land in-vocabulary."""
    for char_class, prefs in AUTO_EQUIP_PREFS.items():
        starter = list(prefs.get("weapon", [])) + list(prefs.get("armor", []))
        gear = auto_equip_for(char_class, starter)
        stray = set(gear) - set(SLOTS)
        assert not stray, f"{char_class} produced non-canonical slot(s): {stray}"


def test_auto_equip_puts_body_armour_in_chest():
    """The regression: it used to write "armor", which nothing could unequip."""
    gear = auto_equip_for("fighter", ["short-sword", "leather-armor"])

    assert gear.get("chest") == "leather-armor"
    assert "armor" not in gear


def test_inventory_api_does_not_keep_its_own_slot_list():
    assert tuple(_SLOTS) == tuple(SLOTS), "_SLOTS must be archetypes.SLOTS, not a restatement"


@pytest.mark.parametrize(
    "slug,name,itype,expected",
    [
        ("iron-gauntlets", "Iron Gauntlets", "armor", "hands"),
        ("leather-gloves", "Leather Gloves", "armor", "hands"),
        ("steel-boots", "Steel Boots", "armor", "feet"),
        ("iron-greaves", "Iron Greaves", "armor", "feet"),
        ("plate-leggings", "Plate Leggings", "armor", "chest"),
        ("iron-helm", "Iron Helm", "armor", "head"),
        ("tower-shield", "Tower Shield", "armor", "offhand"),
        ("chain-shirt", "Chain Shirt", "armor", "chest"),
        ("long-sword", "Long Sword", "weapon", "weapon"),
        ("gold-band", "Gold Band", "ring", "ring"),
        ("jade-amulet", "Jade Amulet", "amulet", "amulet"),
        ("healing-potion", "Healing Potion", "potion", None),
    ],
)
def test_slot_inference_is_canonical(slug, name, itype, expected):
    """An authored item must land where a procedural one of the same kind does."""
    item = Item(slug=slug, name=name, type=itype)

    assert _slot_for_item(item, {}) == expected


def test_ring_inference_does_not_depend_on_what_is_worn():
    """There is one ring slot now; the old code returned ring1 or ring2."""
    item = Item(slug="gold-band", name="Gold Band", type="ring")

    assert _slot_for_item(item, {}) == "ring"
    assert _slot_for_item(item, {"ring": "silver-band"}) == "ring"


# --------------------------------------------------------------- end to end


@pytest.fixture()
def armoured(client):
    """A logged-in character carrying one piece of starter body armour."""
    user = User.query.filter_by(username="slot_vocab_user").first()
    if not user:
        user = User(username="slot_vocab_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    if not Item.query.filter_by(slug=BODY_ARMOUR).first():
        db.session.add(
            Item(
                slug=BODY_ARMOUR,
                name="Leather Armor",
                type="armor",
                description="fixture",
                value_copper=600,
                level=1,
                rarity="common",
                weight=1.0,
            )
        )
    db.session.commit()

    char = Character(
        user_id=user.id,
        name="Vocab",
        stats=json.dumps({"str": 14, "dex": 10, "con": 12, "int": 10}),
        gear=json.dumps({}),
        items=json.dumps([{"slug": BODY_ARMOUR, "qty": 1}]),
        level=1,
    )
    db.session.add(char)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return char


def _gear(char):
    """The character's gear dict, re-read from the database."""
    db.session.refresh(char)
    return json.loads(char.gear)


def _bag(char):
    """slug -> qty for the character's bag, as the app itself reads it."""
    from app.inventory.utils import load_inventory

    db.session.refresh(char)
    return {e["slug"]: e["qty"] for e in load_inventory(char.items) if "slug" in e}


def test_body_armour_equips_to_chest_and_comes_back_off(client, armoured):
    """The headline bug, end to end: equip, then actually take it off again.

    Body armour used to land in "armor", a slot in no vocabulary at all, so
    unequip_item rejected it with 400 "invalid slot" and the piece was stuck
    on the character permanently.
    """
    equip = client.post(f"/api/characters/{armoured.id}/equip", json={"slug": BODY_ARMOUR})

    assert equip.status_code == 200, equip.get_json()
    assert equip.get_json()["slot"] == "chest"
    assert _gear(armoured)["chest"] == BODY_ARMOUR
    assert BODY_ARMOUR not in _bag(armoured)

    unequip = client.post(f"/api/characters/{armoured.id}/unequip", json={"slot": "chest"})

    assert unequip.status_code == 200, unequip.get_json()
    assert not _gear(armoured).get("chest")
    assert _bag(armoured)[BODY_ARMOUR] == 1


def test_everything_auto_equip_writes_can_be_taken_off_again(client, armoured):
    """auto_equip_for is the producer that broke; unequip_item is the consumer.

    Feeding one straight into the other is what a check on either alone misses.
    """
    gear = auto_equip_for("fighter", ["short-sword", BODY_ARMOUR])
    assert gear, "fixture assumes fighter auto-equips something"
    armoured.gear = json.dumps(gear)
    db.session.commit()

    for slot in gear:
        resp = client.post(f"/api/characters/{armoured.id}/unequip", json={"slot": slot})

        assert resp.status_code == 200, (slot, resp.get_json())
        assert resp.get_json()["unequipped"] == gear[slot]
