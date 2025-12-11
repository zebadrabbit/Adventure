"""Line-of-sight and fog-of-war visibility calculation.

Implements proper vision rules:
- No X-ray vision through walls
- Entering a room reveals the entire room
- Opening a door reveals the tunnel beyond
- Line-of-sight limited to reasonable distance
"""

from __future__ import annotations

from typing import Set, Tuple


def calculate_visible_tiles(
    grid: list[list[str]], player_x: int, player_y: int, vision_range: int = 12
) -> Set[Tuple[int, int]]:
    """Calculate all tiles visible from the player's current position.

    Rules:
    - Player's current tile is always visible
    - If player is in a room, reveal entire room
    - Cast rays in all directions to find visible corridors/doors
    - Walls and caves block line of sight
    - Doors are visible but block vision beyond (until opened)

    Args:
        grid: 2D grid of tile characters (grid[x][y])
        player_x: Player's X coordinate
        player_y: Player's Y coordinate
        vision_range: Maximum vision distance

    Returns:
        Set of (x, y) coordinates that are visible
    """
    if not grid or not grid[0]:
        return set()

    width = len(grid)
    height = len(grid[0])
    visible = set()

    # Validate player position
    if not (0 <= player_x < width and 0 <= player_y < height):
        return visible

    current_tile = grid[player_x][player_y]
    visible.add((player_x, player_y))

    # If player is in a room, reveal the entire room
    if current_tile == "R":  # ROOM
        _reveal_room(grid, player_x, player_y, visible, width, height)
        # Also reveal doors leading out of the room
        _reveal_adjacent_doors(grid, visible, width, height)

    # Cast rays in multiple directions for corridor visibility
    _cast_vision_rays(grid, player_x, player_y, visible, width, height, vision_range)

    return visible


def _reveal_room(
    grid: list[list[str]], start_x: int, start_y: int, visible: Set[Tuple[int, int]], width: int, height: int
):
    """Flood-fill to reveal all tiles in the current room."""
    from collections import deque

    queue = deque([(start_x, start_y)])
    checked = {(start_x, start_y)}

    while queue:
        x, y = queue.popleft()
        visible.add((x, y))

        # Check all 4 orthogonal neighbors
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy

            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in checked:
                continue

            checked.add((nx, ny))
            tile = grid[nx][ny]

            # Continue flood fill for room tiles and walls (room boundary)
            if tile == "R":  # ROOM
                queue.append((nx, ny))
            elif tile == "W":  # WALL
                visible.add((nx, ny))  # Make walls visible but don't expand beyond


def _reveal_adjacent_doors(grid: list[list[str]], visible: Set[Tuple[int, int]], width: int, height: int):
    """Reveal doors adjacent to any visible room tiles."""
    doors_to_add = set()

    for x, y in visible:
        if grid[x][y] in ("R", "W"):  # ROOM, WALL
            # Check neighbors for doors
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    tile = grid[nx][ny]
                    if tile in ("D", "L"):  # DOOR, LOCKED_DOOR
                        doors_to_add.add((nx, ny))
                        # Also reveal 1-2 tiles beyond the door in corridors
                        _reveal_beyond_door(grid, nx, ny, x, y, doors_to_add, width, height)

    visible.update(doors_to_add)


def _reveal_beyond_door(
    grid: list[list[str]],
    door_x: int,
    door_y: int,
    from_x: int,
    from_y: int,
    visible: Set[Tuple[int, int]],
    width: int,
    height: int,
):
    """Reveal a few tiles beyond a door in the direction away from the room."""
    # Determine direction through door
    dx = door_x - from_x
    dy = door_y - from_y

    # Look 1-2 tiles beyond the door
    for step in range(1, 3):
        nx = door_x + dx * step
        ny = door_y + dy * step

        if not (0 <= nx < width and 0 <= ny < height):
            break

        tile = grid[nx][ny]
        if tile in ("T", "D", "L"):  # TUNNEL, DOOR, LOCKED_DOOR
            visible.add((nx, ny))
        else:
            break  # Stop at walls or other obstacles


def _cast_vision_rays(
    grid: list[list[str]],
    player_x: int,
    player_y: int,
    visible: Set[Tuple[int, int]],
    width: int,
    height: int,
    vision_range: int,
):
    """Cast rays in all directions to find visible corridors and features.

    Uses Bresenham-like line algorithm to trace visibility.
    """
    current_tile = grid[player_x][player_y]

    # If in a tunnel or at a door, cast rays to see down corridors
    if current_tile in ("T", "D", "L"):  # TUNNEL, DOOR, LOCKED_DOOR
        # Cast rays in 8 primary directions plus some intermediate angles
        angles = 32  # Number of rays to cast

        for i in range(angles):
            angle_ratio = i / angles
            # Convert to radians
            import math

            angle = angle_ratio * 2 * math.pi

            dx = math.cos(angle)
            dy = math.sin(angle)

            _cast_ray(grid, player_x, player_y, dx, dy, visible, width, height, vision_range)


def _cast_ray(
    grid: list[list[str]],
    start_x: int,
    start_y: int,
    dx: float,
    dy: float,
    visible: Set[Tuple[int, int]],
    width: int,
    height: int,
    max_distance: int,
):
    """Cast a single ray to determine visibility along a line.

    Stops at walls, caves, or secret doors (which block vision).
    """
    x, y = float(start_x), float(start_y)

    for _ in range(max_distance):
        x += dx
        y += dy

        # Convert to grid coordinates
        grid_x = int(round(x))
        grid_y = int(round(y))

        if not (0 <= grid_x < width and 0 <= grid_y < height):
            break

        tile = grid[grid_x][grid_y]

        # Always make the tile visible before checking if it blocks
        visible.add((grid_x, grid_y))

        # Check if this tile blocks further vision
        if tile in ("W", "C", "S"):  # WALL, CAVE, SECRET_DOOR
            # Walls and caves block vision completely
            break
        elif tile == "D" or tile == "L":  # DOOR, LOCKED_DOOR
            # Doors are visible but block vision beyond
            break
        # Tunnels and rooms allow vision to continue
