"""Reseeding must work on a database that has been played.

Found 2026-07-28 with both the dev and test databases sitting at 0 monsters and
0 archetypes: `reseed-items` aborts partway on any database containing floor
loot, and everything after the failing file never loads.

`clear_item_categories` cleared `dungeon_loot` only for items of type
weapon/armor/potion/misc, but the SQL seed files delete a wider set --
items_misc.sql alone covers tool, gem, key, material, quest, scroll and
consumable. A single floor-loot row pointing at, say, a gem survived the clear
and then blocked that file's own DELETE with a
`dungeon_loot_item_id_fkey` violation. seed_items raises RuntimeError on a
failed file, so the monster catalogue -- loaded last -- was never reached, and
the game was left with no monsters at all.

The failure is silent from the player's side: encounters fall back to
"Elite Monster" stubs (see test_spawn_integration_catalog) rather than erroring.
"""

import pytest
from sqlalchemy import text

from app import db
from app.models.loot import DungeonLoot
from app.models.models import Item
from app.seed_items import clear_item_categories


def _an_item_of_type(type_name: str) -> Item:
    """An existing catalogue item of the given type, or a created one."""
    item = Item.query.filter_by(type=type_name).first()
    if item:
        return item
    item = Item(
        slug=f"_test_{type_name}_item",
        name=f"Test {type_name}",
        type=type_name,
        description="fixture",
        value_copper=10,
        level=1,
        rarity="common",
        weight=1.0,
    )
    db.session.add(item)
    db.session.commit()
    return item


@pytest.mark.parametrize("item_type", ["gem", "scroll", "tool", "material", "potion"])
def test_clearing_items_releases_floor_loot_of_every_type(item_type):
    """The bug: only four types had their floor loot released."""
    item = _an_item_of_type(item_type)
    db.session.add(DungeonLoot(seed=987654, x=1, y=1, z=0, item_id=item.id))
    db.session.commit()

    clear_item_categories()

    remaining = db.session.execute(
        text("SELECT COUNT(*) FROM dungeon_loot WHERE item_id = :iid"), {"iid": item.id}
    ).scalar()
    assert remaining == 0, f"floor loot referencing a {item_type} survived the clear and will block the reseed"


def test_items_can_be_deleted_after_clearing(monkeypatch):
    """End-to-end shape of the failure: the DELETE the seed files run."""
    item = _an_item_of_type("gem")
    db.session.add(DungeonLoot(seed=987655, x=2, y=2, z=0, item_id=item.id))
    db.session.commit()

    clear_item_categories()

    # This is what items_misc.sql does; it must not raise a FK violation.
    db.session.execute(text("DELETE FROM item WHERE type IN ('gem','scroll','tool','material','quest','consumable')"))
    db.session.commit()


def test_clear_leaves_no_floor_loot_at_all():
    """Floor loot is per-run and regenerated; clearing all of it is the contract."""
    item = _an_item_of_type("potion")
    db.session.add(DungeonLoot(seed=987656, x=3, y=3, z=0, item_id=item.id))
    db.session.commit()

    clear_item_categories()

    assert db.session.execute(text("SELECT COUNT(*) FROM dungeon_loot")).scalar() == 0
