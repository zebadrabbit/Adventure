#!/usr/bin/env python3
"""
Quick script to check what's at a specific coordinate in a dungeon.

Usage:
    python scripts/check_tile.py <seed> <x> <y>
    python scripts/check_tile.py 156264 7 73
"""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dungeon.dungeon import Dungeon


def check_tile(seed: int, x: int, y: int, map_size: int = 75):
    """Check what's at the given coordinates for the specified seed."""
    print(f"Generating dungeon with seed {seed}...")
    dungeon = Dungeon(seed=seed, size=(map_size, map_size, 1))

    print(f"\nChecking coordinates ({x}, {y}):\n")

    # Check tile
    if 0 <= x < map_size and 0 <= y < map_size:
        tile_char = dungeon.grid[x][y]

        # Map tile characters to names
        tile_types = {
            "C": "CAVE",
            "R": "ROOM",
            "W": "WALL",
            "T": "TUNNEL",
            "D": "DOOR",
            "S": "SECRET_DOOR",
            "L": "LOCKED_DOOR",
        }

        tile_name = tile_types.get(tile_char, f"UNKNOWN ({tile_char})")
        print(f"  Tile Type: {tile_name}")
        print(f"  Tile Char: '{tile_char}'")

        # Check which room this belongs to (if any)
        for room in dungeon.rooms:
            if room["x"] <= x < room["x"] + room["w"] and room["y"] <= y < room["y"] + room["h"]:
                print(f"  Part of Room: {room}")
                break
    else:
        print(f"  Coordinates ({x}, {y}) out of bounds (map size: {map_size}x{map_size})")

    # Check for entities (monsters/treasure)
    entities_found = []
    if hasattr(dungeon, "entities"):
        for entity in dungeon.entities:
            if entity.get("x") == x and entity.get("y") == y:
                entities_found.append(entity)

    if entities_found:
        print("\n  Entities at this location:")
        for entity in entities_found:
            print(f"    - {entity.get('type', 'unknown')}: {json.dumps(entity, indent=6)}")
    else:
        print("\n  No entities at this location")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    try:
        seed = int(sys.argv[1])
        x = int(sys.argv[2])
        y = int(sys.argv[3])
        map_size = int(sys.argv[4]) if len(sys.argv) > 4 else 75

        check_tile(seed, x, y, map_size)
    except ValueError as e:
        print(f"Error: Arguments must be integers - {e}")
        print(__doc__)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
