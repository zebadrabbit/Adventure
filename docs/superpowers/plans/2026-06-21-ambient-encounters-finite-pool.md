# Ambient Encounters: Finite Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the random per-move encounter roll with combat that comes
entirely from the existing finite `SpawnManager` pool — by giving
ambient-tier monsters proximity aggro so they can actually reach the
player, closing the gap where a monster reaching the player's tile didn't
trigger combat, and giving those monsters real catalog names instead of
generic archetype labels.

**Architecture:** `app/dungeon/spawn_manager.py` gains stateless
proximity-aggro movement for PATROL/WANDERER/GUARD/AMBIENT spawns.
`app/dungeon/api_helpers/encounters.py` gains one shared
`trigger_collision_combat(instance)` helper (extracted from
`movement_handler.py`'s existing inline player-onto-monster check),
called from both directions of contact. The random-roll system
(`maybe_spawn_encounter` and its dead admin control) is deleted.
`app/dungeon/spawn_integration.py`'s `populate_spawn_stats` is changed so
ambient-tier spawns draw from the real `MonsterCatalog` instead of the
generic `EnemyArchetype` label system (bosses/elites unchanged).

**Tech Stack:** Flask, SQLAlchemy, pytest (existing patterns throughout —
no new dependencies).

## Global Constraints

- Aggro applies only to PATROL, WANDERER, GUARD, AMBIENT spawn behaviors.
  BOSS and ELITE are never touched by any change in this plan — neither
  their movement nor their monster-selection mechanism
  (`choose_archetype_monster`).
- `aggro_radius` default is `5`, using Chebyshev distance
  (`max(abs(dx), abs(dy))`).
- Aggro is stateless: recomputed fresh every tick from the spawn's and
  player's current positions. No persisted "is aggroed" flag, no
  de-aggro radius.
- `trigger_collision_combat` takes `instance.user_id` (already a column
  on `DungeonInstance`), not Flask-Login's `current_user` — this is a
  deliberate decoupling so the helper is unit-testable without a request
  context, and is behaviorally identical in both real call sites (the
  instance always belongs to the logged-in user there).
- Backend test suite must stay green:
  `tests/ -q --deselect tests/test_combat_persistence.py`. Baseline at
  the start of this plan: 405 passed, 2 skipped, 3 deselected, 1 xpassed.
  After this plan's deletions and additions, expect 405 passed (3 random-
  roll tests removed, multiple new tests added — exact count depends on
  how many are written per task below; each task states its own expected
  delta).
- `DATABASE_URL`/`TEST_DATABASE_URL` must both be exported to the test DB
  before running pytest:
  `export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test`
  `export TEST_DATABASE_URL=$DATABASE_URL`

---

### Task 1: Proximity aggro in SpawnManager

**Files:**
- Modify: `app/dungeon/spawn_manager.py`
- Test: `tests/test_spawn_aggro.py` (new file)

**Interfaces:**
- Produces: `SpawnConfig.aggro_radius: int = 5` (new field).
- Produces: `SpawnManager._is_aggroed(spawn: SpawnEntry, player_x: int | None, player_y: int | None) -> bool`
  (new private method).
- Produces: `SpawnManager._move_toward_player(spawn: SpawnEntry, player_x: int, player_y: int) -> None`
  (new private method, mutates `spawn.x`/`spawn.y` in place, same
  convention as `_move_patrol`/`_move_wanderer`).
- Modifies behavior of: `SpawnManager.update_spawns(current_tick: int) -> List[SpawnEntry]`
  (unchanged signature and return type).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spawn_aggro.py`:

```python
"""Tests for SpawnManager's proximity-aggro movement (PATROL/WANDERER/
GUARD/AMBIENT spawns moving toward a nearby player instead of their
normal behavior)."""

from app.dungeon.dungeon import Dungeon
from app.dungeon.spawn_manager import SpawnBehavior, SpawnConfig, SpawnEntry, SpawnManager


class _StubInstance:
    """Minimal stand-in for DungeonInstance -- SpawnManager only reads
    .seed, .pos_x, .pos_y, and (via getattr with a default) .tier."""

    def __init__(self, seed, pos_x, pos_y):
        self.seed = seed
        self.pos_x = pos_x
        self.pos_y = pos_y


def _small_dungeon(seed=42):
    return Dungeon(seed=seed, size=(30, 30, 1))


def _manager(dungeon, instance):
    return SpawnManager(dungeon, instance, config=SpawnConfig(aggro_radius=5))


def test_patrol_spawn_within_radius_moves_toward_player():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=0, pos_y=0))
    walkable = manager._get_walkable_tiles()
    assert len(walkable) >= 2, "test dungeon too small/empty to place two tiles"

    spawn_tile = walkable[0]
    player_tile = walkable[-1]
    manager.instance.pos_x, manager.instance.pos_y = player_tile

    spawn = SpawnEntry(x=spawn_tile[0], y=spawn_tile[1], behavior=SpawnBehavior.PATROL)
    # Force "within radius" regardless of the two tiles' actual distance,
    # by using a huge radius -- this test is about aggro overriding
    # normal movement, not about the radius boundary itself (see the
    # next test for that).
    manager.config.aggro_radius = 10_000
    manager.spawns = [spawn]

    before = max(abs(spawn.x - player_tile[0]), abs(spawn.y - player_tile[1]))
    manager.update_spawns(current_tick=1)
    after = max(abs(spawn.x - player_tile[0]), abs(spawn.y - player_tile[1]))

    assert after < before, (before, after, spawn.x, spawn.y, player_tile)


