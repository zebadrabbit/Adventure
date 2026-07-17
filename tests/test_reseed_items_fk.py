"""Regression test: reseed_items(clear_first=True) must not violate the
dungeon_loot.item_id -> item.id foreign key.

Spec 3 introduced DungeonLoot rows referencing catalog Item rows. Since
DungeonLoot is per-run, ephemeral floor loot (not player-owned property),
clearing the item catalog for reseeding must first clear any DungeonLoot
rows that reference the items being replaced.
"""

from app import db
from app.models.loot import DungeonLoot
from app.models.models import Item
from app.seed_items import clear_item_categories

# NOTE: this exercises clear_item_categories() directly rather than the full
# reseed_items(clear_first=True) entry point. reseed_items() also calls
# execute_sql_file(), which opens a *separate* raw DBAPI connection
# (db.engine.raw_connection()) outside the ORM session. The test suite's
# _db_transaction_rollback fixture (tests/conftest.py) wraps each test's ORM
# session in an uncommitted outer transaction for isolation -- and that
# fixture's own docstring notes raw_connection() is deliberately left
# untouched by it. Combining the two here means the test's own uncommitted
# Item insert (held under the wrapper transaction) row-locks the `item`
# table against execute_sql_file's independent raw connection, deadlocking
# the test process -- a pre-existing test-harness limitation unrelated to
# this bug. clear_item_categories() is where the FK violation and the fix
# both live (it never touches execute_sql_file/raw_connection), so testing
# it directly gives full coverage of the bug without tripping that deadlock.


def test_clear_item_categories_does_not_violate_dungeon_loot_fk(test_app):
    with test_app.app_context():
        # Seed a catalog item in one of the categories that clear_item_categories()
        # deletes ("misc" is one of them).
        item = Item(
            slug="test-fk-widget",
            name="Test FK Widget",
            type="misc",
            description="temp",
            value_copper=1,
            level=0,
            rarity="common",
            weight=1.0,
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

        # Seed a DungeonLoot row referencing it, as would exist for a live
        # dungeon run whose floor loot rolled this item.
        loot = DungeonLoot(seed=12345, x=1, y=1, z=0, item_id=item_id)
        db.session.add(loot)
        db.session.commit()
        loot_id = loot.id

        # Should not raise IntegrityError.
        clear_item_categories()

        # clear_item_categories ran its own raw-SQL deletes on this same
        # session; the ORM identity map doesn't know about them, so force a
        # fresh read.
        db.session.expire_all()

        # The stale loot row referencing the now-deleted item must be gone too.
        assert DungeonLoot.query.filter_by(id=loot_id).first() is None
        # The original test item (type=misc) has been cleared as part of reseed.
        assert Item.query.filter_by(id=item_id).first() is None
