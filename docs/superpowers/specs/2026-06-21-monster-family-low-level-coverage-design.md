# Widen Low-Level Monster-Family Coverage

**Date:** 2026-06-21
**Status:** Design approved — ready for implementation planning.

## Context

The dungeon enemy-theming work (`docs/superpowers/specs/2026-06-21-dungeon-enemy-theming-design.md`)
assigns each `DungeonInstance` one deterministic `MonsterCatalog` family (one of
`MONSTER_THEME_FAMILIES = ["undead", "humanoid", "beast", "construct", "elemental",
"aberration", "demon"]`, `app/services/spawn_service.py:28`) via `pick_monster_family(seed)`,
then restricts ambient (PATROL/WANDERER/GUARD/AMBIENT) spawns to that family via
`choose_monster(level, family=...)`.

That work's own final review flagged (sanctioned, not fixed) an uneven-coverage gap in
`sql/monsters_seed.sql`: `undead`/`humanoid`/`beast` have entries from level 1, but
`demon` starts at level 4 and `elemental`/`aberration`/`construct` start at level 7.
`_eligible_monsters()` (`app/services/spawn_service.py:85`) filters strictly by
`family` AND `level_min <= level <= level_max` — a low-level dungeon themed as one of
the four sparse families finds zero eligible rows, `choose_monster` raises
`ValueError`, and the caller falls back to generic "Trash Monster" stats for that
dungeon's entire ambient pool: a visible, themed-by-luck regression in encounter
quality for roughly 4 of the 7 possible themes.

## Goal

Add the missing low-level rows so every family has real monster content at every
level band a low-level dungeon could roll. Concretely: `elemental`, `construct`, and
`aberration` are missing **both** T1 (levels 1-3) and T2 (levels 4-6) — they
currently start at T3 (level 7); `demon` is missing only T1 — it currently starts at
T2 (level 4).

## Non-goals

- No change to `pick_monster_family`, `choose_monster`, `_eligible_monsters`, or any
  other spawn-selection code — this is a pure content/data gap, not a logic bug.
- No change to T3+ tiers for any family — those are already populated and unaffected.
- No change to boss/elite/named monster selection (`choose_archetype_monster`) —
  out of scope per the original theming spec, unchanged here too.

## Design

Add 7 new rows to `sql/monsters_seed.sql`'s `INSERT INTO monster_catalog` statement,
following the file's existing conventions exactly: slug pattern `family_name_tier`,
`common` rarity (matching every other family's T1/T2 baseline rows), a `loot_table`
following each family's existing `_basic` naming (e.g. `elemental_basic`, already
used by `fire_elemental_minor_t3`/`earth_elemental_minor_t3`), and stats following
the file's documented curve (`base_hp ~ level * (8 + tier_modifier)`, `base_damage ~
level * (1 + tier_mod/10)`), cross-checked against sibling families' T1/T2 rows at
the same level band so a themed dungeon doesn't feel meaningfully easier or harder
than an undead/humanoid/beast-themed one at the same level:

| slug | name | level_min | level_max | base_hp | base_damage | armor | speed | family | traits | loot_table | xp_base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `spark_wisp_t1` | Spark Wisp | 1 | 3 | 17 | 4 | 0 | 15 | elemental | shock_touch,evasive | elemental_basic | 16 |
| `gust_elemental_t2` | Gust Elemental | 4 | 6 | 65 | 12 | 1 | 16 | elemental | gust,evasive | elemental_basic | 60 |
| `rubble_construct_t1` | Rubble Construct | 1 | 3 | 26 | 5 | 4 | 7 | construct | slam,resist_slash | construct_basic | 18 |
| `animated_armor_t2` | Animated Armor | 4 | 6 | 75 | 13 | 6 | 9 | construct | slam,resist_slash | construct_basic | 65 |
| `spore_crawler_t1` | Spore Crawler | 1 | 3 | 20 | 5 | 0 | 9 | aberration | psychic_bite,spores | aberration_basic | 17 |
| `gloom_tendril_t2` | Gloom Tendril | 4 | 6 | 68 | 13 | 2 | 10 | aberration | psychic_bite,aura_fear | aberration_basic | 62 |
| `imp_lesser_t1` | Lesser Imp | 1 | 3 | 17 | 4 | 0 | 13 | demon | flying,firebolt | demon_basic | 15 |

All seven are `boss = false`, matching every other non-boss row's literal `false` in
this file's existing `INSERT` values.

No code changes anywhere — `_eligible_monsters`'s query (`family` + level-band
overlap) and `choose_monster`'s rarity-weighted selection already operate generically
over whatever rows exist; adding rows is sufficient to close the gap.

## Data Flow

```
dungeon created (low level, e.g. level 2)
  -> pick_monster_family(seed) rolls "elemental" (one of the 4 previously-sparse families)
  -> ambient spawn needs a monster: choose_monster(level=2, family="elemental")
  -> _eligible_monsters(2, family="elemental") -- BEFORE this fix: 0 rows -> ValueError
                                                -- AFTER this fix: spark_wisp_t1 (1-3) matches
  -> real themed monster returned instead of falling back to generic "Trash Monster"
```

## Error Handling

None needed — this fix removes an error path (the `ValueError` fallback) by ensuring
data exists; it doesn't add a new one.

## Testing

- New test asserting `choose_monster(level=2, family="elemental")` no longer raises
  `ValueError` and returns an instance with `family == "elemental"`. Same pattern
  repeated for `construct` and `aberration` at level 2 and level 5 (covering both new
  tiers), and `demon` at level 2 (covering its one new tier).
- Existing `choose_monster`/`_eligible_monsters` tests (if any exist for other
  families) should be re-run to confirm no regression — this is a pure addition, no
  existing row is modified or removed.
- Full backend suite run after, per existing project convention.

## Migration

None — `sql/monsters_seed.sql` is a re-runnable seed file (`DELETE FROM
monster_catalog;` at the top, then re-inserts everything), loaded via `python run.py
reseed-items`. No schema change; applying this fix to a running dev/prod DB is just
re-running that existing command.
