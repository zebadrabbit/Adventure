# Phase 3b — Three.js Dungeon View: Player/Entity Billboards & Movement — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
second milestone of Phase 3 of 5.

**Process note:** Continuing under the user's standing autonomous-work
authorization ("make the best recommendations the choice to use... go until
quota runs out"). Every decision below that would normally be a brainstorming
question-and-answer is instead documented with its reasoning.

## Context

Phase 3a (merged) delivered a toggle-gated (`?renderer=three`), static Three.js
scene rendering the dungeon's tile grid — no entities, no player marker, no
movement. This milestone adds the player and monster/NPC billboards and wires
real movement (camera-follow as the player moves), bringing
`DungeonCanvasThree` to functional parity with `DungeonCanvas` on everything
except fog-of-war opacity gradient and the minimap (still Phase 3c/3d).

## Current-state findings grounding this design

- `dungeon-canvas.js`'s entity contract (confirmed by reading its
  `setEntities`/render code): each entity is `{x, y, icon?}` in grid
  coordinates; `icon` is a path like `/static/iconography/goblin-scout-t1.svg`,
  falling back to a hardcoded default if absent. The player has its own fixed
  icon, `/static/iconography/axe-sword.svg`.
- `dungeon-canvas.js` filters which entities it draws by Euclidean distance
  from the player using `OUTER_VIS_RADIUS` (default 26, configurable via
  `setFogConfig`) — entities farther than that are skipped entirely (a binary
  cutoff, not the opacity gradient applied to *tiles*, which is Phase 3c's
  concern). This milestone ports the same cutoff for entity billboards, since
  it's already binary/cheap and keeps 3b's entity visibility behavior matching
  the 2D renderer's, rather than showing monsters through walls/across the map
  that the 2D view would have hidden.
- `dungeon-canvas.js`'s `centerOnPlayer()` recenters the 2D viewport on the
  player's tile on every `updatePlayerPosition` call — i.e. movement is
  "camera follows player," not "player sprite moves across a fixed viewport."
  This milestone's camera-follow direly mirrors that: `_positionCamera` (built
  in Phase 3a, currently called once per `loadMap` with the grid's center as
  target) gets called again on each `updatePlayerPosition`, with the player's
  new position as the look-at target instead of the grid center.
- Three.js's `TextureLoader` cannot load `.svg` files directly (it expects
  raster formats); the existing icons are all SVG. The standard, dependency-free
  way to bridge this (already implicit in how `dungeon-canvas.js` itself draws
  SVGs onto a 2D canvas via `drawImage`) is: load the SVG into an `Image`
  element (browsers rasterize SVG `<img>` sources natively), then feed that
  `Image` directly to `new THREE.Texture(image)` (Three.js accepts any
  `CanvasImageSource`, including a loaded `<img>`, with `texture.needsUpdate =
  true` after load) — no intermediate `<canvas>` draw needed, simpler than
  `dungeon-canvas.js`'s own approach (which draws to canvas because 2D canvas
  has no other way to composite an SVG).
- `THREE.Sprite` always faces the camera (billboard behavior is the *default*
  for this primitive, not something to implement) — exactly the "2D sprite
  billboards in a real 3D environment" approach the original roadmap called
  for.

## Goals (Phase 3b only)

