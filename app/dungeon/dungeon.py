"""Dungeon generator (rooms and mazes, multi-floor).

Pipeline (per floor):
    1. Pack odd-aligned rooms densely (rooms.place_rooms).
    2. Flood remaining space with winding mazes; straight runs capped at
       config.straight_max tiles (connect.fill_maze).
    3. Open connectors between all regions via union-find (+ loop connectors);
       room<->corridor connectors become DOORs (connect.connect_regions).
    4. Retract most maze dead ends (connect.cull_dead_ends).
    5. Derive WALLs as CAVE adjacent to ROOM (connect.derive_walls).
    6. Assign room types, stairs, secret/locked door variants; on the deepest
       floor, a boss room plus a sealed loot room holding the exit portal.

Connectivity is guaranteed by construction; every seal (secret door, loot
door, wall fix-up) is verified against full room reachability first.

Multi-floor: a dungeon is a stack of independently generated floors. Floor z
of base seed S is Dungeon(seed=S, floor=z, num_floors=N) with RNG seed
floor_seed(S, z). Stairs tiles '<'/'>' link floor z to z-1/z+1.

Public contract (consumed across app/):
    Dungeon(seed=None, size=(W,H,1)) | Dungeon(DungeonConfig(...))
    .grid[x][y] (column-major), .rooms, .room_types, .metrics, .seed, .size,
    .config, .stairs_up, .stairs_down, .entry_point, .loot_room_doors, .portal
    .is_walkable(x,y,unlocked_doors=None), .reveal_secret_door(x,y),
    .to_json(), .to_ascii()
    Tiles: C R W T D S L P < >
"""

from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from . import connect as connect_mod
from .config import DungeonConfig
from .rooms import Room, place_rooms
from .tiles import CAVE, DOOR, ROOM, STAIRS_DOWN, STAIRS_UP, TELEPORT, TUNNEL, WALL

SECRET_DOOR = "S"
LOCKED_DOOR = "L"

_WALKABLE = {ROOM, TUNNEL, DOOR, TELEPORT, STAIRS_UP, STAIRS_DOWN}
# Locked doors are logically passable (a key exists), so they count for connectivity.
_CONNECTED = _WALKABLE | {LOCKED_DOOR}


def floor_seed(base_seed: int, z: int) -> int:
    """Deterministic per-floor RNG seed. Floor 0 keeps the base seed so
    single-floor dungeons (and floor 0 of multi-floor ones) match legacy
    seed-keyed state such as explored tiles."""
    if z == 0:
        return base_seed
    return (base_seed ^ (z * 0x9E3779B1)) & 0x7FFFFFFF


