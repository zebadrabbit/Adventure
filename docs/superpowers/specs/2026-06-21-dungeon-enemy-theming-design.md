# Dungeon enemy theming — design

## Problem

Ambient monsters in a dungeon are currently drawn from the full
`MonsterCatalog` with no regard for thematic coherence — a single
dungeon floor can mix skeletons, goblins, golems, and demons with no
narrative grouping. Real dungeons are rarely a true random spread; an
all-skeleton crypt or a goblin warcamp reads as a coherent place,
while today's mix reads as random spawns. (Note: orcs and kobolds, used
as illustrative examples when this was raised, don't exist as
`MonsterCatalog` rows yet — scoped out below, see Out of scope.)

## Goal

Restrict each dungeon instance's ambient-tier monster selection to a
single `MonsterCatalog.family` for that instance's lifetime, so players
encounter a coherent theme (e.g. "this floor is all undead") instead of
a random mix.

## Scope

This affects exactly one real-gameplay code path:
`app/dungeon/spawn_integration.py`'s `populate_spawn_stats`, in its
ambient-tier branch (PATROL/WANDERER/GUARD/AMBIENT — the boundary
already established by the prior ambient-encounters work), which calls
`spawn_service.choose_monster`. Confirmed via grep that
`choose_monster` has exactly one other caller in the entire codebase:
`app/routes/dungeon_api.py`'s `admin_force_spawn`, an admin debug/testing
endpoint unrelated to real play — left untouched (an admin manually
forcing a specific test encounter shouldn't be constrained by a
dungeon's theme).

**Explicitly out of scope** (both confirmed with the user):
- BOSS/ELITE spawns — they don't draw from `MonsterCatalog` at all
  today (they use the generic `choose_archetype_monster`/`EnemyArchetype`
  label system, per the prior ambient-encounters spec). Giving them
  catalog-backed, theme-matching selection is a separate, larger change.
- Any UI surfacing of the theme (a label like "Crypt of the Skeletons").
  Backend-only for this pass — players notice the theme implicitly
  through encountering only one family of monster.
- Adding new monster content (e.g. orc/kobold `MonsterCatalog` rows) or
  a finer-grained tag distinguishing species within a family (orc vs.
  kobold, both currently nonexistent and both would fall under
  `humanoid` alongside goblins if added later). Theming uses the
  existing `family` column as-is: `undead`, `humanoid`, `beast`,
  `construct`, `elemental`, `aberration`, `demon`.

## Design

### Theme assignment: a new `DungeonInstance.monster_family` column

Add a nullable `monster_family` column (`db.Column(db.String(40),
nullable=True)` — matching `MonsterCatalog.family`'s own column width,
`app/models/models.py:291`) to `DungeonInstance`
(`app/models/dungeon_instance.py`), via a new alembic migration
(`down_revision = "c7d8e9f0a1b2"`, the current head).

At instance creation — the three places a `DungeonInstance` row is
constructed for real gameplay (`app/routes/dashboard.py`'s two
`start_adventure` sites, `app/routes/seed_api.py`'s one) — assign the
theme deterministically from the instance's own `seed`:

```python
import random as _theme_rng

MONSTER_THEME_FAMILIES = ["undead", "humanoid", "beast", "construct", "elemental", "aberration", "demon"]

def pick_monster_family(seed: int) -> str:
    return _theme_rng.Random(seed ^ 0x4D4F4E53).choice(MONSTER_THEME_FAMILIES)  # ^ "MONS"
```

(The XOR salt mirrors the existing pattern in `SpawnManager.__init__`:
`random.Random(instance.seed ^ 0x5341574E)` for its own independent RNG
stream — same idea, different salt, so this doesn't collide with or
depend on SpawnManager's seeding.)

This is a plain function (not a method), placed in
`app/services/spawn_service.py` alongside `choose_monster` (the module
that already owns monster-selection logic), and called at each of the
three `DungeonInstance(...)` construction sites:
`instance.monster_family = pick_monster_family(seed)` right after the
row is constructed, before `db.session.add`/`commit`.

Existing (pre-migration) `DungeonInstance` rows get `monster_family =
NULL` and are never backfilled — `None` is handled as "no theme
restriction" (see below), so old/in-progress dungeons keep their
current unrestricted-mix behavior rather than retroactively changing
underfoot. New dungeons get a theme from the moment they're created.

### Filtering: `choose_monster`/`_eligible_monsters` gain a `family` parameter

In `app/services/spawn_service.py`:

```python
def _eligible_monsters(level: int, include_boss: bool = False, family: str | None = None) -> List[MonsterCatalog]:
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
    ...
```

(`family` joins the existing `(level, include_boss)` cache key tuple —
a one-element tuple extension, no cache-invalidation logic needed since
it's just a wider key space.)

`choose_monster` gains the same `family: str | None = None` parameter
and passes it straight through to `_eligible_monsters`. No other
change to `choose_monster`'s body — the existing rarity-weighting,
level-midpoint bonus, and boss-promotion logic all operate on whatever
(now possibly family-filtered) `pool` `_eligible_monsters` returns,
unchanged.

### Consumption: `populate_spawn_stats` passes the instance's theme

In `app/dungeon/spawn_integration.py`'s ambient-tier branch, change:

```python
monster_dict = spawn_service.choose_monster(level=modified_level, party_size=1)
```

to:

```python
monster_dict = spawn_service.choose_monster(
    level=modified_level, party_size=1, family=getattr(instance, "monster_family", None)
)
```

(`getattr` with a default handles both a pre-migration instance with no
such attribute in a stale ORM cache, and the genuinely-`None` case
identically — both mean "no restriction.")

### Graceful degradation: family has no eligible monsters at this level

Already handled by existing code, unchanged: `choose_monster` raises
`ValueError` when `_eligible_monsters` returns an empty pool (e.g. a
family with no rows spanning the requested level band), and
`populate_spawn_stats`'s existing `except Exception` fallback already
catches this and produces generic `"{archetype} Monster"` stats — the
exact same degrade path a catalog gap already takes today, family
filter or not. No new error handling needed; this is a direct
consequence of `family` being "just another filter" on the same query
path that can already return zero rows.

## Testing

- New test for `_eligible_monsters`/`choose_monster`: passing a `family`
  restricts the returned pool to only that family's rows (seed two
  `MonsterCatalog` rows of different families spanning the same level
  band, confirm `choose_monster(level=..., family="undead")` only ever
  returns the undead one across repeated calls).
- New test confirming `family=None` (the default) is unrestricted —
  locks in backward compatibility for the one other caller
  (`admin_force_spawn`) and for pre-migration instances.
- New test for `pick_monster_family`: same seed always returns the same
  family (determinism); confirm it only ever returns a value from
  `MONSTER_THEME_FAMILIES`.
- New test for `populate_spawn_stats`: an ambient-tier spawn, given an
  instance with `monster_family` set, only ever produces a monster from
  that family (seed two different-family `MonsterCatalog` rows spanning
  the same level, run `populate_spawn_stats` several times with a fixed
  `monster_family`, confirm only the matching family's slug ever
  appears).
- Migration test: none needed beyond the standard `alembic upgrade
  head` sanity already covered by this repo's migration-self-stamp
  test infrastructure (per `docs/superpowers/specs/2026-06-20-migrations-self-stamp-design.md`)
  — a single nullable-column-add migration carries no special risk
  beyond what that infrastructure already verifies.
- Full suite regression check
  (`tests/ -q --deselect tests/test_combat_persistence.py`) after.

## Out of scope

(Restated from above for completeness, since this section is the
canonical "won't do this now" list per the spec template.)

- BOSS/ELITE theme-matching.
- UI surfacing of the dungeon's theme.
- New monster content (orc/kobold rows) or a finer-grained
  species/sub-family tag.
- Retroactively assigning a theme to existing `DungeonInstance` rows.
- Weighting theme selection by anything other than a flat random choice
  among the 7 existing families (e.g. rarer families being less likely)
  — not requested, adds tuning surface for no asked-for benefit.
