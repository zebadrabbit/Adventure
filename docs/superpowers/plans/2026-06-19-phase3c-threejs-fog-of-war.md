# Phase 3c — Three.js Client-Side Fog-of-War Opacity Dimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-tile fog-of-war opacity overlay to the Three.js dungeon
renderer (`dungeon-three.js`), approximating `dungeon-canvas.js`'s
distance-based dimming gradient with a small number of discrete opacity
buckets, recomputed on every player move.

**Architecture:** A new `_buildFogOverlay()` method buckets every rendered
tile by Euclidean distance from the player into one of 5 discrete alpha
levels (4 gradient buckets + 1 flat memory-dim bucket), then builds one
semi-transparent black `InstancedMesh` per non-empty bucket — reusing the
exact "group cells, one InstancedMesh per group, plain material" pattern
`_buildTileGrid` already established in Phase 3a. Called from `loadMap` and
`updatePlayerPosition`, the two places the visible tile set or player
position can change.

**Tech Stack:** Same as Phases 3a/3b — Three.js `0.169.0` via CDN ES-module
import, no new dependencies, no JS test runner (verification is
manual/visual via Playwright).

## Global Constraints

- Single file touched: `app/static/js/dungeon-three.js`. No template,
  other-JS, or backend changes.
- Distance/alpha constants (exact values, matching `dungeon-canvas.js`):
  `INNER_VIS_RADIUS = 8`, `OUTER_VIS_RADIUS = 26`, `MIN_FOG_ALPHA = 0.18`,
  `MAX_FOG_ALPHA = 0.92`, `MEMORY_DIM_ALPHA = 0.35`.