1. `setEntities(entities)` builds/updates one `THREE.Sprite` per entity,
   textured from that entity's `icon` (or the existing fallback path),
   positioned at `(x, 0.6, y)` in world space (slightly above the floor plane
   so it doesn't z-fight with floor tiles, low enough to read as "standing on
   the tile" rather than floating). Entities beyond `OUTER_VIS_RADIUS` from
   the current player position are not added to the scene (ported cutoff,
   see above).
2. `updatePlayerPosition(x, y)` creates the player sprite on first call
   (textured from the fixed `axe-sword.svg` icon, same positioning convention
   as entities) and moves it on every subsequent call; then re-targets the
   camera at the new position via `_positionCamera` (camera-follow, matching
   `centerOnPlayer`'s effect) and re-renders.
3. A small `_iconTexture(path)` texture cache (`Map<path, THREE.Texture>`,
   loaded once, reused across calls) — mirrors `dungeon-canvas.js`'s own
   `imageCache` pattern, avoiding redundant network/decode work as entities
   come and go each move.
4. `centerOnPlayer()` (currently a documented no-op) becomes a real,
   idempotent call: re-runs `_positionCamera` at the current `playerPos` if one
   exists, no-ops if not yet set (mirrors the 2D renderer's own guard).
5. Sprite scale: a fixed world-unit size (`0.8 × 0.8`, slightly smaller than
   one tile so adjacent entities don't visually overlap) — no per-entity size
   variation in this milestone (matches 2D renderer's fixed-size icon
   rendering today).

## Non-goals (deferred to later Phase 3 milestones)

- Per-tile fog-of-war opacity/dimming gradient (the "seen before, not
  currently visible" effect) — Phase 3c. This milestone only adds the same
  binary distance cutoff the 2D renderer already applies to entities; tiles
  remain exactly as Phase 3a left them (binary explored/unexplored from the
  server, no client-side dimming).
- Minimap — Phase 3d.
- Smooth/eased camera transitions between player positions — movement snaps
  instantly (one `_positionCamera` call per move), matching the existing
  discrete-grid-move server contract and Phase 3a's "no easing/physics needed"
  framing. Worth revisiting once a live user can judge whether instant snaps
  feel jarring at this camera angle — not a default-quality bar to guess at
  blind.
- Per-direction sprite animation/rotation — `THREE.Sprite`'s always-face-camera
  behavior is used as-is; no walk-cycle or facing-direction art swap (the
  original roadmap explicitly called this out as deferred: "Billboard always
  faces the camera, eliminating the need for per-direction sprite animation in
  this first pass").
- Notices (`setNotices`) rendering — stays a stored-only no-render stub, same
  as Phase 3a; notices are a 2D-canvas-text overlay concern in the existing
  renderer and don't have an obvious 3D-billboard treatment decided yet. Out of
  scope for this milestone; revisit in 3d's polish pass.
- Promoting this renderer to the default — unchanged from Phase 3a, still
  toggle-gated behind `?renderer=three`.

## Sprite construction details

```javascript
_getOrLoadTexture(path) {
    if (this._textureCache.has(path)) return this._textureCache.get(path);
    const texture = new THREE.Texture();
    const img = new Image();
    img.onload = () => {
        texture.image = img;
        texture.needsUpdate = true;
        this._renderFrame();
    };
    img.src = path;
    this._textureCache.set(path, texture);
    return texture;
}

_makeSprite(iconPath) {
    const material = new THREE.SpriteMaterial({
        map: this._getOrLoadTexture(iconPath),
        transparent: true,
    });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(0.8, 0.8, 1);
    return sprite;
}
```

Each sprite's `material.map` is set immediately (possibly still loading); the
texture's own `onload` triggers a re-render once decoded, so callers never
need to await anything — consistent with `dungeon-canvas.js`'s existing
fire-and-forget `loadImage(...).catch(...)` pattern.

`setEntities` diffs against the previously-rendered entity list by identity
(simplest correct approach for this milestone: remove all existing entity
sprites from the scene and rebuild from scratch on every call, rather than a
fine-grained add/move/remove diff) — entity lists are small (a handful of
monsters per floor), rebuilding every call is cheap, and this avoids a whole
class of stale-sprite bugs a diffing approach could introduce. `dungeon-canvas.js`
itself re-walks its full entity list and redraws every frame for the same
reason (canvas redraw is "clear and redraw everything" already) — this
milestone's "clear all entity sprites, re-add" is the direct 3D analog.

## Error handling

- An entity with no `icon` field uses the existing fallback path
  (`/static/iconography/goblin-scout-t1.svg`), matching `dungeon-canvas.js`'s
  own fallback — no new error path introduced.
- An SVG `Image` that fails to load (404, network error) leaves that sprite's
  texture blank (a fully transparent/default-black quad, depending on
  `SpriteMaterial`'s default) rather than throwing — acceptable for this
  milestone since the same failure mode already exists silently in the 2D
  renderer's `loadImage(...).catch(e => console.warn(...))` path; port the
  `console.warn` for parity, but no retry logic.
- `updatePlayerPosition` called before `loadMap` (grid not yet loaded): still
  safe — sprite creation and camera repositioning don't depend on `this.grid`
  being set, only on the scene/camera existing (already true from the
  constructor's `_initScene()` call).

## Testing

Same approach as Phase 3a: no JS test runner exists in this repo; verification
is visual via Playwright. Confirm, on `/adventure?renderer=three`:
- The player's billboard renders at the correct grid tile, oriented to always
  face the camera regardless of camera angle (trivially true given
  `THREE.Sprite`, but confirm no console errors from texture loading).
- Moving (via the existing movement controls) snaps the camera to follow the
  player to the new tile.
- Any monster/NPC entities present in the test dungeon render as billboards at
  their correct tiles, and disappear once farther than `OUTER_VIS_RADIUS` from
  the player (achievable by checking a fresh long-corridor dungeon or by
  temporarily lowering `OUTER_VIS_RADIUS` during a manual check).
- No console errors on load or on movement.
- `/adventure` (no query param) still shows the unaffected default 2D renderer.

Backend: zero changes — same read-only contract as Phase 3a. Run the existing
pytest suite once at the end as a regression check only.

## Affected files

- Modify: `app/static/js/dungeon-three.js` (the only file touched —
  `setEntities`, `updatePlayerPosition`, `centerOnPlayer`, plus new private
  helpers `_getOrLoadTexture`/`_makeSprite`/`_rebuildEntitySprites`).
- No template, other-JS, or backend changes.
