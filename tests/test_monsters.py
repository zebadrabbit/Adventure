import os

from app import db
from app.models import MonsterCatalog
from app.services.spawn_service import choose_monster, sample_distribution

SQL_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "monsters_seed.sql")


def _load_seed_sql():
    # Execute raw SQL seed file (already idempotent). Use direct connection to existing DB.
    path = os.path.abspath(SQL_SEED_PATH)
    if not os.path.exists(path):
        raise RuntimeError("monsters_seed.sql missing at " + path)
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = db.engine.raw_connection()
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def test_monster_seed_load(test_app):
    with test_app.app_context():
        _load_seed_sql()
        rows = MonsterCatalog.query.limit(5).all()
        assert rows, "Expected monsters to be loaded"
        # Check presence of a known slug
        goblin = MonsterCatalog.query.filter_by(slug="goblin_scout_t1").first()
        assert goblin is not None
        assert goblin.level_min == 1 and goblin.level_max >= 2
        # Ensure optional columns accessible (may be None)
        assert hasattr(goblin, "resistances")


def test_choose_monster_level_band(test_app):
    with test_app.app_context():
        _load_seed_sql()
        inst = choose_monster(level=8, party_size=2)
        assert inst["level"] == 8
        # Should choose something whose band includes 8
        row = MonsterCatalog.query.filter_by(slug=inst["slug"]).first()
        assert row.level_min <= 8 <= row.level_max
        # Scaling applied: hp should be > base_hp for party size 2
        assert inst["hp"] > row.base_hp


def test_distribution_variety(test_app):
    with test_app.app_context():
        _load_seed_sql()
        freq = sample_distribution(level=8, samples=80)
        # Expect at least 2 different slugs at level 8 band
        assert len(freq) >= 2
        # Bosses should not appear by default
        assert not any("necromancer_overlord" in k for k in freq.keys())


def test_include_boss(test_app):
    from app.services.spawn_service import choose_monster as choose

    with test_app.app_context():
        _load_seed_sql()
        # Run several attempts including boss
        seen_boss = False
        for _ in range(200):
            try:
                inst = choose(level=15, include_boss=True)
            except ValueError:
                continue
            if inst["boss"]:
                seen_boss = True
                break
        assert seen_boss, "Expected to encounter a boss when include_boss=True over many samples"
