#!/usr/bin/env bash
# Install the dungeon tileset from a pack you own.
#
# The art is third-party and its licence forbids re-distributing the assets
# (see docs/ASSETS.md), so it is gitignored and cannot ship with this repo.
# Without it the map renderer falls back to procedural tiles and the game runs
# exactly as before -- this script is purely a visual upgrade for anyone who
# owns the pack.
#
# Usage:
#   scripts/import_tiles.sh [path/to/Set\ 1.1.png]
#
# Default source is the local, gitignored .Downloaded_Assets copy.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:-.Downloaded_Assets/DungeonGathering/Set 1.1.png}"
DEST="app/static/tiles/dungeon-set.png"

if [[ ! -f "$SRC" ]]; then
    echo "Tileset not found: $SRC" >&2
    echo >&2
    echo "Buy or download 'Dungeon Gathering - Under The Castle Set' by SnowHex:" >&2
    echo "  https://snowhex.itch.io/dungeon-gathering" >&2
    echo "then re-run with the path to its 'Set 1.1.png'." >&2
    exit 1
fi

# The renderer indexes this sheet by [col, row] at 16px (TILE_SPRITES in
# app/static/js/dungeon-canvas.js), so a differently-sized sheet would silently
# draw the wrong tiles. Fail loudly instead.
if command -v identify >/dev/null 2>&1; then
    dims="$(identify -format '%wx%h' "$SRC")"
    if [[ "$dims" != "304x160" ]]; then
        echo "Unexpected sheet size ${dims}; expected 304x160 (19x10 cells of 16px)." >&2
        echo "If the pack was updated, re-check the [col,row] values in TILE_SPRITES." >&2
        exit 1
    fi
fi

mkdir -p "$(dirname "$DEST")"
cp "$SRC" "$DEST"
echo "Installed $DEST"
echo "Reload the adventure page; tiles are picked up automatically."
