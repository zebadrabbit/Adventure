# Phase 3a — Three.js Dungeon View: Static Scene & Tile Grid — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
first milestone of Phase 3 of 5.

**Process note:** The user explicitly authorized autonomous decision-making for
this session ("make the best recommendations the choice to use... go until
quota runs out") while away. Every decision below that would normally be a
brainstorming question-and-answer is instead documented with its reasoning, so
it can be reviewed and overridden later if needed.

## Context

Phase 3 (Three.js dungeon view) is the roadmap's largest, most technically novel
piece — no WebGL exists anywhere in this codebase today, and the roadmap itself
flags it as needing "room for iteration, not a fixed-scope cutover." Attempting
the full feature set (camera, instanced tiles, billboard entities, fog-of-war,
minimap, movement) in one pass — especially without the user available to give
visual feedback on each tuning decision (camera angle, tile proportions,
lighting) — is the wrong risk profile for a single session.

This spec scopes the **first milestone only**: a static Three.js scene that
renders the dungeon's tile grid (from the existing, unmodified
`GET /api/dungeon/map` JSON contract) at a fixed 3/4-angle orthographic camera.
No player/entity rendering, no movement, no fog-of-war beyond what the server
already encodes (`"unknown"` for unexplored tiles), no minimap. Those are each
their own follow-up milestone (3b: entities + movement, 3c: fog-of-war +
opacity/dimming, 3d: minimap + polish), matching the roadmap's own phased
intent.

**Critical safety decision:** this milestone does **not** replace the live
renderer for real players. It ships behind a `?renderer=three` query-param
toggle in `adventure.js`, so the existing `DungeonCanvas` (`dungeon-canvas.js`)
stays the default for every real player session. This avoids the single biggest
risk of building 3D UI work blind (without a human watching) — a partially-built
renderer silently becoming what players actually see and being unable to move,
see monsters, or use fog-of-war. The toggle is removed only once a later
milestone reaches full feature parity and is explicitly promoted to default.

## Current-state findings grounding this design

- `GET /api/dungeon/map` returns `grid` as `grid[y][x]`, each cell one of 9
  string values: `"room"`, `"tunnel"`, `"door"`, `"wall"`, `"secret_door"`,
  `"locked_door"`, `"teleporter"`, `"cave"` (the dungeon model's catch-all
  default), and `"unknown"` (added by `dungeon_map()`'s own grid-building loop
  for tiles outside the server-persisted `explored` set — confirmed in
  `app/routes/dungeon_api.py`, not part of `char_to_type()`'s own 7-value
  mapping in `app/dungeon/api_helpers/tiles.py`). This is a **separate**
  mechanism from the *client-side* radius-based fog dimming
  `dungeon-canvas.js` also does — the server tells the client "never seen this
  tile, don't even tell you what it is"; the client's radius logic (Phase 3c's
  concern) handles "seen before, but not currently in view, dim it."
- `#dungeon-map` (`app/templates/adventure.html:56`) is a `<canvas
  width="800" height="600">` element. Three.js can render directly into this
  same element via `new THREE.WebGLRenderer({ canvas: existingCanvasEl })` —
  no new DOM element needed, no template markup change beyond what the toggle
  itself requires (see "Toggle mechanism" below).
- Every CDN dependency in this codebase (Bootstrap, Bootstrap Icons,
  Socket.IO) is loaded via a version-pinned `jsdelivr` URL in `base.html`,
  with no build step or bundler anywhere. Three.js's modern distribution is
  **ES-modules-only** (the old global/UMD `three.min.js` build was removed
  from the package around r150) — this is the one place this milestone
  introduces a new pattern (`<script type="module">` + an import map), but it
  coexists cleanly with every other classic `<script src>` file; nothing
  else needs to change.
