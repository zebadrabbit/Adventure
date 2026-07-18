# Room Events & Pacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dungeons stop feeling empty and samey: shrines to find, traps to dodge, ambush rooms to trip, and a bounded trickle of wandering respawns so late-run floors aren't dead — all reusing existing systems (DungeonEntity, status effects, perception, SpawnManager).

**Architecture:** Three new `DungeonEntity` types (`shrine`, `trap`, `ambush`) seeded deterministically per instance alongside the existing treasure-cache seeding; resolved on step-on inside the shared movement path (`process_movement`), which both REST and WebSocket moves already route through; wandering respawns live in `SpawnManager.update_spawns` behind hard caps and stop once the boss is dead (so full clears stay achievable).

**Tech Stack:** Flask/SQLAlchemy, existing dungeon/spawn/status/perception services, vanilla JS canvas renderer.

## Global Constraints

- New entity types are strings on the existing `DungeonEntity.type` column (String(24)) — NO schema changes, NO new tables, NO alembic revision in this plan.
- `trap` and `ambush` entities must NEVER reach the client: filter them out of every entity serialization/broadcast (the `entities_update` payload and any REST entity listing). Shrines ARE visible.
- Status effects only via existing helpers (`replace_effect`, existing `regen_buff`/`poison` types) — no new effect types.
- Event placement is deterministic from the instance seed (`random.Random(seed ^ <constant>)`), mirroring how treasure caches are seeded, so re-deriving an instance reproduces it.
- All event resolution goes in the shared movement path so REST and WebSocket moves behave identically — find the single function both call (`process_movement`) and hook there, never in a route handler.
- Respawns: hard-bounded (cap = half the initial ambient count), never spawn within 8 tiles of the player, and NEVER after `bosses_defeated >= bosses_total` (keeps full-clear achievable; `is_full_clear` counts remaining monster entities).
- Tests: `cd /home/winter/work/Adventure && source .venv/bin/activate && TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test pytest -q` (never `-x`). Suite currently: 550 passed, 1 skipped, 1 xpassed — must stay green plus new tests.
- PROCESS: all test runs foreground (no background shells/watchers/Monitors for pytest); never two pytest processes; full suite exactly once before each task's commit. If a schema question arises — there should be none — stop and report BLOCKED.
- Pre-commit hooks may reformat; re-add and retry. Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## Tuning constants (final for v1 — one module-level dict, adjustable later via playtest)

Define once in `app/dungeon/room_events.py` (new file, Task 1):

```python
# ponytail: flat constants for v1; move into GameConfig if playtesting demands live tuning
EVENT_TUNING = {
    "shrines_per_instance": 2,
    "traps_per_instance": 4,
    "ambushes_per_instance": 2,
    "shrine_mana_restore_pct": 0.5,     # instant, of max_mana
    "shrine_regen_ticks": 10,           # same well-rested buff camp grants
    "trap_damage_pct": 0.10,            # of max_hp, party leader
    "trap_poison_ticks": 5,
    "trap_perception_dc": 12,           # d20 + perception mod >= DC avoids
    "ambush_pack_size": (2, 3),         # inclusive range
    "respawn_interval_ticks": 20,
    "respawn_cap_fraction": 0.5,        # of initial ambient count
    "respawn_min_player_distance": 8,
}
```

---

### Task 1: Seed shrine/trap/ambush entities per instance + hide hidden types from clients

**Files:**
- Create: `app/dungeon/room_events.py` (EVENT_TUNING above + `seed_room_events(instance, dungeon) -> int`)
- Modify: the instance-setup path that currently calls `_seed_treasure_caches` (app/routes/dungeon_api.py ~line 656 — read how/when it runs and idempotency guard; hook `seed_room_events` at the same point with the same once-per-instance guard)
- Modify: every place entities are serialized to clients — the `entities_update` broadcast builder and `dungeon_entities()` (app/routes/dungeon_api.py ~1248) — to exclude `type in ("trap", "ambush")`
- Test: `tests/test_room_events_seeding.py` (create)

**Interfaces:**
- Produces: `seed_room_events(instance, dungeon)` — creates `DungeonEntity` rows: `type="shrine"` (visible, `name="Ancient Shrine"`, `slug="shrine"`), `type="trap"` (`name="Hidden Trap"`), `type="ambush"` (`name=None`); placed on distinct walkable floor tiles ≥3 tiles from the entrance and not on tiles already holding an entity; deterministic via `random.Random(instance.seed ^ 0xE7E47)`. Returns count created. Idempotent: no-op if any row of these types already exists for the instance.
- Later tasks consume: entity types `"shrine"|"trap"|"ambush"` and `EVENT_TUNING`.

- [ ] **Step 1: Failing tests** — (a) seeding creates exactly 2 shrines / 4 traps / 2 ambushes on walkable, distinct, entity-free tiles; (b) calling twice creates nothing new; (c) same seed → identical placements across two instances (compare coordinate sets); (d) `dungeon_entities()` response and the entities broadcast payload contain shrines but no trap/ambush rows (follow tests/test_websockets.py or the dungeon API tests for how to invoke those payload builders). Use the established instance/dungeon fixtures (tests/dungeon_test_utils.py).
- [ ] **Step 2: RED**, implement (walkable tiles via the same helper SpawnManager uses — `_get_walkable_tiles` logic; read it and reuse the dungeon grid API it uses rather than copying).
- [ ] **Step 3: GREEN + full suite; commit** — `feat(dungeon): seed shrine/trap/ambush room events per instance (hidden types filtered from clients)`

---

### Task 2: Step-on resolution in the shared movement path

