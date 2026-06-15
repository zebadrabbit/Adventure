# Dungeon Rescue — Stabilization Design

**Date:** 2026-06-14
**Status:** Approved design, pending implementation plan
**Author:** brocade.erin@gmail.com + Claude

## Problem

This is a seeded, multiplayer cave dungeon-crawler (Flask + SocketIO + SQLAlchemy/Postgres). The
intended loop is: **lobby → build a party → enter a seed-derived dungeon → loot and fight →
extract or die.** Permadeath applies — lose a character if they're left behind, lose everything on
a party wipe.

Most of that loop already exists in pieces (party system, extraction/permadeath service, combat,
loot generation, monster spawning, quests). The project nearly got trashed because the **dungeon
generator** keeps producing bad maps, and the rot spread:

- Maps with **unreachable / broken** areas (teleport pads dropped as a band-aid).
- **Ugly / unreadable** layouts (wall artifacts, misplaced doors).
- **Boring / samey** results.
- **Buggy integration** (entities in walls, map not matching what combat/loot expect).

Baseline on 2026-06-14: `91 passed, 39 failed, 1 skipped, 122 errors` across 72 test files. Most
errors are environment/DB setup; the 39 failures include genuine contradictions (a test asserts
locked doors are walkable while current code makes them non-walkable-unless-unlocked). The venv was
broken (no `pip`/`pytest`).

## Root cause

The generator places **wall-rings first, then carves corridors through walls** without breaking
them. That ordering forces a cascade of repair passes that fight each other:

```
_place_rooms → _build_wall_rings → _connect_rooms → _prune_dead_ends → _door_sanity_pass
→ _dedupe_adjacent_doors → _repair_corridor_gaps → _enforce_full_room_connectivity
→ _add_decoy_tunnels → _door_sanity_pass → _dedupe_adjacent_doors → _compute_connectivity_metrics
→ _place_teleports_for_unreachable (+ supplemental teleport pass) → _collect_counts
```

Connectivity is *patched after the fact* (and ultimately faked with teleports) instead of being
*guaranteed by construction*. This is the single decision that produced all four symptoms.

## Guiding principle

**Carve floor first, derive walls last.** When floor (rooms + corridors) is carved before any wall
exists, walls are simply "cave adjacent to floor," doors are simply "corridor meeting a room edge,"
and connectivity is a property of how the floor was carved — not something to repair.

## Scope

Full stabilization, decomposed into four sequential phases. Each phase ends with a green test run.
This document is the umbrella design; **Phase 1 is specified in implementation detail** because it
is the centerpiece. Phases 0, 2, 3 are scoped here and will each get their own implementation plan
when reached.

---

## Phase 0 — Green baseline & guardrails

**Goal:** a known-good starting line and a repeatable test environment, so later phases have a
safety net.

- Document and script the dev/test environment: venv bootstrap (`ensurepip` + `requirements*.txt`),
  required `DATABASE_URL` / `TEST_DATABASE_URL`, and DB migration step. Capture in `manage.sh` or a
  short `docs/TESTING.md`.
- Triage the 122 errors: confirm they are DB/setup (e.g. `adventure_test` not migrated) and fix the
  setup, not the tests.
- Triage the 39 failures into: (a) real bugs, (b) tests encoding contradictory/obsolete invariants.
  Quarantine (xfail with a reason + tracking note) the contradictory ones rather than silently
  deleting; they get resolved in Phase 1/3.
- **Exit criteria:** `pytest` runs cleanly from a documented setup; remaining red is an explicit,
  enumerated list (no errors from environment).

## Phase 1 — Generator rewrite (centerpiece)

**Goal:** replace the generator with a clean, deterministic, hybrid (rooms + cave pockets)
generator where connectivity is guaranteed by construction, behind the **same public contract** so
downstream code is unaffected.

### Public contract to preserve (drop-in)

Construction: `Dungeon(seed: int | None = None, size=(W, H, 1))` and `Dungeon(DungeonConfig(...))`.

Attributes consumed downstream (verified via grep across `app/`):

| Member | Consumers (count) | Notes |
|---|---|---|
| `.grid[x][y]` | movement, visibility, spawn, perception, api (21) | column-major `grid[x][y]`, single-char tiles |
| `.seed` | api, persistence (50) | int |
| `.config` | api, helpers (36) | `DungeonConfig(width, height, seed)` |
| `.rooms` | spawn, api (8) | list of `Room` with `.x/.y/.w/.h/.center/.cells()` |
| `.room_types` | spawn (3) | parallel to `.rooms`; values incl. `start`, `boss`, `treasure` |
| `.is_walkable(x, y, unlocked_doors=None)` | movement (4) | keep signature |
| `.reveal_secret_door(x, y)` | secret-door API (1) | keep |
| `.metrics` | api/tests (1) | dict; keep documented keys stable |
| `.size`, `.to_json()`, `.to_ascii()` | api | keep |

Tile alphabet stays: `C` cave, `R` room, `W` wall, `T` tunnel, `D` door, `S` secret door
(non-walkable until revealed), `L` locked door, `P` teleport pad.

### Algorithm (carve-floor-first)

1. **Rooms.** Deterministic placement from `Random(seed)` — BSP partition or scatter-with-rejection
   (decide in plan; BSP gives cleaner non-overlap and natural size variety). Each room writes `R`
   into the grid. Record `Room` objects.