def test_spawn_outside_radius_does_not_aggro():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=0, pos_y=0))
    walkable = manager._get_walkable_tiles()
    assert len(walkable) >= 2

    spawn_tile = walkable[0]
    player_tile = walkable[-1]
    manager.instance.pos_x, manager.instance.pos_y = player_tile

    spawn = SpawnEntry(x=spawn_tile[0], y=spawn_tile[1], behavior=SpawnBehavior.GUARD)
    manager.config.aggro_radius = 0  # nothing is ever in range
    manager.spawns = [spawn]

    assert manager._is_aggroed(spawn, player_tile[0], player_tile[1]) is False
    # GUARD never moves on its own (matches existing _should_move behavior) --
    # confirms aggro=False doesn't accidentally grant movement it shouldn't have.
    before = (spawn.x, spawn.y)
    manager.update_spawns(current_tick=1)
    assert (spawn.x, spawn.y) == before


def test_boss_and_elite_never_aggro():
    dungeon = _small_dungeon()
    manager = _manager(dungeon, _StubInstance(seed=42, pos_x=5, pos_y=5))
    spawn = SpawnEntry(x=5, y=6, behavior=SpawnBehavior.BOSS)
    manager.config.aggro_radius = 10_000
    assert manager._is_aggroed(spawn, 5, 5) is False

    spawn2 = SpawnEntry(x=5, y=6, behavior=SpawnBehavior.ELITE)
    assert manager._is_aggroed(spawn2, 5, 5) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_spawn_aggro.py -v
```
Expected: all three FAIL — `_is_aggroed` and `_move_toward_player` don't
exist yet (`AttributeError`), and `SpawnConfig(aggro_radius=...)` raises
`TypeError: unexpected keyword argument 'aggro_radius'`.

- [ ] **Step 3: Add `aggro_radius` to `SpawnConfig`**

In `app/dungeon/spawn_manager.py`, inside the `SpawnConfig` dataclass,
immediately after the existing `patrol_range: int = 8` field (around
line 63), add:

```python
    # Aggro: ambient-tier spawns (PATROL/WANDERER/GUARD/AMBIENT) within
    # this Chebyshev distance of the player move toward them every tick
    # instead of their normal behavior, until contact or until the
    # player moves back outside this radius. Recomputed fresh every
    # tick -- no persisted "is aggroed" state. Bosses/Elites never aggro.
    aggro_radius: int = 5
```

- [ ] **Step 4: Add `_is_aggroed` and `_move_toward_player`**

In `app/dungeon/spawn_manager.py`, immediately after the existing
`_move_wanderer` method (the file's last method, ends with the file
itself per the current layout), add:

```python
    def _is_aggroed(self, spawn: SpawnEntry, player_x: Optional[int], player_y: Optional[int]) -> bool:
        """True if this is an ambient-tier spawn within aggro_radius of the player.

        Bosses/Elites never aggro -- they're deliberate set-piece placements,
        not part of the ambient-encounters pool this behavior is scoped to.
        """
        if player_x is None or player_y is None:
            return False
        if spawn.behavior not in (
            SpawnBehavior.PATROL,
            SpawnBehavior.WANDERER,
            SpawnBehavior.GUARD,
            SpawnBehavior.AMBIENT,
        ):
            return False
        return max(abs(spawn.x - player_x), abs(spawn.y - player_y)) <= self.config.aggro_radius

    def _move_toward_player(self, spawn: SpawnEntry, player_x: int, player_y: int):
        """Take one cardinal step toward the player.

        Reuses the same bounds/walkable/occupied validation as
        _move_patrol/_move_wanderer. Greedily reduces whichever axis has
        the larger distance first (ties broken toward the x-axis); if
        that axis's destination is blocked, tries the other axis; if
        both are blocked, doesn't move this tick.
        """
        from app.dungeon.tiles import DOOR, ROOM, TUNNEL

        walkable_chars = {ROOM, TUNNEL, DOOR}
        dx_dist = player_x - spawn.x
        dy_dist = player_y - spawn.y

        def step(dx: int, dy: int) -> bool:
            new_x, new_y = spawn.x + dx, spawn.y + dy
            if 0 <= new_x < self.dungeon.config.width and 0 <= new_y < self.dungeon.config.height:
                if self.dungeon.grid[new_x][new_y] in walkable_chars and not self.get_spawn_at(new_x, new_y):
                    spawn.x = new_x
                    spawn.y = new_y
                    return True
            return False

        x_step = (1 if dx_dist > 0 else -1 if dx_dist < 0 else 0, 0)
        y_step = (0, 1 if dy_dist > 0 else -1 if dy_dist < 0 else 0)

        if abs(dx_dist) >= abs(dy_dist):
            primary, secondary = x_step, y_step
        else:
            primary, secondary = y_step, x_step

        if primary != (0, 0) and step(*primary):
            return
        if secondary != (0, 0):
            step(*secondary)
