"""The gear-slot migration's mapping table.

Tested through the revision's own remap_gear() rather than by running Alembic,
so the displacement rules are checked directly. The rules:

  armor -> chest, gloves -> hands, boots -> feet, ring1 -> ring
  ring2 -> ring when free, else back to the bag
  legs  -> always back to the bag (no canonical legs slot)
  a legacy item loses to an already-occupied canonical slot and goes to the bag

Nothing is ever destroyed.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import importlib.util
import pathlib

import pytest

REVISION = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "versions" / "c9405725c1f4_unify_gear_slots.py"


@pytest.fixture(scope="module")
def remap():
    spec = importlib.util.spec_from_file_location("_unify_gear_slots", REVISION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.remap_gear


def _slugs(items):
    """Flatten an items list to a slug -> qty map, ignoring gear instances."""
    out = {}
    for entry in items:
        if isinstance(entry, dict) and "slug" in entry and "uid" not in entry:
            out[entry["slug"]] = out.get(entry["slug"], 0) + int(entry.get("qty", 1))
    return out


def test_straight_renames(remap):
    gear, items = remap(
        {"armor": "chain-shirt", "gloves": "leather-gloves", "boots": "steel-boots", "ring1": "gold-band"},
        [],
    )

    assert gear == {
        "chest": "chain-shirt",
        "hands": "leather-gloves",
        "feet": "steel-boots",
        "ring": "gold-band",
    }
    assert items == []


def test_canonical_slots_are_left_alone(remap):
    before = {"weapon": "long-sword", "chest": "plate-mail", "ring": "gold-band"}

    gear, items = remap(before, [])

    assert gear == before
    assert items == []


def test_second_ring_goes_to_the_bag(remap):
    gear, items = remap({"ring1": "gold-band", "ring2": "silver-band"}, [])

    assert gear == {"ring": "gold-band"}
    assert _slugs(items) == {"silver-band": 1}


def test_legs_always_goes_to_the_bag(remap):
    gear, items = remap({"legs": "plate-leggings", "chest": "plate-mail"}, [])

    assert gear == {"chest": "plate-mail"}
    assert _slugs(items) == {"plate-leggings": 1}


def test_legacy_loses_to_an_occupied_canonical_slot(remap):
    """Both names filled: the canonical item stays, the legacy one is bagged."""
    gear, items = remap({"armor": "chain-shirt", "chest": "plate-mail"}, [])

    assert gear == {"chest": "plate-mail"}
    assert _slugs(items) == {"chain-shirt": 1}


def test_displaced_slug_stacks_onto_an_existing_bag_entry(remap):
    gear, items = remap({"legs": "plate-leggings"}, [{"slug": "plate-leggings", "qty": 2}])

    assert gear == {}
    assert _slugs(items) == {"plate-leggings": 3}


def test_gear_instances_survive_displacement_as_dicts(remap):
    """Procedural gear is a dict with a uid; it must go back whole, not as a slug."""
    instance = {"uid": "abc123", "slot": "hands", "name": "Sturdy Gauntlets", "affixes": []}

    gear, items = remap({"gloves": "leather-gloves", "hands": instance}, [])

    assert gear == {"hands": instance}
    assert _slugs(items) == {"leather-gloves": 1}


def test_empty_and_null_slots_are_dropped(remap):
    """unequip_item's legacy path writes gear[slot] = None rather than deleting."""
    gear, items = remap({"weapon": "long-sword", "boots": None, "gloves": ""}, [])

    assert gear == {"weapon": "long-sword"}
    assert items == []


def test_unknown_slot_names_are_left_untouched(remap):
    """Forward-compatible: don't silently eat a slot this table doesn't know."""
    gear, items = remap({"trinket": "odd-thing"}, [])

    assert gear == {"trinket": "odd-thing"}
    assert items == []


def test_inputs_are_not_mutated(remap):
    gear_in = {"armor": "chain-shirt"}
    items_in = []

    remap(gear_in, items_in)

    assert gear_in == {"armor": "chain-shirt"}
    assert items_in == []