2. **Connectivity graph.** Compute an MST over room centers; add a small, seed-determined number of
   extra edges to create loops (avoids pure-tree dead-feeling maps). Because the MST spans every
   room, the carved corridors reach every room — **connectivity guaranteed.**
3. **Corridors.** For each graph edge, carve an L-shaped (or straight) path of `T` between room
   centers, writing `T` over `C` and passing through rooms as `R`. No wall exists yet, so nothing to
   break.
4. **Cave pockets (hybrid).** In a few seed-chosen regions, grow organic caverns via cellular
   automata, then carve a corridor splicing each pocket onto the existing floor graph (so pockets
   are connected, never stranded).
5. **Derive walls.** Any `C` orthogonally/diagonally adjacent to floor (`R`/`T`) becomes `W`.
6. **Derive doors.** Each grid cell where a `T` meets a room edge becomes `D` (exactly one door per
   distinct room approach). This replaces all door sanity/dedup passes.
7. **Room typing.** Assign `start` (entrance room), `boss` (largest/farthest by graph distance),
   `treasure`, generic `room`. Deterministic and used by spawn placement.
8. **Variant doors.** Optionally convert a seeded subset to `S`/`L`. Invariant resolved here (see
   below). Never seal a room's only door.
9. **Validate.** Single BFS from the start room over walkable tiles. Every room reachable. This is a
   **hard assertion / test**, not a teleport trigger.

### What gets deleted

`_build_wall_rings` (pre-walls), `_door_sanity_pass`, `_dedupe_adjacent_doors`,
`_repair_corridor_gaps`, `_enforce_full_room_connectivity`, `_add_decoy_tunnels` (optional, can be
re-added cleanly later), `_place_teleports_for_unreachable` + supplemental pass, and the
teleport-as-connectivity plumbing.

### Teleports

Teleport pads (`P`) are **removed as a connectivity crutch.** Movement/patrol/api code that reads
`metrics["teleport_lookup"]` (`movement_handler.py`, `api_helpers/movement.py`,
`api_helpers/tiles.py`, `monster_patrol.py`, `routes/dungeon_api.py`) must tolerate their absence
(empty lookup → no teleport behavior). `P` may return later as an intentional designed feature, out
of scope here.

### Locked/secret door invariant (resolve the contradiction)

Pick one and make code + tests agree:
- `L` locked door: **non-walkable until present in `unlocked_doors`** (matches current code). Update
  the old test that asserts unconditional walkability.
- `S` secret door: non-walkable until `reveal_secret_door` converts it to `D`.

This kills the Phase-0 quarantined contradiction.

### Determinism & tests (golden seeds)

- Same `(seed, size)` ⇒ byte-identical grid. Add a golden-seed snapshot test (store ASCII for a few
  seeds; regenerate and compare).
- Connectivity test: BFS reaches every room for a sample of seeds — **no teleports allowed.**
- Invariants: every `D` has a room neighbor and a walkable neighbor; no orphan doors; walls fully
  ring floor; no floor on the grid border.
- Integration smoke: spawn placement only lands on walkable tiles; existing movement/api dungeon
  tests pass against the new generator.
- Performance: keep sub-~50ms for medium maps (existing perf guard).

**Exit criteria:** new generator passes determinism, connectivity (no teleports), invariant, and
integration tests; downstream dungeon/movement/api tests green.

## Phase 2 — Loop integration

**Goal:** the end-to-end loop works against the new maps.

- Walk the path: lobby → create characters → build party → start adventure (seed-derived dungeon) →
  move/search/loot → combat → boss → extraction or death → permadeath consequences → party wipe
  resets.
- Fix integration bugs surfaced by the rewrite: entities spawning in walls, map/grid mismatches,
  movement edge cases, extraction state transitions.
- **Exit criteria:** an automated end-to-end test (or documented manual run) completes the loop on a
  fixed seed; "buggy integration" symptoms gone.

## Phase 3 — Cleanup & docs

**Goal:** leave the codebase honest.

- Prune dead/duplicate modules (e.g. `admin_new.py` vs `admin.py`, stray debug scripts, deprecation
  stubs), reconcile any remaining contradictory invariants, un-quarantine or delete Phase-0 xfails
  with resolution.
- Rewrite `docs/DUNGEON_GENERATION.md` to describe the carve-floor-first generator and drop legacy
  pipeline references.
- **Exit criteria:** full suite green; docs match code; no orphaned modules referenced by routes.

---

## Risks & mitigations

- **Interface drift breaks downstream.** Mitigation: the contract table above is the test surface;
  keep the new generator behind it; run the full dungeon/movement/api suite as the gate.
- **Hidden consumers of teleport metrics.** Mitigation: the grep list above enumerates them; each
  must no-op gracefully when no teleports exist.
- **Cave pockets reintroduce connectivity holes.** Mitigation: pockets are spliced onto the floor
  graph before walls are derived, and the BFS assertion covers them.
- **Phase 0 churn.** Mitigation: quarantine (xfail) rather than edit contradictory tests until
  Phase 1 resolves the invariant.

## Decisions captured

- Layout style: **hybrid** (rooms + corridors backbone with occasional cave pockets).
- Connectivity: **guaranteed by construction**, teleports removed as a crutch.
- Rewrite style: **clean rewrite behind the existing public contract.**
- Sequencing: **full spec (this doc) → implement Phase 1 first.**