```

- [ ] **Step 5: Wire aggro into `update_spawns`**

In `app/dungeon/spawn_manager.py`, replace the existing `update_spawns`
method body:

```python
    def update_spawns(self, current_tick: int) -> List[SpawnEntry]:
        """Update spawn positions based on game clock.

        Args:
            current_tick: Current game clock tick

        Returns:
            List of spawns that moved this update
        """
        moved_spawns = []

        for spawn in self.spawns:
            if spawn.in_combat:
                continue

            # Check if spawn should move
            if not self._should_move(spawn, current_tick):
                continue

            # Move based on behavior
            old_x, old_y = spawn.x, spawn.y

            if spawn.behavior == SpawnBehavior.PATROL:
                self._move_patrol(spawn)
            elif spawn.behavior == SpawnBehavior.WANDERER:
                self._move_wanderer(spawn)

            # Track movement
            if (spawn.x, spawn.y) != (old_x, old_y):
                spawn.last_move_tick = current_tick
                moved_spawns.append(spawn)

        return moved_spawns
```

with:

```python
    def update_spawns(self, current_tick: int) -> List[SpawnEntry]:
        """Update spawn positions based on game clock.

        Args:
            current_tick: Current game clock tick

        Returns:
            List of spawns that moved this update
        """
        moved_spawns = []
        player_x = getattr(self.instance, "pos_x", None)
        player_y = getattr(self.instance, "pos_y", None)

        for spawn in self.spawns:
            if spawn.in_combat:
                continue

            aggroed = self._is_aggroed(spawn, player_x, player_y)

            # Aggro overrides the normal move-interval gate -- a chasing
            # spawn moves every tick, not on its usual patrol/wander cadence.
            if not aggroed and not self._should_move(spawn, current_tick):
                continue

            old_x, old_y = spawn.x, spawn.y

            if aggroed:
                self._move_toward_player(spawn, player_x, player_y)
            elif spawn.behavior == SpawnBehavior.PATROL:
                self._move_patrol(spawn)
            elif spawn.behavior == SpawnBehavior.WANDERER:
                self._move_wanderer(spawn)

            # Track movement
            if (spawn.x, spawn.y) != (old_x, old_y):
                spawn.last_move_tick = current_tick
                moved_spawns.append(spawn)

        return moved_spawns
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_aggro.py -v
```
Expected: all three PASS.

- [ ] **Step 7: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 408 passed (405 baseline + 3 new), 2 skipped, 3 deselected, 1
xpassed.

- [ ] **Step 8: Commit**

```bash
git add app/dungeon/spawn_manager.py tests/test_spawn_aggro.py
git commit -m "feat(spawn): add proximity aggro for ambient-tier spawns"
```

---

### Task 2: Shared collision-trigger helper

**Files:**
- Modify: `app/dungeon/api_helpers/encounters.py`
- Test: `tests/test_collision_combat.py` (new file)

**Interfaces:**
- Consumes: nothing from Task 1 directly (independent of the aggro
  change, just shares the same module).
- Produces: `trigger_collision_combat(instance) -> dict | None` in
  `app/dungeon/api_helpers/encounters.py`. Returns
  `{"monster": {...}, "combat_id": <int>}` if a `DungeonEntity` of
  `type="monster"` occupies `(instance.pos_x, instance.pos_y, instance.pos_z)`
  for `instance.id` (starts combat via `combat_service.start_session` and
  deletes that entity); returns `None` otherwise. Uses
  `instance.user_id`, not Flask-Login's `current_user`.
- Produces: `run_monster_patrols` now also calls
  `trigger_collision_combat` after moving spawns, writing the result into
  `resp["encounter"]` when one fires (the same `resp`-mutation
  convention the function already uses for its websocket side effects).
- This task does NOT yet update `movement_handler.py` to call the new
  helper (Task 3) or remove `maybe_spawn_encounter` (also Task 3) — both
  the old and new collision logic coexist after this task, which is
  intentional so this task's diff is reviewable on its own.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_collision_combat.py`:

```python
"""Tests for the shared monster-at-player-tile collision-combat trigger."""

from app import db
from app.dungeon.api_helpers.encounters import trigger_collision_combat
from app.models.entities import DungeonEntity
from tests.factories import create_instance, create_user


def test_trigger_collision_combat_starts_combat_and_removes_entity(test_app):
    with test_app.app_context():
        user = create_user("collision_" + "1")
        inst = create_instance(user, seed=555)
        inst.pos_x, inst.pos_y, inst.pos_z = 3, 4, 0
        db.session.commit()

        entity = DungeonEntity(
            user_id=user.id,
            instance_id=inst.id,
            seed=inst.seed,
            type="monster",
            slug="test-grunt",
            name="Test Grunt",
            x=3,
            y=4,
            z=0,
            hp_current=20,
            data='{"hp": 20, "damage": 4, "speed": 8}',
        )
        db.session.add(entity)
        db.session.commit()
        entity_id = entity.id

        result = trigger_collision_combat(inst)

        assert result is not None
        assert result["monster"]["slug"] == "test-grunt"
        assert "combat_id" in result
        assert db.session.get(DungeonEntity, entity_id) is None


def test_trigger_collision_combat_returns_none_when_nothing_there(test_app):
    with test_app.app_context():
        user = create_user("collision_" + "2")
        inst = create_instance(user, seed=556)
        inst.pos_x, inst.pos_y, inst.pos_z = 1, 1, 0
        db.session.commit()

        assert trigger_collision_combat(inst) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_collision_combat.py -v
```
Expected: both FAIL with `ImportError`/`AttributeError` —
`trigger_collision_combat` doesn't exist yet.

- [ ] **Step 3: Add `trigger_collision_combat` and wire it into `run_monster_patrols`**

