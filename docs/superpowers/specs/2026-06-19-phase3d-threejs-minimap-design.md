# Phase 3d — Three.js Dungeon View: Minimap — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
fourth and final milestone of Phase 3 of 5.

**Process note:** Continuing under the established session pattern —
decisions below are self-documented with their reasoning, kept tight since
this is a small, well-scoped milestone closing out Phase 3.

## Context

Phases 3a/3b/3c (merged) brought `DungeonCanvasThree` to feature parity with
`dungeon-canvas.js` on tiles, entities, player movement, and fog-of-war
dimming. The one remaining gap, called out explicitly in the original
roadmap, is the minimap — and the roadmap already settled the architectural
question: *"Minimap: keep as a flat 2D canvas overlay (no reason to render it
in 3D) — cheapest path, already isolated logic in the current
`dungeon-canvas.js` minimap code, portable almost as-is."* This milestone
implements exactly that, closing out Phase 3.

Scope note: this milestone is the minimap only. The roadmap's Phase 3
heading mentions "minimap + polish" but doesn't specify concrete polish
items beyond what 3a/3b/3c already delivered — inventing additional polish
work here would be scope creep without a concrete requirement driving it.
Phase 3 is considered complete once this milestone merges.

## Current-state findings grounding this design

- `dungeon-canvas.js`'s `renderMinimap()` (`app/static/js/dungeon-canvas.js:828-876`)
  draws directly onto its own 2D canvas context (the *same* `<canvas
  id="dungeon-map">` element used for the main view) via `ctx.save()`/
  `ctx.fillRect()`/`ctx.arc()`/`ctx.restore()`, as a final overlay pass after
  the main scene renders. `DungeonCanvasThree`'s canvas is owned by
  `THREE.WebGLRenderer` — a single `<canvas>` element cannot serve both a
  `webgl` context and a `2d` context simultaneously, so the minimap can't be
  drawn onto the same element. It needs its **own** `<canvas>` element,
  absolutely positioned on top of the WebGL canvas.
- `app/templates/adventure.html:54-57`: the main canvas already sits inside
  `<div class="panel-body position-relative"><div class="position-relative">`,
  with `.map-controls` already using `position: absolute` to overlay the
  zoom buttons on top of the canvas. Adding a sibling absolutely-positioned
  `<canvas>` for the minimap follows this exact existing pattern.
