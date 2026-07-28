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

from app.loot.data.archetypes import SLOTS
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