In `app/dungeon/api_helpers/encounters.py`, add `import json` to the
top-level imports (the file currently only has `import random as _r`):

```python
import json
import random as _r
```

Then, immediately before the `def maybe_spawn_encounter(...)` function
(which Task 3 will delete — leave it in place for this task), add:

```python
def trigger_collision_combat(instance) -> dict | None:
    """If a monster entity occupies the player's current tile, start
    combat and permanently remove that entity (finite pool -- it never
    regenerates).

    Used both when the player walks onto a monster
    (movement_handler.process_movement) and when a chasing monster
    reaches the player (run_monster_patrols, below).

    Returns {"monster": <payload dict>, "combat_id": <int>} if combat
    started, else None.
    """
    from app.models.entities import DungeonEntity

    try:
        monster_ent = DungeonEntity.query.filter_by(
            instance_id=instance.id,
            type="monster",
            x=instance.pos_x,
            y=instance.pos_y,
            z=instance.pos_z,
        ).first()
    except Exception:
        return None

    if not monster_ent:
        return None

    mdata = {}
    try:
        if monster_ent.data:
            mdata = json.loads(monster_ent.data)
    except Exception:
        mdata = {}

    monster_payload = {
        "slug": monster_ent.slug,
        "name": monster_ent.name or monster_ent.slug,
        "hp": monster_ent.hp_current or mdata.get("hp", 30),
        "damage": mdata.get("damage", 6),
        "speed": mdata.get("speed", 10),
    }

    from app.services import combat_service

    session_row = combat_service.start_session(instance.user_id, monster_payload)
    combat_id = session_row.id

    try:
        db.session.delete(monster_ent)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return {"monster": monster_payload, "combat_id": combat_id}
```

Update `__all__` near the top of the file:

```python
__all__ = ["maybe_spawn_encounter", "trigger_collision_combat", "run_monster_patrols"]
```

Then, in `run_monster_patrols`, add a call to `trigger_collision_combat`
after the existing `if moved_spawns: ... except Exception: db.session.rollback()`
block, but still inside the function's outer `try`. The end of
`run_monster_patrols` currently reads:

```python
            except Exception:
                db.session.rollback()

    except Exception:
        # Swallow exceptions to avoid blocking player actions
        pass
```

Change it to:

```python
            except Exception:
                db.session.rollback()

        # After monsters move, check whether a chasing spawn reached the
        # player's tile this tick -- mirrors the player-onto-monster
        # check in movement_handler.process_movement, just triggered by
        # monster movement instead of player movement. Runs every call,
        # not just when something moved this tick, so a spawn that was
        # already standing on the player's tile from a prior tick is
        # still caught.
        try:
            collision = trigger_collision_combat(instance)
            if collision:
                resp["encounter"] = collision
        except Exception:
            pass

    except Exception:
        # Swallow exceptions to avoid blocking player actions
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_collision_combat.py -v
```
Expected: both PASS.

- [ ] **Step 5: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 410 passed (408 from Task 1 + 2 new), 2 skipped, 3 deselected,
1 xpassed. `maybe_spawn_encounter` still exists and is still called from
`movement_handler.py` at this point — nothing should regress.

- [ ] **Step 6: Commit**

```bash
git add app/dungeon/api_helpers/encounters.py tests/test_collision_combat.py
git commit -m "feat(encounters): add shared monster-reaches-player collision trigger"
```

---

### Task 3: Wire movement_handler to the new helper, retire the random roll

**Files:**
- Modify: `app/dungeon/movement_handler.py`
- Modify: `app/routes/dungeon_api.py`
- Modify: `app/dungeon/api_helpers/encounters.py`
- Modify: `tests/conftest.py`
- Delete tests: `tests/test_time_and_encounters.py::test_encounter_miss_streak_accumulates_with_gap`,
  `tests/test_encounter_config.py::test_encounter_spawn_probability_config`,
  `tests/test_encounter_config.py::test_encounter_spawn_probability_zero`

**Interfaces:**
- Consumes: `trigger_collision_combat` from Task 2.
- Produces: `app/routes/dungeon_api.py`'s `advance_non_combat_time` gains
  an optional `resp: dict | None = None` keyword parameter (return type
  unchanged — still `int | None`, the tick value — so the other 5
  existing call sites in `dungeon_api.py` that don't pass `resp` are
  completely unaffected).
- `movement_handler.process_movement`'s public contract (return type
  `Tuple[bool, Dict[str, Any]]`, the response dict's keys) is unchanged;
  only how `combat_started`/`combat_id`/`encounter` get populated changes
  internally.

- [ ] **Step 1: Update `advance_non_combat_time` to accept an optional `resp`**

In `app/routes/dungeon_api.py`, find:

```python
def advance_non_combat_time(instance, *, tick_amount: int = 1) -> int | None:
    """Advance global non-combat time and run patrol updates.

    Parameters:
        instance: DungeonInstance (player's current dungeon instance row)
        tick_amount: How many ticks to add for this action (default 1). Could scale for longer actions later.
    Side effects:
        * Increments GameClock.tick if not in combat
        * Invokes run_monster_patrols to adjust monster positions (which can emit websocket updates)
    Failures are swallowed to avoid interrupting player flow.
    """
    try:
        clock = GameClock.get()
        if clock.combat:
            return
        clock.tick += int(tick_amount)

        # Acquire dungeon object to pass into patrols (mirrors movement logic)
        MAP_SIZE = 75
        dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
        run_monster_patrols(dungeon, instance, resp={}, tick_amount=tick_amount)
```

