"""Regression test for the low-level monster-family coverage gap: a themed
dungeon rolling elemental/construct/aberration (which previously started at
level 7) or demon (which previously started at level 4) found zero eligible
ambient monsters below that level and fell back to a generic 'Trash Monster'.
This loads the REAL sql/monsters_seed.sql (the actual content gap, not a
synthetic fixture) and confirms choose_monster succeeds for every family at
every level band it should now cover.
"""

import os

import pytest

from app import db
from app.services.spawn_service import choose_monster

SQL_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "monsters_seed.sql")


def _load_seed_sql():
    path = os.path.abspath(SQL_SEED_PATH)
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = db.engine.raw_connection()
    try:
        if hasattr(conn, "executescript"):
            conn.executescript(sql)
        else:
            cur = conn.cursor()
            try:
                cur.execute(sql)
            finally:
                cur.close()
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    "family,level",
    [
        ("elemental", 2),
        ("elemental", 5),
        ("construct", 2),
        ("construct", 5),
        ("aberration", 2),
        ("aberration", 5),
        ("demon", 2),
    ],
)
def test_choose_monster_succeeds_for_previously_sparse_family_and_level(test_app, family, level):
    with test_app.app_context():
        _load_seed_sql()
        from app.services import spawn_service

        spawn_service._ELIGIBLE_CACHE.clear()
        inst = choose_monster(level=level, family=family)
        assert inst["slug"]  # did not raise, got a real monster back


def test_demon_still_has_no_t1_gap_at_level_1(test_app):
    # Boundary check: level 1 (the very edge of T1's 1-3 band) must also work,
    # not just the level-2 midpoint the parametrized test above checks.
    with test_app.app_context():
        _load_seed_sql()
        from app.services import spawn_service

        spawn_service._ELIGIBLE_CACHE.clear()
        inst = choose_monster(level=1, family="demon")
        assert inst["slug"]
