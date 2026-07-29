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


def _unbaggable(value, aggregate_shaped):
    """Why ``value`` cannot be bagged without losing it, or None if it can be.

    Both cases end the same way: the row is left untouched and the reason is
    printed, rather than writing a bag entry the app's own reader would throw
    away on the next load. Nothing is destroyed to fix the rest of the row.
    """
    if not isinstance(value, (str, dict)):
        # load_inventory keeps a bare-string entry only if it is a str, and a
        # {"slug", "qty"} entry only if its slug is a str -- so neither shape
        # can carry, say, an int. Bagging one would silently delete it.
        return f"a displaced gear value is neither a slug nor a gear instance (got {type(value).__name__})"
    if aggregate_shaped and isinstance(value, dict):
        return "a displaced gear instance has no lossless representation in this character's bare-string items list"
    return None


def _bag(items, value, aggregate_shaped):
    """Append a displaced gear value to an items list, in place.

    Callers must have cleared ``value`` through ``_unbaggable`` first (see
    ``remap_gear``). Gear instances (dicts with a uid) go back whole. A legacy
    slug stacks onto an existing {"slug", "qty"} entry when one is present,
    matching the app's own add_item() -- unless the list is in load_inventory's
    legacy bare-string aggregate shape (entry 0 is a plain string), in which
    case the slug is appended as a bare string too, matching that shape:
    appending a dict there would be silently unreadable by that loader, which
    decides the whole list's format from entry 0 alone.
    """
    if isinstance(value, dict):
        items.append(value)
        return
    slug = value
    if aggregate_shaped:
        items.append(slug)
        return
    for entry in items:
        if isinstance(entry, dict) and entry.get("slug") == slug and "uid" not in entry:
            # Read this field exactly as load_inventory does -- a bare
            # `except Exception`, because int() of a JSON Infinity raises
            # OverflowError, which is neither TypeError nor ValueError and
            # would escape upgrade(), roll the whole migration back, and
            # (since _ensure_schema swallows it) leave every character
            # un-migrated with no visible error, on every restart.
            #
            # A falsy-but-valid 0 is deliberately *not* treated as "absent":
            # `or 1` would turn a reader-invisible qty:0 into a phantom extra
            # item (0 -> 1, then +1 -> 2 instead of the correct 1). Negative
            # quantities are equally invisible to the reader (it drops
            # qty <= 0), so they clamp to 0 as well -- without the clamp,
            # stacking onto qty:-3 lands on -2, still invisible, and the
            # displaced item is gone.
            try:
                q = int(entry.get("qty", 1))
            except Exception:
                q = 1
            entry["qty"] = max(0, q) + 1
            return
    items.append({"slug": slug, "qty": 1})


def _remap(gear, items):
    """The whole of remap_gear, plus the reason a row was left alone.

    Returns (new_gear, new_items, reason). ``reason`` is None when the remap
    succeeded, and otherwise a human-readable string naming the displaced
    value that had no lossless home -- see remap_gear's docstring. upgrade()
    wants that string; the tests only want the two mapped halves.
    """
    gear = gear or {}
    items = items or []
    original_gear = dict(gear)
    original_items = json.loads(json.dumps(items)) if items else []
    aggregate_shaped = bool(items) and isinstance(items[0], str)

    new_gear = {}
    new_items = json.loads(json.dumps(items)) if items else []

    # Canonical and unknown slots first, so a legacy item cannot claim a
    # destination that is already spoken for regardless of dict ordering.
    for slot, value in gear.items():
        if not value:
            continue
        if slot not in SLOT_MAP:
            new_gear[slot] = value

    # Legacy slots in SLOT_MAP's own order (not the row's JSON key order), so
    # a tie between two legacy names sharing a destination -- ring1/ring2 --
    # resolves deterministically by table order rather than incidental
    # dict/JSON ordering.
    for slot in SLOT_MAP:
        value = gear.get(slot)
        if not value:
            continue
        dest = SLOT_MAP[slot]
        if dest is None or dest in new_gear:
            reason = _unbaggable(value, aggregate_shaped)
            if reason:
                return original_gear, original_items, reason
            _bag(new_items, value, aggregate_shaped)
        else:
            new_gear[dest] = value

    return new_gear, new_items, None


def remap_gear(gear, items):
    """Return (new_gear, new_items).

    Neither the ``gear`` dict nor the ``items`` list passed in is modified in
    place. ``items`` is JSON-round-tripped, so its entries are fresh objects,
    never shared with the input. ``gear``'s values are not deep-copied --
    ``new_gear`` reuses them by reference, so a gear-instance dict that
    survives displacement is the *same* object as in the input, not a clone.

    Canonical slots win: where a legacy name and its destination are both
    occupied, the legacy item is bagged. Slot names this table does not know
    are passed through untouched rather than silently eaten. Among legacy
    names that share a destination (ring1/ring2), the winner is SLOT_MAP's own
    order -- ring1 -- not the row's incidental JSON key order.

    A displaced value with no lossless home in this row's items list -- a gear
    instance (a dict) that would have to go into a bare-string aggregate list,
    or a value that is neither a slug nor a gear instance and so survives in
    neither items shape -- leaves the whole row untouched (original gear and
    items returned as-is). A partial remap that drops one item to fix the rest
    is not acceptable.
    """
    new_gear, new_items, _reason = _remap(gear, items)
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
            # Can't safely bag a displaced item into something that isn't a
            # list -- leaving it for a human to look at, but say so, or no
            # one finds out this row was skipped.
            print(
                f"gear-slot migration: character {row.id} left unchanged -- "
                f"items column is not a list (got {type(items).__name__})"
            )
            continue
        if not any(slot in SLOT_MAP for slot in gear):
            continue  # already canonical

        new_gear, new_items, reason = _remap(gear, items)
        if reason:
            # A displaced value with no lossless home in this row's items list
            # (see remap_gear's docstring). The row is left exactly as it came
            # in -- say so, or no one finds out it was skipped.
            print(f"gear-slot migration: character {row.id} left unchanged -- {reason}")
            continue
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
