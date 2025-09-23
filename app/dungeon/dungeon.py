"""Dungeon Generator (Conceptual Adaptation of donjon.pl)

This module provides a fresh procedural dungeon generator designed for the
Adventure MUD grid. It is an original Python implementation inspired by the
high-level ideas of the donjon (https://donjon.bin.sh) dungeon algorithm:
	* Scatter non-overlapping rooms
	* Build perimeter walls
	* Connect rooms with a minimum spanning tree plus occasional extra links
	* Carve corridors while preserving wall rings (doors instead of wall erasure)
	* Optionally prune dead-end corridor stubs

No Perl source code is copied; only overall procedural concepts are adapted.

Public contract expected elsewhere in the codebase:
  Dungeon(seed: int|None = None, size=(W,H,1)) OR Dungeon(DungeonConfig(...))
  Attributes: grid[x][y], rooms, config, metrics (dict), size, seed
  Tiles: 'C' (CAVE), 'R' (ROOM), 'W' (WALL), 'T' (TUNNEL), 'D' (DOOR)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Iterable
import random
from collections import deque

# Support modules (kept under old/ directory currently)
from .old.tiles import CAVE, ROOM, WALL, TUNNEL, DOOR
from .old.config import DungeonConfig
from .old.rooms import Room, place_rooms
from .old import tunnels as tunnels_mod

@dataclass
class _DoorCandidate:
	x: int
	y: int
	room_index: int


class Dungeon:
	def __init__(self, config: DungeonConfig | None = None, *, seed: int | None = None, size: Tuple[int,int,int] | None = None, **_legacy):
		# Accept either config object or legacy (seed,size) call style
		if config is None:
			width = 75; height = 75
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
			self.config.seed = random.randint(0, 2**31-1)
		# Local RNG so external random usage does not affect generation
		self._rng = random.Random(self.config.seed)
		self.seed = self.config.seed
		self.size = (self.config.width, self.config.height, 1)
		# 2D grid (column-major: grid[x][y]) consistent with existing code expectations
		self.grid: List[List[str]] = [[CAVE for _ in range(self.config.height)] for _ in range(self.config.width)]
		self.rooms: List[Room] = []
		self.metrics: Dict[str, Any] = {}
		self._generate()

	# ------------------------------------------------------------------
	# Generation Pipeline
	# ------------------------------------------------------------------
	def _generate(self):
		self._place_rooms()
		self._build_wall_rings()
		self._connect_rooms()
		self._prune_dead_ends(max_iterations=2)
		self._door_sanity_pass()
		self._compute_connectivity_metrics()
		self._collect_counts()

	# ------------------------------------------------------------------
	# Rooms
	# ------------------------------------------------------------------
	def _place_rooms(self):
		rooms, target, placed = place_rooms(self.grid, self.config)
		self.rooms = rooms
		self.metrics['rooms_attempted'] = target
		self.metrics['rooms_placed'] = placed

	def _build_wall_rings(self):
		w = self.config.width; h = self.config.height
		for r in self.rooms:
			# Mark perimeter walls (outer ring) only where current tile is still CAVE
			for ix in range(r.x - 1, r.x + r.w + 1):
				for iy in range(r.y - 1, r.y + r.h + 1):
					if 0 <= ix < w and 0 <= iy < h:
						if self.grid[ix][iy] == CAVE:
							# Only convert if adjacent (orthogonal) to a room interior
							if any(0 <= nx < w and 0 <= ny < h and self.grid[nx][ny] == ROOM for nx,ny in ((ix+1,iy),(ix-1,iy),(ix,iy+1),(ix,iy-1))):
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
		w,h = self.config.width, self.config.height
		for _ in range(max_iterations):
			removed_any = False
			for x in range(w):
				for y in range(h):
					if self.grid[x][y] == TUNNEL:
						# Count orthogonal walkable neighbors (tunnel or door)
						neighbors = [(nx,ny) for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)) if 0<=nx<w and 0<=ny<h and self.grid[nx][ny] in (TUNNEL, DOOR)]
						if len(neighbors) <= 1:
							# Protect corridor tiles that directly touch a room (potential doorway position)
							if any(0<=nx<w and 0<=ny<h and self.grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))):
								continue
							# Leaf; ensure not adjacent to a door leading into a room (keep those)
							if not any(self.grid[nx][ny] == DOOR for nx,ny in neighbors):
								self.grid[x][y] = CAVE
								removed_any = True
			if not removed_any:
				break

	# ------------------------------------------------------------------
	# Door sanity: ensure each DOOR has a room and a tunnel; demote invalid doors
	# ------------------------------------------------------------------
	def _door_sanity_pass(self):
		w,h = self.config.width, self.config.height
		for x in range(w):
			for y in range(h):
				if self.grid[x][y] == DOOR:
					has_room = any(0<=nx<w and 0<=ny<h and self.grid[nx][ny]==ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
					has_tunnel = any(0<=nx<w and 0<=ny<h and self.grid[nx][ny]==TUNNEL for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
					if not (has_room and has_tunnel):
						# If it borders a room, revert to WALL else revert to CAVE
						self.grid[x][y] = WALL if has_room else CAVE

	# ------------------------------------------------------------------
	# Connectivity / metrics
	# ------------------------------------------------------------------
	def _compute_connectivity_metrics(self):
		# BFS from first room center to check reachable rooms
		if not self.rooms:
			self.metrics['unreachable_rooms'] = 0
			return
		start = self.rooms[0].center
		walkable = {ROOM, TUNNEL, DOOR}
		w,h = self.config.width, self.config.height
		q = deque([start])
		seen = {start}
		while q:
			x,y = q.popleft()
			for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
				if 0<=nx<w and 0<=ny<h and (nx,ny) not in seen and self.grid[nx][ny] in walkable:
					seen.add((nx,ny)); q.append((nx,ny))
		unreachable = 0
		for r in self.rooms:
			# If none of the interior tiles are reachable, count as unreachable
			if all((ix,iy) not in seen for ix,iy in r.cells()):
				unreachable += 1
		self.metrics['unreachable_rooms'] = unreachable

	def _collect_counts(self):
		counts={CAVE:0, ROOM:0, WALL:0, TUNNEL:0, DOOR:0}
		w,h=self.config.width,self.config.height
		for x in range(w):
			for y in range(h):
				t=self.grid[x][y]
				counts[t]=counts.get(t,0)+1
		self.metrics.update({
			'seed': self.seed,
			'rooms': len(self.rooms),
			'tiles_cave': counts[CAVE],
			'tiles_room': counts[ROOM],
			'tiles_wall': counts[WALL],
			'tiles_tunnel': counts[TUNNEL],
			'tiles_door': counts[DOOR],
		})

	# Convenience outputs
	def to_ascii(self) -> str:
		return "\n".join(''.join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height))

	def to_json(self) -> Dict[str, Any]:
		return {
			'seed': self.seed,
			'width': self.config.width,
			'height': self.config.height,
			'grid': [''.join(self.grid[x][y] for x in range(self.config.width)) for y in range(self.config.height)],
			'metrics': self.metrics,
		}

__all__ = [
	'Dungeon', 'DungeonConfig',
	'CAVE','ROOM','WALL','TUNNEL','DOOR'
]

if __name__ == '__main__':  # manual quick smoke
	d = Dungeon(seed=1234, size=(60,60,1))
	print(d.to_ascii())
	print(d.metrics)
