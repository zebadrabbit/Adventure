# Gear Slot Vocabulary Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `app/loot/data/archetypes.SLOTS` the only gear-slot vocabulary in the codebase, and migrate existing characters' gear onto it.

**Architecture:** Three producers currently write three different slot vocabularies into the same `Character.gear` JSON dict — `auto_equip_for()` writes `armor`, `inventory_api._slot_for_item()` writes `boots`/`gloves`/`ring1`/`ring2`/`legs`, and the procedural loot path writes the canonical eight. Each producer is corrected at its source, `inventory_api._SLOTS` stops restating a thirteen-name union and imports the canonical list instead, and a data-only Alembic revision rewrites existing rows. No schema changes, no UI changes.

**Tech Stack:** Flask, SQLAlchemy, Alembic, pytest, Postgres.

**Spec:** [specs/2026-07-28-character-panel-redesign.md](../specs/2026-07-28-character-panel-redesign.md)

## Global Constraints

- **The canonical vocabulary is exactly eight slots**, defined at `app/loot/data/archetypes.py:8`:
  `weapon, offhand, head, chest, hands, feet, ring, amulet`.
  Copy it from that constant; never restate the list as a literal in another module.
- **The migration is data-only.** It issues no DDL. It must not `ALTER`, `ADD COLUMN` or `CREATE` anything — the project's schema revisions need guards because `create_all` pre-creates columns and unguarded DDL hangs the suite, and this revision avoids that class entirely by touching only column *values*.
- **No item may be destroyed.** Anything displaced from a slot goes back into the character's `items` JSON. A migration that drops an item is wrong even if the slot mapping is right.
- **Migrations are self-contained.** Do not import application helpers (`load_inventory`, `add_item`, `_normalize_gear`) into the revision — they can change under a migration that must keep working against old data. Inline what you need.
- **Slot mapping, authoritative:**

  | legacy name | destination |
  |---|---|
  | `armor` | `chest` |
  | `gloves` | `hands` |
  | `boots` | `feet` |
  | `ring1` | `ring` |
  | `ring2` | `ring` if free, else back to the bag |
  | `legs` | back to the bag — no canonical slot exists |

  Where a legacy name and its canonical destination are both occupied, the **legacy** item loses and returns to the bag.

## Why this is worth doing

Not cosmetic. `unequip_item` rejects any slot outside `_SLOTS`, so starter body armour written to `armor` by `auto_equip_for()` can never be removed, and no panel draws it. And in the development database all **176** characters hold exactly `{"weapon": "<slug>"}` — nothing has ever been equipped into any other slot.

