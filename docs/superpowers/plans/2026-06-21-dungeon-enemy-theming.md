# Dungeon Enemy Theming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict each dungeon instance's ambient-tier monster
selection to a single `MonsterCatalog.family`, chosen deterministically
from the instance's seed, so a dungeon reads as a coherent theme (e.g.
all-undead) instead of a random mix.

**Architecture:** A new nullable `DungeonInstance.monster_family` column
is assigned once at instance creation (deterministic from `seed`).
`spawn_service.choose_monster`/`_eligible_monsters` gain an optional
`family` filter. `spawn_integration.populate_spawn_stats`'s existing
ambient-tier branch passes the instance's theme through — the only
real-gameplay caller of `choose_monster` (confirmed: the only other
caller is an admin debug endpoint, left untouched).

**Tech Stack:** Flask, SQLAlchemy, Alembic, pytest.

## Global Constraints

- Theme values are restricted to the 7 existing `MonsterCatalog.family`
  values: `undead`, `humanoid`, `beast`, `construct`, `elemental`,
  `aberration`, `demon`. No new monster content, no new tag/column on
  `MonsterCatalog` itself.
- BOSS/ELITE spawns are never touched — they don't use
  `MonsterCatalog`/`choose_monster` at all today (separate
  `choose_archetype_monster` system), unchanged by this plan.
- No UI surfacing of the theme in this plan.
- Pre-migration `DungeonInstance` rows keep `monster_family = NULL`
  (no backfill) — `None` means "no restriction," preserving current
  behavior for in-progress dungeons.
- Backend test suite must stay green:
  `tests/ -q --deselect tests/test_combat_persistence.py`. Baseline at
  the start of this plan: 410 passed, 2 skipped, 3 deselected, 1
  xpassed.
- `DATABASE_URL`/`TEST_DATABASE_URL` must both be exported to the test
  DB before running pytest:
  `export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test`
  `export TEST_DATABASE_URL=$DATABASE_URL`

---

### Task 1: Migration and model column

**Files:**
- Create: `migrations/versions/a1b2c3d4e5f7_add_monster_family_to_dungeon_instance.py`
- Modify: `app/models/dungeon_instance.py`
- Test: `tests/test_dungeon_instance_monster_family.py` (new file)

