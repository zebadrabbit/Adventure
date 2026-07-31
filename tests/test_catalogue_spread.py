"""The static catalogue has to scale with depth, or nothing downstream can.

Every one of the 215 rows in sql/items_potions.sql and sql/items_misc.sql used
to carry no level and no rarity: all 34 INSERT headers used the 5-column form,
so the loader (`app/seed_items.py::_augment_item_level_default`) stamped
`, 0, 'common', 1.0` on every one. 225 of 229 rows in a seeded database were
level 0 common.

The consequence was not cosmetic. Four separate mechanisms filter or weight
loot by these two columns, and with every row identical **all four were
no-ops**:

  * `app/loot/generator.py`'s level window (`lo <= it.level <= hi`)
  * `app/loot/tables.py`'s rarity filter (every tier's tuple includes 'common')
  * the rarity draw weights in both modules
  * `LEVEL_HEADROOM`, which excluded nothing

A Mythic dungeon at the cap and a Novice dungeon at level 1 drew from the same
flat pool. These tests read the seed files directly rather than the database:
`db_isolation` rebuilds leave a minimal catalogue mid-suite, so asserting
against the live table is order-dependent (docs/TESTING.md).
"""

import re
from collections import Counter
from pathlib import Path

import pytest

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SEED_FILES = ["items_potions.sql", "items_misc.sql"]

# slug, name, type, description, value_copper, level, rarity, weight
_ROW = re.compile(
    r"^\s*\('(?P<slug>[^']+)','(?P<name>(?:[^']|'')*)','(?P<type>[^']+)',"
    r"'(?P<desc>(?:[^']|'')*)',\s*(?P<price>\d+),\s*(?P<level>\d+),\s*'(?P<rarity>[^']+)'"
)


def _rows():
    out = []
    for fname in SEED_FILES:
        for line in (SQL_DIR / fname).read_text(encoding="utf-8").splitlines():
            m = _ROW.match(line)
            if m:
                out.append(m)
    return out


def test_the_seed_files_parse():
    """A guard on the guards: a regex matching nothing would make every
    assertion below pass by having no rows to disagree with."""
    assert len(_rows()) > 200, f"only parsed {len(_rows())} catalogue rows"


def test_every_row_carries_a_level_and_a_rarity():
    """i.e. every INSERT header is the 8-column form. In the 5-column form the
    loader supplies the defaults and the row silently becomes level 0 common."""
    for fname in SEED_FILES:
        text = (SQL_DIR / fname).read_text(encoding="utf-8")
        headers = re.findall(r"INSERT INTO item \(([^)]*)\)", text)
        assert headers, f"{fname} has no item INSERT at all"
        for h in headers:
            assert "level" in h and "rarity" in h and "weight" in h, f"{fname}: 5-column header still present: {h}"


def test_the_catalogue_is_not_all_one_rarity():
    counts = Counter(m.group("rarity") for m in _rows())

    assert len(counts) >= 4, f"only {len(counts)} rarities in the whole catalogue: {dict(counts)}"
    most_common_share = counts.most_common(1)[0][1] / sum(counts.values())
    assert most_common_share < 0.5, f"one rarity is {most_common_share:.0%} of the catalogue: {dict(counts)}"


def test_the_catalogue_covers_the_whole_level_range():
    """A tier that can reach level 20 needs something to drop there."""
    levels = {int(m.group("level")) for m in _rows()}

    for band_lo, band_hi in ((1, 4), (5, 9), (10, 14), (15, 18), (19, 20)):
        assert any(band_lo <= level <= band_hi for level in levels), f"no catalogue item at levels {band_lo}-{band_hi}"


def test_potion_level_matches_its_slug_tier():
    """151 potions carry their tier in the slug (`_l<N>`), which is where the
    level came from -- so the two must not drift apart."""
    mismatched = []
    for m in _rows():
        tier = re.search(r"_l(\d+)$", m.group("slug"))
        if tier and int(tier.group(1)) != int(m.group("level")):
            mismatched.append(f"{m.group('slug')} is level {m.group('level')}, slug says {tier.group(1)}")
    assert not mismatched, mismatched


def test_free_items_stay_at_level_zero():
    """Keys and quest items have no price to rank by, and the generator treats
    level 0 as always-eligible -- which is what a gate key should be."""
    for m in _rows():
        if int(m.group("price")) == 0:
            assert int(m.group("level")) == 0, f"{m.group('slug')} is free but level {m.group('level')}"


@pytest.mark.parametrize(
    "band,expected", [(1, "common"), (7, "uncommon"), (12, "rare"), (16, "epic"), (20, "legendary")]
)
def test_rarity_tracks_level(band, expected):
    """Rarity is banded from the level, so the two can never disagree."""
    for m in _rows():
        if int(m.group("level")) == band:
            assert m.group("rarity") == expected, f"{m.group('slug')} is level {band} but {m.group('rarity')}"
