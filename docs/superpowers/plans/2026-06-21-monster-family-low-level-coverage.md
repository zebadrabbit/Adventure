# Widen Low-Level Monster-Family Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 missing low-level `MonsterCatalog` rows to `sql/monsters_seed.sql` so every theme family (`elemental`, `construct`, `aberration`, `demon`) has real monster content at every level band a low-level themed dungeon could roll, eliminating a `choose_monster` `ValueError`-and-generic-fallback gap.

**Architecture:** Pure data addition to the existing seed SQL file — no code changes. `choose_monster`/`_eligible_monsters` (`app/services/spawn_service.py`) already query generically by family + level-band overlap; this plan only adds rows for the gap.

**Tech Stack:** SQL (seed data), pytest (raw-SQL-loading test pattern already established in `tests/test_monsters.py`).

## Global Constraints

- `elemental`, `construct`, `aberration` need T1 (level_min=1, level_max=3) AND T2 (level_min=4, level_max=6) rows added — they currently start at T3 (level 7).
- `demon` needs only a T1 (level_min=1, level_max=3) row added — it currently starts at T2 (level 4).
- All 7 new rows: `rarity = 'common'`, `boss = false`, matching every other family's T1/T2 baseline rows in this file.
- No changes to `app/services/spawn_service.py` or any other application code — this is a content-only fix.
- No changes to any existing row in `sql/monsters_seed.sql`.

---

### Task 1: Add the 7 missing rows and verify via the real seed file

**Files:**
- Modify: `sql/monsters_seed.sql`
- Test: `tests/test_monster_family_low_level_coverage.py` (new file)

**Interfaces:** None — this is the only task in this plan. No other code consumes anything from this task beyond the seed file's own content.

- [ ] **Step 1: Write the failing test**

Create `tests/test_monster_family_low_level_coverage.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_monster_family_low_level_coverage.py -v
```

Expected: FAIL — every `elemental`/`construct`/`aberration` case at levels 2 and 5, and the `demon` cases at levels 1-2, raise `ValueError: No monsters available for level <N>` (the bug this plan fixes).

- [ ] **Step 3: Add the 7 rows to `sql/monsters_seed.sql`**