**Interfaces:**
- Produces: `DungeonInstance.monster_family: str | None` (new column,
  `db.String(40)`, nullable, no default — matches
  `MonsterCatalog.family`'s own column width per
  `app/models/models.py:291`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_dungeon_instance_monster_family.py`:

```python
"""Tests for DungeonInstance.monster_family (the per-instance enemy
theme column)."""

from app import db
from app.models.dungeon_instance import DungeonInstance
from tests.factories import create_user


def test_monster_family_defaults_to_none(test_app):
    with test_app.app_context():
        user = create_user("themecol_1")
        inst = DungeonInstance(user_id=user.id, seed=111, pos_x=0, pos_y=0, pos_z=0)
        db.session.add(inst)
        db.session.commit()

        assert inst.monster_family is None


def test_monster_family_can_be_set_and_persisted(test_app):
    with test_app.app_context():
        user = create_user("themecol_2")
        inst = DungeonInstance(user_id=user.id, seed=112, pos_x=0, pos_y=0, pos_z=0, monster_family="undead")
        db.session.add(inst)
        db.session.commit()
        inst_id = inst.id

        db.session.expire_all()
        reloaded = db.session.get(DungeonInstance, inst_id)
        assert reloaded.monster_family == "undead"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_dungeon_instance_monster_family.py -v
```
Expected: both FAIL with `TypeError: 'monster_family' is an invalid
keyword argument for DungeonInstance` (the column/constructor argument
doesn't exist yet).

- [ ] **Step 3: Add the column to the model**

In `app/models/dungeon_instance.py`, add the new column immediately
after the existing `affix_ids` line:

```python
    tier = db.Column(db.Integer, default=1)
    affix_ids = db.Column(db.Text, nullable=True)  # JSON array of affix_id strings
    monster_family = db.Column(db.String(40), nullable=True)  # Per-instance enemy theme (MonsterCatalog.family value)
```

- [ ] **Step 4: Write the migration**

Create `migrations/versions/a1b2c3d4e5f7_add_monster_family_to_dungeon_instance.py`:

```python
"""add monster_family to dungeon_instance

Revision ID: a1b2c3d4e5f7
Revises: c7d8e9f0a1b2
Create Date: 2026-06-21

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dungeon_instance", sa.Column("monster_family", sa.String(length=40), nullable=True))


def downgrade():
    op.drop_column("dungeon_instance", "monster_family")
```

(`down_revision = "c7d8e9f0a1b2"` is the current alembic head — verified
via `.venv/bin/python -m alembic heads` against the test DB before
writing this plan; confirm it's still the head when you run this step,
in case another migration has landed since.)

- [ ] **Step 5: Apply the migration to the test DB and run tests**

Run:
```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m pytest tests/test_dungeon_instance_monster_family.py -v
```
Expected: `alembic upgrade head` reports the new revision applied; both
tests PASS.

- [ ] **Step 6: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 412 passed (410 baseline + 2 new), 2 skipped, 3 deselected, 1
xpassed.

- [ ] **Step 7: Commit**

```bash
git add app/models/dungeon_instance.py migrations/versions/a1b2c3d4e5f7_add_monster_family_to_dungeon_instance.py tests/test_dungeon_instance_monster_family.py
git commit -m "feat(dungeon): add monster_family column to DungeonInstance"
```

---

### Task 2: Theme-picking helper

**Files:**
- Modify: `app/services/spawn_service.py`
- Test: `tests/test_spawn_service_theme.py` (new file)

**Interfaces:**
- Consumes: nothing from Task 1 (independent of the DB column; this is
  a pure function).
- Produces: `pick_monster_family(seed: int) -> str` in
  `app/services/spawn_service.py`. Always returns one of
  `MONSTER_THEME_FAMILIES` (also defined in this task, in the same
  module): `["undead", "humanoid", "beast", "construct", "elemental",
  "aberration", "demon"]`. Deterministic — same `seed` always returns
  the same family.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spawn_service_theme.py`:

```python
"""Tests for spawn_service.pick_monster_family (deterministic per-seed
dungeon enemy theme selection)."""

from app.services.spawn_service import MONSTER_THEME_FAMILIES, pick_monster_family


def test_pick_monster_family_is_deterministic():
    result_a = pick_monster_family(seed=12345)
    result_b = pick_monster_family(seed=12345)
    assert result_a == result_b


def test_pick_monster_family_returns_valid_family():
    for seed in (1, 2, 3, 4, 5, 100, 999999):
        assert pick_monster_family(seed=seed) in MONSTER_THEME_FAMILIES


def test_pick_monster_family_varies_across_seeds():
    results = {pick_monster_family(seed=s) for s in range(50)}
    # With 7 possible families and 50 different seeds, expect more than
    # one distinct result -- this is not a strict uniformity test, just
    # a sanity check that the function isn't accidentally constant.
    assert len(results) > 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_service_theme.py -v
```
Expected: all FAIL with `ImportError` — `pick_monster_family` and
`MONSTER_THEME_FAMILIES` don't exist yet.

- [ ] **Step 3: Add `MONSTER_THEME_FAMILIES` and `pick_monster_family`**

In `app/services/spawn_service.py`, find the existing `RARITY_WEIGHTS`
module-level constant near the top of the file (immediately after the
imports). Add the new constant right after it:

```python
RARITY_WEIGHTS = {
    ...  # existing content unchanged
}

MONSTER_THEME_FAMILIES = ["undead", "humanoid", "beast", "construct", "elemental", "aberration", "demon"]


def pick_monster_family(seed: int) -> str:
    """Deterministically pick a dungeon's enemy theme from its seed.

    Same seed always returns the same family, for the lifetime of that
    dungeon instance. The XOR salt mirrors SpawnManager's own
    independent RNG stream (random.Random(instance.seed ^ 0x5341574E)
    in app/dungeon/spawn_manager.py) -- same idea, different salt, so
    this doesn't collide with or depend on SpawnManager's seeding.
    """
    return random.Random(seed ^ 0x4D4F4E53).choice(MONSTER_THEME_FAMILIES)  # ^ "MONS"
```

(`random` is already imported at the top of `app/services/spawn_service.py`
— confirmed via the existing `choose_monster`'s use of `rng = rng or
random`. No new import needed.)

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_service_theme.py -v
```
Expected: all PASS.

- [ ] **Step 5: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 415 passed (412 from Task 1 + 3 new), 2 skipped, 3 deselected,
1 xpassed.

- [ ] **Step 6: Commit**

```bash
git add app/services/spawn_service.py tests/test_spawn_service_theme.py
git commit -m "feat(spawn): add deterministic per-seed dungeon theme picker"
```

---

### Task 3: Family filter on `choose_monster`/`_eligible_monsters`

**Files:**
- Modify: `app/services/spawn_service.py`
- Test: `tests/test_spawn_service_family_filter.py` (new file)

**Interfaces:**
- Consumes: nothing from Tasks 1-2 directly (independent of the new
  column and the theme-picker; this task only changes the
  selection/filtering function signature).
- Produces: `_eligible_monsters(level: int, include_boss: bool = False, family: str | None = None) -> List[MonsterCatalog]`
  and `choose_monster(level: int, party_size: int = 1, include_boss: bool = False, rng: Optional[random.Random] = None, family: str | None = None)`
  — both gain the new `family` parameter, defaulting to `None`
  (unrestricted, preserving current behavior for every existing
  caller that doesn't pass it).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spawn_service_family_filter.py`:

```python
"""Tests that choose_monster/_eligible_monsters can be restricted to a
single MonsterCatalog family."""

from app import db
from app.models.models import MonsterCatalog
from app.services import spawn_service


def _seed_two_families():
    for slug, family in (("theme-undead-1", "undead"), ("theme-beast-1", "beast")):
        if MonsterCatalog.query.filter_by(slug=slug).first():
            continue
        db.session.add(
            MonsterCatalog(
                slug=slug,
                name=slug,
                level_min=1,
                level_max=10,
                base_hp=20,
                base_damage=3,
                family=family,
                rarity="common",
                boss=False,
                xp_base=10,
            )
        )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def test_family_filter_restricts_eligible_pool(test_app):
    with test_app.app_context():
        _seed_two_families()
        pool = spawn_service._eligible_monsters(level=1, family="undead")
        slugs = {m.slug for m in pool}
        assert "theme-undead-1" in slugs
        assert "theme-beast-1" not in slugs


def test_choose_monster_with_family_only_returns_that_family(test_app):
    with test_app.app_context():
        _seed_two_families()
        for _ in range(10):
            monster = spawn_service.choose_monster(level=1, family="undead")
            assert monster["slug"] == "theme-undead-1"


def test_choose_monster_without_family_is_unrestricted(test_app):
    with test_app.app_context():
        _seed_two_families()
        seen_slugs = {spawn_service.choose_monster(level=1)["slug"] for _ in range(30)}
        # Both seeded slugs are eligible at level 1 with no family
        # restriction; over 30 draws we expect to see at least one of
        # them (not asserting both appear, to avoid test flakiness --
        # this just confirms the unrestricted call doesn't silently
        # apply a leftover/cached family filter).
        assert seen_slugs & {"theme-undead-1", "theme-beast-1"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_service_family_filter.py -v
```
Expected: `test_family_filter_restricts_eligible_pool` and
`test_choose_monster_with_family_only_returns_that_family` FAIL with
`TypeError: _eligible_monsters() got an unexpected keyword argument
'family'` (and the equivalent for `choose_monster`).
`test_choose_monster_without_family_is_unrestricted` PASSES already
(no `family` arg involved) — expected, it locks in the unchanged
default-call behavior.

- [ ] **Step 3: Add the `family` parameter**

In `app/services/spawn_service.py`, replace:

```python
def _eligible_monsters(level: int, include_boss: bool = False) -> List[MonsterCatalog]:
    now = time.time()
    key = (level, include_boss)
    cached = _ELIGIBLE_CACHE.get(key)
    if cached:
        ts, rows = cached
        if (now - ts) <= _ELIGIBLE_TTL_SECONDS:
            return rows
    q = MonsterCatalog.query
    rows = q.filter(MonsterCatalog.level_min <= level, MonsterCatalog.level_max >= level).all()
    if not include_boss:
        rows = [r for r in rows if not r.boss]
    _ELIGIBLE_CACHE[key] = (now, rows)
    # Simple cap (avoid unbounded growth if level range large)
    if len(_ELIGIBLE_CACHE) > 128:
        # Drop oldest by timestamp
        oldest_key = min(_ELIGIBLE_CACHE.items(), key=lambda kv: kv[1][0])[0]
        if oldest_key != key:
            _ELIGIBLE_CACHE.pop(oldest_key, None)
    return rows
```

with:

```python
def _eligible_monsters(level: int, include_boss: bool = False, family: Optional[str] = None) -> List[MonsterCatalog]:
    now = time.time()
    key = (level, include_boss, family)
    cached = _ELIGIBLE_CACHE.get(key)
    if cached:
        ts, rows = cached
        if (now - ts) <= _ELIGIBLE_TTL_SECONDS:
            return rows
    q = MonsterCatalog.query
    if family:
        q = q.filter(MonsterCatalog.family == family)
    rows = q.filter(MonsterCatalog.level_min <= level, MonsterCatalog.level_max >= level).all()
    if not include_boss:
        rows = [r for r in rows if not r.boss]
    _ELIGIBLE_CACHE[key] = (now, rows)
    # Simple cap (avoid unbounded growth if level range large)
    if len(_ELIGIBLE_CACHE) > 128:
        # Drop oldest by timestamp
        oldest_key = min(_ELIGIBLE_CACHE.items(), key=lambda kv: kv[1][0])[0]
        if oldest_key != key:
            _ELIGIBLE_CACHE.pop(oldest_key, None)
    return rows
```

Then replace the `choose_monster` signature line and its
`_eligible_monsters` call:

```python
def choose_monster(level: int, party_size: int = 1, include_boss: bool = False, rng: Optional[random.Random] = None):
    """Return a scaled monster instance dict for target level.

    Selection steps:
      1. Filter by level band.
      2. Apply rarity weighting.
      3. Randomly choose.
      4. Scale stats for party size.
    Raises ValueError if no eligible monsters.
    """
    rng = rng or random
    pool = _eligible_monsters(level, include_boss=include_boss)
```

with:

```python
def choose_monster(
    level: int,
    party_size: int = 1,
    include_boss: bool = False,
    rng: Optional[random.Random] = None,
    family: Optional[str] = None,
):
    """Return a scaled monster instance dict for target level.

    Selection steps:
      1. Filter by level band (and by family, if given).
      2. Apply rarity weighting.
      3. Randomly choose.
      4. Scale stats for party size.
    Raises ValueError if no eligible monsters.
    """
    rng = rng or random
    pool = _eligible_monsters(level, include_boss=include_boss, family=family)
```

(The rest of `choose_monster`'s body — rarity weighting, boss
promotion, `scaled_instance` call — is unchanged; it already operates
on whatever `pool` is returned, regardless of how that pool was
filtered.)

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_service_family_filter.py -v
```
Expected: all 3 PASS.

- [ ] **Step 5: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 418 passed (415 from Task 2 + 3 new), 2 skipped, 3 deselected,
1 xpassed.

- [ ] **Step 6: Commit**

```bash
git add app/services/spawn_service.py tests/test_spawn_service_family_filter.py
git commit -m "feat(spawn): add optional family filter to choose_monster"
```

---

### Task 4: Wire theme assignment and consumption

**Files:**
- Modify: `app/routes/dashboard.py`
- Modify: `app/routes/seed_api.py`
- Modify: `app/dungeon/spawn_integration.py`
- Test: `tests/test_spawn_integration_theming.py` (new file)
- Test: `tests/test_dashboard_theme_assignment.py` (new file)

**Interfaces:**
- Consumes: `DungeonInstance.monster_family` (Task 1),
  `spawn_service.pick_monster_family` (Task 2),
  `spawn_service.choose_monster(..., family=...)` (Task 3).
- Produces: every real-gameplay `DungeonInstance(...)` construction now
  also sets `monster_family` via `pick_monster_family(seed)`.
  `populate_spawn_stats`'s ambient-tier branch now passes
  `family=getattr(instance, "monster_family", None)` to `choose_monster`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spawn_integration_theming.py`:

```python
"""Tests that populate_spawn_stats restricts ambient-tier spawns to the
instance's assigned monster_family theme."""

from app import db
from app.dungeon.spawn_integration import populate_spawn_stats
from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry
from app.models.models import MonsterCatalog
from app.services import spawn_service
from tests.factories import create_instance, create_user


def _seed_two_families():
    for slug, family in (("themespawn-undead", "undead"), ("themespawn-beast", "beast")):
        if MonsterCatalog.query.filter_by(slug=slug).first():
            continue
        db.session.add(
            MonsterCatalog(
                slug=slug,
                name=slug,
                level_min=1,
                level_max=10,
                base_hp=20,
                base_damage=3,
                family=family,
                rarity="common",
                boss=False,
                xp_base=10,
            )
        )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def test_ambient_spawn_respects_instance_theme(test_app):
    with test_app.app_context():
        _seed_two_families()
        user = create_user("spawntheme_1")
        inst = create_instance(user, seed=701)
        inst.monster_family = "undead"
        db.session.commit()

        for _ in range(10):
            spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
            populate_spawn_stats(spawn, party_level=1, instance=inst)
            assert spawn.slug == "themespawn-undead"


def test_ambient_spawn_unrestricted_when_theme_is_none(test_app):
    with test_app.app_context():
        _seed_two_families()
        user = create_user("spawntheme_2")
        inst = create_instance(user, seed=702)
        assert inst.monster_family is None

        seen = set()
        for _ in range(30):
            spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
            populate_spawn_stats(spawn, party_level=1, instance=inst)
            seen.add(spawn.slug)
        assert seen & {"themespawn-undead", "themespawn-beast"}
```

Create `tests/test_dashboard_theme_assignment.py`. Note: the `auth_client`
fixture (in `tests/conftest.py`) pre-creates its own `DungeonInstance`
(seed `1234`) and a `"Hero"` character, and already seeds
`session["dungeon_instance_id"]`/`session["dungeon_seed"]` pointing at
it — so the test must explicitly clear those two session keys first,
or `dashboard.py`'s `if instance is None:` check will find that
pre-existing row and skip creating a new one, never exercising the
code this task adds. `start_adventure` also requires 1-4 valid
`party_ids` belonging to the current user or it returns a validation
error before reaching instance creation at all — use the fixture's
own `"Hero"` character's id for that.

```python
"""Tests that starting an adventure assigns a deterministic
monster_family theme to a newly-created DungeonInstance row."""

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character
from app.services.spawn_service import MONSTER_THEME_FAMILIES, pick_monster_family


def test_start_adventure_assigns_theme_to_new_instance(auth_client, test_app):
    with test_app.app_context():
        hero = Character.query.filter_by(name="Hero").first()
        assert hero is not None, "auth_client fixture should have created a 'Hero' character"
        hero_id = hero.id

    with auth_client.session_transaction() as sess:
        # Force the dashboard route's "if instance is None" branch to
        # actually create a fresh DungeonInstance, instead of reusing
        # the one auth_client's fixture already seeded.
        sess.pop("dungeon_instance_id", None)
        sess.pop("dungeon_seed", None)

    resp = auth_client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": str(hero_id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with auth_client.session_transaction() as sess:
        instance_id = sess.get("dungeon_instance_id")
    assert instance_id is not None

    with test_app.app_context():
        inst = db.session.get(DungeonInstance, instance_id)
        assert inst.monster_family in MONSTER_THEME_FAMILIES
        assert inst.monster_family == pick_monster_family(inst.seed)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_integration_theming.py tests/test_dashboard_theme_assignment.py -v
```
Expected: `test_ambient_spawn_respects_instance_theme` FAILS (spawns
come from either family, not just `"undead"`, since `populate_spawn_stats`
doesn't pass `family` yet). `test_ambient_spawn_unrestricted_when_theme_is_none`
PASSES already (no restriction expected, and there's none yet) —
expected, locks in the no-theme case. `test_start_adventure_assigns_theme_to_new_instance`
FAILS with `AssertionError` (`inst.monster_family` is `None`, not in
`MONSTER_THEME_FAMILIES`, since nothing assigns it yet).

- [ ] **Step 3: Wire `populate_spawn_stats`**

In `app/dungeon/spawn_integration.py`, change:

```python
            monster_dict = spawn_service.choose_monster(level=modified_level, party_size=1)
```

to:

```python
            monster_dict = spawn_service.choose_monster(
                level=modified_level, party_size=1, family=getattr(instance, "monster_family", None)
            )
```

- [ ] **Step 4: Assign the theme at instance creation in `dashboard.py`**

In `app/routes/dashboard.py`, there are two near-identical
`DungeonInstance(...)` construction sites (one under the
`start_adventure` form branch, one under `continue_adventure`'s
fallback). Both currently read:

```python
                instance = DungeonInstance(user_id=current_user_id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
                db.session.add(instance)
                db.session.commit()
```

Change **both occurrences** to:

```python
                from app.services.spawn_service import pick_monster_family

                instance = DungeonInstance(
                    user_id=current_user_id,
                    seed=seed,
                    pos_x=0,
                    pos_y=0,
                    pos_z=0,
                    monster_family=pick_monster_family(seed),
                )
                db.session.add(instance)
                db.session.commit()
```

(Both sites already have `seed` in scope as a local variable
immediately before this block — confirmed by reading the surrounding
code; this is a same-scope, drop-in replacement at each site.)

- [ ] **Step 5: Assign the theme at instance creation in `seed_api.py`**

In `app/routes/seed_api.py`, find:

```python
    if instance is None:
        instance = DungeonInstance(user_id=current_user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
        db.session.add(instance)
        db.session.commit()
        session["dungeon_instance_id"] = instance.id
```

Change to:

```python
    if instance is None:
        from app.services.spawn_service import pick_monster_family

        instance = DungeonInstance(
            user_id=current_user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0, monster_family=pick_monster_family(seed)
        )
        db.session.add(instance)
        db.session.commit()
        session["dungeon_instance_id"] = instance.id
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_integration_theming.py tests/test_dashboard_theme_assignment.py -v
```
Expected: all 3 PASS.

- [ ] **Step 7: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 421 passed (418 from Task 3 + 3 new), 2 skipped, 3 deselected,
1 xpassed. Pay particular attention to any existing dashboard/seed_api
tests that construct or assert on a `DungeonInstance` row — confirm
none of them break from the new `monster_family` argument being passed
at construction (it's an additive keyword argument with a model-level
default of `None`, so any test not asserting on this specific field
should be unaffected).

- [ ] **Step 8: Commit**

```bash
git add app/routes/dashboard.py app/routes/seed_api.py app/dungeon/spawn_integration.py tests/test_spawn_integration_theming.py tests/test_dashboard_theme_assignment.py
git commit -m "feat(dungeon): assign and apply per-instance enemy theme"
```

---

## Post-implementation

Update `docs/superpowers/TODO.md`: mark the "Dungeon enemy theming"
entry (currently unchecked, logged as a follow-up to the
ambient-encounters finite-pool work) as done, summarizing the new
`monster_family` column, the deterministic per-seed assignment, and the
final test count.