**Files:**
- Modify: `app/dungeon/room_events.py` (add `resolve_events_at(instance, x, y) -> list[dict]`)
- Modify: the shared movement function (`process_movement` in app/dungeon/movement_handler.py — verify name/location by reading how dungeon_api's move route and the WS move handler both delegate) — after movement commits and collision-combat check runs, call `resolve_events_at` and merge its events into the movement response under `"events"`
- Test: `tests/test_room_events_resolution.py` (create)

**Interfaces:**
- Produces: `resolve_events_at(instance, x, y)` returns a list of event dicts, each `{"kind": "shrine"|"trap_avoided"|"trap_hit"|"ambush", "message": str, ...}`; movement responses gain `"events": [...]` (empty list omitted is fine — match how the response already handles optional keys like encounters).
- Behavior (all entities consumed on trigger — delete the row):
  - **shrine**: every living party character gets instant mana `+= max_mana * shrine_mana_restore_pct` (capped) and the same `regen_buff` camp grants (reuse the exact `replace_effect` call and insert-after-time-advance ordering camp uses — read `dungeon_camp` first; if no time advance happens on move, plain `replace_effect` is correct). Message: "You touch the Ancient Shrine — the party feels invigorated."
  - **trap**: roll `d20 + perception mod` for the party leader (reuse `_perception_mod_from_stats` — import it or lift it into a shared spot if it's private; lifting to `app/dungeon/api_helpers/perception.py` public name is allowed) vs `trap_perception_dc`. Success → `trap_avoided` ("You spot and disarm a hidden trap."). Failure → `trap_hit`: leader takes `max_hp * trap_damage_pct` (floor at 1 hp — traps never kill outright, mirroring the out-of-combat poison floor) plus `poison` via `replace_effect` for `trap_poison_ticks`. The roll uses `random.Random(instance.seed ^ (x << 8) ^ y)` so the same trap resolves the same way for the same party stats (deterministic, testable).
  - **ambush**: spawn `randint(*ambush_pack_size)` ambient monsters of the instance's `monster_family` on walkable tiles adjacent to (x,y) (reuse `spawn_service.choose_monster` + however `SpawnManager`/entity creation persists ambient monsters — read `_generate_ambient_spawns` and the DungeonEntity monster-row creation used at instance setup; create BOTH the SpawnEntry and the DungeonEntity row the same way normal ambients get them). Message: "It's an ambush!" Existing proximity-aggro then does the rest.
- [ ] **Step 1: Failing tests** — shrine restores mana + applies regen_buff + row deleted; trap success path (stat the leader high) vs failure path (stat low) with damage floor and poison row; ambush creates 2-3 monster entities adjacent + marker deleted; movement response carries the events list; a tile with no event yields no key/empty list.
- [ ] **Step 2: RED → implement → GREEN + full suite; commit** — `feat(dungeon): shrines, traps, and ambush rooms resolve on step-on in the shared movement path`

---

### Task 3: Bounded wandering respawns

**Files:**
- Modify: `app/dungeon/spawn_manager.py` — `SpawnManager.update_spawns` gains the respawn check; `to_dict`/`from_dict` persist two new counters (`initial_ambient_count`, `respawns_done`); `initialize_spawns` records `initial_ambient_count`
- Test: `tests/test_wandering_respawns.py` (create)

**Interfaces:**
- Behavior, checked at the top of `update_spawns(current_tick)`: if `current_tick % respawn_interval_ticks == 0` AND living ambient-tier spawns < 40% of `initial_ambient_count` AND `respawns_done < int(initial_ambient_count * respawn_cap_fraction)` AND NOT boss-complete (`instance.bosses_defeated >= instance.bosses_total` → never respawn) → add ONE wanderer-behavior ambient spawn (same generation path as `_generate_ambient_spawns`, family-themed) on a walkable tile ≥ `respawn_min_player_distance` from the player, increment `respawns_done`. Mirror however moved/new spawns get their DungeonEntity rows synced (read the patrol-sync code in app/dungeon/api_helpers/encounters.py `run_monster_patrols` — new spawns need entity rows the same way).
- [ ] **Step 1: Failing tests** — respawn fires when depleted below threshold on an interval tick; not on off-interval ticks; not when above threshold; not past the cap; never when bosses are all dead; never within 8 tiles of the player; counters survive a to_dict/from_dict round-trip.
- [ ] **Step 2: RED → implement → GREEN + full suite; commit** — `feat(dungeon): bounded wandering respawns (stop at cap and after boss falls)`

---

### Task 4: Client rendering + docs

**Files:**
- Modify: `app/static/js/dungeon-canvas.js` — render `shrine` entities (icon: `app/static/iconography/aura.svg` via the existing per-entity icon mechanism — read how monster entities pick their icon/fallback and register shrine the same way; if entity icons key off a `slug`→file convention, placing/naming the slug correctly may be zero-code)
- Modify: `app/static/js/adventure.js` — surface movement-response `events` messages in whatever existing message/toast/log surface the adventure screen already has for encounter messages (read how combat-start/encounter messages display; reuse that, no new UI widget)
- Modify: `docs/superpowers/TODO.md` — dated entry for the feature; note tuning constants live in `app/dungeon/room_events.py`
- Test: `node --check` both JS files; backend suite once (unchanged code, regression only)

- [ ] **Step 1: Implement, `node --check`, full suite, commit** — `feat(ui): render shrines and surface room-event messages; docs`

Manual live verification (shrine visible on canvas, trap message on step, ambush pack appears) belongs to the user's next playtest — note that in the TODO entry.