- Bucket table (exact, from the spec — 4 gradient buckets evaluated at each
  slice's midpoint distance, plus 1 flat memory bucket):
  - `dist <= 8`: no overlay (fully lit).
  - `8 < dist <= 12.5`: alpha `≈0.272`.
  - `12.5 < dist <= 17`: alpha `≈0.458`.
  - `17 < dist <= 21.5`: alpha `≈0.643`.
  - `21.5 < dist <= 26`: alpha `≈0.828`.
  - `dist > 26` and tile key in `this.seenTiles`: alpha `0.35` (flat).
  - `dist > 26` and not in `seenTiles`: no overlay (tile was never built —
    it's `"unknown"` server-side, already skipped by `_buildTileGrid`).
- Overlay instance height: `y = 0.02` for floor-category tiles (`room`,
  `tunnel`, `door`, `locked_door`, `teleporter`), `y = 1.02` for
  wall-category tiles (`wall`, `secret_door`) — matches the spec's "just
  above the tile's visible top surface" placement.
- `_buildFogOverlay()` must no-op (no overlay instances, no throw) when
  `this.playerPos` is `null` — this is the existing Phase 3a/3b pre-move
  visual (undimmed static grid) and must not regress.
- No noise/dithering term — explicitly out of scope per the spec's
  Non-goals.

---

### Task 1: `_buildFogOverlay()` — bucket computation and overlay mesh construction

**Files:**
- Modify: `app/static/js/dungeon-three.js`

**Interfaces:**
- Consumes: `this.grid`, `this.width`, `this.height`, `this.playerPos`,
  `this.seenTiles` (all existing fields from Phases 3a/3b),
  `FLOOR_TYPES`/`WALL_TYPES` (existing constants), `this._buildInstancedMesh`
  (existing helper from Phase 3a, signature
  `_buildInstancedMesh(cells, geometry, colorHex, placeFn)`).
- Produces: `this.fogMeshes` (array, initialized in the constructor),
  `_buildFogOverlay()` (no params, no return) — called by Task 2's wiring.

- [ ] **Step 1: Add the fog constants**

In `app/static/js/dungeon-three.js`, find the existing constants block
(`OUTER_VIS_RADIUS`/`ENTITY_DEFAULT_ICON`, added in Phase 3b). Add
immediately after `ENTITY_DEFAULT_ICON`:

```javascript
const INNER_VIS_RADIUS = 8;
const MIN_FOG_ALPHA = 0.18;
const MAX_FOG_ALPHA = 0.92;
const MEMORY_DIM_ALPHA = 0.35;

// 4 discrete buckets approximating dungeon-canvas.js's continuous gradient
// between INNER_VIS_RADIUS and OUTER_VIS_RADIUS. Each bucket's alpha is the
// 2D renderer's own formula (MIN_FOG_ALPHA + fogProgress * (MAX_FOG_ALPHA -
// MIN_FOG_ALPHA)) evaluated at that bucket's distance-range midpoint.
const FOG_GRADIENT_BUCKETS = [
    { maxDist: 12.5, alpha: 0.272 },
    { maxDist: 17, alpha: 0.458 },
    { maxDist: 21.5, alpha: 0.643 },
    { maxDist: 26, alpha: 0.828 },
];
```

- [ ] **Step 2: Add the `fogMeshes` field to the constructor**

Find the constructor's field initialization block (currently ending with
`this.entitySprites = [];`, added in Phase 3b Task 1). Add immediately
after:

```javascript
        this.fogMeshes = [];
```

- [ ] **Step 3: Add `_buildFogOverlay()`**

Add this method anywhere after `_buildTileGrid()` and before
`_buildInstancedMesh()` (or anywhere else at the class body level — exact
position doesn't matter, just keep it near the other tile-building methods):

```javascript
    _buildFogOverlay() {
        this.fogMeshes.forEach((mesh) => {
            this.scene.remove(mesh);
            mesh.material.dispose();
        });
        this.fogMeshes = [];

        if (!this.playerPos) {
            this._renderFrame();
            return;
        }

        // bucket key -> { alpha, cells: [{x, y, isWall}] }
        const cellsByBucket = new Map();

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const cellType = this.grid[y][x];
                const isWall = WALL_TYPES.has(cellType);
                if (!FLOOR_TYPES.has(cellType) && !isWall) {
                    continue;
                }

                const dist = Math.hypot(x - this.playerPos.x, y - this.playerPos.y);
                let alpha = null;

                if (dist <= INNER_VIS_RADIUS) {
                    alpha = null;
                } else if (dist <= 26) {
                    const bucket = FOG_GRADIENT_BUCKETS.find((b) => dist <= b.maxDist);
                    alpha = bucket.alpha;
                } else if (this.seenTiles.has(`${x},${y}`)) {
                    alpha = MEMORY_DIM_ALPHA;
                }

                if (alpha === null) {
                    continue;
                }

                const bucketKey = alpha;
                if (!cellsByBucket.has(bucketKey)) {
                    cellsByBucket.set(bucketKey, { alpha, cells: [] });
                }
                cellsByBucket.get(bucketKey).cells.push({ x, y, isWall });
            }
        }

        for (const { alpha, cells } of cellsByBucket.values()) {
            const material = new THREE.MeshBasicMaterial({
                color: 0x000000,
                transparent: true,
                opacity: alpha,
            });
            const geometry = new THREE.PlaneGeometry(1, 1);
            const mesh = new THREE.InstancedMesh(geometry, material, cells.length);
            const m = new THREE.Matrix4();
            cells.forEach((cell, i) => {
                m.identity();
                m.makeRotationX(-Math.PI / 2);
                m.setPosition(cell.x, cell.isWall ? 1.02 : 0.02, cell.y);
                mesh.setMatrixAt(i, m);
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.fogMeshes.push(mesh);
            this.scene.add(mesh);
        }

        this._renderFrame();
    }
```

Note: `OUTER_VIS_RADIUS` already exists from Phase 3b — this step doesn't
redefine it, it's reused as the literal `26` boundary check above (matching
the Global Constraints table; using the named constant directly is fine too,
but the literal `26` here matches `OUTER_VIS_RADIUS`'s existing value — if
you prefer, replace the literal `26` with `OUTER_VIS_RADIUS` for clarity,
they are the same value).

- [ ] **Step 4: Verify the file still parses with no syntax errors**

Run: `node --check app/static/js/dungeon-three.js`
Expected: no output, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): add _buildFogOverlay bucketed opacity dimming"
```

---

### Task 2: Wire `_buildFogOverlay` into `loadMap`/`updatePlayerPosition`, verify, update TODO

**Files:**
- Modify: `app/static/js/dungeon-three.js`
- Modify: `docs/superpowers/TODO.md`
- Test: manual, via real browser (Playwright), as used for Phases 1-3b.

**Interfaces:**
- Consumes: `_buildFogOverlay()` (Task 1).
- Produces: nothing new — closing wiring + verification + documentation task.

- [ ] **Step 1: Call `_buildFogOverlay()` from `loadMap`**

Find `loadMap`'s body (currently ending with `this._buildTileGrid();` then
`this._positionCamera(...)` then `this._renderFrame();`). Add the call
immediately after `this._buildTileGrid();`:

```javascript
        this._buildTileGrid();
        this._buildFogOverlay();
        this._positionCamera(new THREE.Vector3(this.width / 2, 0, this.height / 2));
        this._renderFrame();
