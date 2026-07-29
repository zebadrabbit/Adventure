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
