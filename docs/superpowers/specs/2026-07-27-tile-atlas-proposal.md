# Tile atlas — proposal

Written while the author was playtesting; **the open questions at the bottom
need answers before any of this gets built.**

## Why this is worth doing now

Two things changed on 2026-07-27:

1. The renderer draws from a spritesheet (`TILE_SPRITES` in
   `app/static/js/dungeon-canvas.js`), so tile art is now a data question rather
   than a code question.
2. The author has Aseprite, so art can be *authored* rather than only licensed.

That second point is the strategic one. The Dungeon Gathering pack cannot be
committed to a public repo (see `docs/ASSETS.md`), which means today the game
looks good only on machines that own the pack. **Art authored in-house has no
such restriction** — a project-owned atlas can ship in the repo, so every clone
looks the way the game is meant to look. The licensed pack stays useful as
reference and as the local-only "nice version" while the owned atlas fills in.

## Current state

| | |
|---|---|
| Cell size | 16×16 source, drawn at 32px (`TILE_SIZE`), `imageSmoothingEnabled = false` |
| Sheet | `app/static/tiles/dungeon-set.png`, gitignored, 19×10 cells |
| Mapping | `TILE_SPRITES`, keyed by server tile-type name, `[col, row]`, optional `overlay` |
| Fallback | `paintTile()` procedural rendering when the sheet is absent |
| Entities | separate SVGs in `app/static/iconography/` (30 files), drawn per-entity |

Tile types the server can send: `room`, `tunnel`, `wall`, `secret_door`, `door`,
`locked_door`, `stairs_up`, `stairs_down`, `teleporter`, `cave`.

## Proposed atlas layout

One PNG, 16×16 cells, organised in **rows by purpose** so a row can be extended
without renumbering anything already mapped. Column 0 of each row is the
canonical/default variant; further columns are alternates the renderer may pick
deterministically from tile coordinates.

| Row | Purpose | Notes |
|-----|---------|-------|
| 0 | Floor — room | variants for visual noise; picked by `(x+y)` hash so it is stable per tile |
| 1 | Floor — corridor | visibly distinct from room floor; that distinction is what fixed the "can't tell floors from walls" complaint |
| 2 | Wall — face | the side a player looks at from the south |
| 3 | Wall — top | what a wall reads as when it is not adjacent to walkable floor |
| 4 | Doors | door, locked/portcullis, secret (must be pixel-identical to wall face) |
| 5 | Stairs & portal | transparent overlays, drawn on a floor base |
| 6 | Props — static | rubble, barrels, bones, debris; overlays on floor |
| 7 | Props — interactive | chest closed/open, lever, shrine, brazier |
| 8+ | Reserved | keep growing downward, never renumber |

### Conventions worth fixing early

- **Transparent backgrounds for anything that is an overlay** (stairs, props),
  so the renderer composites floor + overlay rather than needing a baked variant
  per floor type.
- **Secret doors must be byte-identical to the wall face.** An undiscovered
  secret door that differs by a single pixel is a solved puzzle.
- **No cell reuse across rows.** Duplicating a tile is cheaper than a mapping
  that means two things.
- **Palette discipline** — pick a fixed palette in Aseprite and stay in it, or
  new tiles will drift in hue from old ones. Aseprite's palette-lock helps here.

### Rendering upgrades the atlas unlocks

1. **Wall face vs top** (~15 lines): a wall cell with walkable floor to its
   south draws the face, everything else draws the top. This is the single
   biggest visual win and the reason rows 2 and 3 are separate.
2. **Deterministic floor variants** (~5 lines): hash `(x, y)` to pick a column
   so floors stop tiling visibly, without per-tile storage.
3. **Props layer**: the map already knows where treasure, shrines and traps are;
   they currently render as SVG icons. Moving them into the atlas makes them
   part of the scene rather than symbols on top of it.

## Open questions

1. **Scope** — atlas for terrain only, or terrain + props + entities? Entities
   are SVGs today and that works; mixing may not be worth it.
2. **Original vs derived.** Tiles *traced from* or *edited from* Dungeon
   Gathering remain covered by its licence and still cannot be committed. Is the
   goal (a) original art that ships, or (b) local-only edits of the licensed
   pack that look better for you alone? These lead to different workflows.
3. **Do we keep two sheets** — the licensed one (local, richer) and the owned
   one (committed, simpler) — with the renderer preferring whichever is present?
   Cheap to support: `TILE_SHEET_SRC` becomes a list.
4. **Aseprite export** — a single `.aseprite` with the atlas as one layer/frame
   grid, exported to PNG by a script? Worth wiring `scripts/import_tiles.sh` to
   run the export if the `.aseprite` is newer than the PNG.
5. **Cell size** — stay at 16×16, or author at 32×32 to match render size? 16
   keeps it consistent with the reference pack and scales cleanly; 32 allows
   more detail per tile but doubles the drawing work.
