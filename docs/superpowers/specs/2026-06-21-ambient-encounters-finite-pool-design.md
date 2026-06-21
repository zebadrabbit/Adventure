# Ambient encounters: finite, contact-based pool — design

## Problem

Today, every dungeon combat encounter comes from `maybe_spawn_encounter`
(`app/dungeon/api_helpers/encounters.py`): a context-free random roll on
every player move, with a miss-streak bonus to avoid long dry spells.
This is architecturally disconnected from the dungeon's actual monster
placements. Walking past a visibly-rendered "Goblin Guard" on the minimap
does nothing — it's pure decoration. The random roll lets a player farm
XP indefinitely by walking back and forth on the same few tiles, since
nothing is ever depleted.

Separately, a fully-built finite spawn system already exists
(`app/dungeon/spawn_manager.py`'s `SpawnManager`, backed by
`DungeonEntity` rows): a deterministic, capped number of monsters
(bosses, elites, and "ambient"-tier patrol/wanderer/guard/ambient
spawns) placed per dungeon instance at generation time, with patrol/wander
movement, visible on the live minimap. Combat-on-contact already works
mechanically — `movement_handler.process_movement` checks for a
`DungeonEntity` at the player's new tile right after a successful move,
starts combat, and deletes that entity (so it never regenerates). But
this only fires when the *player* walks onto a monster's tile, and no
monster ever moves toward the player — there's a dead code comment on
`GUARD` claiming it "aggros on proximity," but no such logic exists
anywhere. Contact is pure coincidence today, which is exactly why the
random-roll crutch exists.

## Goal

Make ambient combat come entirely from the existing finite spawn pool,
by giving ambient-tier monsters the ability to notice and approach the
player, and by closing the gap where a monster reaching the player's
tile doesn't trigger combat. Once that's reliable, retire the random
roll entirely — encounters become finite per instance, deplete
permanently on defeat or flee, and can no longer be farmed by pacing
back and forth.

## Design

### 1. Proximity aggro (`app/dungeon/spawn_manager.py`)