class Dungeon:
    def __init__(
        self,
        config: DungeonConfig | None = None,
        *,
        seed: int | None = None,
        size: Tuple[int, int, int] | None = None,
        floor: int | None = None,
        num_floors: int | None = None,
        **_legacy,
    ):
        if config is None:
            width = height = 75
            if size is not None and len(size) >= 2:
                width, height = size[0], size[1]
            config = DungeonConfig(width=width, height=height, seed=seed)
        else:
            if seed is not None:
                config.seed = seed
            if size is not None and len(size) >= 2:
                config.width, config.height = size[0], size[1]
        if floor is not None:
            config.floor = floor
        if num_floors is not None:
            config.num_floors = num_floors
        self.config = config
        if self.config.seed is None:
            self.config.seed = random.randint(0, 2**31 - 1)
        self._rng = random.Random(floor_seed(self.config.seed, self.config.floor))
        self.seed = self.config.seed
        self.size = (self.config.width, self.config.height, self.config.num_floors)
        self.grid: List[List[str]] = [[CAVE for _ in range(self.config.height)] for _ in range(self.config.width)]
        self.rooms: List[Room] = []
        self.room_types: List[str] = []
        self.metrics: Dict[str, Any] = {}
        self.stairs_up: Optional[Tuple[int, int]] = None
        self.stairs_down: Optional[Tuple[int, int]] = None
        self.portal: Optional[Tuple[int, int]] = None
        self.loot_room_doors: Set[Tuple[int, int]] = set()
        self._generate()

    @property
    def is_deepest(self) -> bool:
        return self.config.floor >= self.config.num_floors - 1

    @property
    def entry_point(self) -> Tuple[int, int]:
        """Where a party arriving on this floor stands: the up-stairs, or the
        start room center on floor 0."""
        if self.config.floor > 0 and self.stairs_up:
            return self.stairs_up
        return self.rooms[0].center if self.rooms else (1, 1)

    # ------------------------------------------------------------------
    def _generate(self):
        self._place_rooms()
        connect_mod.fill_maze(self.grid, self._rng, self.config.straight_max)
        connect_mod.connect_regions(self.grid, self._rng, self.config.extra_connection_chance, self.config.straight_max)
        connect_mod.cull_dead_ends(self.grid, self._rng, self.config.dead_end_keep)
        connect_mod.derive_walls(self.grid)
        self._assign_room_types()
        self._place_stairs()
        self._augment_doors_with_variants()
        if self.is_deepest:
            self._seal_loot_room()
        self._compute_connectivity_metrics()
        self._collect_counts()
        # Teleports retired: expose empty structures for backward-compatible consumers.
        self.metrics["teleport_pairs"] = []
        self.metrics["teleport_lookup"] = {}
        self.metrics["tiles_teleport"] = 0

    def _place_rooms(self):
        rooms, target, placed = place_rooms(self.grid, self.config, rng=self._rng)
        self.rooms = rooms
        self.metrics["rooms_attempted"] = target
        self.metrics["rooms_placed"] = placed

    # ---------------- Room typing ----------------
    def _assign_room_types(self):
        n = len(self.rooms)
        self.room_types = ["room"] * n
        if n == 0:
            return
        if self.config.floor == 0:
            self.room_types[0] = "start"
        if self.is_deepest:
            areas = sorted(((r.w * r.h, i) for i, r in enumerate(self.rooms)), reverse=True)
            candidates = [i for _, i in areas if self.room_types[i] != "start"]
            if candidates:
                self.room_types[candidates[0]] = "boss"
            if len(candidates) > 1:
                self.room_types[candidates[1]] = "treasure"
        # connector/deadend by door count (skip special rooms)
        for idx, r in enumerate(self.rooms):
            if self.room_types[idx] in ("start", "boss", "treasure"):
                continue
            dc = len(self._room_doors(r))
            if dc <= 1:
                self.room_types[idx] = "deadend"
            elif dc >= 3:
                self.room_types[idx] = "connector"

    def _room_doors(self, r: Room, kinds=(DOOR,)) -> List[Tuple[int, int]]:
        w, h = self.config.width, self.config.height
        seen = set()
        for x, y in r.cells():
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] in kinds:
                    seen.add((nx, ny))
        return sorted(seen)

    # ---------------- Stairs ----------------
    def _place_stairs(self):
        """Place '<' (to floor above) and '>' (to floor below) on room centers.
        Kept far apart so descending means traversing the floor."""
        if not self.rooms:
            return
        special = {i for i, t in enumerate(self.room_types) if t in ("boss", "treasure")}
        candidates = [i for i in range(len(self.rooms)) if i not in special] or list(range(len(self.rooms)))

        def far_from(pt: Tuple[int, int]) -> int:
            return max(
                candidates, key=lambda i: abs(self.rooms[i].center[0] - pt[0]) + abs(self.rooms[i].center[1] - pt[1])
            )

        if self.config.floor > 0:
            up_idx = self._rng.choice(candidates)
            self.stairs_up = self.rooms[up_idx].center
            x, y = self.stairs_up
            self.grid[x][y] = STAIRS_UP
        if not self.is_deepest:
            anchor = self.stairs_up or self.rooms[0].center
            down_idx = far_from(anchor)
            cx, cy = self.rooms[down_idx].center
            if (cx, cy) == self.stairs_up:
                cx += 1  # tiny floor with one candidate room: nudge off the up-stairs
            self.stairs_down = (cx, cy)
            self.grid[cx][cy] = STAIRS_DOWN

    # ---------------- Door variants ----------------
    def _augment_doors_with_variants(self):
        if not self.rooms:
            return
        idx_boss = next((i for i, t in enumerate(self.room_types) if t == "boss"), None)
        # Lock a boss door only when the room has more than one door, so an
        # unlocked approach always remains and the room is never sealed off.
        if idx_boss is not None:
            doors = self._room_doors(self.rooms[idx_boss])
            if len(doors) > 1:
                x, y = self._rng.choice(doors)
                self.grid[x][y] = LOCKED_DOOR
        # Secret doors go only on redundant doors of dead-end rooms: converting a
        # bridge door to a wall-like secret would sever the dungeon. We verify full
        # room connectivity (secrets treated as non-walkable) before committing each.
        sealed: set = set()
        for i, t in enumerate(self.room_types):
            if t != "deadend" or i == idx_boss:
                continue
            doors = self._room_doors(self.rooms[i])
            if len(doors) <= 1:
                continue  # never seal a room's only exit
            for x, y in doors[1:]:  # keep at least one normal door
                if self._rng.random() < 0.3 and self._keeps_connectivity(sealed | {(x, y)}):
                    self.grid[x][y] = SECRET_DOOR
                    sealed.add((x, y))

    # ---------------- Loot room (deepest floor) ----------------
    def _seal_loot_room(self):
        """Turn the treasure room into the sealed loot room: every opening
        becomes a LOCKED_DOOR (unlocked by the final boss kill) and the exit
        portal sits at its center."""
        idx = next((i for i, t in enumerate(self.room_types) if t == "treasure"), None)
        if idx is None:
            return
        room = self.rooms[idx]
        openings = self._room_doors(room, kinds=(DOOR, TUNNEL, SECRET_DOOR, LOCKED_DOOR))
        for x, y in openings:
            self.grid[x][y] = LOCKED_DOOR
        # No-adjacent-door-variants invariant: two openings can touch when a
        # corridor corner hugs the room. Wall one of each adjacent pair off,
        # but only when the rest of the dungeon stays fully connected.
        opening_set = set(openings)
        for x, y in list(opening_set):
            if self.grid[x][y] != LOCKED_DOOR:
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in opening_set and self.grid[nx][ny] == LOCKED_DOOR:
                    if self._keeps_connectivity({(x, y)}):
                        self.grid[x][y] = WALL
                        opening_set.discard((x, y))
                        break
        self.loot_room_doors = {(x, y) for x, y in opening_set if self.grid[x][y] == LOCKED_DOOR}
        cx, cy = room.center
        self.grid[cx][cy] = TELEPORT
        self.portal = (cx, cy)

    def _keeps_connectivity(self, blocked: set) -> bool:
        """True if every room is still reachable from the entry point when the
        given cells are treated as non-walkable."""
        if not self.rooms:
            return True
        w, h = self.config.width, self.config.height
        start = self.rooms[0].center
        q = deque([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (
                    0 <= nx < w
                    and 0 <= ny < h
                    and (nx, ny) not in seen
                    and (nx, ny) not in blocked
                    and self.grid[nx][ny] in _CONNECTED
                ):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return all(any((ix, iy) in seen for ix, iy in r.cells()) for r in self.rooms)

    def reveal_secret_door(self, x: int, y: int) -> bool:
        if 0 <= x < self.config.width and 0 <= y < self.config.height and self.grid[x][y] == SECRET_DOOR:
            self.grid[x][y] = DOOR
            return True
        return False

    def is_walkable(self, x: int, y: int, unlocked_doors=None) -> bool:
        if not (0 <= x < self.config.width and 0 <= y < self.config.height):
            return False
        cell = self.grid[x][y]
        if cell == LOCKED_DOOR:
            return unlocked_doors is not None and (x, y) in unlocked_doors
        return cell in _WALKABLE  # secret doors not walkable until revealed

    # ---------------- Metrics ----------------
    def _compute_connectivity_metrics(self):
        if not self.rooms:
            self.metrics["unreachable_rooms"] = 0
            return
        self.metrics["unreachable_rooms"] = 0 if self._keeps_connectivity(set()) else self._count_unreachable()

    def _count_unreachable(self) -> int:
        w, h = self.config.width, self.config.height
        start = self.rooms[0].center
        q = deque([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and self.grid[nx][ny] in _CONNECTED:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return sum(1 for r in self.rooms if all((ix, iy) not in seen for ix, iy in r.cells()))

    def _collect_counts(self):
        counts: Dict[str, int] = {}
        w, h = self.config.width, self.config.height
        for x in range(w):
            for y in range(h):
                t = self.grid[x][y]
                counts[t] = counts.get(t, 0) + 1
        self.metrics.update(
            {
                "seed": self.seed,
                "floor": self.config.floor,
                "num_floors": self.config.num_floors,
                "rooms": len(self.rooms),
                "tiles_cave": counts.get(CAVE, 0),
                "tiles_room": counts.get(ROOM, 0),
                "tiles_wall": counts.get(WALL, 0),
                "tiles_tunnel": counts.get(TUNNEL, 0),
                "tiles_door": counts.get(DOOR, 0),
                "secret_doors": counts.get(SECRET_DOOR, 0),
                "locked_doors": counts.get(LOCKED_DOOR, 0),
                "stairs_up": counts.get(STAIRS_UP, 0),
                "stairs_down": counts.get(STAIRS_DOWN, 0),
            }
        )
        walkable = sum(counts.get(t, 0) for t in _CONNECTED)
        self.metrics["walkable_coverage"] = walkable / float(w * h)
        rtc: Dict[str, int] = {}
        for t in self.room_types:
            rtc[t] = rtc.get(t, 0) + 1
        self.metrics["room_type_counts"] = rtc

    # ---------------- Outputs ----------------
    def to_ascii(self) -> str:
        return "\n".join("".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height))

    def to_json(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "width": self.config.width,
            "height": self.config.height,
            "floor": self.config.floor,
            "num_floors": self.config.num_floors,
            "grid": ["".join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)],
            "metrics": self.metrics,
        }


__all__ = [
    "Dungeon",
    "DungeonConfig",
    "floor_seed",
    "CAVE",
    "ROOM",
    "WALL",
    "TUNNEL",
    "DOOR",
    "SECRET_DOOR",
    "LOCKED_DOOR",
    "TELEPORT",
    "STAIRS_UP",
    "STAIRS_DOWN",
]

if __name__ == "__main__":
    d = Dungeon(seed=1234, size=(75, 75, 1))
    print(d.to_ascii())
    print(d.metrics)
