#!/usr/bin/env python3
"""Debug script to investigate wall at coordinates (37,46) in seed 216665"""

from app.dungeon.config import DungeonConfig
from app.dungeon.dungeon import Dungeon
from app.dungeon.tiles import CAVE, DOOR, ROOM, TELEPORT, TUNNEL, WALL


def analyze_coordinate(dungeon, x, y):
    """Analyze what's at a specific coordinate and its neighbors"""
    w, h = dungeon.config.width, dungeon.config.height

    if not (0 <= x < w and 0 <= y < h):
        print(f"Coordinates ({x},{y}) out of bounds!")
        return

    tile = dungeon.grid[x][y]
    print(f"\n=== Analysis of coordinate ({x},{y}) ===")
    print(f"Tile type: '{tile}'")

    tile_names = {
        WALL: "WALL",
        ROOM: "ROOM",
        TUNNEL: "TUNNEL",
        DOOR: "DOOR",
        CAVE: "CAVE",
        TELEPORT: "TELEPORT",
        "S": "SECRET_DOOR",
        "L": "LOCKED_DOOR",
    }
    print(f"Tile name: {tile_names.get(tile, 'UNKNOWN')}")

    # Check neighbors
    print("\nNeighbors (N/S/E/W):")
    neighbors = [(x, y - 1, "North"), (x, y + 1, "South"), (x + 1, y, "East"), (x - 1, y, "West")]

    for nx, ny, direction in neighbors:
        if 0 <= nx < w and 0 <= ny < h:
            ntile = dungeon.grid[nx][ny]
            print(f"  {direction:5s} ({nx:2d},{ny:2d}): '{ntile}' - {tile_names.get(ntile, 'UNKNOWN')}")
        else:
            print(f"  {direction:5s} ({nx:2d},{ny:2d}): OUT OF BOUNDS")

    # Check if this wall is adjacent to any room
    room_adjacent = any(
        0 <= nx < w and 0 <= ny < h and dungeon.grid[nx][ny] == ROOM
        for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    )
    print(f"\nAdjacent to ROOM: {room_adjacent}")

    # Check which room (if any) this wall belongs to
    print("\nChecking room associations:")
    for idx, room in enumerate(dungeon.rooms):
        # Check if this coordinate is in the wall ring around a room
        # Wall ring is 1 tile outside room perimeter
        if room.x - 1 <= x <= room.x + room.w and room.y - 1 <= y <= room.y + room.h:
            # It's within the bounding box including walls
            if not (room.x <= x < room.x + room.w and room.y <= y < room.y + room.h):
                # Not in room interior, so it's in the wall ring
                print(f"  Room {idx}: Wall ring member")
                print(f"    Room bounds: x={room.x}..{room.x + room.w - 1}, y={room.y}..{room.y + room.h - 1}")
                print(f"    Room center: {room.center}")

    # Show 5x5 grid around this coordinate
    print(f"\n5x5 grid centered on ({x},{y}):")
    print("    ", end="")
    for dx in range(-2, 3):
        print(f"{x+dx:3d}", end=" ")
    print()

    for dy in range(-2, 3):
        ny = y + dy
        print(f"{ny:3d}:", end=" ")
        for dx in range(-2, 3):
            nx = x + dx
            if 0 <= nx < w and 0 <= ny < h:
                t = dungeon.grid[nx][ny]
                marker = f" {t} "
                if nx == x and ny == y:
                    marker = f"[{t}]"
                print(marker, end=" ")
            else:
                print(" ? ", end=" ")
        print()


def main():
    seed = 216665
    x, y = 37, 46

    print(f"Investigating seed {seed} at coordinates ({x},{y})")

    cfg = DungeonConfig(seed=seed, width=75, height=75)
    dungeon = Dungeon(cfg)

    print("\nDungeon metrics:")
    print(f"  Rooms: {dungeon.metrics.get('rooms', 0)}")
    print(f"  Tiles - WALL: {dungeon.metrics.get('tiles_wall', 0)}")
    print(f"  Tiles - ROOM: {dungeon.metrics.get('tiles_room', 0)}")
    print(f"  Tiles - TUNNEL: {dungeon.metrics.get('tiles_tunnel', 0)}")
    print(f"  Tiles - DOOR: {dungeon.metrics.get('tiles_door', 0)}")

    analyze_coordinate(dungeon, x, y)

    # Also check if this is on a boundary or edge
    if x == 0 or x == 74 or y == 0 or y == 74:
        print(f"\n⚠️  WARNING: Coordinate ({x},{y}) is on the map boundary!")

    # Check if any room placement logic would place a room here
    print("\n=== Checking room placement constraints ===")
    print("From rooms.py, rooms are placed with:")
    print(f"  x = randint(1, config.width - w - 2)  [1..{75-3-2}] for min size")
    print(f"  y = randint(1, config.height - h - 2) [1..{75-3-2}] for min size")
    print("This prevents rooms from touching the edges (0 or 74)")
    print("Wall rings extend 1 tile beyond room perimeter")

    if x <= 0 or y <= 0 or x >= 74 or y >= 74:
        print(f"\n⚠️  Coordinate ({x},{y}) is near boundary - may have special handling")


if __name__ == "__main__":
    main()
