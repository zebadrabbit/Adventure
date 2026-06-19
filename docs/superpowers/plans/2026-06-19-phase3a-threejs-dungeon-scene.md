# Phase 3a — Three.js Dungeon Scene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a toggle-gated (`?renderer=three`) Three.js scene that renders
the dungeon's tile grid as instanced 3D geometry at a fixed 3/4-angle
orthographic camera, implementing `dungeon-canvas.js`'s full public method
surface so `adventure.js` needs only a one-line renderer-selection change.

**Architecture:** A new ES module (`app/static/js/dungeon-three.js`) exposes
`window.DungeonCanvasThree`, loaded via Three.js's CDN ES-module build behind
an import map. `adventure.html` loads both the import map and the new module
unconditionally (cheap, toggle-gated); `adventure.js` picks `DungeonCanvas` or
`DungeonCanvasThree` based on a `?renderer=three` query param, falling back to
the existing 2D canvas renderer if Three.js fails to load. The existing 2D
renderer (`dungeon-canvas.js`) and the existing `GET /api/dungeon/map`
contract are both completely unmodified.

**Tech Stack:** Three.js (pinned CDN ES module, `three@0.169.0`), vanilla
JS (no bundler, consistent with the rest of this codebase).

## Global Constraints

- No backend changes. `GET /api/dungeon/map`'s JSON contract (`grid[y][x]`,
  9 string tile-type values including `"unknown"` for unexplored tiles) is
  read-only to this work.
- `dungeon-canvas.js` is not modified — it remains the unconditional default
  renderer for every real player session.
- The new renderer must expose every method `adventure.js` calls on
  `window.dungeonCanvas`: `loadMap`, `updatePlayerPosition`, `setEntities`,
  `setNotices`, `addRevealedTiles`, `zoomIn`, `zoomOut`, `resetZoom`,
  `getCoverage`, `clearSeenTiles`, `loadSeenTiles`, `saveSeenTiles`,
  `centerOnPlayer` — even where a method is a documented no-op in this
  milestone, it must never throw.
- No player/entity rendering, no movement, no client-side radius-based fog
  dimming, no minimap, no CSS-variable theming of the 3D scene, no special
  door geometry, no lighting/shadows — all explicitly deferred to later
  milestones per the spec's Non-goals.
- Camera: `THREE.OrthographicCamera`, azimuth 45°, elevation 55°, `RADIUS =
  12` world units, frustum `±10` world units at `zoom = 1.0`, using
  `ZOOM_STEP = 0.1`, `MIN_ZOOM = 0.5`, `MAX_ZOOM = 2.0` (same constants
  `dungeon-canvas.js` already uses).
- Tile colors (hex, must match exactly): `room` `#2d3340`, `tunnel`
  `#242a36`, `door` `#9a6b35`, `locked_door` `#964a4a`, `teleporter`
  `#6B46C1`, `wall`/`secret_door` `#39414f`. `cave` and `unknown` render
  nothing.

---

### Task 1: Three.js CDN wiring, module skeleton, and renderer toggle

**Files:**
- Create: `app/static/js/dungeon-three.js`
- Modify: `app/templates/adventure.html` (add import map + module script tag,
  in the existing `{% block scripts %}` block)
- Modify: `app/static/js/adventure.js:914-925` (renderer-selection toggle)

**Interfaces:**
- Produces: `window.DungeonCanvasThree` — a class with a constructor
  `(canvasId, options = {})` and stub (no-op-but-safe) versions of every
  method listed in Global Constraints, so this task is independently
  testable (page loads, toggle works, nothing throws) before any later task
  adds real rendering logic.

- [ ] **Step 1: Create the module skeleton**

