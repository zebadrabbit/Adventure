"""Dungeon generator (carve-floor-first).

Pipeline:
    1. Place rooms (rectangular, perturbed, or organic blobs) as ROOM.
    2. Connect every room with an MST (+ a few loop edges); carve corridors as
       TUNNEL through CAVE. Connectivity is guaranteed because the MST spans all rooms.
    3. Derive DOORs where a tunnel meets a room (one per approach, never adjacent).
    4. Derive WALLs as CAVE adjacent to ROOM. Tunnels run bare through solid CAVE.
    5. Assign room types and optional secret/locked door variants.

No post-hoc repair, dedup, or teleport passes: the floor is valid by construction.

Public contract (consumed across app/):
    Dungeon(seed=None, size=(W,H,1)) | Dungeon(DungeonConfig(...))
    .grid[x][y] (column-major), .rooms, .room_types, .metrics, .seed, .size, .config
    .is_walkable(x,y,unlocked_doors=None), .reveal_secret_door(x,y), .to_json(), .to_ascii()
    Tiles: C R W T D S L P
"""

from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Tuple

from . import connect as connect_mod
from .config import DungeonConfig
from .rooms import Room, place_rooms
from .tiles import CAVE, DOOR, ROOM, TELEPORT, TUNNEL, WALL

SECRET_DOOR = "S"
LOCKED_DOOR = "L"

_WALKABLE = {ROOM, TUNNEL, DOOR, TELEPORT}
# Locked doors are logically passable (a key exists), so they count for connectivity.
_CONNECTED = {ROOM, TUNNEL, DOOR, LOCKED_DOOR, TELEPORT}


class Dungeon:
    def __init__(
        self,
        config: DungeonConfig | None = None,
        *,
        seed: int | None = None,
        size: Tuple[int, int, int] | None = None,
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
        self.config = config
        if self.config.seed is None:
            self.config.seed = random.randint(0, 2**31 - 1)
        self._rng = random.Random(self.config.seed)
        self.seed = self.config.seed
        self.size = (self.config.width, self.config.height, 1)
        self.grid: List[List[str]] = [[CAVE for _ in range(self.config.height)] for _ in range(self.config.width)]
        self.rooms: List[Room] = []
        self.room_types: List[str] = []
        self.metrics: Dict[str, Any] = {}
        self._generate()

    # ------------------------------------------------------------------
    def _generate(self):
        self._place_rooms()
        self._connect_rooms()
        connect_mod.derive_doors(self.grid)
        connect_mod.derive_walls(self.grid)
        self._assign_room_types()
        self._augment_doors_with_variants()
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

    def _connect_rooms(self):
        if len(self.rooms) <= 1:
            return
        centers = [r.center for r in self.rooms]
        edges = connect_mod.mst_edges(centers)
        edges += connect_mod.extra_edges(centers, edges, self._rng, self.config.extra_connection_chance)
        for a, b in edges:
            connect_mod.carve_corridor(self.grid, centers[a], centers[b], self._rng)

    # ---------------- Room typing ----------------
    def _assign_room_types(self):
        n = len(self.rooms)
        self.room_types = ["room"] * n
        if n == 0:
            return
        self.room_types[0] = "start"
        areas = sorted(((r.w * r.h, i) for i, r in enumerate(self.rooms)), reverse=True)
        largest = areas[0][1]
        treasure = areas[1][1] if n > 1 else largest
        if treasure != 0:
            self.room_types[treasure] = "treasure"
        if largest not in (0, treasure):
            self.room_types[largest] = "boss"
        # connector/deadend by door count (skip special rooms)
        w, h = self.config.width, self.config.height
        for idx, r in enumerate(self.rooms):
            if self.room_types[idx] in ("start", "boss", "treasure"):
                continue
            dc = 0
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                        dc += 1
            if dc <= 1:
                self.room_types[idx] = "deadend"
            elif dc >= 3:
                self.room_types[idx] = "connector"

    # ---------------- Door variants ----------------
    def _augment_doors_with_variants(self):
        if not self.rooms:
            return
        w, h = self.config.width, self.config.height
        room_doors: Dict[int, List[Tuple[int, int]]] = {}
        for i, r in enumerate(self.rooms):
            seen = set()
            for x, y in r.cells():
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == DOOR:
                        seen.add((nx, ny))
            if seen:
                room_doors[i] = sorted(seen)
        idx_boss = next((i for i, t in enumerate(self.room_types) if t == "boss"), None)
        # Lock a boss door only when the room has more than one door, so an
        # unlocked approach always remains and the room is never sealed off.
        if idx_boss is not None and len(room_doors.get(idx_boss, [])) > 1:
            x, y = self._rng.choice(room_doors[idx_boss])
            self.grid[x][y] = LOCKED_DOOR
        # Secret doors are placed only on REDUNDANT doors (loop edges): converting a
        # bridge door to a wall-like secret would sever the dungeon. We verify full
        # room connectivity (secrets treated as non-walkable) before committing each.
        sealed: set = set()
        for i, t in enumerate(self.room_types):
            if i == idx_boss:
                continue
            doors = room_doors.get(i, [])
            if len(doors) <= 1:
                continue  # never seal a room's only exit
            if t == "deadend":
                for x, y in doors[1:]:  # keep at least one normal door
                    if self._rng.random() < 0.3 and self._secret_keeps_connectivity(sealed | {(x, y)}):
                        self.grid[x][y] = SECRET_DOOR
                        sealed.add((x, y))
            elif t == "treasure":
                x, y = self._rng.choice(doors)
                if self._secret_keeps_connectivity(sealed | {(x, y)}):
                    self.grid[x][y] = SECRET_DOOR
                    sealed.add((x, y))

    def _secret_keeps_connectivity(self, blocked: set) -> bool:
        """True if every room is still reachable from the start room when the given
        cells (prospective secret doors) are treated as non-walkable."""
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
        unreachable = sum(1 for r in self.rooms if all((ix, iy) not in seen for ix, iy in r.cells()))
        self.metrics["unreachable_rooms"] = unreachable

    def _collect_counts(self):
        counts = {CAVE: 0, ROOM: 0, WALL: 0, TUNNEL: 0, DOOR: 0, SECRET_DOOR: 0, LOCKED_DOOR: 0}
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
                "secret_doors": counts[SECRET_DOOR],
                "locked_doors": counts[LOCKED_DOOR],
            }
        )
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
    "TELEPORT",
]

if __name__ == "__main__":
    d = Dungeon(seed=1234, size=(60, 60, 1))
    print(d.to_ascii())
    print(d.metrics)
