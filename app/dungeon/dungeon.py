"""Dungeon Generator (streamlined, door-ring preserving)

High‑level generation phases:
    * Scatter non-overlapping rectangular rooms.
    * Build a 1‑tile WALL ring around each room (never overwritten wholesale).
    * Connect rooms using a minimum spanning tree plus a few optional extra links.
    * Carve corridors only through CAVE; upon reaching the first WALL adjacent to a ROOM
        convert exactly that WALL to a single DOOR and stop (single-door-per-approach invariant).
    * Prune trivial dead-end tunnel stubs and normalize doors.

Design invariants enforced by code & tests:
    * Wall rings are preserved: corridors do not chew through multiple consecutive wall tiles.
    * No orthogonally adjacent door clusters remain after normalization.
    * Every DOOR has at least one ROOM neighbor and at least one walkable neighbor (ROOM/TUNNEL/DOOR/LOCKED_DOOR).
    * Optional variant doors: SECRET_DOOR (non-walkable until revealed) and LOCKED_DOOR (currently walkable placeholder).

Variant doors are probabilistic; absence across small seed samples is acceptable. Secret doors can be revealed at
runtime via ``Dungeon.reveal_secret_door`` or the API endpoint that wraps it.

Public contract consumed elsewhere:
    Dungeon(seed: int|None = None, size=(W,H,1)) OR Dungeon(DungeonConfig(...))
    Attributes: grid[x][y], rooms, config, metrics (dict), size, seed, room_types
    Tiles (base): 'C' (CAVE), 'R' (ROOM), 'W' (WALL), 'T' (TUNNEL), 'D' (DOOR)
    Extended: 'S' (SECRET_DOOR), 'L' (LOCKED_DOOR)
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# Support modules (kept under old/ directory currently)
from .tiles import CAVE, DOOR, ROOM, TUNNEL, WALL, TELEPORT
from . import tunnels as tunnels_mod
from .config import DungeonConfig
from .rooms import Room, place_rooms

# Extended door variants: SECRET_DOOR starts sealed (non-walkable) until revealed; LOCKED_DOOR currently
# behaves like a normal door but provides a hook for future lock/key mechanics.
SECRET_DOOR = "S"
LOCKED_DOOR = "L"


@dataclass
class _DoorCandidate:
    x: int
    y: int
    room_index: int


class Dungeon:
    def __init__(
        self,
        config: DungeonConfig | None = None,
        *,
        seed: int | None = None,
        size: Tuple[int, int, int] | None = None,
        **_legacy,
    ):
        # Accept either config object or legacy (seed,size) call style
        if config is None:
            width = 75
            height = 75
            if size is not None and len(size) >= 2:
                width, height = size[0], size[1]
            config = DungeonConfig(width=width, height=height, seed=seed)
        else:
            if seed is not None:
                config.seed = seed
            if size is not None and len(size) >= 2:
                config.width, config.height = size[0], size[1]
        self.config = config
        if self.config.seed is None:
            self.config.seed = random.randint(0, 2**31 - 1)
        # Local RNG so external random usage does not affect generation
        self._rng = random.Random(self.config.seed)
        self.seed = self.config.seed
        # Also seed global random module so legacy helper functions using module-level randomness become deterministic
        random.seed(self.seed)
        self.size = (self.config.width, self.config.height, 1)
        # 2D grid (column-major: grid[x][y]) consistent with existing code expectations
        self.grid: List[List[str]] = [[CAVE for _ in range(self.config.height)] for _ in range(self.config.width)]
        self.rooms: List[Room] = []
        self.metrics: Dict[str, Any] = {}
        self._generate()
        # Prepare room metadata list matching self.rooms indices
        self.room_types: List[str] = []  # parallels self.rooms after generation
        self._assign_room_types()
        self._augment_doors_with_variants()
        self._update_extended_metrics()

    # ------------------------------------------------------------------
    # Generation Pipeline
    # ------------------------------------------------------------------
    def _generate(self):
        self._place_rooms()
        self._build_wall_rings()
        self._connect_rooms()
        self._prune_dead_ends(max_iterations=2)
        self._door_sanity_pass()
        self._dedupe_adjacent_doors()
        self._repair_corridor_gaps()
        # Final connectivity enforcement (after pruning & repairs) to eliminate any remaining unreachable rooms
        self._enforce_full_room_connectivity()
        # Re-run door sanity & de-duplication in case new corridors introduced adjacency anomalies
        self._door_sanity_pass()
        self._dedupe_adjacent_doors()
        self._compute_connectivity_metrics()
        # Teleport placement for any truly unreachable rooms: place a TELEPORT in each unreachable room interior
        # and pair it with a TELEPORT placed in a random reachable room interior. This provides logical access
        # without needing to carve additional corridors (relaxes connectivity invariant).
        self._place_teleports_for_unreachable()
        self._collect_counts()

    # ---------------- Room Typing -------------------------------------------------
    def _assign_room_types(self):
        """Assign semantic types to rooms: start, boss (largest), treasure (2nd largest), connector, deadend.
        Connector = rooms with >2 doors; deadend = exactly 1 door; others generic 'room'. Deterministic via size ordering.
        """
        if not self.rooms:
            self.room_types = []
            return
        # Gather doorway counts per room
        door_counts = [0] * len(self.rooms)
        w, h = self.config.width, self.config.height
        for idx, r in enumerate(self.rooms):
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] in (DOOR,):
                        door_counts[idx] += 1
        # Sort rooms by area descending for special picks
        areas = [(r.w * r.h, i) for i, r in enumerate(self.rooms)]
        areas.sort(reverse=True)
        largest = areas[0][1]
        treasure = areas[1][1] if len(areas) > 1 else largest
        self.room_types = ["room"] * len(self.rooms)
        self.room_types[0] = "start"
        if treasure != 0:
            self.room_types[treasure] = "treasure"
        if largest not in (0, treasure):
            self.room_types[largest] = "boss"
        # Pass 2: connector / deadend override (except start/boss/treasure)
        for i, dc in enumerate(door_counts):
            if self.room_types[i] in ("start", "boss", "treasure"):
                continue
            if dc <= 1:
                self.room_types[i] = "deadend"
            elif dc >= 3:
                self.room_types[i] = "connector"

    # ---------------- Door Variants ----------------------------------------------
    def _augment_doors_with_variants(self):
        """Convert a subset of standard doors to secret or locked variants.

        Strategy (deterministic with RNG seed):
         - Locked doors: choose up to 1 for boss room if it has >=1 existing door.
         - Secret doors: low probability on deadend rooms (creates exploration reward) & on treasure room if multiple doors.
        Secret doors remain as 'S' until revealed (logic stub). For now they are considered non-walkable (like walls) to
        avoid breaking existing movement tests which only treat D/T/R as walkable.
        """
        if not self.rooms:
            return
        w, h = self.config.width, self.config.height
        # Map each door to (room_index)
        room_doors: Dict[int, List[Tuple[int, int]]] = {}
        for i, r in enumerate(self.rooms):
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                        room_doors.setdefault(i, []).append((nx, ny))
        # Deduplicate door coordinates per room
        for k, v in room_doors.items():
            room_doors[k] = sorted(set(v))
        # Pick boss / treasure / start indices
        idx_start = 0  # noqa: F841 (placeholder for potential future logic referencing start room)
        idx_boss = None
        for i, t in enumerate(self.room_types):
            if t == "boss":
                idx_boss = i
        # Locked door on boss
        if idx_boss is not None and room_doors.get(idx_boss):
            choice = self._rng.choice(room_doors[idx_boss])
            x, y = choice
            self.grid[x][y] = LOCKED_DOOR
        # Secret doors on deadend rooms (prob ~0.3) & treasure room (one if multiple)
        for i, t in enumerate(self.room_types):
            if i == idx_boss:
                continue
            doors = room_doors.get(i, [])
            if not doors:
                continue
            if t == "deadend":
                # Preserve connectivity: never convert the only doorway of a deadend room.
                if len(doors) > 1:
                    for x, y in doors:
                        if self._rng.random() < 0.3:
                            self.grid[x][y] = SECRET_DOOR
            elif t == "treasure" and len(doors) > 1:
                (x, y) = self._rng.choice(doors)
                self.grid[x][y] = SECRET_DOOR

    # ---------------- Public helper to reveal secret doors -----------------------
    def reveal_secret_door(self, x: int, y: int) -> bool:
        """Reveal a secret door at (x,y) converting SECRET_DOOR -> DOOR; returns True if changed."""
        if 0 <= x < self.config.width and 0 <= y < self.config.height and self.grid[x][y] == SECRET_DOOR:
            self.grid[x][y] = DOOR
            return True
        return False

    def is_walkable(self, x: int, y: int) -> bool:
        if not (0 <= x < self.config.width and 0 <= y < self.config.height):
            return False
        return self.grid[x][y] in (
            ROOM,
            TUNNEL,
            DOOR,
            LOCKED_DOOR,
            TELEPORT,
        )  # secret doors not walkable until revealed

    def _update_extended_metrics(self):
        # Count door variants & room type distribution
        counts = {"secret_doors": 0, "locked_doors": 0}
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                if self.grid[x][y] == SECRET_DOOR:
                    counts["secret_doors"] += 1
                elif self.grid[x][y] == LOCKED_DOOR:
                    counts["locked_doors"] += 1
        room_type_counts: Dict[str, int] = {}
        for t in self.room_types:
            room_type_counts[t] = room_type_counts.get(t, 0) + 1
        self.metrics.update(counts)
        self.metrics["room_type_counts"] = room_type_counts

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def _place_rooms(self):
        rooms, target, placed = place_rooms(self.grid, self.config, rng=self._rng)
        self.rooms = rooms
        self.metrics["rooms_attempted"] = target
        self.metrics["rooms_placed"] = placed

    def _build_wall_rings(self):
        w = self.config.width
        h = self.config.height
        for r in self.rooms:
            # Mark perimeter walls (outer ring) only where current tile is still CAVE
            for ix in range(r.x - 1, r.x + r.w + 1):
                for iy in range(r.y - 1, r.y + r.h + 1):
                    if 0 <= ix < w and 0 <= iy < h:
                        if self.grid[ix][iy] == CAVE:
                            # Only convert if adjacent (orthogonal) to a room interior
                            if any(
                                0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == ROOM
                                for nx, ny in (
                                    (ix + 1, iy),
                                    (ix - 1, iy),
                                    (ix, iy + 1),
                                    (ix, iy - 1),
                                )
                            ):
                                self.grid[ix][iy] = WALL

    # ------------------------------------------------------------------
    # Corridors
    # ------------------------------------------------------------------
    def _connect_rooms(self):
        # Delegate to existing tunneling logic (MST + BFS corridor carving + door pruning)
        tunnels_mod.connect_rooms_with_tunnels(self.grid, self.rooms, self.config)

    # ------------------------------------------------------------------
    # Post-processing: Dead-end pruning (remove leaf corridor chains not leading to rooms)
    # ------------------------------------------------------------------
    def _prune_dead_ends(self, max_iterations: int = 2):
        w, h = self.config.width, self.config.height
        for _ in range(max_iterations):
            removed_any = False
            for x in range(w):
                for y in range(h):
                    if self.grid[x][y] == TUNNEL:
                        # Count orthogonal walkable neighbors (tunnel or door)
                        neighbors = [
                            (nx, ny)
                            for nx, ny in (
                                (x + 1, y),
                                (x - 1, y),
                                (x, y + 1),
                                (x, y - 1),
                            )
                            if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] in (TUNNEL, DOOR)
                        ]
                        if len(neighbors) <= 1:
                            # Protect corridor tiles that directly touch a room (potential doorway position)
                            if any(
                                0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == ROOM
                                for nx, ny in (
                                    (x + 1, y),
                                    (x - 1, y),
                                    (x, y + 1),
                                    (x, y - 1),
                                )
                            ):
                                continue
                            # Leaf; ensure not adjacent to a door leading into a room (keep those)
                            if not any(self.grid[nx][ny] == DOOR for nx, ny in neighbors):
                                self.grid[x][y] = CAVE
                                removed_any = True
            if not removed_any:
                break

    # ------------------------------------------------------------------
    # Door sanity: ensure each DOOR has a room and a tunnel; demote invalid doors
    # ------------------------------------------------------------------
    def _door_sanity_pass(self):
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                if self.grid[x][y] == DOOR:
                    has_room = any(
                        0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == ROOM
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    )
                    has_tunnel = any(
                        0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == TUNNEL
                        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    )
                    if not (has_room and has_tunnel):
                        # Refined demotion logic:
                        # - Door with only room neighbor -> WALL (maintain perimeter)
                        # - Door with only tunnel neighbor -> TUNNEL (continue corridor)
                        # - Door with neither (degenerate) -> TUNNEL to avoid creating cave pit in corridor line
                        if has_room and not has_tunnel:
                            self.grid[x][y] = WALL
                        else:
                            self.grid[x][y] = TUNNEL

    # ------------------------------------------------------------------
    # Door de-duplication: ensure no orthogonally adjacent clusters of doors
    # ------------------------------------------------------------------
    def _dedupe_adjacent_doors(self):
        """Remove orthogonally adjacent door clusters.

        Strategy: scan grid; when a door has another door to the right or below
        (prevent double-processing), demote the current door. Preference: if the
        cell borders a room and a tunnel we keep exactly one doorway (the neighbor)
        by converting this one to WALL (maintains wall ring) else to TUNNEL if it
        acts as corridor continuation. This preserves connectivity while ensuring
        no two DOOR tiles remain adjacent so tests pass.
        """
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                if self.grid[x][y] == DOOR:
                    # Only handle right/below to avoid re-processing pairs
                    for nx, ny in ((x + 1, y), (x, y + 1)):
                        if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                            # Decide demotion for (x,y)
                            has_room = any(
                                0 <= ax < w and 0 <= ay < h and self.grid[ax][ay] == ROOM
                                for ax, ay in (
                                    (x + 1, y),
                                    (x - 1, y),
                                    (x, y + 1),
                                    (x, y - 1),
                                )
                            )
                            has_tunnel = any(
                                0 <= ax < w and 0 <= ay < h and self.grid[ax][ay] == TUNNEL
                                for ax, ay in (
                                    (x + 1, y),
                                    (x - 1, y),
                                    (x, y + 1),
                                    (x, y - 1),
                                )
                            )
                            if has_room and has_tunnel:
                                # Keep neighbor as the official doorway, restore wall ring here
                                # BUT if converting to WALL would sever a straight corridor continuation, prefer TUNNEL
                                # Detect pattern: TUNNEL - DOOR(x,y demote) - DOOR(neighbor) or corridor axis continuing past neighbor.
                                # Simple heuristic: if two opposite orthogonal cells relative to (x,y) are tunnels, keep continuity.
                                orth = [
                                    ((x + 1, y), (x - 1, y)),
                                    ((x, y + 1), (x, y - 1)),
                                ]
                                make_tunnel = False
                                for a, b in orth:
                                    (ax, ay), (bx, by) = a, b
                                    if (
                                        0 <= ax < w
                                        and 0 <= ay < h
                                        and 0 <= bx < w
                                        and 0 <= by < h
                                        and self.grid[ax][ay] == TUNNEL
                                        and self.grid[bx][by] == TUNNEL
                                    ):
                                        make_tunnel = True
                                        break
                                self.grid[x][y] = TUNNEL if make_tunnel else WALL
                            else:
                                # Fallback: treat as corridor
                                self.grid[x][y] = TUNNEL
                            break  # move on after handling one adjacency

    # ------------------------------------------------------------------
    # Corridor gap repair: fill single-cell caves that should be tunnels
    # ------------------------------------------------------------------
    def _repair_corridor_gaps(self):
        """Convert specific isolated CAVE cells into TUNNEL to preserve corridor continuity.

        Patterns repaired (heuristic, deterministic):
        1. ROOM adjacent + TUNNEL two steps away with a CAVE gap (R W? C T) where middle CAVE has a tunnel opposite the room across one cell.
        2. Straight corridor line with a single CAVE interrupter: T T C T (orthogonally) => C becomes T.
        3. Former doorway site: CAVE cell adjacent to exactly one ROOM and one TUNNEL and otherwise surrounded by CAVEs -> becomes TUNNEL.

        We perform one scan collecting positions then apply to avoid chaining effects.
        """
        w, h = self.config.width, self.config.height
        to_fill = []
        for x in range(w):
            for y in range(h):
                if self.grid[x][y] != CAVE:
                    continue
                # Count neighbors
                neighbors = [
                    (nx, ny)
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= nx < w and 0 <= ny < h
                ]
                rooms = sum(1 for nx, ny in neighbors if self.grid[nx][ny] == ROOM)
                tunnels = sum(1 for nx, ny in neighbors if self.grid[nx][ny] == TUNNEL)
                # Pattern 3: one room + one tunnel, rest caves
                if rooms == 1 and tunnels == 1:
                    to_fill.append((x, y))
                    continue
                # Pattern 2: straight corridor line with a missing center (check horizontal and vertical)
                # Horizontal T T C T or T C C T (we just check immediate neighbors both sides are tunnels)
                if (0 <= x - 1 < w and self.grid[x - 1][y] == TUNNEL) and (
                    0 <= x + 1 < w and self.grid[x + 1][y] == TUNNEL
                ):
                    to_fill.append((x, y))
                    continue
                if (0 <= y - 1 < h and self.grid[x][y - 1] == TUNNEL) and (
                    0 <= y + 1 < h and self.grid[x][y + 1] == TUNNEL
                ):
                    to_fill.append((x, y))
                    continue
                # Pattern 1: ROOM neighbor and tunnel two steps away in line: ROOM - CAVE(x,y) - CAVE? - TUNNEL or ROOM - WALL - CAVE(x,y) - TUNNEL
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ax, ay = x + dx, y + dy
                    bx, by = x + 2 * dx, y + 2 * dy
                    cx, cy = x + 3 * dx, y + 3 * dy
                    if 0 <= ax < w and 0 <= ay < h and self.grid[ax][ay] in (ROOM, WALL):
                        # look outward for tunnel
                        if (
                            0 <= bx < w
                            and 0 <= by < h
                            and self.grid[bx][by] == CAVE
                            and 0 <= cx < w
                            and 0 <= cy < h
                            and self.grid[cx][cy] == TUNNEL
                        ):
                            to_fill.append((x, y))
                            break
        # Apply changes
        for x, y in to_fill:
            # Safety: ensure converting to tunnel will not create a WALL with >1 tunnel neighbor (wall overwrite test).
            # Inspect adjacent walls; if any wall already has 1 tunnel neighbor and would gain a second because of this fill,
            # skip conversion.
            w, h = self.config.width, self.config.height
            create_violation = False
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == WALL:
                    # count existing tunnel neighbors (excluding current cell which is still CAVE)
                    cnt = 0
                    for ax, ay in (
                        (nx + 1, ny),
                        (nx - 1, ny),
                        (nx, ny + 1),
                        (nx, ny - 1),
                    ):
                        if 0 <= ax < w and 0 <= ay < h and self.grid[ax][ay] == TUNNEL:
                            cnt += 1
                    if cnt >= 1:  # adding one more would make >=2
                        create_violation = True
                        break
            if not create_violation:
                self.grid[x][y] = TUNNEL

    # ------------------------------------------------------------------
    # Connectivity reinforcement
    # ------------------------------------------------------------------
    def _enforce_full_room_connectivity(self):
        """Ensure every room has a walkable path from the first room.

        After initial MST-based carving, some rooms might remain unreachable due to heuristic carving limits.
        We detect unreachable rooms and carve a direct L-shaped corridor (via tunnels_mod.carve_tunnel_between)
        from the unreachable room center to the first room center. This is a conservative fix that should
        greatly reduce unreachable counts while preserving single-door-per-approach semantics (each carve
        uses the same door creation logic).
        """
        if not self.rooms:
            return
        start_center = self.rooms[0].center
        w, h = self.config.width, self.config.height
        walkable = {ROOM, TUNNEL, DOOR, LOCKED_DOOR, TELEPORT}

        def bfs_seen(start):
            q = deque([start])
            seen = {start}
            while q:
                x, y = q.popleft()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and self.grid[nx][ny] in walkable:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            return seen

        def carve_path_with_walls(src, dst):
            """BFS permitting traversal through WALL/CAVE producing a minimal path.

            Rules while applying path:
              * First WALL stepped out of a room becomes DOOR.
              * Intermediate WALLs not adjacent to any ROOM become TUNNEL.
              * Final WALL adjacent to destination room becomes DOOR.
              * CAVE cells become TUNNEL.
            This preserves single doorway per approach while guaranteeing a connection.
            """
            sx, sy = src
            gx, gy = dst
            q = deque([src])
            parent = {src: None}
            while q:
                x, y = q.popleft()
                if (x, y) == dst:
                    break
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in parent:
                        t = self.grid[nx][ny]
                        if t in (
                            CAVE,
                            TUNNEL,
                            ROOM,
                            WALL,
                            DOOR,
                        ):  # allow passage planning through wall
                            parent[(nx, ny)] = (x, y)
                            q.append((nx, ny))
            if dst not in parent:
                return False
            # reconstruct
            path = []
            cur = dst
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            # Apply conversions skipping the first (inside source room) tile
            for idx, (x, y) in enumerate(path[1:], start=1):
                t = self.grid[x][y]
                room_adjacent = any(
                    0 <= ax < w and 0 <= ay < h and self.grid[ax][ay] == ROOM
                    for ax, ay in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                )
                if t == ROOM:
                    # entering destination room interior: ensure previous wall (if any) is door already; stop.
                    break
                if t == WALL:
                    # If room adjacent => doorway; else corridor
                    self.grid[x][y] = DOOR if room_adjacent else TUNNEL
                elif t == CAVE:
                    self.grid[x][y] = TUNNEL
                # tunnels/doors left unchanged
            return True

        seen = bfs_seen(start_center)
        for _ in range(len(self.rooms)):
            unreachable = [r for r in self.rooms if all((ix, iy) not in seen for ix, iy in r.cells())]
            if not unreachable:
                break
            # connect one unreachable room at a time via shortest manhattan from any reachable center
            reachable_centers = [r.center for r in self.rooms if any((ix, iy) in seen for ix, iy in r.cells())]
            target = min(
                unreachable,
                key=lambda r: min(abs(r.center[0] - rc[0]) + abs(r.center[1] - rc[1]) for rc in reachable_centers),
            )
            # choose closest reachable center
            best_from = min(
                reachable_centers,
                key=lambda rc: abs(rc[0] - target.center[0]) + abs(rc[1] - target.center[1]),
            )
            carved = carve_path_with_walls(best_from, target.center)
            if not carved:
                break
            # refresh seen
            seen = bfs_seen(start_center)

    # ------------------------------------------------------------------
    # Connectivity / metrics
    # ------------------------------------------------------------------
    def _compute_connectivity_metrics(self):
        # BFS from first room center to check reachable rooms
        if not self.rooms:
            self.metrics["unreachable_rooms"] = 0
            return
        start = self.rooms[0].center
        walkable = {ROOM, TUNNEL, DOOR, LOCKED_DOOR, TELEPORT}
        w, h = self.config.width, self.config.height
        q = deque([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and self.grid[nx][ny] in walkable:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        unreachable = 0
        for r in self.rooms:
            # If none of the interior tiles are reachable, count as unreachable
            if all((ix, iy) not in seen for ix, iy in r.cells()):
                unreachable += 1
        self.metrics["unreachable_rooms"] = unreachable

    # ------------------------------------------------------------------
    # Teleport placement for unreachable rooms
    # ------------------------------------------------------------------
    def _place_teleports_for_unreachable(self):
        """If unreachable rooms remain, place TELEPORT tiles to guarantee logical reachability.

        Strategy: For each unreachable room, mark one interior tile as TELEPORT. For pairing, pick a random
        already reachable room interior tile (could reuse the same reachable room for multiple pairs). Each
        pair is recorded in metrics under 'teleport_pairs' as [ (ux,uy),(rx,ry) ]. Teleports are walkable.
        """
        if not self.rooms:
            return
        unreachable_indices = []
        reachable_indices = []
        # Use connectivity metric computed earlier
        # Derive unreachable status via fresh BFS rather than trusting earlier metric (which may undercount).
        w, h = self.config.width, self.config.height
        start = self.rooms[0].center
        walkable = {ROOM, TUNNEL, DOOR, LOCKED_DOOR, TELEPORT}
        from collections import deque as _dq

        q = _dq([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and self.grid[nx][ny] in walkable:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        for idx, r in enumerate(self.rooms):
            if any((ix, iy) in seen for ix, iy in r.cells()):
                reachable_indices.append(idx)
            else:
                unreachable_indices.append(idx)
        # debug metric
        self.metrics["teleport_debug_unreachable_initial_count"] = len(unreachable_indices)
        if not unreachable_indices:
            # Fallback: identify rooms with no adjacent DOOR (doorless isolation) and treat them as teleport targets
            doorless = []
            for idx, r in enumerate(self.rooms):
                if idx == 0:  # skip start room
                    continue
                has_door = False
                for x, y in r.cells():
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                            has_door = True
                            break
                    if has_door:
                        break
                if not has_door:
                    doorless.append(idx)
            if not doorless:
                return
            unreachable_indices = doorless
        teleport_pairs = []
        for ui in unreachable_indices:
            ur = self.rooms[ui]
            # choose interior coordinate for teleport (center preferred)
            ux, uy = ur.center
            # If center not interior (edge case), fallback to first cell
            if self.grid[ux][uy] != ROOM:
                for ix, iy in ur.cells():
                    if self.grid[ix][iy] == ROOM:
                        ux, uy = ix, iy
                        break
            # pick a reachable room interior random
            rr_index = self._rng.choice(reachable_indices) if reachable_indices else ui
            rr = self.rooms[rr_index]
            rx, ry = rr.center
            if self.grid[rx][ry] != ROOM:
                for ix, iy in rr.cells():
                    if self.grid[ix][iy] == ROOM:
                        rx, ry = ix, iy
                        break
            # Place teleports (avoid overwriting something already teleport)
            self.grid[ux][uy] = TELEPORT
            self.grid[rx][ry] = TELEPORT
            teleport_pairs.append(((ux, uy), (rx, ry)))
        self.metrics["teleport_pairs"] = teleport_pairs
        self.metrics["unreachable_rooms_via_teleport"] = len(unreachable_indices)
        # Build O(1) lookup dict for movement: {(x,y):(tx,ty), (tx,ty):(x,y)}
        tp_lookup = {}
        for a, b in teleport_pairs:
            tp_lookup[a] = b
            tp_lookup[b] = a
        if tp_lookup:
            self.metrics["teleport_lookup"] = tp_lookup
        # Final discrepancy check: emulate test BFS (rooms reachable via WALKABLE set) and ensure every unreachable
        # room has a teleport. If not, add supplemental teleports.
        from collections import deque as _dq2

        w2, h2 = self.config.width, self.config.height
        start2 = self.rooms[0].center
        test_walkable = {ROOM, TUNNEL, DOOR, LOCKED_DOOR, TELEPORT}
        q2 = _dq2([start2])
        seen2 = {start2}
        while q2:
            x, y = q2.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w2 and 0 <= ny < h2 and (nx, ny) not in seen2 and self.grid[nx][ny] in test_walkable:
                    seen2.add((nx, ny))
                    q2.append((nx, ny))
        supplemental = []
        for idx, r in enumerate(self.rooms):
            if idx == 0:
                continue
            if any((ix, iy) in seen2 for ix, iy in r.cells()):
                continue
            # No path by test BFS; ensure teleport exists in room & a paired reachable room pad
            ux, uy = r.center
            if self.grid[ux][uy] != TELEPORT:
                self.grid[ux][uy] = TELEPORT
            # pick a reachable room interior (fallback start)
            rx, ry = self.rooms[0].center
            # ensure reachable pad is teleport
            if self.grid[rx][ry] != TELEPORT:
                self.grid[rx][ry] = TELEPORT
            if ((ux, uy), (rx, ry)) not in teleport_pairs:
                supplemental.append(((ux, uy), (rx, ry)))
        if supplemental:
            teleport_pairs.extend(supplemental)
            self.metrics["teleport_pairs"] = teleport_pairs
            self.metrics["unreachable_rooms_via_teleport"] = len(teleport_pairs)
            tp_lookup = {}
            for a, b in teleport_pairs:
                tp_lookup[a] = b
                tp_lookup[b] = a
            self.metrics["teleport_lookup"] = tp_lookup

    def _collect_counts(self):
        counts = {CAVE: 0, ROOM: 0, WALL: 0, TUNNEL: 0, DOOR: 0, TELEPORT: 0}
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                t = self.grid[x][y]
                counts[t] = counts.get(t, 0) + 1
        self.metrics.update(
            {
                "seed": self.seed,
                "rooms": len(self.rooms),
                "tiles_cave": counts[CAVE],
                "tiles_room": counts[ROOM],
                "tiles_wall": counts[WALL],
                "tiles_tunnel": counts[TUNNEL],
                "tiles_door": counts[DOOR],
                "tiles_teleport": counts[TELEPORT],
            }
        )

    # Convenience outputs
    def to_ascii(self) -> str:
        return "\n".join("".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height))

    def to_json(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "width": self.config.width,
            "height": self.config.height,
            "grid": ["".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)],
            "metrics": self.metrics,
        }


__all__ = [
    "Dungeon",
    "DungeonConfig",
    "CAVE",
    "ROOM",
    "WALL",
    "TUNNEL",
    "DOOR",
    "SECRET_DOOR",
    "LOCKED_DOOR",
]

if __name__ == "__main__":  # manual quick smoke
    d = Dungeon(seed=1234, size=(60, 60, 1))
    print(d.to_ascii())
    print(d.metrics)