Create `app/static/js/dungeon-three.js`:
```javascript
/**
 * Three.js-based dungeon map renderer (Phase 3a — static tile grid only).
 * Toggle-gated alternative to dungeon-canvas.js; see docs/superpowers/specs/
 * 2026-06-19-phase3a-threejs-dungeon-scene-design.md for full design.
 */
import * as THREE from 'three';

const ZOOM_STEP = 0.1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.0;
const FRUSTUM_HALF_SIZE = 10; // world units at zoom = 1.0
const CAMERA_RADIUS = 12; // world units
const CAMERA_ELEVATION_DEG = 55;
const CAMERA_AZIMUTH_DEG = 45;

const TILE_COLORS = {
    room: 0x2d3340,
    tunnel: 0x242a36,
    door: 0x9a6b35,
    locked_door: 0x964a4a,
    teleporter: 0x6b46c1,
    wall: 0x39414f,
    secret_door: 0x39414f,
};

const FLOOR_TYPES = new Set(['room', 'tunnel', 'door', 'locked_door', 'teleporter']);
const WALL_TYPES = new Set(['wall', 'secret_door']);

class DungeonCanvasThree {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element #${canvasId} not found`);
        }
        this.options = options;

        this.grid = null;
        this.width = 0;
        this.height = 0;
        this.seed = null;
        this.playerPos = null;
        this.seenTiles = new Set();
        this.entities = [];
        this.notices = [];

        this.zoom = 1.0;
        this.targetZoom = 1.0;

        this.floorMesh = null;
        this.wallMesh = null;

        this._initScene();
    }

    _initScene() {
        this.scene = new THREE.Scene();
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
        this.renderer.setSize(this.canvas.width, this.canvas.height, false);

        const aspect = this.canvas.width / this.canvas.height;
        this.camera = new THREE.OrthographicCamera(
            -FRUSTUM_HALF_SIZE * aspect,
            FRUSTUM_HALF_SIZE * aspect,
            FRUSTUM_HALF_SIZE,
            -FRUSTUM_HALF_SIZE,
            0.1,
            1000
        );
        this._positionCamera(new THREE.Vector3(0, 0, 0));
        this._renderFrame();
    }

    _positionCamera(target) {
        const elevRad = THREE.MathUtils.degToRad(CAMERA_ELEVATION_DEG);
        const azimRad = THREE.MathUtils.degToRad(CAMERA_AZIMUTH_DEG);
        const horizDist = CAMERA_RADIUS * Math.cos(elevRad);
        this.camera.position.set(
            target.x + horizDist * Math.cos(azimRad),
            CAMERA_RADIUS * Math.sin(elevRad),
            target.z + horizDist * Math.sin(azimRad)
        );
        this.camera.lookAt(target);
        this.camera.updateProjectionMatrix();
    }

    _renderFrame() {
        this.renderer.render(this.scene, this.camera);
    }

    // -- Public API (stubs in this task; filled in by later tasks) --
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;
        this._renderFrame();
    }

    updatePlayerPosition(x, y) {
        this.playerPos = { x, y };
    }

    setEntities(entities) {
        this.entities = entities;
    }

    setNotices(notices) {
        this.notices = notices;
    }

    addRevealedTiles(tiles) {
        // No-op in this milestone (Phase 3a renders a static grid only).
    }

    zoomIn() {
        this.targetZoom = Math.min(MAX_ZOOM, this.targetZoom + ZOOM_STEP);
    }

    zoomOut() {
        this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
    }

    resetZoom() {
        this.targetZoom = 1.0;
    }

    getCoverage() {
        const total = this.width * this.height;
        const seen = this.seenTiles.size;
        const pct = total ? (seen / total) * 100 : 0;
        return { seen, total, pct: pct.toFixed(2) };
    }

    clearSeenTiles() {
        this.seenTiles.clear();
    }

    loadSeenTiles() {
        // No-op in this milestone — seenTiles is populated directly from
        // loadMap()'s grid data, not persisted/restored from localStorage.
    }

    saveSeenTiles() {
        // No-op in this milestone (see loadSeenTiles note above).
    }

    centerOnPlayer() {
        // No-op in this milestone (no player rendering/camera-follow yet).
    }
}

