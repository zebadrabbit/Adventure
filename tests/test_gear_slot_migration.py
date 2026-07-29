"""The gear-slot migration's mapping table.

Tested through the revision's own remap_gear() rather than by running Alembic,
so the displacement rules are checked directly. The rules:

  armor -> chest, gloves -> hands, boots -> feet, ring1 -> ring
  ring2 -> ring when free, else back to the bag
  legs  -> always back to the bag (no canonical legs slot)
  a legacy item loses to an already-occupied canonical slot and goes to the bag

ring1 beats ring2 for the ring slot regardless of which key comes first in the
row's own JSON -- the tie is broken by SLOT_MAP's table order, not incidental
key order. A displaced slug is appended in whatever shape the target items
list already uses (bare string vs {"slug", "qty"} dict), since load_inventory
infers the whole list's shape from its first entry and a mismatched shape
would make the item invisible on the next load. A displaced gear instance
that would need a bare-string items list to grow a dict entry is not bagged
at all -- the whole row is left untouched rather than dropping the item.
A displaced value that is neither a slug nor a gear instance is not bagged
either: no items shape can carry it, so the row is left untouched too.

Stacking onto an existing bag entry reads that entry's qty exactly as
load_inventory does -- same bare `except Exception`, because int() of a JSON
Infinity raises OverflowError and anything escaping here rolls back the whole
migration for every character. A present-but-invalid or present-but-None qty
reads as 1; a genuine 0 (invisible to the reader, since it drops qty <= 0 on
load) reads as 0, not 1, so no phantom extra item is conjured; and a negative
qty clamps to 0, so the displaced item lands at a readable 1 instead of a
still-invisible negative.

Nothing is ever destroyed.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import importlib.util
import json
import pathlib

import pytest

from app.inventory.utils import load_inventory

REVISION = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "versions" / "c9405725c1f4_unify_gear_slots.py"


@pytest.fixture(scope="module")
def revision():
    spec = importlib.util.spec_from_file_location("_unify_gear_slots", REVISION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def remap(revision):
    return revision.remap_gear


def _slugs(items):
    """Flatten an items list to a slug -> qty map, ignoring gear instances."""
    out = {}
    for entry in items:
        if isinstance(entry, dict) and "slug" in entry and "uid" not in entry:
            out[entry["slug"]] = out.get(entry["slug"], 0) + int(entry.get("qty", 1))
    return out


def _as_the_game_reads_it(items):
    """slug -> qty as the running app would actually see this bag.

    "Not destroyed" means visible to load_inventory, not merely present in the
    JSON: it drops any entry whose qty is <= 0 or whose slug is not a string.
    """
    return {e["slug"]: e["qty"] for e in load_inventory(json.dumps(items)) if "slug" in e}


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


def test_ring1_wins_regardless_of_key_order(remap):
    """The tie-break is SLOT_MAP's table order, not the row's JSON key order."""
    gear, items = remap({"ring2": "silver-band", "ring1": "gold-band"}, [])

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


def test_displaced_slug_stacking_treats_an_existing_qty_zero_as_the_reader_does(remap):
    """load_inventory drops any entry with qty <= 0 -- it's invisible on read.

    Stacking must add exactly one physical item, landing at qty 1, not treat
    the invisible 0 as "nothing here yet" and default it to 1 before adding,
    which would conjure a phantom second item.
    """
    gear, items = remap({"legs": "plate-leggings"}, [{"slug": "plate-leggings", "qty": 0}])

    assert gear == {}
    assert _slugs(items) == {"plate-leggings": 1}


def test_displaced_slug_stacking_survives_a_non_numeric_qty(remap):
    """A corrupt qty must not raise -- that would abort the whole migration
    run partway through and, since _ensure_schema swallows the exception,
    leave the database silently un-migrated with no visible error."""
    gear, items = remap({"legs": "plate-leggings"}, [{"slug": "plate-leggings", "qty": "oops"}])

    assert gear == {}
    assert _slugs(items) == {"plate-leggings": 2}


def test_displaced_slug_stacking_survives_a_json_infinity_qty(remap):
    """json.loads accepts Infinity, and int(float('inf')) raises OverflowError.

    That is neither TypeError nor ValueError, so a coercion narrower than
    load_inventory's own bare `except Exception` lets it escape upgrade():
    alembic rolls the transaction back, _ensure_schema swallows it, and every
    character stays un-migrated with no visible error -- identically on every
    restart. The corrupt row is reachable straight from stored JSON, so this
    parses it the way the migration itself does rather than synthesising inf.
    """
    stored = json.loads('[{"slug": "plate-leggings", "qty": Infinity}]')

    gear, items = remap({"legs": "plate-leggings"}, stored)

    assert gear == {}
    assert _as_the_game_reads_it(items) == {"plate-leggings": 2}


def test_a_negative_existing_qty_does_not_destroy_the_displaced_item(remap):
    """Worse than the qty:0 case: without a clamp this *deletes* a real item.

    -3 + 1 is -2, still <= 0, so load_inventory drops the entry and the
    leggings are gone. The corrupt qty predates the migration, but the loss
    would be caused by the migration writing into it. Clamping to 0 first
    lands the displaced item at a readable 1.
    """
    gear, items = remap({"legs": "plate-leggings"}, [{"slug": "plate-leggings", "qty": -3}])

    assert gear == {}
    assert _as_the_game_reads_it(items) == {"plate-leggings": 1}


def test_a_gear_value_that_is_neither_slug_nor_instance_leaves_the_row_untouched(remap):
    """No items shape can carry it, so bagging it would silently delete it.

    load_inventory keeps a bare-string entry only if it is a str and a
    {"slug", "qty"} entry only if its slug is a str -- an int survives
    neither. Same answer as the gear-instance-into-bare-strings case: leave
    the whole row for a human rather than drop the item.
    """
    gear_in = {"boots": 123, "feet": "steel-boots"}
    items_in = [{"slug": "potion-a", "qty": 1}]

    gear, items = remap(gear_in, items_in)

    assert gear == gear_in
    assert gear is not gear_in
    assert items == items_in
    assert items is not items_in


def test_both_unbaggable_cases_report_why_the_row_was_skipped(revision):
    """upgrade() prints this reason; a silently skipped row is a lost report."""
    instance = {"uid": "abc123", "slot": "chest", "name": "Old Armor"}

    _, _, no_reason = revision._remap({"armor": "chain-shirt"}, [])
    _, _, bare_string = revision._remap({"armor": instance, "chest": "plate-mail"}, ["potion-a"])
    _, _, wrong_type = revision._remap({"boots": 123, "feet": "steel-boots"}, [])

    assert no_reason is None
    assert "bare-string" in bare_string
    assert "int" in wrong_type


def test_gear_instances_survive_displacement_as_dicts(remap):
    """Procedural gear is a dict with a uid; it must go back whole, not as a slug."""
    instance = {"uid": "abc123", "slot": "hands", "name": "Sturdy Gauntlets", "affixes": []}

    gear, items = remap({"gloves": "leather-gloves", "hands": instance}, [])

    assert gear == {"hands": instance}
    assert _slugs(items) == {"leather-gloves": 1}


def test_displaced_slug_matches_a_bare_string_items_shape(remap):
    """load_inventory infers the whole list's format from entry 0.

    Appending a {"slug", "qty"} dict to a list that starts with a bare string
    would make that dict invisible to load_inventory's legacy aggregate
    branch, so the displaced slug must be appended as a bare string too.
    """
    gear, items = remap({"legs": "plate-leggings"}, ["potion-a", "potion-a"])

    assert gear == {}
    assert items == ["potion-a", "potion-a", "plate-leggings"]


def test_gear_instance_into_bare_string_items_leaves_the_row_untouched(remap):
    """No lossless bare-string representation exists for a gear instance.

    Rather than drop it, the whole row is left exactly as it came in.
    """
    instance = {"uid": "abc123", "slot": "chest", "name": "Old Armor", "affixes": []}
    gear_in = {"armor": instance, "chest": "plate-mail"}
    items_in = ["potion-a"]

    gear, items = remap(gear_in, items_in)

    assert gear == gear_in
    assert gear is not gear_in
    assert items == items_in
    assert items is not items_in


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