That second fact is caused by a separate defect (the dungeon's equip path cannot send a `uid`, so procedural gear 404s), which the **next** plan fixes when the two paper dolls are consolidated. It also means this migration is close to a no-op against current data: it is insurance for saves that predate it, and correctness matters more than the volume it moves.

## How to run the tests

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```

`tests/test_camp_regen_buff.py` and `tests/test_camp_supplies_and_cooldown.py` have a known pre-existing flake when run together. If one fails, re-run it alone; passing alone means it is not a regression.

## File Structure

| File | Change | Responsible for |
|---|---|---|
| `app/services/auto_equip.py` | modify | Starter gear picks a canonical slot |
| `app/routes/inventory_api.py` | modify | `_SLOTS` single-sourced; `_slot_for_item` returns canonical names |
| `migrations/versions/c9405725c1f4_unify_gear_slots.py` | **create** | Rewriting existing `Character.gear` rows |
| `tests/test_gear_slot_vocabulary.py` | **create** | That one vocabulary exists and every producer honours it |
| `tests/test_gear_slot_migration.py` | **create** | The mapping table, including the displacement rules |
| `tests/test_autofill_gear.py` | modify | Existing assertion names the `armor` slot |

---

### Task 1: Starter gear picks a canonical slot

`auto_equip_for()` returns `gear["armor"]`. That key is in neither vocabulary, so no panel renders it and `unequip_item` refuses to remove it. It is the smallest and most isolated of the three producers.

**Files:**
- Modify: `app/services/auto_equip.py:73-75`
- Modify: `tests/test_autofill_gear.py:30,36-37`
- Test: `tests/test_gear_slot_vocabulary.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `auto_equip_for(char_class, starter_items)` returns a dict whose keys are drawn only from `archetypes.SLOTS`. Callers are `app/routes/dashboard_helpers.py` (autofill) and the character-creation path; neither reads the key names, so no caller changes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gear_slot_vocabulary.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/test_gear_slot_vocabulary.py -q
```
Expected: `test_canonical_vocabulary_is_the_eight_slots` PASSES (it already describes reality); the other two FAIL on the `armor` key.

- [ ] **Step 3: Return the canonical slot**

In `app/services/auto_equip.py`, replace lines 73-75:

```python
    a = pick(armor_pref)
    if a:
        # Body armour is one piece and lives in "chest" -- the canonical slot
        # from app.loot.data.archetypes.SLOTS. This used to be "armor", a name
        # in no vocabulary at all, so no panel drew it and unequip_item (which
        # rejects any slot outside _SLOTS) could never take it off.
        gear["chest"] = a
    return gear
```

Also update the docstring's example at line 40 from `{"weapon": "short-sword", "armor": "leather-armor"}` to `{"weapon": "short-sword", "chest": "leather-armor"}`, and the note at line 42 from `(armor omitted ...)` to `(chest omitted ...)`.

- [ ] **Step 4: Update the existing autofill test**

In `tests/test_autofill_gear.py`, replace lines 30 and 36-37:

```python
        # gear should be a dict mapping canonical slot -> slug (may omit chest
        # for classes whose starter kit has no armour, e.g. mage/monk/sorcerer)
```

```python
        if "chest" in gear:
            assert isinstance(gear["chest"], str) and len(gear["chest"]) > 0
        assert "armor" not in gear, "body armour must use the canonical 'chest' slot"
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_gear_slot_vocabulary.py tests/test_autofill_gear.py tests/test_autofill_characters.py -q
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/auto_equip.py tests/test_gear_slot_vocabulary.py tests/test_autofill_gear.py
git commit -m "fix(gear): starter body armour goes in the canonical chest slot

auto_equip_for wrote gear[\"armor\"], a slot name in neither the legacy nor
the canonical vocabulary. No panel rendered it, and unequip_item rejects any
slot outside _SLOTS, so starter armour could never be taken off."
```

---

### Task 2: One slot vocabulary in the inventory API

`_SLOTS` restates a thirteen-name union of both vocabularies, and `_slot_for_item` only ever produces the legacy half — so an authored catalogue item and a procedurally generated one of the same kind land in different slots.

**Files:**
- Modify: `app/routes/inventory_api.py:33-48` (`_SLOTS`), `:96-125` (`_slot_for_item`)
- Test: `tests/test_gear_slot_vocabulary.py` (extend)

**Interfaces:**
- Consumes: `app.loot.data.archetypes.SLOTS`, already imported locally at `inventory_api.py:483` inside `equip_item`.
- Produces: `_SLOTS` is a tuple equal to `archetypes.SLOTS`; `_slot_for_item(item, gear)` returns a member of it or `None`. `equip_item` and `unequip_item` validate against it unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gear_slot_vocabulary.py`:

```python
import pytest

from app.models.models import Item
from app.routes.inventory_api import _SLOTS, _slot_for_item


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
```

Note `plate-leggings` → `chest`: D&D body armour is one piece, so there is no
separate legs slot and leg armour is part of the chest piece.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_gear_slot_vocabulary.py -q
```
Expected: `test_inventory_api_does_not_keep_its_own_slot_list` FAILS (13 names vs 8); the gauntlets/boots/greaves/leggings/ring cases FAIL with the legacy names.

- [ ] **Step 3: Single-source `_SLOTS`**

In `app/routes/inventory_api.py`, replace the whole `_SLOTS` tuple (lines 33-48) with:

```python
# The one gear-slot vocabulary. Defined by the loot generator, which is what
# every procedural item, prefix and suffix keys off, so it is what the player
# actually finds. This module used to restate a thirteen-name union of this
# list and an older one, which let the same kind of item land in two different
# slots depending on which code path equipped it.
from app.loot.data.archetypes import SLOTS as _SLOTS
```

Put the import with the other top-level imports rather than leaving it mid-file, and remove the now-redundant local `from app.loot.data.archetypes import SLOTS as GEAR_SLOTS` inside `equip_item` (line 483), using `_SLOTS` at its one use site (line 496) instead.

- [ ] **Step 4: Make slot inference canonical**

In `app/routes/inventory_api.py`, replace the body of `_slot_for_item` (lines 100-125) with:

```python
    t = (item.type or "").lower()
    slug = (item.slug or "").lower()
    name = (item.name or "").lower()
    if t == "weapon":
        return "weapon"
    if t == "armor":
        if "shield" in slug or "shield" in name:
            return "offhand"
        if any(k in slug or k in name for k in ("helm", "helmet", "hood", "cap")):
            return "head"
        if any(k in slug or k in name for k in ("boots", "greaves")):
            return "feet"
        if any(k in slug or k in name for k in ("glove", "gauntlet")):
            return "hands"
        # No legs slot: D&D body armour is one piece, so leg armour is part of
        # the chest piece rather than its own slot.
        return "chest"
    if t == "ring":
        return "ring"
    if t in ("amulet", "necklace", "talisman"):
        return "amulet"
    # tools, potions, scrolls not equippable
    return None
```

Note the `legging`/`pants`/`trousers`/`legs` branch is gone — those fall through to `chest`. The `gear` parameter is now unused by the ring branch but stays in the signature: `equip_item` calls it as `_slot_for_item(item, gear)` in three places and the parameter documents that slot choice may depend on what is worn.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_gear_slot_vocabulary.py tests/test_gear_equip.py tests/test_gear_equip_api.py tests/test_autofill_gear.py -q
```
Expected: all PASS.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add app/routes/inventory_api.py tests/test_gear_slot_vocabulary.py
git commit -m "fix(gear): one slot vocabulary in the inventory API

_SLOTS restated a thirteen-name union of two vocabularies and _slot_for_item
only ever produced the legacy half, so an authored item and a procedurally
generated one of the same kind landed in different slots. _SLOTS is now
archetypes.SLOTS and inference returns canonical names."
```

---

### Task 3: Migrate existing gear onto the canonical slots

Rewrite every character's `gear` JSON. Anything displaced goes back to `items` — no item is destroyed.

**Files:**
- Create: `migrations/versions/c9405725c1f4_unify_gear_slots.py`
- Test: `tests/test_gear_slot_migration.py`

**Interfaces:**
- Consumes: the mapping table from Global Constraints.
- Produces: a module-level `remap_gear(gear, items)` in the revision, returning `(new_gear, new_items)` and mutating neither argument, so the mapping can be tested without running Alembic.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gear_slot_migration.py`:

```python
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

REVISION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "c9405725c1f4_unify_gear_slots.py"
)


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_gear_slot_migration.py -q
```
Expected: collection error — the revision file does not exist.

- [ ] **Step 3: Write the migration**

Create `migrations/versions/c9405725c1f4_unify_gear_slots.py`:

```python
"""Unify gear slot vocabularies onto app.loot.data.archetypes.SLOTS.

Revision ID: c9405725c1f4
Revises: d9e2f3a4b5c6
Create Date: 2026-07-28

Three producers wrote three different slot vocabularies into the same
Character.gear dict. This rewrites existing rows onto the canonical eight.

Data only -- no DDL. Nothing is destroyed: anything displaced from a slot is
appended to the character's items JSON.

Deliberately self-contained. It does not import load_inventory/add_item from
the application: a migration has to keep working against the data as it was,
and app helpers change.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "c9405725c1f4"
down_revision = "d9e2f3a4b5c6"
branch_labels = None
depends_on = None

# legacy slot -> canonical destination. None means "no destination, bag it".
SLOT_MAP = {
    "armor": "chest",
    "gloves": "hands",
    "boots": "feet",
    "ring1": "ring",
    "ring2": "ring",
    "legs": None,
}


def _bag(items, value):
    """Append a displaced gear value to an items list, in place.

    Gear instances (dicts with a uid) go back whole. Legacy slugs stack onto an
    existing entry when one is present, matching the app's own add_item().
    """
    if isinstance(value, dict):
        items.append(value)
        return
    slug = value
    for entry in items:
        if isinstance(entry, dict) and entry.get("slug") == slug and "uid" not in entry:
            entry["qty"] = int(entry.get("qty", 1)) + 1
            return
    items.append({"slug": slug, "qty": 1})


def remap_gear(gear, items):
    """Return (new_gear, new_items). Neither argument is mutated.

    Canonical slots win: where a legacy name and its destination are both
    occupied, the legacy item is bagged. Slot names this table does not know
    are passed through untouched rather than silently eaten.
    """
    new_gear = {}
    new_items = json.loads(json.dumps(items)) if items else []

    # Canonical and unknown slots first, so a legacy item cannot claim a
    # destination that is already spoken for regardless of dict ordering.
    for slot, value in (gear or {}).items():
        if not value:
            continue
        if slot not in SLOT_MAP:
            new_gear[slot] = value

    for slot, value in (gear or {}).items():
        if not value or slot not in SLOT_MAP:
            continue
        dest = SLOT_MAP[slot]
        if dest is None or dest in new_gear:
            _bag(new_items, value)
        else:
            new_gear[dest] = value

    return new_gear, new_items


def upgrade():
    conn = op.get_bind()
    # "character" is quoted: it is a type keyword in several dialects, and
    # Postgres only tolerates it bare by being lenient about non-reserved words.
    rows = conn.execute(sa.text('SELECT id, gear, items FROM "character"')).fetchall()

    for row in rows:
        try:
            gear = json.loads(row.gear) if row.gear else {}
            items = json.loads(row.items) if row.items else []
        except (TypeError, ValueError):
            continue  # malformed JSON predates us; leave it alone
        if not isinstance(gear, dict):
            continue
        if not isinstance(items, list):
            items = []
        if not any(slot in SLOT_MAP for slot in gear):
            continue  # already canonical

        new_gear, new_items = remap_gear(gear, items)
        conn.execute(
            sa.text('UPDATE "character" SET gear = :gear, items = :items WHERE id = :id'),
            {"gear": json.dumps(new_gear), "items": json.dumps(new_items), "id": row.id},
        )


def downgrade():
    # Not reversible: ring1/ring2 collapse to one slot and legs items move to
    # the bag, so the original arrangement cannot be reconstructed. Leaving the
    # data on the canonical vocabulary is the safe outcome either way -- the
    # older code accepted these names too, via the union in _SLOTS.
    pass
```

The table name is `character` (verified via `Character.__tablename__`), and both
statements quote it.

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_gear_slot_migration.py -q
```
Expected: all PASS.

- [ ] **Step 5: Run the migration against the development database**

```bash
.venv/bin/alembic upgrade head
```
Expected: completes without error. Then confirm the vocabulary is clean:

```bash
.venv/bin/python -c "
import json, collections
from app import app
from app.models.models import Character
from app.loot.data.archetypes import SLOTS
with app.app_context():
    c = collections.Counter()
    for ch in Character.query.all():
        g = json.loads(ch.gear or '{}')
        if isinstance(g, dict):
            c.update(g.keys())
    print('slot keys:', dict(c))
    print('non-canonical:', set(c) - set(SLOTS))
"
```
Expected: `non-canonical: set()`.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: no new failures. The suite creates its schema through `create_all`, so a data-only revision changes nothing for it — which is the point of keeping DDL out of this one.

- [ ] **Step 7: Commit**

```bash
git add migrations/versions/c9405725c1f4_unify_gear_slots.py tests/test_gear_slot_migration.py
git commit -m "feat(gear): migrate existing gear onto the canonical slots

Rewrites Character.gear keys: armor->chest, gloves->hands, boots->feet,
ring1->ring. A second ring and any legs item go back to the bag, as does a
legacy item whose canonical destination is already occupied. Nothing is
destroyed.

Data only, no DDL."
```

- [ ] **Step 8: Update the TODO**

Add to `docs/superpowers/TODO.md` under Engineering:

```markdown
- [x] ~~Three gear-slot vocabularies~~ — `auto_equip_for` wrote `armor` (a name
      in no vocabulary, so nothing could unequip it), `_slot_for_item` wrote the
      legacy `boots`/`gloves`/`ring1`/`ring2`, and procedural loot wrote the
      canonical eight, all into the same `gear` dict. Now single-sourced from
      `archetypes.SLOTS`, with a data migration. Plan:
      [plans/2026-07-28-gear-slot-unification.md](plans/2026-07-28-gear-slot-unification.md).
- [ ] **Looted gear cannot be equipped during a run** — the dungeon's only equip
      path (`equipment.js`) posts `{slug, slot}` and has no `uid` branch, so
      procedural instances 404 on the legacy path. Fixed by consolidating the
      two paper dolls onto the one that sends `uid`. Spec:
      [specs/2026-07-28-character-panel-redesign.md](specs/2026-07-28-character-panel-redesign.md).
```

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): gear slot vocabularies unified"
```

---

## Self-Review

**Spec coverage** — the "One slot vocabulary" and "Existing gear migrates in place" sections of `2026-07-28-character-panel-redesign.md`:

| Spec requirement | Task |
|---|---|
| `_SLOTS` imports `archetypes.SLOTS` | 2 |
| `_slot_for_item` returns canonical names | 2 |
| `auto_equip_for` remapped (`armor` → `chest`) | 1 |
| `gloves→hands`, `boots→feet`, `ring1`/`ring2`→`ring` | 3 |
| `legs` → bag | 3 |
| `ring1` wins the ring slot, `ring2` bagged | 3 |
| Legacy loses to an occupied canonical slot | 3 |
| Nothing deleted | 3 (every displacement test asserts the item lands in `items`) |
| Data-only, no DDL | 3 |
| Migration self-contained | 3 |

Out of scope by design, and covered by the next plan: the panel consolidation, the `uid` equip fix, encumbrance on the party frame, and the `tactical-btn-*` base colours.

**Type consistency:** `remap_gear(gear, items) -> (new_gear, new_items)` is defined in Task 3 Step 3 and called with that signature throughout Task 3 Step 1. `SLOT_MAP` uses `None` for "no destination" and `remap_gear` tests `dest is None` — consistent. `_SLOTS` is a tuple in Task 2 and compared with `tuple(_SLOTS) == tuple(SLOTS)`, which holds whether `archetypes.SLOTS` is a list or tuple.

**Known risk:** Task 2 removes the `legging`/`pants`/`trousers` keywords from `_slot_for_item`, so those items now infer `chest` and would displace body armour. The catalogue currently contains **zero** items matching those keywords (verified), so nothing is affected today; it becomes relevant only if leg armour is authored, at which point the right answer is to decide whether the game wants a legs slot at all rather than to restore the keyword branch.