window.DungeonCanvasThree = DungeonCanvasThree;
```

- [ ] **Step 2: Add the import map and module script tag to `adventure.html`**

In `app/templates/adventure.html`, inside the existing `{% block scripts %}`
block, immediately before the existing
`<script src="{{ asset_url('js/dungeon-canvas.js') }}"></script>` line, add:
```html
<!-- Three.js (Phase 3a dungeon scene, toggle-gated via ?renderer=three) -->
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js"
  }
}
</script>
<script type="module" src="{{ asset_url('js/dungeon-three.js') }}"></script>
```

- [ ] **Step 3: Add the renderer-selection toggle to `adventure.js`**

In `app/static/js/adventure.js`, find the block at lines 914-925 (search for
`window.dungeonCanvas = new DungeonCanvas('dungeon-map'`). Replace:
```javascript
          // Initialize Canvas-based dungeon renderer
          if (window.dungeonCanvas) {
            // Already exists, reload map data
            window.dungeonCanvas.loadMap(data);
          } else {
            window.dungeonCanvas = new DungeonCanvas('dungeon-map', {
              tileSize: TILE_SIZE,
              innerVisRadius: activeFogConfig.innerRadius,
              outerVisRadius: activeFogConfig.fullRadius
            });
            window.dungeonCanvas.loadMap(data);
          }
```
with:
```javascript
          // Initialize dungeon renderer (2D canvas by default; Three.js
          // behind ?renderer=three for Phase 3a dev preview — see
          // docs/superpowers/specs/2026-06-19-phase3a-threejs-dungeon-scene-design.md)
          if (window.dungeonCanvas) {
            // Already exists, reload map data
            window.dungeonCanvas.loadMap(data);
          } else {
            const wantsThree = new URLSearchParams(location.search).get('renderer') === 'three';
            const RendererClass = (wantsThree && window.DungeonCanvasThree) || window.DungeonCanvas;
            window.dungeonCanvas = new RendererClass('dungeon-map', {
              tileSize: TILE_SIZE,
              innerVisRadius: activeFogConfig.innerRadius,
              outerVisRadius: activeFogConfig.fullRadius
            });
            window.dungeonCanvas.loadMap(data);
          }
```

- [ ] **Step 4: Manually verify both paths load without errors**

Use the `run` skill to launch the dev server, then check via Playwright (or
browser devtools) console output for both:
- `http://localhost:5000/adventure` (no query param) — confirm
  `window.dungeonCanvas` is an instance of the original `DungeonCanvas`
  (`window.dungeonCanvas.constructor.name === 'DungeonCanvas'`), zero
  console errors, the existing 2D renderer renders as before.
- `http://localhost:5000/adventure?renderer=three` — confirm
  `window.dungeonCanvas.constructor.name === 'DungeonCanvasThree'`, zero
  console errors, and `window.DungeonCanvasThree` is defined (the Three.js
  module loaded successfully). The canvas will show a blank/cleared frame at
  this point (no tile geometry yet — that's Task 2).

- [ ] **Step 5: Commit**

```bash
git add app/static/js/dungeon-three.js app/templates/adventure.html app/static/js/adventure.js
git commit -m "feat(dungeon-three): scaffold Three.js renderer behind ?renderer=three toggle"
```

---

### Task 2: Render the tile grid via InstancedMesh

**Files:**
- Modify: `app/static/js/dungeon-three.js` (`loadMap`, plus new private
  helper methods)

**Interfaces:**
- Consumes: `TILE_COLORS`, `FLOOR_TYPES`, `WALL_TYPES` (Task 1), `this.scene`/
  `this.camera`/`this._renderFrame()`/`this._positionCamera()` (Task 1).
- Produces: `this.floorMesh`/`this.wallMesh` populated as real
  `THREE.InstancedMesh` objects after `loadMap()` runs — no later task
  depends on these directly (Task 3/4 only touch camera/zoom and
  seenTiles), but documenting them here for clarity.

- [ ] **Step 1: Replace `loadMap` and add the tile-grid builder**

In `app/static/js/dungeon-three.js`, replace the existing `loadMap` method:
```javascript
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;
        this._renderFrame();
    }
```
with:
```javascript
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;

        this._buildTileGrid();
        this._positionCamera(new THREE.Vector3(this.width / 2, 0, this.height / 2));
        this._renderFrame();
    }

    _buildTileGrid() {
        if (this.floorMesh) {
            this.scene.remove(this.floorMesh);
            this.floorMesh.dispose?.();
        }
        if (this.wallMesh) {
            this.scene.remove(this.wallMesh);
            this.wallMesh.dispose?.();
        }

        const floorCells = [];
        const wallCells = [];
        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const cellType = this.grid[y][x];
                if (FLOOR_TYPES.has(cellType)) {
                    floorCells.push({ x, y, type: cellType });
                } else if (WALL_TYPES.has(cellType)) {
                    wallCells.push({ x, y, type: cellType });
                }
                // 'cave' and 'unknown' (and anything else unrecognized):
                // intentionally skipped, no instance allocated.
            }
        }

        this.floorMesh = this._buildInstancedMesh(
            floorCells,
            new THREE.PlaneGeometry(1, 1),
            (mesh, i, cell) => {
                const m = new THREE.Matrix4();
                m.makeRotationX(-Math.PI / 2);
                m.setPosition(cell.x, 0, cell.y);
                mesh.setMatrixAt(i, m);
                mesh.setColorAt(i, new THREE.Color(TILE_COLORS[cell.type]));
            }
        );

        this.wallMesh = this._buildInstancedMesh(
            wallCells,
            new THREE.BoxGeometry(1, 1, 1),
            (mesh, i, cell) => {
                const m = new THREE.Matrix4();
                m.setPosition(cell.x, 0.5, cell.y);
                mesh.setMatrixAt(i, m);
                mesh.setColorAt(i, new THREE.Color(TILE_COLORS[cell.type]));
            }
        );

        this.scene.add(this.floorMesh);
        this.scene.add(this.wallMesh);
    }

    _buildInstancedMesh(cells, geometry, placeFn) {
        const material = new THREE.MeshBasicMaterial({ vertexColors: true });
        const mesh = new THREE.InstancedMesh(geometry, material, Math.max(cells.length, 1));
        mesh.count = cells.length;
        cells.forEach((cell, i) => placeFn(mesh, i, cell));
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) {
            mesh.instanceColor.needsUpdate = true;
        }
        return mesh;
    }
```
(`Math.max(cells.length, 1)` avoids constructing a zero-capacity
`InstancedMesh`, which some Three.js versions reject; `mesh.count = 0` after
construction still correctly renders nothing when `cells.length` is 0 — e.g.
a brand-new instance where every tile is `"unknown"`.)

- [ ] **Step 2: Manually verify tile rendering**

Use the `run` skill to launch the dev server (with a character/dungeon
instance active so `/api/dungeon/map` returns real explored tiles, not all
`"unknown"`), then load `/adventure?renderer=three` and take a screenshot
(Playwright, as used in Phases 1-2's verification). Confirm:
- A grid of colored floor tiles is visible at a 3/4 angle (not top-down, not
  side-on).
- Wall tiles visibly rise above the floor plane as boxes.
- Colors match the palette in Global Constraints (no amber/brown leaking in
  anywhere — though note this scene currently uses hardcoded hex, not the
  Cold Steel CSS variables, per the spec's Non-goals, so there's no live
  Theme-DB dependency to verify here).
- No console errors.

- [ ] **Step 3: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): render tile grid via InstancedMesh floor/wall meshes"
```

---

### Task 3: Zoom controls and coverage tracking

**Files:**
- Modify: `app/static/js/dungeon-three.js` (`zoomIn`, `zoomOut`, `resetZoom`,
  `loadMap` — add seenTiles population, `getCoverage` already correct from
  Task 1)

**Interfaces:**
- Consumes: `this.camera` (a `THREE.OrthographicCamera`, from Task 1),
  `MIN_ZOOM`/`MAX_ZOOM`/`ZOOM_STEP` (Task 1).
- Produces: `this.camera.zoom` reflects `this.targetZoom` after each zoom
  call (applied immediately — no animation/easing in this milestone, unlike
  `dungeon-canvas.js`'s eased zoom, since there's no player position to
  smoothly recenter on yet; documented as a Phase 3b concern once
  camera-follow exists).

- [ ] **Step 1: Make zoom calls actually update the camera**

Replace the three zoom methods:
```javascript
    zoomIn() {
        this.targetZoom = Math.min(MAX_ZOOM, this.targetZoom + ZOOM_STEP);
    }

    zoomOut() {
        this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
    }

    resetZoom() {
        this.targetZoom = 1.0;
    }
```
with:
```javascript
    zoomIn() {
        this.targetZoom = Math.min(MAX_ZOOM, this.targetZoom + ZOOM_STEP);
        this._applyZoom();
    }

    zoomOut() {
        this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
        this._applyZoom();
    }

    resetZoom() {
        this.targetZoom = 1.0;
        this._applyZoom();
    }

    _applyZoom() {
        this.zoom = this.targetZoom;
        this.camera.zoom = this.zoom;
        this.camera.updateProjectionMatrix();
        this._renderFrame();
    }
```

- [ ] **Step 2: Populate `seenTiles` from `loadMap`'s grid data**

In `loadMap` (from Task 2), add seenTiles population. The method should now
read:
```javascript
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                if (this.grid[y][x] !== 'unknown') {
                    this.seenTiles.add(`${x},${y}`);
                }
            }
        }

        this._buildTileGrid();
        this._positionCamera(new THREE.Vector3(this.width / 2, 0, this.height / 2));
        this._renderFrame();
    }