Replace with:

```python
def advance_non_combat_time(instance, *, tick_amount: int = 1, resp: dict | None = None) -> int | None:
    """Advance global non-combat time and run patrol updates.

    Parameters:
        instance: DungeonInstance (player's current dungeon instance row)
        tick_amount: How many ticks to add for this action (default 1). Could scale for longer actions later.
        resp: Optional dict to receive patrol side effects -- currently just
            an "encounter" key if a chasing monster reached the player this
            tick (see encounters.trigger_collision_combat). Callers that
            don't care can omit it entirely; it defaults to a throwaway dict.
    Side effects:
        * Increments GameClock.tick if not in combat
        * Invokes run_monster_patrols to adjust monster positions (which can emit websocket updates)
    Failures are swallowed to avoid interrupting player flow.
    """
    try:
        clock = GameClock.get()
        if clock.combat:
            return
        clock.tick += int(tick_amount)

        # Acquire dungeon object to pass into patrols (mirrors movement logic)
        MAP_SIZE = 75
        dungeon = get_cached_dungeon(instance.seed, (MAP_SIZE, MAP_SIZE, 1))
        run_monster_patrols(dungeon, instance, resp=resp if resp is not None else {}, tick_amount=tick_amount)
```

(The rest of the function body — clock commit, `apply_tick_decay` call,
return value — is unchanged; only the signature line and the
`run_monster_patrols` call line change.)

- [ ] **Step 2: Replace the inline collision block in `movement_handler.py`**

In `app/dungeon/movement_handler.py`, change the import line:

```python
from app.dungeon.api_helpers.encounters import maybe_spawn_encounter
```

to:

```python
from app.dungeon.api_helpers.encounters import trigger_collision_combat
```

Then replace the entire block from `# Check for collision-based encounter`
through the end of the random-roll block (everything between
`combat_started = False` and the line right before
`# Get current position and build description`):

```python
    # Check for collision-based encounter (monster entity on tile)
    combat_started = False
    combat_id = None
    encounter_payload = None

    if moved:
        try:
            monster_ent = DungeonEntity.query.filter_by(
                instance_id=instance.id,
                type="monster",
                x=instance.pos_x,
                y=instance.pos_y,
                z=instance.pos_z,
            ).first()

            if monster_ent:
                mdata = {}
                try:
                    if monster_ent.data:
                        mdata = _json.loads(monster_ent.data)
                except Exception:
                    mdata = {}

                monster_payload = {
                    "slug": monster_ent.slug,
                    "name": monster_ent.name or monster_ent.slug,
                    "hp": monster_ent.hp_current or mdata.get("hp", 30),
                    "damage": mdata.get("damage", 6),
                    "speed": mdata.get("speed", 10),
                }

                from app.services import combat_service

                session_row = combat_service.start_session(current_user.id, monster_payload)
                combat_id = session_row.id
                combat_started = True
                encounter_payload = {"monster": monster_payload, "combat_id": combat_id}

                try:
                    db.session.delete(monster_ent)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            logger.error(event="monster_collision_error", error=str(e))

    # Roll for random encounter if no collision encounter
    encounter_debug = {}
    if (moved or not noop) and not combat_started:
        maybe_spawn_encounter(instance, bool(moved or not noop), resp := {})
        if "encounter" in resp:
            combat_started = True
            combat_id = resp["encounter"].get("combat_id")
            encounter_payload = resp["encounter"]
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
        else:
            if "encounter_chance" in resp:
                encounter_debug["encounter_chance"] = resp["encounter_chance"]
            if "encounter_roll" in resp:
                encounter_debug["encounter_roll"] = resp["encounter_roll"]
```

with:

```python
    # Check for collision-based encounter (monster entity on player's tile)
    combat_started = False
    combat_id = None
    encounter_payload = None

    if moved:
        try:
            collision = trigger_collision_combat(instance)
            if collision:
                combat_id = collision["combat_id"]
                combat_started = True
                encounter_payload = collision
        except Exception as e:
            logger.error(event="monster_collision_error", error=str(e))
```

This removes the `encounter_debug` mechanism entirely along with the
random roll it existed to support — also remove its later use. Find:

```python
    # Add debug info if present
    if encounter_debug:
        response.update(encounter_debug)
```

and delete those two lines (the `if encounter_debug:` block).

- [ ] **Step 3: Gate `advance_non_combat_time` and merge its encounter result**

In `app/dungeon/movement_handler.py`, find the existing block:

```python
    # Advance game time for any world-advancing action (a move is a turn, whether
    # or not it triggered combat). The clock should never stall on the move that
    # happens to bump into a monster.
    if moved or not noop:
        try:
            from app.routes.dungeon_api import advance_non_combat_time

            tick_val = advance_non_combat_time(instance, tick_amount=1)
            if tick_val is not None:
                response["game_tick"] = tick_val
        except Exception as e:
            logger.error(event="time_advance_error", error=str(e))

    return moved, response
```

Replace with:

