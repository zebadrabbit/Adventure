# Phase 3c — Three.js Dungeon View: Client-Side Fog-of-War Opacity Dimming — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
third milestone of Phase 3 of 5.

**Process note:** Continuing under the established session pattern — decisions
below that would normally be a brainstorming question-and-answer are
self-documented with their reasoning, kept tight since this is a small,
well-scoped milestone continuing directly from Phase 3b's parity work.

## Context

Phase 3b (merged) added player/entity billboards and camera-follow movement.
`DungeonCanvasThree` still has no fog-of-war *dimming* — Phase 3a's binary
explored/unexplored cutoff (server-side `"unknown"` tiles render nothing) is
the only fog mechanism so far. The 2D renderer additionally applies a
client-side Euclidean-distance opacity gradient on top of that: fully lit
near the player, a dimming gradient out to `OUTER_VIS_RADIUS`, and a flatter
"memory" dim for previously-seen-but-now-out-of-range tiles. This milestone
ports that gradient to the 3D scene, closing the last visual-fidelity gap
before the minimap (3d).

## Current-state findings grounding this design

- `dungeon-canvas.js`'s exact fog logic (`app/static/js/dungeon-canvas.js:672-694`):
  for each visible (non-`"unknown"`) tile, computed `dist` from the player:
  - `dist <= INNER_VIS_RADIUS` (8): no fog.
  - `INNER_VIS_RADIUS < dist <= OUTER_VIS_RADIUS` (26): a linear alpha
    gradient between `MIN_FOG_ALPHA` (0.18) and `MAX_FOG_ALPHA` (0.92), plus a
    small sine/cosine positional noise term (`FOG_NOISE_AMPLITUDE`, 0.08) for
    a dithered, less-uniform look on a flat-filled 2D canvas.
  - `dist > OUTER_VIS_RADIUS` and previously seen: a flat `MEMORY_DIM_ALPHA`
    (0.35) dim.
  - `dist > OUTER_VIS_RADIUS` and never seen: doesn't apply (server already
    sends `"unknown"` for those, skipped before fog logic runs at all).
  This is recomputed **every 2D frame** (`render()`'s tile loop), since the
  2D canvas is fully redrawn each time regardless.
- `DungeonCanvasThree` (Phase 3a/3b), by contrast, only rebuilds its tile
  geometry once per `loadMap` call — `updatePlayerPosition` (Phase 3b) moves
  the player sprite and camera but never touches tile meshes. Fog dimming
  depends on the player's *current* position, so it must be recomputed on
  every move, not just on map load — this milestone adds that recomputation.
- `MeshBasicMaterial` has one `opacity` value for the *whole* mesh, not
  per-instance — Phase 3a/3b's per-tile-type `InstancedMesh` approach (one
  mesh per tile type, e.g. all `room` tiles share one mesh) can't vary opacity
  per individual tile through that material alone. True per-instance alpha
  would need a custom shader with an `InstancedBufferAttribute`, which is a
  meaningfully bigger lift than this milestone's scope warrants.
- The simpler, scope-appropriate approach (and the one this design uses):
  keep tile color/geometry meshes exactly as Phase 3a/3b built them
  (untouched), and add a **separate overlay layer** of plain black,
  semi-transparent quads — one `InstancedMesh` per discrete opacity *bucket*
  (not per tile), positioned just above each tile that needs dimming. This
  reuses the exact "group cells, one InstancedMesh per group, plain material"
  pattern Phase 3a already established and proved correct, just keyed on
  opacity bucket instead of tile type. A handful of buckets approximates the
  2D renderer's continuous gradient closely enough to read as a smooth fade
  at this tile density, without needing custom shaders.

## Goals (Phase 3c only)