```
(Only the new `for` loop is added — `_buildTileGrid()`/`_positionCamera()`/
`_renderFrame()` calls from Task 2 stay exactly as they were.)

- [ ] **Step 3: Manually verify zoom and coverage**

Use the `run` skill to launch the dev server, load
`/adventure?renderer=three`, and in the browser console:
- Run `window.dungeonCanvas.zoomIn()` three times, then check
  `window.dungeonCanvas.camera.zoom` equals `1.3` (three `0.1` steps above
  the `1.0` default) and confirm the rendered tiles visibly appear larger/
  zoomed in after each call.
- Run `window.dungeonCanvas.getCoverage()` and confirm it returns a `{ seen,
  total, pct }` object where `seen` is less than or equal to `total` (`75 *
  75 = 5625` for a full map) and matches the count of non-`"unknown"` cells
  in the loaded map (spot-check by comparing against the same map's data
  from `/api/dungeon/map` directly).

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): wire zoom controls to camera and populate seenTiles for coverage"
```

---

### Task 4: End-to-end verification and TODO update

**Files:**
- Modify: `docs/superpowers/TODO.md`
- Test: manual, via real browser screenshots (Playwright)

**Interfaces:**
- Consumes: all of Tasks 1-3.
- Produces: nothing new — closing verification + documentation task.