- `dungeon-canvas.js`'s public interface (constructor + 12 methods) is the
  contract `adventure.js` calls against. Confirmed exact signatures by reading
  both files: `new DungeonCanvas(canvasId, { tileSize, innerVisRadius,
  outerVisRadius })`, then `loadMap(data)`, `updatePlayerPosition(x, y)`,
  `setEntities(arr)`, `setNotices(arr)`, `addRevealedTiles(tiles)`,
  `zoomIn()`, `zoomOut()`, `resetZoom()`, `getCoverage()`, `clearSeenTiles()`,
  `loadSeenTiles()`, `saveSeenTiles()`, plus a `centerOnPlayer()` method
  `adventure.js` also calls. The replacement class must expose the same
  method names (even where a method is a documented no-op in this milestone)
  so `adventure.js` never throws regardless of which renderer is active.

## Goals (Phase 3a only)

1. A new ES-module file, `app/static/js/dungeon-three.js`, exporting a global
   `window.DungeonCanvasThree` class implementing the full method surface
   listed above.
2. `loadMap(data)` builds and renders the tile grid as actual 3D geometry:
   walkable/floor-category tiles (`room`, `tunnel`, `door`, `locked_door`,
   `teleporter`) as flat instanced planes, color-coded per type; `wall` and
   `secret_door` as instanced boxes with real height (the first real "3D"-ness
   of this milestone — walls visibly rise off the floor at the 3/4 angle).
   `cave` and `unknown` tiles render nothing (the void/background shows
   through) — both are "don't draw anything here" states for this milestone,
   for different reasons (one is a real unlit cave tile type, the other is
   fog-of-war's "never seen it").
3. A fixed `THREE.OrthographicCamera` at a 3/4 angle (see "Camera" section),
   looking down at the grid. `zoomIn()`/`zoomOut()`/`resetZoom()` adjust the
   orthographic frustum (zoom in/out), matching the *behavior* of the existing
   2D canvas's zoom even though the mechanism differs.
4. `getCoverage()` ports as-is from `dungeon-canvas.js` (it's pure
   seen-tiles-set math, independent of the rendering backend) so the existing
   `window.dungeonDev.coverage()` dev helper keeps working when the toggle is
   active.
5. A `?renderer=three` query-param toggle in `adventure.js`, choosing between
   `new DungeonCanvas(...)` (default) and `new DungeonCanvasThree(...)` — a
   small, explicit, auditable change, not a default-behavior switch.

## Non-goals (deferred to later Phase 3 milestones)

- Player/monster/treasure rendering (billboards) — Phase 3b.
- Movement, camera-follow, smooth transitions between tiles — Phase 3b.
- Client-side radius-based fog dimming (the "seen before, not currently
  visible" gradient `dungeon-canvas.js` does) — Phase 3c. This milestone only
  respects the server's binary `"unknown"` vs. real-type signal.
- Minimap — Phase 3d.
- Wiring the Cold Steel `--ui-*` CSS palette into the 3D scene's colors.
  Hardcoded Three.js `Color` values matching `dungeon-canvas.js`'s existing
  `TILE_COLORS` palette (already neutral dark tones, not brown/amber) are used
  instead — reading CSS custom properties into a WebGL scene is a real but
  separate concern, not needed for this milestone's goal of proving the
  camera/geometry approach works. Worth revisiting once Phase 3 is feature-
  complete and a "should the 3D scene re-theme with the admin theme-switcher"
  decision is deliberately made, not bundled into the first 3D milestone.
- Promoting this renderer to the default for any real player. The toggle
  exists specifically so this does not happen until explicitly decided later.
- Special door geometry (today's 2D renderer draws doors as floor-plus-wood-
  plank art). This milestone treats doors as a distinctly-colored flat floor
  tile, matching the "walkable category" grouping above — door-specific 3D
  geometry (a frame, a swinging panel) is cosmetic polish for a later pass.
- Lighting/shadows. `MeshBasicMaterial` (unlit, flat-colored) is used for
  every tile this milestone — simplest possible rendering, defers any
  lighting-rig decision (which materially affects performance at 5,625
  tiles) until entities/movement (3b) make lighting's visual payoff clearer.

## Toggle mechanism

`app/templates/adventure.html` gains one new `<script type="importmap">` block
(mapping the bare specifier `"three"` to the pinned CDN ESM URL) and one new
`<script type="module" src="{{ asset_url('js/dungeon-three.js') }}"></script>`
tag, alongside the existing `dungeon-canvas.js` classic-script tag — both load
unconditionally (cheap, ~600KB minified-gzipped Three.js core, acceptable for a
dev-preview-gated feature; lazy-loading only the module when the query param is
present is a possible future optimization, not needed for this milestone since
nothing about it affects real player page-load until promoted to default).

In `app/static/js/adventure.js`'s existing dungeon-map initialization block
(`app/static/js/adventure.js:914-925`), the renderer choice becomes:
```javascript
const RendererClass = new URLSearchParams(location.search).get('renderer') === 'three'
  ? window.DungeonCanvasThree
  : window.DungeonCanvas;
// ...new RendererClass('dungeon-map', { tileSize: TILE_SIZE, innerVisRadius: ..., outerVisRadius: ... });
```
This is the only `adventure.js` change in this milestone — every other call
site (`window.dungeonCanvas.setEntities(...)`, etc.) is unaffected since both
classes expose the same method names on whichever instance got assigned to
`window.dungeonCanvas`.

## Camera

`THREE.OrthographicCamera`, matching the roadmap's stated rationale
(orthographic avoids perspective distortion at grid edges, closer to the
PoE2/Diablo "flattened isometric" feel than a perspective camera). Concrete
angle: azimuth 45° (camera offset equally on both the X and Z grid axes, the
classic "corner view" every Diablo-likes use so all four tile edges read
clearly) and an elevation that reads as a steep top-down-leaning 3/4 view
rather than a shallow true-isometric one (true isometric's ~35.26° elevation
reads too flat for a dungeon-crawler grid at this tile density) — elevation
**55°** from the ground plane.

Concretely, with `target` = the look-at point (the grid's center coordinate,
`new THREE.Vector3(width / 2, 0, height / 2)`, since there's no player
position to follow yet) and a horizontal distance constant `RADIUS = 12`
(world units — chosen so the camera's horizontal offset, combined with the
frustum size below, frames roughly a 20×20 tile area, matching the 2D
canvas's default zoomed-in feel rather than the full 75×75 grid at once):

```javascript
const elevRad = THREE.MathUtils.degToRad(55);
const azimRad = THREE.MathUtils.degToRad(45);
const horizDist = RADIUS * Math.cos(elevRad);
camera.position.set(
  target.x + horizDist * Math.cos(azimRad),
  RADIUS * Math.sin(elevRad),
  target.z + horizDist * Math.sin(azimRad)
);
camera.lookAt(target);
```

The orthographic frustum itself (`left`/`right`/`top`/`bottom` on
`THREE.OrthographicCamera`) is set to `±10` world units at `zoom = 1.0` (i.e.
a 20×20-unit viewing area, one world unit per tile) — `zoomIn()`/`zoomOut()`
adjust `camera.zoom` by the same `ZOOM_STEP = 0.1` / `MIN_ZOOM = 0.5` /
`MAX_ZOOM = 2.0` constants `dungeon-canvas.js` already uses, then call
`camera.updateProjectionMatrix()`. Camera rotation is otherwise fixed — no
orbit/rotate controls in this milestone (the roadmap's "fixed 3/4 angle"
decision, not user-adjustable).

## Tile geometry & instancing

Two `THREE.InstancedMesh` objects cover the whole grid (5,625 max tiles):

1. **Floor instances** (`room`, `tunnel`, `door`, `locked_door`, `teleporter`):
   `THREE.PlaneGeometry(1, 1)` rotated flat (`rotation.x = -Math.PI / 2`),
   one instance per walkable grid cell, positioned at `(x, 0, y)` in world
   space (grid coordinates map 1:1 to world X/Z; Y is up). Per-instance color
   set via `InstancedMesh.setColorAt(i, new THREE.Color(hexForType))`,
   requiring `vertexColors: true` on the shared `MeshBasicMaterial` so each
   instance can show its own type color from one draw call.
2. **Wall instances** (`wall`, `secret_door`): `THREE.BoxGeometry(1, 1, 1)`
   (a literal 1×1×1 unit cube — full-height relative to a floor tile's
   thickness, the simplest possible "walls stick up" treatment for this
   milestone), positioned at `(x, 0.5, y)` so its base sits on the floor
   plane. Both wall sub-types share one box-color (matching
   `dungeon-canvas.js`'s `TILE_STYLE.wall.base`/`secret_door` using the same
   base color today) since secret doors are indistinguishable from walls
   until revealed — a real game-design property already true of the 2D
   renderer, not something this milestone changes.

`cave` and `unknown` cells are skipped entirely (no instance allocated for
them in either mesh) — simplest correct behavior for "render nothing here."

Colors per type (hex, matching `dungeon-canvas.js`'s existing
`TILE_COLORS`/`TILE_STYLE` base values exactly, so the 3D scene's palette is
recognizable against the 2D one rather than introducing a third, divergent
color scheme during the transition period both renderers coexist):
`room` `#2d3340`, `tunnel` `#242a36`, `door` `#9a6b35`, `locked_door`
`#964a4a`, `teleporter` `#6B46C1`, `wall`/`secret_door` `#39414f`.

## Error handling

- `loadMap(data)` called with a grid containing only `"cave"`/`"unknown"`
  cells (e.g. a brand-new instance before any tile is explored) renders an
  empty scene rather than throwing — both instanced meshes simply get zero
  instances set (`InstancedMesh.count = 0`), which Three.js handles natively.
- If the `three` CDN import fails to load (network issue), `window.
  DungeonCanvasThree` is simply undefined; the toggle code in `adventure.js`
  falls back to the default `DungeonCanvas` class rather than throwing, since
  `RendererClass` would be `undefined` otherwise — add an explicit fallback:
  `const RendererClass = (wantsThree && window.DungeonCanvasThree) ||
  window.DungeonCanvas;`.
- A `WebGLRenderer` constructor failure (e.g. a browser/environment with no
  WebGL support) is caught and logged; the toggle's fallback above also covers
  this since the failure happens inside `DungeonCanvasThree`'s constructor,
  which this spec's plan will wrap in a try/catch that re-throws a clearly-
  labeled error the developer (not a real player, since this is toggle-gated)
  can see in the console.

## Testing

No WebGL/Three.js test runner exists or is being introduced (consistent with
this repo having zero JS test infrastructure anywhere). Verification is
visual: load `/adventure?renderer=three` in a real browser (Playwright, as
used for Phases 1-2's verification) and confirm:
- A grid of colored floor tiles and taller wall boxes renders at the 3/4
  angle, with colors matching the palette above.
- `unknown`/`cave` cells show as gaps (no geometry), not as e.g. black voids
  with visible seams or z-fighting artifacts.
- `window.dungeonDev.coverage()` still returns a sane number when the toggle
  is active (confirms `getCoverage()` ported correctly).
- Loading `/adventure` **without** the query param still shows the existing
  2D canvas renderer, completely unaffected (confirms the toggle's default
  path and that nothing about the new module's unconditional script-loading
  breaks the existing page).
- No console errors on either path.

Backend: zero changes (`GET /api/dungeon/map`'s contract is read-only to this
milestone) — the existing pytest suite is run once at the end purely as a
confirm-nothing-broke check, not because new backend behavior needs covering.

## Affected files

- Create: `app/static/js/dungeon-three.js` (new ES module, `window.
  DungeonCanvasThree`).
- Modify: `app/templates/adventure.html` (add the import map + module
  `<script>` tag, alongside the existing classic-script tags — no removal of
  anything).
- Modify: `app/static/js/adventure.js` (the renderer-selection toggle at the
  existing dungeon-map initialization block — the only behavioral change to
  an existing file).
- No backend changes. No changes to `dungeon-canvas.js` itself (it remains
  the unmodified default).