```python
    # Advance game time for any world-advancing action (a move is a turn, whether
    # or not it triggered combat). The clock should never stall on the move that
    # happens to bump into a monster. Skipped entirely if combat already started
    # this turn (player walked onto a monster) -- advancing the clock and running
    # patrol movement on top of a combat-starting turn doesn't make sense, and
    # would risk a chasing monster also reaching the player in the same request,
    # starting a second combat session.
    if (moved or not noop) and not combat_started:
        try:
            from app.routes.dungeon_api import advance_non_combat_time

            patrol_resp: Dict[str, Any] = {}
            tick_val = advance_non_combat_time(instance, tick_amount=1, resp=patrol_resp)
            if tick_val is not None:
                response["game_tick"] = tick_val
            if "encounter" in patrol_resp:
                response["combat_started"] = True
                response["combat_id"] = patrol_resp["encounter"].get("combat_id")
                response["encounter"] = patrol_resp["encounter"]
        except Exception as e:
            logger.error(event="time_advance_error", error=str(e))

    return moved, response
```

(`Dict`/`Any` are already imported at the top of this file —
`from typing import Any, Dict, Tuple` — confirmed present.)

- [ ] **Step 4: Delete now-unused imports in `movement_handler.py`**

Run:
```bash
grep -n "_json\." app/dungeon/movement_handler.py
grep -n "DungeonEntity" app/dungeon/movement_handler.py
```
The first should return no matches (the only use was the collision
block just removed) — delete the line `import json as _json` from the
top of the file. The second should return only the `from
app.models.entities import DungeonEntity` import line itself (no other
usage) — delete that import line too. If either grep returns an
additional match beyond its own import line, leave that particular
import in place instead.

- [ ] **Step 5: Delete `maybe_spawn_encounter`, `_load_spawn_config`, `_debug_flag`**

In `app/dungeon/api_helpers/encounters.py`, delete the entire
`_load_spawn_config` function, the entire `_debug_flag` function, and the
entire `maybe_spawn_encounter` function (everything from
`def _load_spawn_config():` through the end of `maybe_spawn_encounter`'s
body, immediately before `def run_monster_patrols`).

Update `__all__`:

```python
__all__ = ["trigger_collision_combat", "run_monster_patrols"]
```

Update the module docstring at the top of the file — it currently lists
`maybe_spawn_encounter` in its "Public functions" section and describes
"Encounter spawn chance calculation with streak-based pacing" and
"Debug keys included only if debug_encounters flag truthy" in its
design notes. Replace the docstring with:

```python
"""Encounter triggering and patrol helpers.

Public functions:
- trigger_collision_combat(instance) -> dict | None (starts combat if a
  monster entity occupies the player's current tile; deletes that
  entity so the finite spawn pool never regenerates)
- run_monster_patrols(dungeon, instance, resp: dict) -> None (moves
  spawns, including proximity-aggro chasing; also calls
  trigger_collision_combat after moving them, writing into resp if a
  chasing monster reached the player)

Design choices:
- Functions swallow exceptions to avoid blocking player movement
"""
```

- [ ] **Step 6: Delete the three random-roll-specific tests**

In `tests/test_time_and_encounters.py`, delete the entire
`test_encounter_miss_streak_accumulates_with_gap` function (it directly
exercises `maybe_spawn_encounter`'s streak logic, which no longer
exists). Leave `test_gameclock_advances_and_returned_in_move` and
`test_patrol_multiple_attempts_for_large_tick` exactly as they are.