Find the elemental block (currently lines 50-54, right after the `humanoid`/`undead`/`beast` "Common / baseline creatures" `INSERT`):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('fire_elemental_minor_t3', 'Minor Fire Elemental', 7, 9, 130, 24, 3, 12, 'uncommon', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_basic', 160, false),
 ('fire_elemental_greater_t5', 'Greater Fire Elemental', 13, 15, 340, 48, 6, 12, 'rare', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_elite', 420, false),
 ('earth_elemental_minor_t3', 'Minor Earth Elemental', 7, 9, 180, 20, 10, 8, 'uncommon', 'elemental', 'resist_slash,slow', 'elemental_basic', 170, false),
 ('earth_elemental_greater_t5', 'Greater Earth Elemental', 13, 15, 400, 42, 14, 8, 'rare', 'elemental', 'resist_slash,slow', 'elemental_elite', 440, false);
```

Replace with (adds the two new low-level rows before the existing T3+ rows, in the same statement):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('spark_wisp_t1', 'Spark Wisp', 1, 3, 17, 4, 0, 15, 'common', 'elemental', 'shock_touch,evasive', 'elemental_basic', 16, false),
 ('gust_elemental_t2', 'Gust Elemental', 4, 6, 65, 12, 1, 16, 'common', 'elemental', 'gust,evasive', 'elemental_basic', 60, false),
 ('fire_elemental_minor_t3', 'Minor Fire Elemental', 7, 9, 130, 24, 3, 12, 'uncommon', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_basic', 160, false),
 ('fire_elemental_greater_t5', 'Greater Fire Elemental', 13, 15, 340, 48, 6, 12, 'rare', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_elite', 420, false),
 ('earth_elemental_minor_t3', 'Minor Earth Elemental', 7, 9, 180, 20, 10, 8, 'uncommon', 'elemental', 'resist_slash,slow', 'elemental_basic', 170, false),
 ('earth_elemental_greater_t5', 'Greater Earth Elemental', 13, 15, 400, 42, 14, 8, 'rare', 'elemental', 'resist_slash,slow', 'elemental_elite', 440, false);
```

Find the construct block (currently lines 85-88):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('golemClay_t3','Clay Golem',7,9,240,24,10,8,'uncommon','construct','slam,resist_slash','construct_basic',190, false),
 ('golemStone_t4','Stone Golem',10,12,420,38,14,7,'rare','construct','slam,resist_physical','construct_elite',320, false),
 ('golemIron_t5','Iron Golem',13,15,640,54,18,7,'rare','construct','slam,reflect_missile','construct_elite',520, false);
```

Replace with:

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('rubble_construct_t1','Rubble Construct',1,3,26,5,4,7,'common','construct','slam,resist_slash','construct_basic',18, false),
 ('animated_armor_t2','Animated Armor',4,6,75,13,6,9,'common','construct','slam,resist_slash','construct_basic',65, false),
 ('golemClay_t3','Clay Golem',7,9,240,24,10,8,'uncommon','construct','slam,resist_slash','construct_basic',190, false),
 ('golemStone_t4','Stone Golem',10,12,420,38,14,7,'rare','construct','slam,resist_physical','construct_elite',320, false),
 ('golemIron_t5','Iron Golem',13,15,640,54,18,7,'rare','construct','slam,reflect_missile','construct_elite',520, false);
```

Find the aberration block (currently lines 92-95):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('mindleech_spawn_t3','Mindleech Spawn',7,9,130,22,4,12,'uncommon','aberration','psychic_bite,aura_fear','aberration_basic',180, false),
 ('eyestalk_watcher_t4','Eyestalk Watcher',10,12,260,36,6,11,'rare','aberration','multi_beam,levitate','aberration_elite',340, false),
 ('void_carapace_t5','Void Carapace',13,15,480,48,12,9,'rare','aberration','phase_shift,psychic_blast','aberration_elite',560, false);
```

Replace with:

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('spore_crawler_t1','Spore Crawler',1,3,20,5,0,9,'common','aberration','psychic_bite,spores','aberration_basic',17, false),
 ('gloom_tendril_t2','Gloom Tendril',4,6,68,13,2,10,'common','aberration','psychic_bite,aura_fear','aberration_basic',62, false),
 ('mindleech_spawn_t3','Mindleech Spawn',7,9,130,22,4,12,'uncommon','aberration','psychic_bite,aura_fear','aberration_basic',180, false),
 ('eyestalk_watcher_t4','Eyestalk Watcher',10,12,260,36,6,11,'rare','aberration','multi_beam,levitate','aberration_elite',340, false),
 ('void_carapace_t5','Void Carapace',13,15,480,48,12,9,'rare','aberration','phase_shift,psychic_blast','aberration_elite',560, false);
```

Find the demon block (currently lines 99-102):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('imp_brimstone_t2','Brimstone Imp',4,6,70,14,2,14,'common','demon','flying,firebolt,immune_fire','demon_basic',66, false),
 ('fiend_fleshripper_t4','Fleshripper Fiend',10,12,300,44,6,13,'uncommon','demon','bleed_claw,immune_fire','demon_elite',360, false),
 ('demon_infernal_knight_t5','Infernal Knight',13,15,560,62,12,11,'rare','demon','flame_aura,shield','demon_elite',620, false);
```

Replace with (adds the one new T1 row):

```sql
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('imp_lesser_t1','Lesser Imp',1,3,17,4,0,13,'common','demon','flying,firebolt','demon_basic',15, false),
 ('imp_brimstone_t2','Brimstone Imp',4,6,70,14,2,14,'common','demon','flying,firebolt,immune_fire','demon_basic',66, false),
 ('fiend_fleshripper_t4','Fleshripper Fiend',10,12,300,44,6,13,'uncommon','demon','bleed_claw,immune_fire','demon_elite',360, false),
 ('demon_infernal_knight_t5','Infernal Knight',13,15,560,62,12,11,'rare','demon','flame_aura,shield','demon_elite',620, false);
```

(The four block replacements above use the file's exact pre-existing formatting for
each block — note the elemental/demon blocks in the real file use spaces after
commas while construct/aberration use no spaces; preserve each block's own existing
style, don't reformat surrounding blocks.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_monster_family_low_level_coverage.py -v
```

Expected: PASS (8 tests — 7 parametrized cases + the level-1 boundary check)

- [ ] **Step 5: Run the existing monster/spawn test suite to confirm no regression**

```bash
.venv/bin/python -m pytest tests/test_monsters.py tests/test_spawn_service_family_filter.py tests/test_spawn_service_theme.py tests/test_spawn_integration_theming.py tests/test_spawn_integration_catalog.py -v
```

Expected: PASS — these tests load or seed `MonsterCatalog` rows independently
(several use synthetic fixtures, `test_monsters.py` loads the real file) and assert
on pre-existing rows/behavior this plan doesn't touch; none should be affected by
purely additive new rows.

- [ ] **Step 6: Run the full backend suite**

```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py -p no:randomly
```

Expected: all tests pass, no regressions vs. the pre-this-plan baseline (446 passed
as of the end of the Character Cards series).

- [ ] **Step 7: Commit**

```bash
git add sql/monsters_seed.sql tests/test_monster_family_low_level_coverage.py
git commit -m "feat(monsters): add low-level elemental/construct/aberration/demon coverage"
```

- [ ] **Step 8: Update the handoff TODO**

In `docs/superpowers/TODO.md`, find the follow-up note (around the dungeon-enemy-theming entry) that reads:

```
      Follow-up found during final review (sanctioned by the design spec's graceful-
      degradation section, not a defect, just worth tracking): `MONSTER_THEME_FAMILIES`'
      7 values have very uneven low-level coverage in `sql/monsters_seed.sql` -- `beast`/
      `humanoid`/`undead` have non-boss rows from level 1, but `demon` starts at level 4
      and `aberration`/`construct`/`elemental` start at level 7. A new low-level dungeon
      themed as one of those three sparse families finds zero eligible ambient monsters,
      hits `choose_monster`'s `ValueError`, and falls back to generic "Trash Monster"
      stats for its whole ambient pool -- a visible, themed-by-luck regression in
      encounter quality for roughly 4/7 of new low-level dungeons. Two candidate fixes,
      neither done yet: widen low-level `MonsterCatalog` coverage for the sparse
      families, or bias `pick_monster_family` away from families with no rows in the
      dungeon's likely level band.
```

Append a new line directly after it (same indentation level):

```
      **Fixed ✅** (2026-06-21): added `spark_wisp_t1`/`gust_elemental_t2`
      (elemental), `rubble_construct_t1`/`animated_armor_t2` (construct),
      `spore_crawler_t1`/`gloom_tendril_t2` (aberration), and `imp_lesser_t1`
      (demon) to `sql/monsters_seed.sql` -- every family now has T1 (1-3) and
      T2 (4-6) coverage. No code changes needed (`choose_monster`/
      `_eligible_monsters` already query generically). Tests:
      `tests/test_monster_family_low_level_coverage.py` (8 passed, loads the
      real seed file via the same pattern `tests/test_monsters.py` already
      established). Spec: `specs/2026-06-21-monster-family-low-level-coverage-design.md`.
```

- [ ] **Step 9: Commit the TODO update**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark low-level monster-family coverage gap fixed"
```