1. A new `_buildFogOverlay()` method: for every rendered tile (anything in
   `this.tileMeshes`' source data — i.e. `FLOOR_TYPES`/`WALL_TYPES`, matching
   Phase 3a's existing skip-list for `cave`/`unknown`), compute `dist` from
   `this.playerPos` and bucket it into one of 5 discrete alpha levels using
   the **exact same thresholds and constants** as `dungeon-canvas.js`
   (`INNER_VIS_RADIUS=8`, `OUTER_VIS_RADIUS=26`, `MIN_FOG_ALPHA=0.18`,
   `MAX_FOG_ALPHA=0.92`, `MEMORY_DIM_ALPHA=0.35`) — see "Bucketing" below for
   the exact bucket boundaries. Tiles within `INNER_VIS_RADIUS` get no
   overlay (skip — fully lit, matching 2D).
2. One semi-transparent black `InstancedMesh` per non-empty bucket
   (`MeshBasicMaterial({color: 0x000000, transparent: true, opacity:
   bucketAlpha})`), each instance positioned just above that tile's visible
   top surface: `y = 0.02` for floor-category tiles, `y = 1.02` for
   wall-category tiles (walls are `1` unit tall, floors are at `y=0`).
3. `_buildFogOverlay()` is called from `loadMap` (after `_buildTileGrid`) and
   from `updatePlayerPosition` (after the player sprite/camera update) — the
   two places the player's position or the visible tile set can change.
4. Tiles with no fog this frame (within `INNER_VIS_RADIUS`, or `"unknown"`
   and thus never built into `tileMeshes` at all) get no overlay instance —
   consistent with "no fog = nothing drawn there," not a zero-opacity
   instance, to avoid wasted draw calls.
5. `seenTiles` (already populated in `loadMap`, Phase 3a) is consulted for
   the memory-dim bucket exactly as `dungeon-canvas.js` does: beyond
   `OUTER_VIS_RADIUS`, dim if the tile is in `seenTiles`, otherwise (already
   true today, unchanged) the tile was never built at all since it's
   `"unknown"` server-side.

## Bucketing

`dungeon-canvas.js`'s gradient zone (`INNER_VIS_RADIUS < dist <=
OUTER_VIS_RADIUS`) is a continuous linear interpolation over 18 distance
steps (`FOG_GRADIENT_STEPS = 26 - 8`). This milestone approximates it with
**4 discrete buckets**, evenly splitting that same distance range, each using
the linear-interpolation midpoint of its slice (matching `dungeon-canvas.js`'s
own formula, `MIN_FOG_ALPHA + fogProgress * (MAX_FOG_ALPHA - MIN_FOG_ALPHA)`,
evaluated at each slice's midpoint `fogProgress`), plus a 5th fixed bucket for
the memory-dim case:

| Bucket | Distance range | Alpha |
|---|---|---|
| (no overlay) | `dist <= 8` | — fully lit, skip |
| Gradient 1 | `8 < dist <= 12.5` | `0.18 + 0.125*(0.92-0.18) ≈ 0.272` |
| Gradient 2 | `12.5 < dist <= 17` | `0.18 + 0.375*(0.92-0.18) ≈ 0.458` |
| Gradient 3 | `17 < dist <= 21.5` | `0.18 + 0.625*(0.92-0.18) ≈ 0.643` |
| Gradient 4 | `21.5 < dist <= 26` | `0.18 + 0.875*(0.92-0.18) ≈ 0.828` |
| Memory | `dist > 26`, in `seenTiles` | `0.35` (flat `MEMORY_DIM_ALPHA`) |

4 buckets (rather than, say, 18 matching the 2D renderer's per-distance-step
granularity) is the chosen tradeoff: at the 3/4 camera angle and this tile
density, banding between 4 discrete dimming levels is far less perceptible
than it would be on a flat top-down 2D canvas (the original reason
`dungeon-canvas.js` adds noise-dithering to mask its own bands) — so the noise
term is dropped entirely for this milestone rather than ported (see
Non-goals). If banding *is* visible once a live user can judge it, increasing
the bucket count is a cheap follow-up — it doesn't change the architecture,
just the lookup table.

## Non-goals (deferred to later Phase 3 milestones / follow-ups)

- The 2D renderer's sine/cosine positional noise dithering — a flat-canvas
  visual trick to mask banding; not obviously needed (or even visually
  equivalent) on textured 3D geometry at a 3/4 angle. Skip for this
  milestone; revisit only if live visual feedback says the 4-bucket banding
  reads as banding rather than a gradient.
- Per-instance true-continuous alpha via a custom shader/`InstancedBufferAttribute`
  — the architecturally "correct" long-term approach, but a meaningfully
  bigger lift (custom `ShaderMaterial`, attribute buffer management) than
  this milestone's "close the visual-parity gap" goal needs. Worth
  reconsidering only if/when this renderer is promoted to default and bucket
  banding becomes a real complaint.
- Side-face dimming on wall geometry — the overlay quad sits on the wall's
  *top* face only (`y=1.02`); the box's four side faces (the ones the 3/4
  camera actually sees most of) are not separately dimmed. This is a known,
  accepted simplification: a true side-face treatment needs the overlay to be
  a thin box shell around each wall instance, not a flat quad, for marginal
  visual gain at real implementation cost. Document and defer; not pursued
  this milestone.
- Minimap — Phase 3d, unchanged.
- Promoting this renderer to default — unchanged, still `?renderer=three`-gated.

## Error handling

- `_buildFogOverlay()` called before `loadMap` (no `this.grid` yet): no-op
  guard, same pattern as `updatePlayerPosition`'s existing safety (Phase 3b
  already calls this safely before any map is loaded in principle, though in
  practice `adventure.js` always calls `loadMap` first).
- `_buildFogOverlay()` called before `this.playerPos` exists (no
  `updatePlayerPosition` call yet, e.g. right after `loadMap`): treat every
  tile as at infinite distance from the player (matching
  `dungeon-canvas.js`'s own `dist = this.playerPos ? ... : Infinity`), so
  every non-memory, non-`"unknown"` tile would route to... — to keep this
  simple and match Phase 3a's existing pre-player-position visual (the
  static grid renders with no fog at all before any move), `_buildFogOverlay`
  early-returns (no overlay instances) when `this.playerPos` is `null`,
  same condition Phase 3b already uses to guard `setEntities`'s vision
  cutoff. This intentionally differs from `dungeon-canvas.js`'s
  fog-everything-as-infinite-distance behavior, because Phase 3a's static
  scene (no player marker yet) already established "no player position yet
  = show the full static grid, undimmed" as this renderer's pre-move visual,
  and changing that now would be an unrelated regression to Phase 3a's
  already-reviewed behavior.

## Testing

Same as Phases 3a/3b: no JS test runner exists; verification is visual via
Playwright. Confirm, on `/adventure?renderer=three`:
- On initial load (before any move), tiles render exactly as Phase 3a/3b
  left them — undimmed (per the error-handling note above).
- After a move, tiles near the player render undimmed, tiles in the mid
  ring show visibly darker overlays the farther they are (the 4-bucket
  gradient), and any previously-seen-but-now-distant tiles show the flatter
  memory dim.
- No console errors on load or after a move.
- `/adventure` (no query param) still shows the unaffected default 2D renderer.

Backend: zero changes — same read-only contract as Phases 3a/3b. Run the
existing pytest suite once at the end as a regression check only.

## Affected files

- Modify: `app/static/js/dungeon-three.js` (the only file touched — new
  constants, `_buildFogOverlay()`, and two call sites in `loadMap` and
  `updatePlayerPosition`).
- No template, other-JS, or backend changes.