In `tests/test_encounter_config.py`, delete the entire
`test_encounter_spawn_probability_config` and
`test_encounter_spawn_probability_zero` functions. Leave
`test_rarity_weight_override`, `test_loot_service_special_drop`, and
`test_loot_service_no_special` exactly as they are (and leave the
`_seed_monsters_for_band` autouse fixture in place — Task 5 below uses
this same monster catalog seeding precedent in a different test file,
but doesn't touch this fixture).

- [ ] **Step 7: Clean up the now-dead `VOLATILE_KEYS` entries in `tests/conftest.py`**

Find the `_reset_volatile_game_config` fixture's `VOLATILE_KEYS` tuple:

```python
    VOLATILE_KEYS = (
        "encounter_spawn",
        "rarity_weights",
        "game_rules.encounter_spawn_rate",
        "monster_ai",
        "debug_encounters",
        "regen_rates",
    )
```

Replace with:

```python
    VOLATILE_KEYS = (
        "rarity_weights",
        "monster_ai",
        "regen_rates",
    )
```

- [ ] **Step 8: Run the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 407 passed (410 from Task 2, minus 3 deleted tests), 2 skipped,
3 deselected, 1 xpassed. Pay particular attention to
`tests/test_time_and_encounters.py` and `tests/test_continue_adventure.py`
passing cleanly — both exercise movement/patrol code paths this task
directly modifies.

- [ ] **Step 9: Commit**

```bash
git add app/dungeon/movement_handler.py app/routes/dungeon_api.py app/dungeon/api_helpers/encounters.py tests/conftest.py tests/test_time_and_encounters.py tests/test_encounter_config.py
git commit -m "feat(encounters): retire the random per-move encounter roll"
```

---

### Task 4: Remove the dead admin control

**Files:**
- Modify: `app/routes/admin.py`
- Modify: `app/templates/admin_game_rules.html`

**Interfaces:**
- No code interfaces — this is dead-config cleanup following Task 3's
  removal of the only reader of `game_rules.encounter_spawn_rate` and
  `debug_encounters`.

- [ ] **Step 1: Remove the field from `admin.py`'s `game_rules` view**

In `app/routes/admin.py`, in the `game_rules` view's POST handler, find:

```python
        rules = {
            "encounter_spawn_rate": float(request.form.get("encounter_spawn_rate", 0.15)),
            "xp_multiplier": float(request.form.get("xp_multiplier", 1.0)),
```

Delete the `"encounter_spawn_rate"` line, leaving `"xp_multiplier"` as
the dict's first entry.

In the same view's GET branch, find:

```python
    rules = {
        "encounter_spawn_rate": get_rule("encounter_spawn_rate", 0.15),
        "xp_multiplier": get_rule("xp_multiplier", 1.0),
```

Delete the `"encounter_spawn_rate"` line there too.

- [ ] **Step 2: Remove the field from the template**

In `app/templates/admin_game_rules.html`, find:

```html
                            <div class="col-md-6">
                                <label class="form-label">Encounter Spawn Rate</label>
                                <input type="number" step="0.01" min="0" max="1" name="encounter_spawn_rate"
                                    value="{{ rules.encounter_spawn_rate }}" class="form-control" required>
                                <small class="form-text text-muted">Probability of monster encounter per move
                                    (0.0-1.0)</small>
                            </div>
```

Delete this entire `<div class="col-md-6">` block.

- [ ] **Step 3: Verify the admin page still renders**

Run:
```bash
.venv/bin/python -m pytest tests/ -q -k "admin" --deselect tests/test_combat_persistence.py
```
Expected: all admin-related tests pass (no test in this repo specifically
asserts on the `encounter_spawn_rate` field's presence — confirmed via
`grep -rn "encounter_spawn_rate" tests/` returning no matches before this
change, so this is a clean removal with no test to update).

- [ ] **Step 4: Run the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 407 passed (unchanged from Task 3 — this task touches no
tested code path), 2 skipped, 3 deselected, 1 xpassed.

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin.py app/templates/admin_game_rules.html
git commit -m "chore(admin): remove dead encounter_spawn_rate control"
```

---

### Task 5: Ambient-tier spawns get real catalog monsters

**Files:**
- Modify: `app/dungeon/spawn_integration.py`
- Test: `tests/test_spawn_integration_catalog.py` (new file)

**Interfaces:**
- Consumes: `app.dungeon.spawn_manager.SpawnBehavior` (existing enum).
- Modifies behavior of: `populate_spawn_stats(spawn, party_level, instance) -> SpawnEntry`
  (signature unchanged; ambient-tier spawns now get `spawn.slug`/`spawn.name`
  from `spawn_service.choose_monster` instead of
  `spawn_service.choose_archetype_monster`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_spawn_integration_catalog.py`:

```python
"""Tests that ambient-tier spawns draw from the real MonsterCatalog,
while boss/elite spawns keep the existing archetype-label system."""

from app import db
from app.dungeon.spawn_integration import populate_spawn_stats
from app.dungeon.spawn_manager import SpawnBehavior, SpawnEntry
from app.models.models import MonsterCatalog
from app.services import spawn_service
from tests.factories import create_instance, create_user


def _seed_test_monster():
    if MonsterCatalog.query.filter_by(slug="test-grunt").first():
        return
    db.session.add(
        MonsterCatalog(
            slug="test-grunt",
            name="Test Grunt",
            level_min=1,
            level_max=10,
            base_hp=20,
            base_damage=3,
            family="test",
            rarity="common",
            boss=False,
            xp_base=10,
        )
    )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def test_ambient_spawn_uses_real_catalog_monster(test_app):
    with test_app.app_context():
        _seed_test_monster()
        user = create_user("catalogspawn_1")
        inst = create_instance(user, seed=901)

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.PATROL, archetype="Trash", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.slug == "test-grunt"
        assert spawn.name == "Test Grunt"
        assert spawn.hp_current == 20


def test_boss_spawn_still_uses_archetype_label(test_app):
    with test_app.app_context():
        user = create_user("catalogspawn_2")
        inst = create_instance(user, seed=902)

        spawn = SpawnEntry(x=0, y=0, behavior=SpawnBehavior.BOSS, archetype="Boss", level=1)
        populate_spawn_stats(spawn, party_level=1, instance=inst)

        assert spawn.name is not None and "(L" in spawn.name
        assert spawn.slug == "boss"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_integration_catalog.py -v
```
Expected: `test_ambient_spawn_uses_real_catalog_monster` FAILS —
`spawn.slug` is `"trash"`/`spawn.name` is something like `"Trash (L1)"`,
not `"test-grunt"`/`"Test Grunt"`. `test_boss_spawn_still_uses_archetype_label`
PASSES already (boss behavior is unchanged by this task) — that's
expected; it exists to lock in the unchanged path, not to be red itself.

- [ ] **Step 3: Branch `populate_spawn_stats` by behavior**

In `app/dungeon/spawn_integration.py`, add an import at the top:

```python
from app.dungeon.spawn_manager import SpawnBehavior
```

Replace the existing `populate_spawn_stats` function body:

```python
def populate_spawn_stats(spawn: "SpawnEntry", party_level: int, instance: "DungeonInstance") -> "SpawnEntry":
    """Populate a spawn with full monster stats using archetype system.

    Args:
        spawn: SpawnEntry to populate
        party_level: Average party level for scaling
        instance: DungeonInstance for tier/affix context

    Returns:
        SpawnEntry with populated stats
    """
    # Get tier and affixes from instance
    tier = getattr(instance, "tier", 1) or 1
    affix_ids_str = getattr(instance, "affix_ids", None)
    affix_ids = []
    if affix_ids_str:
        try:
            affix_ids = json.loads(affix_ids_str) if isinstance(affix_ids_str, str) else affix_ids_str
        except Exception:
            pass

    # Generate monster using archetype system
    try:
        monster_dict = spawn_service.choose_archetype_monster(
            level=spawn.level or party_level,
            archetype_name=spawn.archetype,
            tier=tier,
            affix_ids=affix_ids,
            party_size=1,  # Base stats, scale in combat as needed
        )

        # Populate spawn with generated stats
        spawn.slug = monster_dict.get("slug")
        spawn.name = monster_dict.get("name")
        spawn.hp_current = monster_dict.get("hp")
        spawn.hp_max = monster_dict.get("hp")
        spawn.data = monster_dict

    except Exception:
        # Fallback to basic stats if archetype system fails
        spawn.slug = f"{spawn.archetype.lower()}_monster"
        spawn.name = f"{spawn.archetype} Monster"
        spawn.hp_current = spawn.level * 20
        spawn.hp_max = spawn.level * 20
        spawn.data = {
            "hp": spawn.hp_current,
            "damage": spawn.level * 4,
            "level": spawn.level,
            "archetype": spawn.archetype,
        }

    return spawn
```

with:

```python
def populate_spawn_stats(spawn: "SpawnEntry", party_level: int, instance: "DungeonInstance") -> "SpawnEntry":
    """Populate a spawn with full monster stats.

    Ambient-tier spawns (PATROL/WANDERER/GUARD/AMBIENT) draw from the
    real MonsterCatalog via spawn_service.choose_monster, so placed
    monsters have real names/variety instead of a generic archetype
    label. BOSS/ELITE spawns keep the existing tier/affix-driven
    archetype system, unchanged -- they're deliberate set-piece
    placements with their own scaling mechanic, not part of this scope.

    Args:
        spawn: SpawnEntry to populate
        party_level: Average party level for scaling
        instance: DungeonInstance for tier/affix context

    Returns:
        SpawnEntry with populated stats
    """
    # Get tier and affixes from instance
    tier = getattr(instance, "tier", 1) or 1
    affix_ids_str = getattr(instance, "affix_ids", None)
    affix_ids = []
    if affix_ids_str:
        try:
            affix_ids = json.loads(affix_ids_str) if isinstance(affix_ids_str, str) else affix_ids_str
        except Exception:
            pass

    is_ambient_tier = spawn.behavior in (
        SpawnBehavior.PATROL,
        SpawnBehavior.WANDERER,
        SpawnBehavior.GUARD,
        SpawnBehavior.AMBIENT,
    )

    try:
        if is_ambient_tier:
            from app.models.dungeon_tier import DungeonAffix, DungeonTier

            tier_row = DungeonTier.query.filter_by(tier=tier).first()
            if not tier_row:
                tier_row = DungeonTier.query.filter_by(tier=1).first()
            modified_level = (spawn.level or party_level) + (tier_row.monster_level_modifier if tier_row else 0)

            monster_dict = spawn_service.choose_monster(level=modified_level, party_size=1)

            if affix_ids:
                for affix_id in affix_ids:
                    affix = DungeonAffix.query.filter_by(affix_id=affix_id).first()
                    if affix:
                        monster_dict = affix.apply_to_monster_stats(monster_dict)

            if tier_row:
                monster_dict["xp"] = int(monster_dict.get("xp", 0) * tier_row.xp_multiplier)
                monster_dict["loot_multiplier"] = monster_dict.get("loot_multiplier", 1.0) * (
                    1.0 + tier_row.loot_quality_bonus
                )
        else:
            monster_dict = spawn_service.choose_archetype_monster(
                level=spawn.level or party_level,
                archetype_name=spawn.archetype,
                tier=tier,
                affix_ids=affix_ids,
                party_size=1,  # Base stats, scale in combat as needed
            )

        # Populate spawn with generated stats
        spawn.slug = monster_dict.get("slug")
        spawn.name = monster_dict.get("name")
        spawn.hp_current = monster_dict.get("hp")
        spawn.hp_max = monster_dict.get("hp")
        spawn.data = monster_dict

    except Exception:
        # Fallback to basic stats if monster selection fails (catalog or
        # archetype system), same fallback shape for both paths.
        spawn.slug = f"{spawn.archetype.lower()}_monster"
        spawn.name = f"{spawn.archetype} Monster"
        spawn.hp_current = spawn.level * 20
        spawn.hp_max = spawn.level * 20
        spawn.data = {
            "hp": spawn.hp_current,
            "damage": spawn.level * 4,
            "level": spawn.level,
            "archetype": spawn.archetype,
        }

    return spawn
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_spawn_integration_catalog.py -v
```
Expected: both PASS.

- [ ] **Step 5: Run the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 409 passed (407 from Task 4 + 2 new), 2 skipped, 3 deselected,
1 xpassed.

- [ ] **Step 6: Commit**

```bash
git add app/dungeon/spawn_integration.py tests/test_spawn_integration_catalog.py
git commit -m "feat(spawn): ambient-tier spawns use the real monster catalog"
```

---

## Post-implementation

Update `docs/superpowers/TODO.md`: mark the "Ambient encounters need to
be a finite per-instance pool" entry (currently unchecked, with a note
pointing at the design spec) as done, summarizing the five tasks above
and the final test count. Note that play-feel tuning of `aggro_radius`
and spawn density is explicitly out of scope and left as an easy
follow-up once this is verified live.
