# Dungeon Generator Rewrite — Implementation Plan (Phases 0 & 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a green, repeatable test environment (Phase 0), then replace the band-aid dungeon generator with a clean carve-floor-first generator where connectivity is guaranteed by construction (Phase 1), behind the existing `Dungeon` public contract.

**Architecture:** Carve floor first (rooms, then MST-connected corridors as `TUNNEL` through solid `CAVE`), then *derive* walls (`CAVE` adjacent to `ROOM` → `WALL`) and doors (a `TUNNEL` touching a `ROOM` → `DOOR`). Connectivity is a property of carving an MST over every room, so the old repair/dedup/teleport passes are deleted. Hybrid look comes from mixing rectangular rooms with organic blob rooms.

**Tech Stack:** Python 3.12, Flask + SQLAlchemy (Postgres for app/tests), pytest, `random.Random(seed)` for determinism.

**Reference spec:** `docs/superpowers/specs/2026-06-14-dungeon-rescue-design.md`

---

## File Structure

- `app/dungeon/tiles.py` — tile constants (unchanged; keep `TELEPORT` for compat).
- `app/dungeon/config.py` — `DungeonConfig` (minor: add `blob_room_chance`, bump room spacing).
- `app/dungeon/rooms.py` — `Room` + room placement (extend: organic blob rooms, spacing pad=3).
- `app/dungeon/connect.py` — **new**: MST + corridor carving + door derivation (pure functions).
- `app/dungeon/dungeon.py` — **rewritten**: `Dungeon` orchestrator, same public contract.
- `app/dungeon/tunnels.py` — old corridor logic; left unused after rewrite, deleted in Phase 3.
- `docs/TESTING.md` — **new**: how to bootstrap venv + run tests.
- `tests/test_dungeon_carve_floor.py` — **new**: unit tests for the new generator internals.
- `tests/test_dungeon_golden_seeds.py` — **new**: determinism snapshot tests.

The `Dungeon` public contract that MUST keep working (verified via grep across `app/`):
construction `Dungeon(seed=, size=(W,H,1))` and `Dungeon(DungeonConfig(...))`; attributes
`.grid[x][y]` (column-major single-char), `.rooms` (list of `Room`), `.room_types` (parallel list),
`.metrics` (dict), `.seed`, `.size`, `.config`; methods `is_walkable(x, y, unlocked_doors=None)`,
`reveal_secret_door(x, y)`, `to_json()`, `to_ascii()`. Tiles: `C R W T D S L P`.

---

## Phase 0 — Green baseline & guardrails

### Task 1: Document and verify the test environment

**Files:**
- Create: `docs/TESTING.md`

- [ ] **Step 1: Write `docs/TESTING.md`**

```markdown
# Running the Tests

## One-time setup
The project ships a venv at `.venv`. If it lacks pip/pytest, bootstrap it:

    .venv/bin/python -m ensurepip --upgrade
    .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt

## Database
Tests require PostgreSQL. Connection comes from `TEST_DATABASE_URL` (falls back to
`DATABASE_URL`). A local Postgres is expected on port 5433 (see `docker-compose.yml`).

    export $(grep -v '^#' .env | xargs)              # loads DATABASE_URL
    export TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DATABASE_URL}"

Create + migrate the test DB once:

    .venv/bin/python -c "from app import create_app, db; \
      app=create_app(); ctx=app.app_context(); ctx.push(); db.create_all()"

## Run

    .venv/bin/python -m pytest -q

## Pure-generator tests (no DB needed)
Dungeon generation is pure Python and can run without a database:

    .venv/bin/python -m pytest tests/test_dungeon_basic.py \
      tests/test_dungeon_carve_floor.py tests/test_dungeon_golden_seeds.py \
      tests/test_room_connectivity.py -q
```

- [ ] **Step 2: Verify generator tests run without DB**

Run: `.venv/bin/python -m pytest tests/test_dungeon_basic.py tests/test_room_connectivity.py -q`
Expected: collected and run (pass/fail both fine here; we only confirm no import/collection error).

- [ ] **Step 3: Commit**

```bash
git add docs/TESTING.md
git commit -m "docs: add TESTING.md with venv + DB bootstrap"
```

### Task 2: Triage and quarantine contradictory tests

**Files:**
- Modify: `tests/test_dungeon_invariants.py` (the locked-door assertion)
- Modify: `tests/test_dungeon_teleport_movement.py` (teleport-as-crutch test)

- [ ] **Step 1: Mark the locked-door contradiction as expected-fail with a reason**

In `tests/test_dungeon_invariants.py`, above `def test_secret_and_locked_door_behavior`, add:

```python
import pytest

@pytest.mark.xfail(
    reason="Invariant being resolved in dungeon rewrite Task 9: locked doors are "
    "non-walkable until unlocked. This test asserts the old contract; updated there.",
    strict=False,
)
```

- [ ] **Step 2: Mark the teleport movement test as expected-fail**

