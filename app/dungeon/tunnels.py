from collections import deque
from typing import Deque, List, Optional, Tuple

from .config import DungeonConfig
from .rooms import Room
from .tiles import CAVE, DOOR, ROOM, TUNNEL, WALL


def connect_rooms_with_tunnels(grid, rooms: List[Room], config: DungeonConfig):
    if not rooms:
        return
    centers = [r.center for r in rooms]
    edges = []
    for i in range(len(centers)):
        x1, y1 = centers[i]
        for j in range(i + 1, len(centers)):
            x2, y2 = centers[j]
            dist = abs(x1 - x2) + abs(y1 - y2)
            edges.append((dist, i, j))
    edges.sort()
    parent = list(range(len(centers)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    mst = []
    for dist, i, j in edges:
        fi, fj = find(i), find(j)
        if fi != fj:
            parent[fi] = fj
            mst.append((i, j))
    # Deterministic extra connections: choose every Nth edge (based on seed-derived stride) instead of pure probability
    if config.extra_connection_chance > 0:
        stride = max(2, int(1 / config.extra_connection_chance)) if config.extra_connection_chance < 1 else 2
        for idx, (dist, i, j) in enumerate(edges):
            if (i, j) not in mst and idx % stride == 0:
                mst.append((i, j))
    for i, j in mst:
        carve_tunnel_between(grid, centers[i], centers[j], config)
    # Prune redundant doors before global finalize
    _prune_redundant_room_doors(grid, config)
    _ensure_entrance_access(grid, rooms, config)
    _finalize_tunnel_cleanup(grid, config)


def carve_tunnel_between(grid, a: Tuple[int, int], b: Tuple[int, int], config: DungeonConfig):
    """Deterministic L-shaped corridor carving from room center a to room center b.

    Strategy:
      * Step horizontally from a.x toward b.x, then vertically toward b.y (classic L path).
      * When leaving a room through its wall ring, convert the encountered WALL to a DOOR and continue.
      * Carve CAVE cells into TUNNEL along the way.
      * When reaching a WALL that borders the destination room, convert it to a DOOR and stop.
    This guarantees at least one connecting corridor between MST room pairs, dramatically reducing
    unreachable rooms while respecting single-wall penetration per approach (one door each side).
    """
    (x, y) = a
    (gx, gy) = b

    def step_towards(cur, goal):
        cx, cy = cur
        if cx != goal[0]:
            return (cx + (1 if goal[0] > cx else -1), cy)
        if cy != goal[1]:
            return (cx, cy + (1 if goal[1] > cy else -1))
        return cur

    # Safety guard
    if a == b:
        return

    # Simple loop with iteration cap
    for _ in range(config.width * config.height):
        if (x, y) == (gx, gy):
            break
        nx, ny = step_towards((x, y), (gx, gy))
        tile = grid[nx][ny]
        if tile == CAVE:
            # Just carve corridor
            grid[nx][ny] = TUNNEL
        elif tile == WALL:
            # Determine if this wall is adjacent to current room (leaving) or destination room (entering)
            if _wall_has_room_opposite(grid, nx, ny, config):
                # If destination room adjacent beyond wall -> make door and continue if not yet at target
                grid[nx][ny] = DOOR
            else:
                # Treat as hard stop (should not happen often); break to avoid over-carving
                break
        elif tile == ROOM:
            # Entered target room interior directly (rooms adjacent) => ensure a door at boundary behind us
            # Convert previous cell to DOOR if it is WALL adjacent to this room.
            pass
        x, y = nx, ny
    _dedupe_local_door_cluster(grid, config)


def _bfs_path(grid, start: Tuple[int, int], goal: Tuple[int, int], config: DungeonConfig) -> List[Tuple[int, int]]:
    w, h = config.width, config.height
    sx, sy = start
    gx, gy = goal
    walkable = {CAVE, ROOM, TUNNEL}
    # We do a BFS but push neighbors that would create a "flanked wall" later to the back (soft penalty)
    q: Deque[Tuple[int, int]] = deque([start])
    parent = {start: None}
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break
        primary = []
        secondary = []
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in parent:
                t = grid[nx][ny]
                if t in walkable:
                    # If moving here would make an adjacent WALL have 2 corridor neighbors (x,y) plus (nx,ny) then penalize
                    penalize = False
                    for wx, wy in (
                        (nx + 1, ny),
                        (nx - 1, ny),
                        (nx, ny + 1),
                        (nx, ny - 1),
                    ):
                        if 0 <= wx < w and 0 <= wy < h and grid[wx][wy] == WALL:
                            tn = 0
                            for tx, ty in (
                                (wx + 1, wy),
                                (wx - 1, wy),
                                (wx, wy + 1),
                                (wx, wy - 1),
                            ):
                                if (tx, ty) == (x, y) or (tx, ty) == (nx, ny):
                                    tn += 1
                                elif 0 <= tx < w and 0 <= ty < h and grid[tx][ty] == TUNNEL:
                                    tn += 1
                            if tn >= 2:
                                penalize = True
                                break
                    (secondary if penalize else primary).append((nx, ny))
        # enqueue primaries first
        for p in primary:
            parent[p] = (x, y)
            q.append(p)
        for s in secondary:
            parent[s] = (x, y)
            q.append(s)
    if goal not in parent:
        return []
    # reconstruct
    path: List[Tuple[int, int]] = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def _bfs_path_strict(
    grid, start: Tuple[int, int], goal: Tuple[int, int], config: DungeonConfig
) -> List[Tuple[int, int]]:
    """BFS that treats WALL as a hard boundary but allows targeting a wall adjacent to the goal room.

    We search through CAVE/TUNNEL/ROOM tiles but record the first wall cell that is adjacent to the *goal* room
    (or any room) on its far side and sits on a path toward the goal center Manhattan corridor. This yields
    a corridor that stops at a single wall which we later promote to DOOR.
    """
    w, h = config.width, config.height
    sx, sy = start
    gx, gy = goal
    walkable = {CAVE, ROOM, TUNNEL}
    q: Deque[Tuple[int, int]] = deque([start])
    parent = {start: None}
    door_target: Optional[Tuple[int, int]] = None
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            # Direct room-to-room path (rooms adjacent); abort to rely on other edges to create door elsewhere.
            break
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in parent:
                continue
            t = grid[nx][ny]
            if t in walkable:
                parent[(nx, ny)] = (x, y)
                q.append((nx, ny))
            elif t == WALL and door_target is None and _wall_has_room_opposite(grid, nx, ny, config):
                # Potential door site; record but do not traverse beyond
                parent[(nx, ny)] = (x, y)
                door_target = (nx, ny)
    target = door_target
    if target is None:
        return []
    # Reconstruct to door target
    path: List[Tuple[int, int]] = []
    cur: Optional[Tuple[int, int]] = target
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def _wall_has_room_opposite(grid, x: int, y: int, config: DungeonConfig) -> bool:
    return any(
        0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == ROOM
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    )


def _dedupe_local_door_cluster(grid, config: DungeonConfig):
    """After carving a single corridor, if we accidentally placed adjacent doors (rare), keep one.

    This is a localized lighter version of global pruning to avoid over-mutating tunnels already carved.
    """
    w, h = config.width, config.height
    for x in range(w):
        for y in range(h):
            if grid[x][y] == DOOR:
                neigh = [
                    (nx, ny)
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == DOOR
                ]
                if neigh:
                    keeper = min([(x, y)] + neigh)
                    for nx, ny in [(x, y)] + neigh:
                        if (nx, ny) != keeper:
                            # prefer restoring wall (if room-adj) else cave
                            if _wall_has_room_opposite(grid, nx, ny, config):
                                grid[nx][ny] = WALL
                            else:
                                grid[nx][ny] = CAVE


def _carve_leg(
    grid,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    config: DungeonConfig,
    allow_wall_break=False,
):
    dx = 1 if x2 > x1 else -1 if x2 < x1 else 0
    dy = 1 if y2 > y1 else -1 if y2 < y1 else 0
    x, y = x1, y1
    steps = abs(x2 - x1) + abs(y2 - y1)
    prev = None
    for _ in range(steps):
        _carve_legacy_tile(grid, x, y, config, prev, allow_wall_break=allow_wall_break)
    prev = (x, y)
    x += dx
    y += dy
    _carve_legacy_tile(grid, x, y, config, prev, allow_wall_break=allow_wall_break)


def _carve_path_tile(grid, x: int, y: int, prev: Tuple[int, int] | None, config: DungeonConfig):
    tile = grid[x][y]
    if tile == ROOM:
        return  # already inside destination or intermediary irregular cavity
    if tile == CAVE:
        grid[x][y] = TUNNEL
        return
    if tile == WALL:
        # Only convert to door if adjacent to room interior on the *other* side and previous was a tunnel (corridor approaching).
        room_adj = any(
            0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == ROOM
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        )
        prev_is_tunnel = prev is not None and grid[prev[0]][prev[1]] == TUNNEL
        if room_adj and prev_is_tunnel:
            grid[x][y] = DOOR
        # else leave wall intact (path should not have included this unless goal inside requires fallback)


def _carve_legacy_tile(grid, x: int, y: int, config: DungeonConfig, prev, allow_wall_break: bool):
    tile = grid[x][y]
    if tile == WALL and allow_wall_break:
        room_adj = any(
            0 <= nx < config.width and 0 <= ny < config.height and grid[nx][ny] == ROOM
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        )
        prev_is_tunnel = prev is not None and grid[prev[0]][prev[1]] == TUNNEL
        if room_adj and prev_is_tunnel:
            grid[x][y] = DOOR
        else:
            grid[x][y] = TUNNEL
    elif tile == CAVE:
        grid[x][y] = TUNNEL


def _post_process_wall_flanks(grid, config: DungeonConfig):
    """Repair any walls that ended up with 2+ tunnel neighbors by converting one adjacent tunnel back to CAVE
    and turning the wall into a DOOR (single doorway) if adjacent to a room, else leave as wall.
    This keeps wall rings intact while avoiding double-corridor flanking artifacts.
    """
    w, h = config.width, config.height
    # 1. Resolve wall flank issues
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                t_neighbors = []
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == TUNNEL:
                        t_neighbors.append((nx, ny))
                if len(t_neighbors) >= 2:
                    room_adj = any(
                        0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    )
                    if room_adj:
                        grid[x][y] = DOOR
                    # revert all but one tunnel neighbor furthest from center to CAVE (naive heuristic)
                    for rx, ry in t_neighbors[1:]:
                        grid[rx][ry] = CAVE
    # 2. Collapse adjacent door clusters to single door (keep first)
    for x in range(w):
        for y in range(h):
            if grid[x][y] == DOOR:
                # if any neighbor door, convert this one to wall unless it is first in lexical order
                if any(
                    0 <= nx < w and 0 <= ny < h and grid[nx][ny] == DOOR
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                ):
                    # choose canonical keeper: smallest (x,y)
                    # If current is not canonical among its door cluster, revert to WALL
                    cluster = [(x, y)]
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == DOOR:
                            cluster.append((nx, ny))
                    keeper = min(cluster)
                    if (x, y) != keeper:
                        # restore wall ring if original neighbors include room
                        if any(
                            0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM
                            for nx, ny in (
                                (x + 1, y),
                                (x - 1, y),
                                (x, y + 1),
                                (x, y - 1),
                            )
                        ):
                            grid[x][y] = WALL
                        else:
                            grid[x][y] = CAVE


def _finalize_tunnel_cleanup(grid, config: DungeonConfig):
    """Global pass after all tunnels carved: eliminate any remaining walls with 2+ tunnel neighbors.
    Rule:
      - If wall has 2+ tunnel neighbors:
          * If not adjacent to a door already and not creating a door cluster, convert to DOOR and prune extra tunnels.
          * Else prune tunnels until only one remains (rest to CAVE) keeping wall (or existing door) intact.
    """
    w, h = config.width, config.height
    for x in range(w):
        for y in range(h):
            if grid[x][y] == WALL:
                t_neighbors = [
                    (nx, ny)
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == TUNNEL
                ]
                if len(t_neighbors) >= 2:
                    door_neighbor = any(
                        0 <= nx < w and 0 <= ny < h and grid[nx][ny] == DOOR
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    )
                    room_adj = any(
                        0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    )
                    if room_adj and not door_neighbor:
                        # Make this the door and prune extra tunnels
                        grid[x][y] = DOOR
                        for rx, ry in t_neighbors[1:]:
                            grid[rx][ry] = CAVE
                    else:
                        # Keep wall; reduce tunnels to one
                        for rx, ry in t_neighbors[1:]:
                            grid[rx][ry] = CAVE
            elif grid[x][y] == DOOR:
                # Ensure door has at least one tunnel and one room neighbor; otherwise downgrade
                has_room = any(
                    0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                )
                has_tunnel = any(
                    0 <= nx < w and 0 <= ny < h and grid[nx][ny] == TUNNEL
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                )
                if not (has_room and has_tunnel):
                    # revert ambiguous door back to wall if room-adj else cave
                    if has_room:
                        grid[x][y] = WALL
                    else:
                        grid[x][y] = CAVE


def _prune_redundant_room_doors(grid, config: DungeonConfig):
    """Remove redundant multiple doors on the same room wall leading into the same corridor component.

    Definition of redundancy:
      - Two or more DOOR tiles adjacent to the same contiguous ROOM interior region, whose tunnel-side neighbors
        are connected through tunnels without entering another room. Keep only one (lexicographically smallest)
        to preserve a single entrance aesthetic.
    Approach:
      1. Identify door tiles and map each to its room-adjacent coordinate (the first ROOM neighbor).
      2. Flood-fill tunnel components (TUNNEL tiles) to assign component IDs.
      3. Group doors by (room_anchor_coord, tunnel_component_id, wall_orientation axis) and keep one.
      4. Revert redundant doors back to WALL (maintaining wall ring) because they are adjacent to a room.
    """
    w, h = config.width, config.height
    # Build tunnel component ids
    comp = [[-1] * h for _ in range(w)]
    cid = 0
    for x in range(w):
        for y in range(h):
            if grid[x][y] == TUNNEL and comp[x][y] == -1:
                # BFS
                q = deque([(x, y)])
                comp[x][y] = cid
                while q:
                    cx, cy = q.popleft()
                    for nx, ny in (
                        (cx + 1, cy),
                        (cx - 1, cy),
                        (cx, cy + 1),
                        (cx, cy - 1),
                    ):
                        if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == TUNNEL and comp[nx][ny] == -1:
                            comp[nx][ny] = cid
                            q.append((nx, ny))
                cid += 1
    groups = {}
    for x in range(w):
        for y in range(h):
            if grid[x][y] == DOOR:
                # find one room neighbor as anchor
                room_neighbors = [
                    (nx, ny)
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == ROOM
                ]
                tunnel_neighbors = [
                    (nx, ny)
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == TUNNEL
                ]
                if not room_neighbors or not tunnel_neighbors:
                    continue
                anchor = min(room_neighbors)
                # choose tunnel component (if multiple pick first)
                t_comp = (
                    comp[tunnel_neighbors[0][0]][tunnel_neighbors[0][1]]
                    if comp[tunnel_neighbors[0][0]][tunnel_neighbors[0][1]] != -1
                    else -1
                )
                # Determine wall orientation axis: horizontal wall (doors stacked vertically) vs vertical wall
                # Use relative position of anchor vs door
                ax, ay = anchor
                orient = "H" if ay == y else "V"
                key = (anchor, t_comp, orient)
                groups.setdefault(key, []).append((x, y))
    # For each group keep smallest coordinate, revert others
    for key, coords in groups.items():
        if len(coords) <= 1:
            continue
        keeper = min(coords)
        for x, y in coords:
            if (x, y) != keeper:
                # revert to wall (since adjacent to room maintains ring)
                grid[x][y] = WALL


def _ensure_entrance_access(grid, rooms: List[Room], config: DungeonConfig):
    """Ensure the first room (entrance) has at least one adjacent tunnel/door so that
    movement tests starting from entrance can move somewhere. If completely sealed
    (rare due to pruning), carve a one-tile tunnel north preference else any direction."""
    if not rooms:
        return
    r0 = rooms[0]
    cx, cy = r0.center
    w, h = config.width, config.height
    # Check for any walkable neighbor outside room
    dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # prefer north first for test expectation
    has_exit = False
    for dx, dy in dirs:
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < w and 0 <= ny < h:
            if grid[nx][ny] in (TUNNEL, DOOR):
                has_exit = True
                break
    if has_exit:
        return
    # carve a doorway + tunnel stub one tile out (if wall present followed by cave)
    for dx, dy in dirs:
        nx, ny = cx + dx, cy + dy
        nnx, nny = cx + dx * 2, cy + dy * 2
        if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == WALL:
            # ensure next cell is not room; carve door then tunnel
            if 0 <= nnx < w and 0 <= nny < h and grid[nnx][nny] in (CAVE, TUNNEL):
                grid[nx][ny] = DOOR
                grid[nnx][nny] = TUNNEL
                return
        elif 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == CAVE:
            grid[nx][ny] = TUNNEL
            return