- The minimap's drawing logic itself is pure 2D-canvas-API code with no
  Three.js dependency — it only reads `this.grid`, `this.width`, `this.height`,
  `this.seenTiles`, `this.playerPos` (all already present on
  `DungeonCanvasThree` from Phase 3a/3b) and a tile-color lookup. Porting it
  means: (1) a 2D-canvas-context version of `TILE_COLORS` (already defined
  in `dungeon-three.js` as hex *numbers* for Three.js materials — the minimap
  needs CSS color *strings*, e.g. `'#2d3340'`, not the same value type), and
  (2) swapping `this.ctx` (doesn't exist on `DungeonCanvasThree`) for a new
  2D context obtained from the new overlay canvas.
- The 2D renderer's minimap is drawn fresh every frame as part of its single
  `render()` call. `DungeonCanvasThree` has no per-frame render loop (it
  renders on-demand after each state change, Phase 3a's established
  pattern) — so the minimap render call needs to be added at the same call
  sites Phase 3c already added fog-overlay recomputation to: `loadMap` and
  `updatePlayerPosition`.

## Goals (Phase 3d only)

1. `app/templates/adventure.html` gains one new sibling `<canvas>` element
   inside the existing `position-relative` wrapper div, absolutely
   positioned in the same corner the 2D renderer's minimap occupies
   (top-right, matching `dungeon-canvas.js`'s `minimapX = rect.width -
   minimapSize - 10; minimapY = 10`): `<canvas id="dungeon-minimap-three"
   width="120" height="120" style="position: absolute; top: 10px; right:
   10px; z-index: 10; display: none; border-radius: 4px;"></canvas>`. Hidden
   (`display: none`) by default so it's invisible whenever the default 2D
   renderer is active (which draws its own minimap onto the main canvas and
   never touches this element).
2. `DungeonCanvasThree`'s constructor looks up this element by ID
   (`document.getElementById('dungeon-minimap-three')`); if found, sets
   `display = 'block'` (only the Three.js renderer ever makes it visible)
   and stores both the element and its `2d` context. If not found (e.g. a
   template that doesn't include it), minimap rendering silently no-ops —
   matching this renderer's existing "never throw on a missing optional
   surface" posture (e.g. Phase 3a's canvas-not-found check is the one
   *required* exception; this is an optional companion element).
3. A new `_renderMinimap()` method, a direct, mechanical port of
   `dungeon-canvas.js`'s `renderMinimap()` onto the new element/context,
   using the *fixed* 120×120 canvas size from the new element directly
   (rather than reading `getBoundingClientRect()` like the 2D version does,
   since this is a dedicated, fixed-size element, not an overlay computed
   relative to a shared canvas's current rendered size) — `minimapSize =
   120`, `minimapX = 0`, `minimapY = 0` (the element's own top-left, not an
   offset within a larger shared canvas).
4. A CSS-string tile-color lookup, `TILE_COLOR_STRINGS`, mapping the exact
   same 6 tile-type keys already in `TILE_COLORS` to their `'#rrggbb'`
   string form (e.g. `room: '#2d3340'`) — used only by `_renderMinimap()`;
   `TILE_COLORS` (the hex-number form) stays as-is for the existing
   Three.js material code, unchanged.
5. `_renderMinimap()` is called from `loadMap` and `updatePlayerPosition`,
   alongside the existing `_buildFogOverlay()` calls Phase 3c added.

## Non-goals

- Any 3D rendering of the minimap — explicitly ruled out by the roadmap.
- Minimap click-to-navigate or other interactivity — `dungeon-canvas.js`'s
  own minimap has none either; this is a straight port, not an enhancement.
- Resizing/responsive minimap sizing — fixed `120×120`, matching the 2D
  renderer's own hardcoded `minimapSize = 120`.
- Any other "polish" item — see the Context section's scope note.

## Error handling

- Missing `#dungeon-minimap-three` element in the DOM: `_renderMinimap()`
  no-ops (checked once in the constructor, cached as `this.minimapCtx =
  null`), never throws.
- `_renderMinimap()` called before `loadMap` (`this.grid` is `null`):
  no-op guard, mirroring `_buildFogOverlay()`'s existing pattern.
- `_renderMinimap()` called before `this.playerPos` exists: matches
  `dungeon-canvas.js`'s own guard (`if (!this.grid || !this.playerPos)
  return;`) — the minimap draws nothing until the player has moved at least
  once, identical to the 2D renderer's existing behavior, not a new
  divergence.

## Testing

Same as Phases 3a/3b/3c: no JS test runner exists; verification is visual
via Playwright. Confirm, on `/adventure?renderer=three`:
- Before any move: the minimap canvas is visible (`display: block`) but
  empty/blank (matches `dungeon-canvas.js`'s own no-playerPos guard).
- After a move: the minimap shows a small colored representation of explored
  tiles and a gold dot for the player's position, in the top-right corner.
- `/adventure` (no query param): the minimap overlay element exists in the
  DOM but stays hidden (`display: none`), and the default 2D renderer's own
  minimap (drawn onto the main canvas) is unaffected.
- No console errors on load or after a move.

Backend: zero changes. Run the existing pytest suite once at the end as a
regression check only.

## Affected files

- Modify: `app/templates/adventure.html` (one new `<canvas>` element).
- Modify: `app/static/js/dungeon-three.js` (constructor lookup,
  `TILE_COLOR_STRINGS` constant, `_renderMinimap()`, two new call sites).
- No other-JS or backend changes.