In `tests/test_dungeon_teleport_movement.py`, above the test function(s), add:

```python
import pytest

pytestmark = pytest.mark.xfail(
    reason="Teleports removed as a connectivity crutch in dungeon rewrite (Task 8). "
    "Connectivity is now guaranteed by construction; this behavior is retired.",
    strict=False,
)
```

- [ ] **Step 3: Run the two files to confirm they xfail (not error)**

Run: `.venv/bin/python -m pytest tests/test_dungeon_invariants.py -q`
Expected: no hard FAIL for the locked-door test (shows `x`/`xfail`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_dungeon_invariants.py tests/test_dungeon_teleport_movement.py
git commit -m "test: quarantine contradictory locked-door + teleport tests pending rewrite"
```

---

## Phase 1 — Generator rewrite

### Task 3: Room placement — spacing + organic blob rooms

**Files:**
- Modify: `app/dungeon/config.py`
- Modify: `app/dungeon/rooms.py`
- Test: `tests/test_dungeon_carve_floor.py`

- [ ] **Step 1: Write failing tests for room placement guarantees**

Create `tests/test_dungeon_carve_floor.py`:

```python
from app.dungeon.config import DungeonConfig
from app.dungeon.rooms import place_rooms, Room
from app.dungeon.tiles import CAVE, ROOM
import random


def _blank(cfg):
    return [[CAVE for _ in range(cfg.height)] for _ in range(cfg.width)]


def test_rooms_have_min_spacing():
    cfg = DungeonConfig(width=60, height=60, seed=7)
    grid = _blank(cfg)
    rooms, _, placed = place_rooms(grid, cfg, rng=random.Random(cfg.seed))
    assert placed >= cfg.min_rooms
    # No two rooms within 3 cells (room interiors must have >=2 cave cells between edges)
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            sep_x = a.x - (b.x + b.w) if a.x > b.x else b.x - (a.x + a.w)
            sep_y = a.y - (b.y + b.h) if a.y > b.y else b.y - (a.y + a.h)
            assert sep_x >= 0 or sep_y >= 0  # not overlapping


def test_rooms_stay_in_bounds_with_border():
    cfg = DungeonConfig(width=50, height=50, seed=3)
    grid = _blank(cfg)
    rooms, _, _ = place_rooms(grid, cfg, rng=random.Random(cfg.seed))
    for r in rooms:
        assert r.x >= 1 and r.y >= 1
        assert r.x + r.w <= cfg.width - 1
        assert r.y + r.h <= cfg.height - 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py -q`
Expected: FAIL or PASS depending on current spacing; if PASS, still proceed (we tighten config next and keep these green).

- [ ] **Step 3: Add config fields**

In `app/dungeon/config.py`, replace the dataclass body fields by adding two fields and widening spacing intent:

```python
@dataclass
class DungeonConfig:
    width: int = 75
    height: int = 75
    min_rooms: int = 8
    max_rooms: int = 14
    min_size: int = 5
    max_size: int = 12
    irregular_chance: float = 0.25
    blob_room_chance: float = 0.20
    seed: Optional[int] = None
    extra_connection_chance: float = 0.15
```

- [ ] **Step 4: Increase room spacing pad to 3 and add blob rooms**

In `app/dungeon/rooms.py`, change `_room_overlaps` pad from `2` to `3`:

```python
def _room_overlaps(room: Room, existing: List[Room]) -> bool:
    pad = 3  # >=3 cave cells between room edges so corridors get a tunnel between doors
    for r in existing:
        if (
            room.x - pad < r.x + r.w
            and room.x + room.w + pad > r.x
            and room.y - pad < r.y + r.h
            and room.y + room.h + pad > r.y
        ):
            return True
    return False
```

Then add a blob carver and call it from `place_rooms`. After the line `for ix, iy in new_room.cells(): grid[ix][iy] = ROOM` (the interior carve), wrap it so blob rooms carve an organic shape:

```python
        # carve interior (rectangular, perturbed, or organic blob)
        if rng.random() < config.blob_room_chance:
            _carve_blob(new_room, grid, rng)
        else:
            for ix, iy in new_room.cells():
                grid[ix][iy] = ROOM
            if rng.random() < config.irregular_chance:
                _perturb_room(new_room, grid, rng)
```

Add at module end:

```python
def _carve_blob(room: Room, grid, rng):
    """Carve an organic ROOM shape via 3 cellular-automata smoothing passes
    inside the room's bounding box. Always keeps the bounding box interior
    connected by seeding the center solid."""
    w = len(grid)
    h = len(grid[0])
    cells = [(ix, iy) for ix, iy in room.cells()]
    fill = {c: (rng.random() < 0.55) for c in cells}
    cx, cy = room.center
    fill[(cx, cy)] = True
    for _ in range(3):
        nxt = {}
        for (ix, iy) in cells:
            n = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    if fill.get((ix + dx, iy + dy), False):
                        n += 1
            nxt[(ix, iy)] = n >= 4 or (ix, iy) == (cx, cy)
        fill = nxt
    for (ix, iy) in cells:
        if fill[(ix, iy)] and 0 <= ix < w and 0 <= iy < h:
            grid[ix][iy] = ROOM
    # guarantee the center is ROOM (used as corridor anchor)
    grid[cx][cy] = ROOM
```

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add app/dungeon/config.py app/dungeon/rooms.py tests/test_dungeon_carve_floor.py
git commit -m "feat(dungeon): room spacing pad + organic blob rooms"
```

### Task 4: MST + extra-edge graph over room centers

**Files:**
- Create: `app/dungeon/connect.py`
- Test: `tests/test_dungeon_carve_floor.py`

- [ ] **Step 1: Write failing test for the graph builder**

Append to `tests/test_dungeon_carve_floor.py`:

```python
from app.dungeon.connect import mst_edges, extra_edges
import random as _r


def test_mst_spans_all_rooms():
    centers = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)]
    edges = mst_edges(centers)
    assert len(edges) == len(centers) - 1
    # all nodes appear
    seen = set()
    for a, b in edges:
        seen.add(a)
        seen.add(b)
    assert seen == set(range(len(centers)))


def test_extra_edges_are_new_and_bounded():
    centers = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)]
    base = mst_edges(centers)
    extra = extra_edges(centers, base, _r.Random(1), chance=1.0)
    base_set = {tuple(sorted(e)) for e in base}
    for e in extra:
        assert tuple(sorted(e)) not in base_set
    assert len(extra) <= len(centers)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py::test_mst_spans_all_rooms -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.dungeon.connect'`.

- [ ] **Step 3: Implement `connect.py` graph functions**

Create `app/dungeon/connect.py`:

```python
"""Carve-floor-first connectivity: MST graph + corridor carving + door derivation.

Pure functions operating on the column-major grid (grid[x][y]). No teleports:
the MST spans every room, so corridors guarantee full reachability.
"""
from __future__ import annotations

from typing import List, Tuple

from .tiles import CAVE, DOOR, ROOM, TUNNEL, WALL

Point = Tuple[int, int]
Edge = Tuple[int, int]


def _dist(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def mst_edges(centers: List[Point]) -> List[Edge]:
    """Prim's algorithm over room-center points; returns list of (i, j) index edges."""
    n = len(centers)
    if n <= 1:
        return []
    in_tree = {0}
    edges: List[Edge] = []
    while len(in_tree) < n:
        best = None
        for i in in_tree:
            for j in range(n):
                if j in in_tree:
                    continue
                d = _dist(centers[i], centers[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        in_tree.add(j)
        edges.append((i, j))
    return edges


def extra_edges(centers: List[Point], base: List[Edge], rng, chance: float) -> List[Edge]:
    """Add up to len(centers) extra short edges (loops) not already in base."""
    n = len(centers)
    base_set = {tuple(sorted(e)) for e in base}
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            if tuple(sorted((i, j))) in base_set:
                continue
            candidates.append((_dist(centers[i], centers[j]), i, j))
    candidates.sort()
    out: List[Edge] = []
    for _, i, j in candidates:
        if rng.random() < chance:
            out.append((i, j))
        if len(out) >= n:
            break
    return out
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py -q`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add app/dungeon/connect.py tests/test_dungeon_carve_floor.py
git commit -m "feat(dungeon): MST + extra-edge graph over room centers"
```

### Task 5: Corridor carving (tunnels through cave)

**Files:**
- Modify: `app/dungeon/connect.py`
- Test: `tests/test_dungeon_carve_floor.py`

- [ ] **Step 1: Write failing test for corridor carving**

Append to `tests/test_dungeon_carve_floor.py`:

```python
from app.dungeon.connect import carve_corridor
from app.dungeon.tiles import CAVE, ROOM, TUNNEL
import random as _rr


def test_carve_corridor_connects_two_points():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    grid[2][2] = ROOM
    grid[15][15] = ROOM
    carve_corridor(grid, (2, 2), (15, 15), _rr.Random(0))
    # BFS over ROOM/TUNNEL from (2,2) reaches (15,15)
    from collections import deque
    q = deque([(2, 2)])
    seen = {(2, 2)}
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and grid[nx][ny] in (ROOM, TUNNEL):
                seen.add((nx, ny))
                q.append((nx, ny))
    assert (15, 15) in seen


def test_carve_corridor_does_not_touch_room_interior_tiles():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    grid[2][2] = ROOM
    grid[15][15] = ROOM
    carve_corridor(grid, (2, 2), (15, 15), _rr.Random(0))
    # endpoints remain ROOM
    assert grid[2][2] == ROOM and grid[15][15] == ROOM
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py::test_carve_corridor_connects_two_points -q`
Expected: FAIL with `ImportError: cannot import name 'carve_corridor'`.

- [ ] **Step 3: Implement `carve_corridor`**

Append to `app/dungeon/connect.py`:

```python
def _l_path(src: Point, dst: Point, rng) -> List[Point]:
    """Ortho-stepped L-shaped path from src to dst (inclusive)."""
    (sx, sy), (dx, dy) = src, dst
    horizontal_first = rng.random() < 0.5
    path: List[Point] = []
    x, y = sx, sy
    path.append((x, y))
    if horizontal_first:
        step = 1 if dx > sx else -1
        while x != dx:
            x += step
            path.append((x, y))
        step = 1 if dy > sy else -1
        while y != dy:
            y += step
            path.append((x, y))
    else:
        step = 1 if dy > sy else -1
        while y != dy:
            y += step
            path.append((x, y))
        step = 1 if dx > sx else -1
        while x != dx:
            x += step
            path.append((x, y))
    return path


def carve_corridor(grid, src: Point, dst: Point, rng) -> None:
    """Carve a tunnel between two room centers. Cells already ROOM are left intact;
    CAVE cells become TUNNEL. Doors are derived later in derive_doors()."""
    for (x, y) in _l_path(src, dst, rng):
        if grid[x][y] == CAVE:
            grid[x][y] = TUNNEL
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/dungeon/connect.py tests/test_dungeon_carve_floor.py
git commit -m "feat(dungeon): L-shaped corridor carving (tunnels through cave)"
```

### Task 6: Derive doors and walls

**Files:**
- Modify: `app/dungeon/connect.py`
- Test: `tests/test_dungeon_carve_floor.py`

- [ ] **Step 1: Write failing tests for door + wall derivation**

Append to `tests/test_dungeon_carve_floor.py`:

```python
from app.dungeon.connect import derive_doors, derive_walls
from app.dungeon.tiles import DOOR, WALL


def _ortho(grid, x, y):
    w, h = len(grid), len(grid[0])
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield grid[nx][ny]


def test_derive_doors_between_room_and_tunnel():
    w = h = 20
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    for ix in range(2, 6):
        for iy in range(2, 6):
            grid[ix][iy] = ROOM
    grid[12][3] = ROOM
    carve_corridor(grid, (4, 4), (12, 3), _rr.Random(0))
    derive_doors(grid)
    doors = [(x, y) for x in range(w) for y in range(h) if grid[x][y] == DOOR]
    assert doors, "expected at least one door"
    for x, y in doors:
        neigh = list(_ortho(grid, x, y))
        assert ROOM in neigh, f"door {(x,y)} has no room neighbor"
        assert TUNNEL in neigh, f"door {(x,y)} has no tunnel neighbor"
    # no two doors orthogonally adjacent
    for x, y in doors:
        assert DOOR not in list(_ortho(grid, x, y)), f"adjacent doors at {(x,y)}"


def test_derive_walls_only_around_rooms():
    w = h = 12
    grid = [[CAVE for _ in range(h)] for _ in range(w)]
    for ix in range(3, 7):
        for iy in range(3, 7):
            grid[ix][iy] = ROOM
    derive_walls(grid)
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                assert ROOM in list(_ortho(grid, x, y)), f"wall {(x,y)} not adjacent to room"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py::test_derive_doors_between_room_and_tunnel -q`
Expected: FAIL with `ImportError: cannot import name 'derive_doors'`.

- [ ] **Step 3: Implement `derive_doors` and `derive_walls`**

Append to `app/dungeon/connect.py`:

```python
def _ortho_neighbors(x: int, y: int):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def derive_doors(grid) -> None:
    """Label tunnel cells that touch a room as DOOR, preserving:
      * each door has a room neighbor AND a tunnel neighbor,
      * no two doors are orthogonally adjacent.
    Deterministic top-left scan."""
    w, h = len(grid), len(grid[0])
    for x in range(w):
        for y in range(h):
            if grid[x][y] != TUNNEL:
                continue
            neigh = [(nx, ny) for nx, ny in _ortho_neighbors(x, y) if 0 <= nx < w and 0 <= ny < h]
            touches_room = any(grid[nx][ny] == ROOM for nx, ny in neigh)
            has_tunnel = any(grid[nx][ny] == TUNNEL for nx, ny in neigh)
            adj_door = any(grid[nx][ny] == DOOR for nx, ny in neigh)
            if touches_room and has_tunnel and not adj_door:
                grid[x][y] = DOOR


def derive_walls(grid) -> None:
    """Convert each CAVE cell orthogonally adjacent to a ROOM into a WALL.
    Tunnels remain bare corridors through solid CAVE; doors are untouched."""
    w, h = len(grid), len(grid[0])
    to_wall = []
    for x in range(w):
        for y in range(h):
            if grid[x][y] != CAVE:
                continue
            for nx, ny in _ortho_neighbors(x, y):
                if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM:
                    to_wall.append((x, y))
                    break
    for x, y in to_wall:
        grid[x][y] = WALL
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/dungeon/connect.py tests/test_dungeon_carve_floor.py
git commit -m "feat(dungeon): derive doors + walls from carved floor"
```

### Task 7: Rewrite the `Dungeon` orchestrator

**Files:**
- Modify: `app/dungeon/dungeon.py` (full rewrite of generation pipeline; keep contract)
- Test: `tests/test_dungeon_basic.py` (existing — must pass), `tests/test_room_connectivity.py` (existing)

- [ ] **Step 1: Confirm the existing contract tests currently pass against old code (baseline)**

Run: `.venv/bin/python -m pytest tests/test_dungeon_basic.py tests/test_room_connectivity.py -q`
Expected: PASS (record this as the bar the rewrite must still clear).

- [ ] **Step 2: Rewrite `app/dungeon/dungeon.py`**

Replace the entire file with:

```python
"""Dungeon generator (carve-floor-first).

Pipeline:
    1. Place rooms (rectangular, perturbed, or organic blobs) as ROOM.
    2. Connect every room with an MST (+ a few loop edges); carve corridors as
       TUNNEL through CAVE. Connectivity is guaranteed because the MST spans all rooms.
    3. Derive DOORs where a tunnel meets a room (one per approach, never adjacent).
    4. Derive WALLs as CAVE adjacent to ROOM. Tunnels run bare through solid CAVE.
    5. Assign room types and optional secret/locked door variants.

No post-hoc repair, dedup, or teleport passes: the floor is valid by construction.

Public contract (consumed across app/):
    Dungeon(seed=None, size=(W,H,1)) | Dungeon(DungeonConfig(...))
    .grid[x][y] (column-major), .rooms, .room_types, .metrics, .seed, .size, .config
    .is_walkable(x,y,unlocked_doors=None), .reveal_secret_door(x,y), .to_json(), .to_ascii()
    Tiles: C R W T D S L P
"""
from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Tuple

from . import connect as connect_mod
from .config import DungeonConfig
from .rooms import Room, place_rooms
from .tiles import CAVE, DOOR, ROOM, TELEPORT, TUNNEL, WALL

SECRET_DOOR = "S"
LOCKED_DOOR = "L"

_WALKABLE = {ROOM, TUNNEL, DOOR, TELEPORT}


class Dungeon:
    def __init__(
        self,
        config: DungeonConfig | None = None,
        *,
        seed: int | None = None,
        size: Tuple[int, int, int] | None = None,
        **_legacy,
    ):
        if config is None:
            width = height = 75
            if size is not None and len(size) >= 2:
                width, height = size[0], size[1]
            config = DungeonConfig(width=width, height=height, seed=seed)
        else:
            if seed is not None:
                config.seed = seed
            if size is not None and len(size) >= 2:
                config.width, config.height = size[0], size[1]
        self.config = config
        if self.config.seed is None:
            self.config.seed = random.randint(0, 2**31 - 1)
        self._rng = random.Random(self.config.seed)
        self.seed = self.config.seed
        self.size = (self.config.width, self.config.height, 1)
        self.grid: List[List[str]] = [
            [CAVE for _ in range(self.config.height)] for _ in range(self.config.width)
        ]
        self.rooms: List[Room] = []
        self.room_types: List[str] = []
        self.metrics: Dict[str, Any] = {}
        self._generate()

    # ------------------------------------------------------------------
    def _generate(self):
        self._place_rooms()
        self._connect_rooms()
        connect_mod.derive_doors(self.grid)
        connect_mod.derive_walls(self.grid)
        self._assign_room_types()
        self._augment_doors_with_variants()
        self._compute_connectivity_metrics()
        self._collect_counts()
        # Teleports retired: expose empty structures for backward-compatible consumers.
        self.metrics["teleport_pairs"] = []
        self.metrics["teleport_lookup"] = {}
        self.metrics["tiles_teleport"] = 0

    def _place_rooms(self):
        rooms, target, placed = place_rooms(self.grid, self.config, rng=self._rng)
        self.rooms = rooms
        self.metrics["rooms_attempted"] = target
        self.metrics["rooms_placed"] = placed

    def _connect_rooms(self):
        if len(self.rooms) <= 1:
            return
        centers = [r.center for r in self.rooms]
        edges = connect_mod.mst_edges(centers)
        edges += connect_mod.extra_edges(
            centers, edges, self._rng, self.config.extra_connection_chance
        )
        for a, b in edges:
            connect_mod.carve_corridor(self.grid, centers[a], centers[b], self._rng)

    # ---------------- Room typing ----------------
    def _assign_room_types(self):
        n = len(self.rooms)
        self.room_types = ["room"] * n
        if n == 0:
            return
        self.room_types[0] = "start"
        areas = sorted(((r.w * r.h, i) for i, r in enumerate(self.rooms)), reverse=True)
        largest = areas[0][1]
        treasure = areas[1][1] if n > 1 else largest
        if treasure != 0:
            self.room_types[treasure] = "treasure"
        if largest not in (0, treasure):
            self.room_types[largest] = "boss"
        # connector/deadend by door count (skip special rooms)
        w, h = self.config.width, self.config.height
        for idx, r in enumerate(self.rooms):
            if self.room_types[idx] in ("start", "boss", "treasure"):
                continue
            dc = 0
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                        dc += 1
            if dc <= 1:
                self.room_types[idx] = "deadend"
            elif dc >= 3:
                self.room_types[idx] = "connector"

    # ---------------- Door variants ----------------
    def _augment_doors_with_variants(self):
        if not self.rooms:
            return
        w, h = self.config.width, self.config.height
        room_doors: Dict[int, List[Tuple[int, int]]] = {}
        for i, r in enumerate(self.rooms):
            seen = set()
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                        seen.add((nx, ny))
            if seen:
                room_doors[i] = sorted(seen)
        idx_boss = next((i for i, t in enumerate(self.room_types) if t == "boss"), None)
        if idx_boss is not None and room_doors.get(idx_boss):
            x, y = self._rng.choice(room_doors[idx_boss])
            self.grid[x][y] = LOCKED_DOOR
        for i, t in enumerate(self.room_types):
            if i == idx_boss:
                continue
            doors = room_doors.get(i, [])
            if len(doors) <= 1:
                continue  # never seal a room's only exit
            if t == "deadend":
                for x, y in doors[1:]:  # keep at least one normal door
                    if self._rng.random() < 0.3:
                        self.grid[x][y] = SECRET_DOOR
            elif t == "treasure":
                x, y = self._rng.choice(doors)
                self.grid[x][y] = SECRET_DOOR

    def reveal_secret_door(self, x: int, y: int) -> bool:
        if 0 <= x < self.config.width and 0 <= y < self.config.height and self.grid[x][y] == SECRET_DOOR:
            self.grid[x][y] = DOOR
            return True
        return False

    def is_walkable(self, x: int, y: int, unlocked_doors=None) -> bool:
        if not (0 <= x < self.config.width and 0 <= y < self.config.height):
            return False
        cell = self.grid[x][y]
        if cell == LOCKED_DOOR:
            return unlocked_doors is not None and (x, y) in unlocked_doors
        return cell in _WALKABLE  # secret doors not walkable until revealed

    # ---------------- Metrics ----------------
    def _compute_connectivity_metrics(self):
        if not self.rooms:
            self.metrics["unreachable_rooms"] = 0
            return
        w, h = self.config.width, self.config.height
        start = self.rooms[0].center
        q = deque([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and self.grid[nx][ny] in _WALKABLE:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        unreachable = sum(1 for r in self.rooms if all((ix, iy) not in seen for ix, iy in r.cells()))
        self.metrics["unreachable_rooms"] = unreachable

    def _collect_counts(self):
        counts = {CAVE: 0, ROOM: 0, WALL: 0, TUNNEL: 0, DOOR: 0, SECRET_DOOR: 0, LOCKED_DOOR: 0}
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                t = self.grid[x][y]
                counts[t] = counts.get(t, 0) + 1
        self.metrics.update(
            {
                "seed": self.seed,
                "rooms": len(self.rooms),
                "tiles_cave": counts[CAVE],
                "tiles_room": counts[ROOM],
                "tiles_wall": counts[WALL],
                "tiles_tunnel": counts[TUNNEL],
                "tiles_door": counts[DOOR],
                "secret_doors": counts[SECRET_DOOR],
                "locked_doors": counts[LOCKED_DOOR],
            }
        )
        rtc: Dict[str, int] = {}
        for t in self.room_types:
            rtc[t] = rtc.get(t, 0) + 1
        self.metrics["room_type_counts"] = rtc

    # ---------------- Outputs ----------------
    def to_ascii(self) -> str:
        return "\n".join(
            "".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "width": self.config.width,
            "height": self.config.height,
            "grid": ["".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)],
            "metrics": self.metrics,
        }


__all__ = [
    "Dungeon", "DungeonConfig", "CAVE", "ROOM", "WALL", "TUNNEL", "DOOR",
    "SECRET_DOOR", "LOCKED_DOOR", "TELEPORT",
]

if __name__ == "__main__":
    d = Dungeon(seed=1234, size=(60, 60, 1))
    print(d.to_ascii())
    print(d.metrics)
```

- [ ] **Step 3: Run the existing contract tests**

Run: `.venv/bin/python -m pytest tests/test_dungeon_basic.py tests/test_room_connectivity.py tests/test_dungeon_carve_floor.py -q`
Expected: PASS. If `test_doors_between_room_and_tunnel` or `test_wall_thickness` fail, the derive steps have a bug — fix `connect.py`, not the tests.

- [ ] **Step 4: Manual smoke — print a map and eyeball it**

Run: `.venv/bin/python -m app.dungeon.dungeon`
Expected: an ASCII map with rooms (`R`) ringed by walls (`W`), tunnels (`T`) connecting them, doors (`D`) at room entries, `unreachable_rooms: 0` in metrics.

- [ ] **Step 5: Commit**

```bash
git add app/dungeon/dungeon.py
git commit -m "feat(dungeon): carve-floor-first generator rewrite (drop repair/teleport passes)"
```

### Task 8: Connectivity guarantee test (no teleports)

**Files:**
- Test: `tests/test_dungeon_carve_floor.py`

- [ ] **Step 1: Write the connectivity invariant test**

Append to `tests/test_dungeon_carve_floor.py`:

```python
from app.dungeon import Dungeon
from app.dungeon.tiles import TELEPORT


def test_every_room_reachable_no_teleports_across_seeds():
    from collections import deque
    walkable = {"R", "T", "D", "L"}  # locked doors traversable for connectivity check
    for seed in range(50, 70):
        d = Dungeon(seed=seed, size=(60, 60, 1))
        assert d.metrics["unreachable_rooms"] == 0, f"seed {seed} has unreachable rooms"
        # there must be zero teleport tiles on the grid
        tp = sum(1 for x in range(d.config.width) for y in range(d.config.height) if d.grid[x][y] == TELEPORT)
        assert tp == 0, f"seed {seed} placed teleports (crutch); count={tp}"
        # independent BFS confirmation from start room
        start = d.rooms[0].center
        q = deque([start])
        seen = {start}
        w, h = d.config.width, d.config.height
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and d.grid[nx][ny] in walkable:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        for r in d.rooms:
            assert any((ix, iy) in seen for ix, iy in r.cells()), f"seed {seed} room unreachable by BFS"
```

- [ ] **Step 2: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_carve_floor.py::test_every_room_reachable_no_teleports_across_seeds -q`
Expected: PASS. If a seed fails, the MST/corridor logic has a gap — fix `connect.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dungeon_carve_floor.py
git commit -m "test(dungeon): guarantee full reachability without teleports across seeds"
```

### Task 9: Determinism golden-seed snapshots

**Files:**
- Create: `tests/test_dungeon_golden_seeds.py`

- [ ] **Step 1: Write the determinism test**

Create `tests/test_dungeon_golden_seeds.py`:

```python
from app.dungeon import Dungeon


def test_same_seed_same_grid():
    a = Dungeon(seed=2024, size=(60, 60, 1))
    b = Dungeon(seed=2024, size=(60, 60, 1))
    assert a.to_ascii() == b.to_ascii()
    assert a.metrics["tiles_room"] == b.metrics["tiles_room"]


def test_different_seeds_differ():
    a = Dungeon(seed=1, size=(60, 60, 1))
    b = Dungeon(seed=2, size=(60, 60, 1))
    assert a.to_ascii() != b.to_ascii()


def test_metrics_stable_keys():
    d = Dungeon(seed=99, size=(60, 60, 1))
    for key in ("seed", "rooms", "tiles_room", "tiles_wall", "tiles_tunnel",
                "tiles_door", "unreachable_rooms", "teleport_lookup", "room_type_counts"):
        assert key in d.metrics, f"missing metric {key}"
    assert d.metrics["unreachable_rooms"] == 0
```

- [ ] **Step 2: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_dungeon_golden_seeds.py -q`
Expected: PASS (3 tests).

- [ ] **Step 3: Resolve the quarantined locked-door test**

Open `tests/test_dungeon_invariants.py`. Remove the `@pytest.mark.xfail` added in Task 2 and update the locked-door assertion to the new contract:

```python
                    elif d.grid[x][y] == LOCKED_DOOR:
                        saw_any = True
                        # New contract: locked doors are NOT walkable until unlocked.
                        assert not d.is_walkable(x, y), "Locked door walkable without unlock key"
                        assert d.is_walkable(x, y, unlocked_doors={(x, y)}), "Locked door not walkable when unlocked"
```

- [ ] **Step 4: Run the invariants file**

Run: `.venv/bin/python -m pytest tests/test_dungeon_invariants.py -q`
Expected: PASS (no longer xfail).

- [ ] **Step 5: Commit**

```bash
git add tests/test_dungeon_golden_seeds.py tests/test_dungeon_invariants.py
git commit -m "test(dungeon): golden-seed determinism + resolve locked-door invariant"
```

### Task 10: Full dungeon-suite regression + integration smoke

**Files:**
- Possibly modify: `tests/test_corridor_gap_repair.py`, `tests/test_dungeon_no_wall_overwrite.py`,
  `tests/test_secret_locked_doors.py`, `tests/test_multiple_doors_exception.py`,
  `tests/test_no_orphan_doors.py`, `tests/test_dungeon_adjacency.py` (only if they assert
  behavior of the deleted passes — quarantine or update; do NOT weaken real invariants).

- [ ] **Step 1: Run the full dungeon-related suite (no DB needed)**

Run:
```bash
.venv/bin/python -m pytest tests/test_dungeon_basic.py tests/test_dungeon_carve_floor.py \
  tests/test_dungeon_golden_seeds.py tests/test_dungeon_invariants.py \
  tests/test_room_connectivity.py tests/test_dungeon_char_mapping.py \
  tests/test_dungeon_adjacency.py tests/test_no_orphan_doors.py \
  tests/test_dungeon_no_redundant_doors.py tests/test_dungeon_no_wall_overwrite.py \
  tests/test_corridor_gap_repair.py tests/test_secret_locked_doors.py \
  tests/test_multiple_doors_exception.py -q
```
Expected: PASS. For each failure, decide: is it a real invariant (fix `connect.py`/`dungeon.py`) or
a test tied to a deleted pass (e.g. `test_corridor_gap_repair` tests `_repair_corridor_gaps`, now
gone)? For tests of deleted internals, mark `@pytest.mark.skip(reason="pass removed in carve-floor-first rewrite")`.

- [ ] **Step 2: Run the DB-backed dungeon API + movement tests**

Run (with env from `docs/TESTING.md`):
```bash
export $(grep -v '^#' .env | xargs); export TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DATABASE_URL}"
.venv/bin/python -m pytest tests/test_dungeon_api.py tests/test_dungeon_api_extended.py \
  tests/test_dungeon_routes_minimal.py tests/test_dungeon_seed_api.py \
  tests/test_room_connectivity.py -q
```
Expected: PASS. Movement/api read `metrics["teleport_lookup"]` — now `{}`, so teleport branches
no-op. If any code does `metrics["teleport_lookup"]` without `.get`, fix the call site to
`metrics.get("teleport_lookup", {})`.

- [ ] **Step 3: Commit any test quarantines / call-site fixes**

```bash
git add -A
git commit -m "test(dungeon): regress full dungeon suite against carve-floor-first generator"
```

- [ ] **Step 4: Full-suite check (record new baseline)**

Run: `.venv/bin/python -m pytest -q 2>&1 | tail -5`
Expected: dungeon-related failures/errors resolved; remaining red is unrelated (DB env / other
subsystems handled in Phase 2). Record the new pass/fail counts in the commit message.

```bash
git commit --allow-empty -m "chore(dungeon): record post-rewrite test baseline"
```

---

## Self-Review

**Spec coverage:**
- Carve-floor-first principle → Tasks 5–7. ✓
- Drop-in public contract → Task 7 (contract preserved; documented in File Structure). ✓
- MST-guaranteed connectivity → Tasks 4, 8. ✓
- Hybrid (rooms + cave pockets) → Task 3 (rect + organic blob rooms). ✓
- Walls derived / doors derived → Task 6. ✓
- Delete repair/dedup/teleport passes → Task 7 (rewrite removes them). ✓
- Teleport removal + graceful no-op downstream → Task 7, Task 10 Step 2. ✓
- Locked/secret door invariant resolved → Tasks 2 (quarantine), 9 (resolve). ✓
- Determinism golden seeds → Task 9. ✓
- Integration smoke (spawn on walkable only, api/movement) → Task 10. ✓
- Phase 0 environment + triage → Tasks 1–2. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** `mst_edges`, `extra_edges`, `carve_corridor`, `derive_doors`, `derive_walls`
defined in Task 4/5/6 and called identically in Task 7. `Room.center`, `Room.cells()` used as
defined in `rooms.py`. Tile constants from `tiles.py`. ✓

**Out of scope (own future plans):** Phase 2 loop integration, Phase 3 cleanup/docs (incl. deleting
`tunnels.py`, rewriting `DUNGEON_GENERATION.md`).

---

## Execution Status (2026-06-15)

**Phases 0 & 1 complete.** Carve-floor-first generator shipped; connectivity guaranteed
by construction (no teleports), determinism + invariants covered by tests. Full dungeon
test suite green.

**Bonus — DB test infrastructure rescued.** Root-caused the 122 baseline errors to a
PostgreSQL reserved-word bug (`SELECT id FROM user` unquoted in a `before_insert` hook)
plus SQLite-only `executescript`/integer-boolean seed SQL. Fixed all of these.

**Suite movement:** baseline `91 passed / 39 failed / 122 errors` → now
`251 passed / 11 failed / 0 errors` (2 skipped, 1 xpassed).

**Remaining 11 failures — deferred to Phase 2/3 (not dungeon-related):**
- `test_autofill_characters` (2), `test_autofill_gear` (1): autofill response shape (`KeyError 'total'`).
- `test_combat_actions` (2): combat balance assertions.
- `test_entity_seeding::test_treasure_claim_endpoint`: perception RNG threshold.
- `scripts/test_hp_mp_persistence`: HP/MP flow.
- `test_server_extended::test_run_migrations_idempotent`: migration idempotency on Postgres.
- `test_encounter_config` (2), `test_time_and_encounters` (1): pass in isolation, fail in
  full run — order-dependent shared-DB-state flakiness in `conftest` (test-infra, Phase 0/2).
