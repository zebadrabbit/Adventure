"""Every themed dungeon, at every depth, must have an ordinary monster to spawn.

When `_eligible_monsters` returns an empty pool, `choose_monster` raises and
`populate_spawn_stats` swallows it into a nameless "Trash Monster" with
`hp = level * 20`, **no xp key and no loot_table** -- the kill pays nothing and
the player is never told why. Silent by construction, so it needs a guard.

Two separate holes existed, and they need two different kinds of test:

  * **A data hole.** The catalogue had no non-boss row for humanoid at 16-18,
    nor for elemental or aberration at 19-20. That is a fact about
    `sql/monsters_seed.sql`, so it is checked by reading that file -- not the
    database, which `db_isolation` rebuilds down to a minimal catalogue
    mid-suite (see docs/TESTING.md). An earlier version of this file asserted
    against the live table and so passed alone and failed in a full run.

  * **A logic hole.** `_eligible_monsters` applied its boss filter *after* the
    level-ceiling fallback, so a band whose only rows were bosses looked
    non-empty, skipped the fallback, and was then emptied by the filter. That is
    checked with a private synthetic family, the house pattern borrowed from
    `test_catalogue_level_ceiling.py`.

The logic test is the one that matters going forward: it fails for any future
boss-only band, while the data test only knows about the families that exist
today.
"""

import re
from pathlib import Path

import pytest

from app import db
from app.models.models import MonsterCatalog
from app.services import spawn_service

# --------------------------------------------------------------- the data hole

SEED = Path(__file__).resolve().parent.parent / "sql" / "monsters_seed.sql"

# Families a dungeon can actually be themed as. A family outside this list
# (dragon, today) is never chosen as a theme, so a gap there is not player-facing.
THEME_FAMILIES = sorted(spawn_service.MONSTER_THEME_FAMILIES)

_KNOWN_FAMILIES = set(spawn_service.MONSTER_THEME_FAMILIES) | {"dragon"}

_ROW = re.compile(r"^\s*\('(?P<slug>[^']+)',\s*'?(?P<rest>.*?)\)\s*[,;]\s*$")


def _seed_rows():
    """(family, level_min, level_max, is_boss) for every row in the seed file."""
    rows = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        fields = [f.strip().strip("'") for f in m.group("rest").split(",")]
        family = next((f for f in fields if f in _KNOWN_FAMILIES), None)
        ints = [f for f in fields if f.lstrip("-").isdigit()]
        if family is None or len(ints) < 2:
            continue
        lmin, lmax = int(ints[0]), int(ints[1])
        rows.append((family, lmin, lmax, fields[-1].lower() == "true"))
    return rows


def test_the_seed_file_parses():
    """A guard on the guard: a regex that matched nothing would make every
    coverage assertion below pass by having no rows to disagree with."""
    rows = _seed_rows()
    assert len(rows) > 100, f"only parsed {len(rows)} monster rows out of {SEED}"


@pytest.mark.parametrize("family", THEME_FAMILIES)
def test_every_themed_family_has_an_ordinary_monster_at_every_level(family):
    all_rows = _seed_rows()
    ordinary = [r for r in all_rows if r[0] == family and not r[3]]
    top = max((r[2] for r in all_rows if r[0] == family), default=0)
    assert top >= 20, f"{family} tops out at level {top}; the catalogue should reach 20"

    missing = [lvl for lvl in range(1, top + 1) if not any(r[1] <= lvl <= r[2] for r in ordinary)]

    assert not missing, (
        f"{family} has no non-boss monster at level(s) {missing} -- a dungeon themed "
        f"{family} at that depth spawns a nameless stub worth zero xp and zero items"
    )


# -------------------------------------------------------------- the logic hole

FAMILY = "_covtest"  # private, so the real catalogue cannot mask a failure


@pytest.fixture()
def _catalogue(test_app):
    """A tiny catalogue whose deepest band holds nothing but a boss."""
    with test_app.app_context():
        spawn_service.clear_cache()
        MonsterCatalog.query.filter_by(family=FAMILY).delete()
        for slug, lmin, lmax, boss, rarity in [
            ("_cov_rat", 1, 5, False, "common"),
            ("_cov_wolf", 6, 10, False, "common"),
            ("_cov_tyrant", 11, 12, True, "boss"),  # boss-only top band
        ]:
            db.session.add(
                MonsterCatalog(
                    slug=slug,
                    name=slug,
                    level_min=lmin,
                    level_max=lmax,
                    base_hp=10,
                    base_damage=2,
                    armor=0,
                    speed=10,
                    rarity=rarity,
                    family=FAMILY,
                    xp_base=5,
                    boss=boss,
                )
            )
        db.session.commit()
        yield
        spawn_service.clear_cache()
        MonsterCatalog.query.filter_by(family=FAMILY).delete()
        db.session.commit()


def test_a_boss_only_band_still_yields_an_ordinary_monster(test_app, _catalogue):
    """Levels 11-12 hold only a boss. Asking for an ordinary monster there must
    fall back rather than return nothing -- the filter has to run *before* the
    emptiness test, not after it."""
    with test_app.app_context():
        spawn_service.clear_cache()
        rows = spawn_service._eligible_monsters(11, family=FAMILY, include_boss=False)

        assert rows, "a boss-only band produced an empty ordinary pool -- spawns degrade to a nameless stub"
        assert not any(r.boss for r in rows), "an ordinary spawn pool must not contain bosses"


def test_above_the_ceiling_the_fallback_is_also_boss_filtered(test_app, _catalogue):
    with test_app.app_context():
        spawn_service.clear_cache()
        rows = spawn_service._eligible_monsters(40, family=FAMILY, include_boss=False)

        assert rows, "above the ceiling the fallback produced nothing"
        assert not any(r.boss for r in rows), "the fallback handed back a boss for an ordinary spawn"


def test_a_boss_pool_still_contains_bosses(test_app, _catalogue):
    with test_app.app_context():
        spawn_service.clear_cache()
        rows = spawn_service._eligible_monsters(40, family=FAMILY, include_boss=True)

        assert any(r.boss for r in rows), "a boss-inclusive pool lost its bosses"
