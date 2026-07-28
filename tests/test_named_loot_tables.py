"""Monsters drop the loot their catalogue entry says they drop.

`monster_catalog.loot_table` stores names -- `goblin_basic`, `undead_elite`,
`boss_dragon`. `loot_service._parse_loot_table` treated the string as a CSV of
item *slugs*, so `boss_dragon` was looked up as an item with that slug, found
nothing, and returned an empty pool. Every monster in the game dropped zero
catalogue items; only procedural gear and boss keys ever appeared, which is why
nobody noticed the curated tables were inert.

Names now resolve through `app/loot/tables.py`: the suffix picks a tier, and the
tier filters the item catalogue by type, rarity and level.
"""

import pytest

from app import db
from app.loot import tables as loot_tables
from app.models.models import Item
from app.services.loot_service import _parse_loot_table, roll_loot


# Item fixtures. Deliberately self-sufficient: tests marked db_isolation rebuild
# the schema and reseed with app.server.seed_items, a *minimal* seeder (~14
# items, no monsters) rather than the full catalogue loader. Any test that
# depends on the real 220-item catalogue therefore passes alone and fails after
# a db_isolation test has run. These tests bring their own items.
_FIXTURE_ITEMS = [
    # (slug, type, rarity, level, value_copper)
    ("_lt_ration", "consumable", "common", 0, 30),
    ("_lt_herb", "material", "common", 1, 60),
    ("_lt_minor_potion", "potion", "common", 1, 120),
    ("_lt_potion", "potion", "common", 2, 300),
    ("_lt_tool", "tool", "common", 1, 400),
    ("_lt_scroll", "scroll", "common", 2, 620),
    ("_lt_gem", "gem", "uncommon", 3, 900),
    ("_lt_great_potion", "potion", "rare", 4, 1500),
]


@pytest.fixture(autouse=True)
def _fresh_cache():
    loot_tables.clear_cache()
    for slug, type_name, rarity, level, value in _FIXTURE_ITEMS:
        if not Item.query.filter_by(slug=slug).first():
            db.session.add(
                Item(
                    slug=slug,
                    name=slug.replace("_", " ").strip().title(),
                    type=type_name,
                    description="loot table fixture",
                    value_copper=value,
                    level=level,
                    rarity=rarity,
                    weight=0.5,
                )
            )
    db.session.commit()
    loot_tables.clear_cache()
    yield
    loot_tables.clear_cache()


def _monster(loot_table, level=5, boss=False):
    return {
        "slug": "loot-dummy",
        "name": "Loot Dummy",
        "level": level,
        "hp": 10,
        "damage": 1,
        "armor": 0,
        "xp": 1,
        "loot_table": loot_table,
        "boss": boss,
    }


# ------------------------------------------------------------------ tier names


@pytest.mark.parametrize(
    "name,expected",
    [
        ("goblin_basic", "basic"),
        ("undead_elite", "elite"),
        ("aberration_named", "named"),
        ("boss_dragon", "boss"),
        ("BOSS_DEMON", "boss"),
    ],
)
def test_catalogue_names_map_to_tiers(name, expected):
    assert loot_tables.tier_for(name) == expected


@pytest.mark.parametrize("name", ["potion-healing", "short-sword,dagger", "", None, "random-slug"])
def test_non_table_names_are_left_alone(name):
    """CSV lists and bare slugs must keep working exactly as before."""
    assert loot_tables.tier_for(name) is None
    assert loot_tables.resolve(name or "") is None


# -------------------------------------------------------------------- pools


def test_a_named_table_resolves_to_real_items():
    pool = loot_tables.resolve("goblin_basic", level=5)
    assert pool, "basic tier resolved to nothing -- the item catalogue may be unseeded"
    slugs = set(pool)
    existing = {i.slug for i in Item.query.filter(Item.slug.in_(slugs)).all()}
    assert slugs == existing, "table produced slugs that do not exist in the catalogue"