Add `aggro_radius: int = 5` to `SpawnConfig`, using Chebyshev distance
(`max(abs(dx), abs(dy))`) for consistency with the existing distance
check pattern already used elsewhere in this codebase
(`app/routes/dungeon_api.py`'s extraction-range checks).

In `SpawnManager.update_spawns`, before applying each spawn's normal
per-behavior movement, check whether the player's current position
(`self.instance.pos_x`/`pos_y`, already live by the time this runs) is
within `aggro_radius` of that spawn. If so, the spawn takes one cardinal
step toward the player this tick instead of its normal behavior —
applies to **PATROL, WANDERER, GUARD, and AMBIENT** (all the "ambient
tier" behaviors); BOSS and ELITE are untouched, since those are
deliberate set-piece placements in boss/treasure rooms, not part of the
"ambient encounters" complaint.

This check re-evaluates fresh every tick from scratch — no persisted
"is aggroed" flag. A monster that loses the player (player moves back
outside `aggro_radius`) simply reverts to its normal behavior next tick.
This is deliberately the simplest version: stateless, no separate
de-aggro radius to tune.

**Chase step:** greedily reduce whichever of `|dx|`/`|dy|` is larger
first (ties broken by preferring the x-axis, matching no particular
deep reasoning — just a deterministic, documented tie-break). Reuses the
exact same validation already used by `_move_patrol`/`_move_wanderer`:
bounds check, walkable-tile check, and "no other spawn already
occupying that tile" check. If the preferred axis's target tile is
blocked, try the other axis; if both are blocked, the spawn simply
doesn't move this tick (matches how `_move_patrol`/`_move_wanderer`
already silently no-op on a blocked destination).

### 2. Monster-initiated contact (`movement_handler.py` + `encounters.py`)

Today, the "monster at player's tile → start combat → delete that
entity" logic lives inline in `process_movement`, checked once, right
after the player's own move. Extract it into a shared helper —
`trigger_collision_combat(instance) -> dict | None` in
`app/dungeon/api_helpers/encounters.py` — that:
1. Queries `DungeonEntity` for `type="monster"` at the player's current
   `(pos_x, pos_y, pos_z)`.
2. If found: builds the monster payload exactly as today, calls
   `combat_service.start_session`, deletes the entity, and returns
   `{"monster": ..., "combat_id": ...}`.
3. Returns `None` if nothing's there.

Call sites:
- `movement_handler.process_movement` calls it once, right after a
  successful player move (replacing the inline block that's there
  today) — this is "player walks onto monster."
- `run_monster_patrols` (`encounters.py`) calls it once, after
  `spawn_manager.update_spawns()` and after persisting the new
  positions to `DungeonEntity` — this is "chasing monster reaches
  player," the new direction this design adds. `run_monster_patrols`
  already returns nothing (`-> None`, mutates `resp` for websocket
  purposes); extend it to also write into `resp["encounter"]` when this
  fires, the same `resp` dict convention `maybe_spawn_encounter` uses
  today, so callers that already check `"encounter" in resp` need no
  further changes.

`advance_non_combat_time` (`app/routes/dungeon_api.py`) already calls
`run_monster_patrols(dungeon, instance, resp={}, tick_amount=tick_amount)`
with a throwaway `resp={}` — change it to build and return that `resp`
dict (or the encounter portion of it) so `movement_handler.process_movement`
can merge it into the player-facing JSON response the same way it
already merges `combat_started`/`combat_id`/`encounter` from the
pre-move collision check.

**Correction from an earlier draft of this design, caught during spec
self-review:** `GameClock.combat` is **not** a reliable same-request
guard here — verified directly in `app/services/time_service.py:138`,
it's only ever set by an explicit setter the combat UI/socket lifecycle
calls, never by `combat_service.start_session` itself. So if the
player-onto-monster collision check starts combat earlier in
`process_movement`, `GameClock.combat` is still `False` for the rest of
that same request, and `advance_non_combat_time` (called unconditionally
today, regardless of whether combat just started) would still run
`run_monster_patrols` — which, with this design's new post-move
collision check added, could trigger a *second* combat session in the
same request. This is a latent quirk in the current code too (patrol
movement already runs pointlessly after collision combat starts), just
harmless until now since patrol movement had no player-facing effect.

**Fix:** gate the call in `movement_handler.process_movement` — only
call `advance_non_combat_time` when `combat_started` is still `False`
after the player-onto-monster check. This is strictly more correct than
today's unconditional call, independent of this design's other changes.

### 3. Retire the random roll

- Delete `maybe_spawn_encounter` (`app/dungeon/api_helpers/encounters.py`)
  and its call site in `movement_handler.process_movement`.
- Delete the now-dead admin control: the `encounter_spawn_rate` field in
  `app/templates/admin_game_rules.html` (lines ~55-56) and its
  read/write handling in `app/routes/admin.py`'s `game_rules` view
  (the `rules` dict's `encounter_spawn_rate` key, both directions).
- Delete the `debug_encounters` `GameConfig` flag — it's read in exactly
  one place (`encounters.py`, the function being deleted) and nowhere
  else.
- `_load_spawn_config`/`_debug_flag` helpers in `encounters.py` are
  deleted along with `maybe_spawn_encounter` (they exist only to serve
  it).

## Testing

- New tests in a new `tests/test_spawn_aggro.py`:
  - A PATROL/WANDERER/GUARD/AMBIENT spawn within `aggro_radius` takes a
    step that strictly reduces its Chebyshev distance to the player,
    regardless of its normal behavior.
  - A spawn outside `aggro_radius` behaves exactly as before (unchanged
    assertions mirroring whatever the current patrol/wander tests
    already check, confirming no regression for the "not aggroed" case).
  - A spawn that reaches the player's exact tile via the chase step
    triggers `trigger_collision_combat` (combat session created, that
    `DungeonEntity` row deleted).
- New test confirming `trigger_collision_combat` itself: returns the
  expected dict shape when a monster is at the given position, returns
  `None` when nothing is there, and that calling it doesn't double-spend
  the same entity (it deletes the row it acts on).
- Delete three tests that directly exercise the removed random-roll
  system: `tests/test_time_and_encounters.py::test_encounter_miss_streak_accumulates_with_gap`,
  `tests/test_encounter_config.py::test_encounter_spawn_probability_config`,
  `tests/test_encounter_config.py::test_encounter_spawn_probability_zero`.
  The other tests in both those files are unaffected (they exercise
  unrelated functionality — game clock advancement, large-tick-gap
  patrol updates via a mocked `SpawnManager`, rarity weighting, loot
  rolls) and are left as-is.
- Clean up `tests/conftest.py`'s `_reset_volatile_game_config` fixture:
  remove the now-dead `"encounter_spawn"`, `"game_rules.encounter_spawn_rate"`,
  and `"debug_encounters"` entries from its `VOLATILE_KEYS` tuple (no
  remaining test sets any of them after the deletions above).
- Full suite regression check
  (`tests/ -q --deselect tests/test_combat_persistence.py`) after all
  changes.

## Out of scope

- Tuning `aggro_radius`, density, or movement-interval values for actual
  play-feel balance — ship sensible defaults (`aggro_radius=5`, matching
  existing density/min/max spawn defaults already in `SpawnConfig`), and
  treat further tuning as a separate, easy follow-up once it's playable.
- Boss/Elite behavior changes — explicitly untouched.
- Any UI change to the minimap/entity rendering — monsters already
  render today; this only changes whether/how they move and what
  happens on contact.
- A de-aggro radius or "lose interest" mechanic — the stateless
  recompute-every-tick approach means a monster naturally stops
  chasing the instant the player is back outside `aggro_radius`.
