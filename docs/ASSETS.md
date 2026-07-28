# Art assets and their licences

Read this before committing any art.

## The rule

**Third-party art does not go in this repo.** The repo is public, so every file
in it is redistributed to anyone who clones it. Most paid (and plenty of free)
asset packs permit *use* in games while forbidding *re-distribution* of the
assets themselves — a distinction that a public repository quietly violates.

Art that cannot be committed lives in a gitignored directory, is installed by a
script from a copy the developer owns, and always has a fallback so the game
still runs without it.

## Dungeon tileset — not committed

| | |
|---|---|
| Pack | Dungeon Gathering — Under The Castle Set (v1.6.2 full) |
| Author | Jose Javier ("SnowHex") — <https://snowhex.itch.io/dungeon-gathering> |
| Used | `Set 1.1.png` — 304×160, a 19×10 grid of 16×16 cells |
| Installed to | `app/static/tiles/dungeon-set.png` (**gitignored**) |
| Install with | `scripts/import_tiles.sh` |

### Why it is not in the repo

The pack's bundled `License.txt` states:

> 2) You are not allowed to:
> a) Re-distribute or re-sell any of the assets included in this pack, or any
> altered versions of them, as games assets, images or NFTs.

Note that the itch.io store page is *less* strict than the bundled file — the
page mentions only reselling. The bundled licence governs, and it also forbids
re-distribution. Three consequences that are easy to get wrong:

- **Being free and non-commercial does not help.** The prohibited act is
  distribution, not profit. A public repo distributes.
- **"Only the tiles we use" does not help.** The clause covers *any* of the
  assets.
- **Editing them does not help.** It explicitly covers altered versions.

Use in the game is fully permitted — the licence allows commercial and
non-commercial projects, and editing. Only redistribution is out.

Credit is "not necessary, but VERY appreciated", so we credit SnowHex.

### How the fallback works

`app/static/js/dungeon-canvas.js` loads `TILE_SHEET_SRC` on startup. If the
image loads, `drawSpriteTile()` renders every cell from it. If it 404s —
the normal case for a fresh clone — `paintTile()` falls back to the procedural
flagstone/bevel/plank rendering that predates the tileset. Nothing else in the
renderer (fog of war, the animated portal, entities, minimap) is affected.

Tile choices live in one table, `TILE_SPRITES`, keyed by the tile-type names the
server sends (`room`, `tunnel`, `wall`, `secret_door`, `door`, `locked_door`,
`stairs_up`, `stairs_down`, `teleporter`) and expressed as `[col, row]` into the
sheet. `base` is drawn first, optional `overlay` on top for tiles with
transparency such as stairs. Re-picking a tile is a one-line edit.

`secret_door` deliberately shares the `wall` sprite: a secret door the player has
not found must be indistinguishable from stone.

## Adding new art

1. Read the pack's licence file, not just its store page. They differ.
2. Redistribution permitted (CC0 and similar)? Commit it, and record it here.
3. Redistribution forbidden? Gitignore it, add an installer to
   `scripts/import_tiles.sh`, and make sure there is a fallback path.
4. Either way, record the author, the pack, the exact files used, and the terms
   in this file.