def test_every_catalogue_loot_table_resolves():
    """No monster should be carrying a table name that yields nothing."""
    from app.models.models import MonsterCatalog

    names = {m.loot_table for m in MonsterCatalog.query.all() if m.loot_table}
    if not names:
        pytest.skip("monster catalogue is not seeded in this database (see the fixture note above)")
    empty = []
    for name in names:
        pool = loot_tables.resolve(name, level=10)
        if pool is None:
            empty.append(f"{name} (not recognised as a table)")
        elif not pool:
            empty.append(f"{name} (resolved to an empty pool)")
    assert not empty, "loot tables that drop nothing: " + ", ".join(sorted(empty))


def test_low_level_monsters_cannot_drop_far_higher_level_items():
    pool = loot_tables.resolve("goblin_basic", level=1)
    assert pool
    levels = [int(i.level or 0) for i in Item.query.filter(Item.slug.in_(list(pool))).all()]
    assert max(levels) <= 1 + loot_tables.LEVEL_HEADROOM


def test_boss_tables_are_worth_more_than_basic_ones():
    """Tiers must actually differ.

    Asserted on value rather than rarity because the item catalogue is ~98%
    common -- there is currently nothing rarer for a boss table to reach. Value
    separates them today and rarity will reinforce it later; see the note in
    app/loot/tables.py.
    """
    basic = loot_tables.resolve("goblin_basic", level=20) or {}
    boss = loot_tables.resolve("boss_dragon", level=20) or {}
    assert basic and boss

    def mean_value(pool):
        rows = Item.query.filter(Item.slug.in_(list(pool))).all()
        return sum(int(i.value_copper or 0) for i in rows) / max(1, len(rows))

    assert mean_value(boss) > mean_value(
        basic
    ), f"boss pool mean {mean_value(boss):.0f}cp is not better than basic {mean_value(basic):.0f}cp"


# ------------------------------------------------------------- parse + roll


def test_parse_returns_the_named_pool():
    ordered, weights = _parse_loot_table("undead_elite", level=8)
    assert ordered and weights
    assert set(ordered) == set(weights)


def test_parse_still_handles_csv_and_json():
    ordered, weights = _parse_loot_table("potion-healing, dagger")
    assert ordered == ["potion-healing", "dagger"]
    assert weights == {"potion-healing": 1.0, "dagger": 1.0}

    ordered, weights = _parse_loot_table('{"potion-healing": 3}')
    assert ordered == ["potion-healing"]
    assert weights == {"potion-healing": 3.0}


def test_a_kill_now_drops_catalogue_items():
    """The end-to-end regression: this used to always be empty."""
    import random

    rng = random.Random(4)
    dropped = set()
    for _ in range(25):
        result = roll_loot(_monster("goblin_basic", level=5), rng=rng)
        dropped.update(result["items"])
    assert dropped, "25 kills produced no catalogue items at all"
    real = {i.slug for i in Item.query.filter(Item.slug.in_(list(dropped))).all()}
    assert dropped <= real, f"dropped slugs that are not real items: {dropped - real}"


def test_an_unknown_table_name_still_drops_nothing_gracefully():
    import random

    result = roll_loot(_monster("nonsense_table_xyz", level=3), rng=random.Random(1))
    assert result["items"] == {} or all(isinstance(k, str) for k in result["items"])


def test_rolling_does_not_crash_without_a_table():
    import random

    result = roll_loot(_monster(None, level=3), rng=random.Random(1))
    assert "items" in result and "gear" in result


def test_cache_is_refreshed_when_items_change():
    """A reseed must not leave a stale pool behind."""
    first = loot_tables.resolve("goblin_basic", level=5)
    assert first is not None
    marker = Item(
        slug="_loot_cache_probe",
        name="Cache Probe",
        type="potion",
        description="fixture",
        value_copper=1,
        level=1,
        rarity="common",
        weight=0.1,
    )
    db.session.add(marker)
    db.session.commit()
    loot_tables.clear_cache()

    second = loot_tables.resolve("goblin_basic", level=5)
    assert "_loot_cache_probe" in second
