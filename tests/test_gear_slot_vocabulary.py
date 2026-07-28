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

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import pytest

from app.loot.data.archetypes import SLOTS
from app.models.models import Item
from app.routes.inventory_api import _SLOTS, _slot_for_item
from app.services.auto_equip import AUTO_EQUIP_PREFS, auto_equip_for


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