```

- [ ] **Step 2: Call `_buildFogOverlay()` from `updatePlayerPosition`**

Find `updatePlayerPosition`'s body (currently ending with
`this.centerOnPlayer();`). Add the call immediately after:

```javascript
    updatePlayerPosition(x, y) {
        this.playerPos = { x, y };
        if (!this.playerSprite) {
            this.playerSprite = this._makeSprite('/static/iconography/axe-sword.svg');
            this.scene.add(this.playerSprite);
        }
        this.playerSprite.position.set(x, 0.6, y);
        this.centerOnPlayer();
        this._buildFogOverlay();
    }
```

- [ ] **Step 3: Verify the file still parses with no syntax errors**

Run: `node --check app/static/js/dungeon-three.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit the wiring**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): recompute fog overlay on map load and player move"
```

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py --deselect tests/test_gear_party_payload.py::test_payload_reflects_gear_hp
```
Expected: all tests pass (the second deselect is the confirmed pre-existing
failure from prior phases, unrelated to this frontend-only work — this phase
makes zero backend changes).

- [ ] **Step 6: Launch the dev server and verify in a real browser**

Use a Playwright install available on the host (as used for Phases 1-3b's
verification: register a throwaway account via curl/Playwright, navigate,
screenshot — all within one continuous Playwright page session per the known
stale-cookie gotcha). Navigate to `/adventure?renderer=three` and confirm:
- On initial load (before any move), tiles render undimmed — no overlay
  visible, matching Phase 3a/3b's existing pre-move visual.
- After triggering a move, tiles near the player remain undimmed, and tiles
  farther away show visibly darker overlays the farther out they are (the
  4-bucket gradient should be visually distinguishable as at least 2-3
  discrete darkness levels across the visible room/corridor).
- No console errors on load or after a move.
- `/adventure` (no query param) still shows the unaffected default 2D
  renderer.

Clean up the throwaway test account afterward, deleting in FK order:
`DungeonEntity` (by `instance_id`) → `Character` (by `user_id`) →
`DungeonInstance` (by `user_id`) → `User`.

- [ ] **Step 7: Update `docs/superpowers/TODO.md`**

Find the Phase 3b entry via `grep -n "UI Redesign Phase 3b" docs/superpowers/TODO.md`.
Add a new entry immediately after it:

```markdown
### UI Redesign Phase 3c — Three.js client-side fog-of-war opacity dimming ✅
Added `_buildFogOverlay()`: buckets every rendered tile by Euclidean distance
from the player into one of 5 discrete alpha levels (4 gradient buckets
between `INNER_VIS_RADIUS` (8) and `OUTER_VIS_RADIUS` (26), plus a flat
`MEMORY_DIM_ALPHA` (0.35) bucket for previously-seen-but-now-distant tiles —
all constants matching `dungeon-canvas.js` exactly), then builds one
semi-transparent black `InstancedMesh` per non-empty bucket positioned just
above each tile's visible top surface. Recomputed on `loadMap` and on every
`updatePlayerPosition` call. Deliberately approximates the 2D renderer's
continuous per-pixel gradient with 4 discrete bands rather than porting its
noise-dithering trick — banding is far less perceptible on 3D geometry at
this tile density than on a flat 2D canvas; revisit only if live feedback
says otherwise. Known simplification: wall tiles get top-surface dimming
only, not per-side-face dimming. Design:
`specs/2026-06-19-phase3c-threejs-fog-of-war-design.md`.
Next: Phase 3d (minimap + polish).
```

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 3c (fog-of-war opacity dimming) done"
```