- [ ] **Step 1: Run the full backend test suite to confirm no regressions**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py --deselect tests/test_gear_party_payload.py::test_payload_reflects_gear_hp
```
Expected: all tests pass (the second deselect is the confirmed pre-existing
failure from Phase 1's merge, unrelated to any UI-redesign work). This phase
makes no backend changes, so the suite should be unaffected.

- [ ] **Step 2: Manual visual verification of both renderer paths**

Use the `run` skill to launch the dev server (with a real character/dungeon
instance so the map has real explored tiles), then via Playwright:
- Screenshot `/adventure` (no query param): confirm the existing 2D canvas
  renderer still renders exactly as before — zero visual or console
  regression from this phase's unconditional script additions.
- Screenshot `/adventure?renderer=three`: confirm the 3D tile grid renders
  at the 3/4 angle with correct colors (per Task 2's verification), zoom
  controls work (per Task 3's verification), and `getCoverage()` returns
  sane numbers.
- Confirm zero console errors on both paths.

- [ ] **Step 3: Update `docs/superpowers/TODO.md`**

Add a new entry immediately after the "UI Redesign Phase 2" entry (find it
via `grep -n "UI Redesign Phase 2" docs/superpowers/TODO.md`):
```markdown
### UI Redesign Phase 3a — Three.js dungeon scene (static tile grid) ✅
First milestone of the Three.js dungeon view: a toggle-gated
(`?renderer=three`) scene rendering the dungeon's tile grid as
`InstancedMesh` floor/wall geometry at a fixed 3/4-angle orthographic
camera, reading the existing unmodified `/api/dungeon/map` contract.
Implements `dungeon-canvas.js`'s full public method surface so
`adventure.js` needed only a one-line renderer-selection change — the
existing 2D canvas renderer stays the unconditional default for every real
player session; this is purely a toggle-gated dev preview. No
player/entity rendering, movement, client-side fog dimming, or minimap yet
— each is its own follow-up milestone (3b/3c/3d) per the roadmap's
"room for iteration, not a fixed-scope cutover" guidance for this phase.
Design: `specs/2026-06-19-phase3a-threejs-dungeon-scene-design.md`.
Next: Phase 3b (player/entity billboards + movement).
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 3a (Three.js dungeon scene) done"
```
