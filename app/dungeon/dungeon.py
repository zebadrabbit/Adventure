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
from .tiles import CAVE, ROOM, WALL, TUNNEL, DOOR
# Extended door variants (new). We won't alter existing tests; they treat DOOR as walkable.
SECRET_DOOR = 'S'  # hidden doorway (treated as wall until revealed)
LOCKED_DOOR = 'L'  # locked door (visible but requires key/logic; still walkable for now or optional rule)
from .config import DungeonConfig
from .rooms import Room, place_rooms
from . import tunnels as tunnels_mod

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
		self._compute_connectivity_metrics()
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
		door_counts = [0]*len(self.rooms)
		w,h = self.config.width, self.config.height
		for idx,r in enumerate(self.rooms):
			for (x,y) in r.cells():
				for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
					if 0<=nx<w and 0<=ny<h and self.grid[nx][ny] in (DOOR,):
						door_counts[idx]+=1
		# Sort rooms by area descending for special picks
		areas = [(r.w*r.h, i) for i,r in enumerate(self.rooms)]
		areas.sort(reverse=True)
		largest = areas[0][1]
		treasure = areas[1][1] if len(areas) > 1 else largest
		self.room_types = ['room'] * len(self.rooms)
		self.room_types[0] = 'start'
		if treasure != 0:
			self.room_types[treasure] = 'treasure'
		if largest not in (0, treasure):
			self.room_types[largest] = 'boss'
		# Pass 2: connector / deadend override (except start/boss/treasure)
		for i,dc in enumerate(door_counts):
			if self.room_types[i] in ('start','boss','treasure'):
				continue
			if dc <= 1:
				self.room_types[i] = 'deadend'
			elif dc >= 3:
				self.room_types[i] = 'connector'

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
		w,h = self.config.width, self.config.height
		# Map each door to (room_index)
		room_doors: Dict[int, List[Tuple[int,int]]] = {}
		for i,r in enumerate(self.rooms):
			for (x,y) in r.cells():
				for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
					if 0<=nx<w and 0<=ny<h and self.grid[nx][ny]==DOOR:
						room_doors.setdefault(i, []).append((nx,ny))
		# Deduplicate door coordinates per room
		for k,v in room_doors.items():
			room_doors[k] = sorted(set(v))
		# Pick boss / treasure / start indices
		idx_start = 0
		idx_boss = None
		idx_treasure = None
		for i,t in enumerate(self.room_types):
			if t=='boss': idx_boss=i
			elif t=='treasure': idx_treasure=i
		# Locked door on boss
		if idx_boss is not None and room_doors.get(idx_boss):
			choice = self._rng.choice(room_doors[idx_boss])
			x,y = choice
			self.grid[x][y] = LOCKED_DOOR
		# Secret doors on deadend rooms (prob ~0.3) & treasure room (one if multiple)
		for i,t in enumerate(self.room_types):
			if i==idx_boss: continue
			doors = room_doors.get(i, [])
			if not doors: continue
			if t=='deadend':
				for (x,y) in doors:
					if self._rng.random() < 0.3:
						self.grid[x][y] = SECRET_DOOR
			elif t=='treasure' and len(doors) > 1:
				(x,y) = self._rng.choice(doors)
				self.grid[x][y] = SECRET_DOOR

	# ---------------- Public helper to reveal secret doors -----------------------
	def reveal_secret_door(self, x:int, y:int) -> bool:
		"""Reveal a secret door at (x,y) converting SECRET_DOOR -> DOOR; returns True if changed."""
		if 0<=x<self.config.width and 0<=y<self.config.height and self.grid[x][y]==SECRET_DOOR:
			self.grid[x][y]=DOOR
			return True
		return False

	def is_walkable(self, x:int, y:int) -> bool:
		if not (0<=x<self.config.width and 0<=y<self.config.height):
			return False
		return self.grid[x][y] in (ROOM, TUNNEL, DOOR, LOCKED_DOOR)  # secret doors not walkable until revealed

	def _update_extended_metrics(self):
		# Count door variants & room type distribution
		counts = { 'secret_doors':0, 'locked_doors':0 }
		w,h = self.config.width, self.config.height
		for x in range(w):
			for y in range(h):
				if self.grid[x][y]==SECRET_DOOR: counts['secret_doors']+=1
				elif self.grid[x][y]==LOCKED_DOOR: counts['locked_doors']+=1
		room_type_counts: Dict[str,int] = {}
		for t in self.room_types:
			room_type_counts[t]=room_type_counts.get(t,0)+1
		self.metrics.update(counts)
		self.metrics['room_type_counts']=room_type_counts

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
		w,h = self.config.width, self.config.height
		for x in range(w):
			for y in range(h):
				if self.grid[x][y] == DOOR:
					# Only handle right/below to avoid re-processing pairs
					for nx,ny in ((x+1,y),(x,y+1)):
						if 0<=nx<w and 0<=ny<h and self.grid[nx][ny]==DOOR:
							# Decide demotion for (x,y)
							has_room = any(0<=ax<w and 0<=ay<h and self.grid[ax][ay]==ROOM for ax,ay in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
							has_tunnel = any(0<=ax<w and 0<=ay<h and self.grid[ax][ay]==TUNNEL for ax,ay in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
							if has_room and has_tunnel:
								# Keep neighbor as the official doorway, restore wall ring here
								# BUT if converting to WALL would sever a straight corridor continuation, prefer TUNNEL
								# Detect pattern: TUNNEL - DOOR(x,y demote) - DOOR(neighbor) or corridor axis continuing past neighbor.
								# Simple heuristic: if two opposite orthogonal cells relative to (x,y) are tunnels, keep continuity.
								orth = [((x+1,y),(x-1,y)), ((x,y+1),(x,y-1))]
								make_tunnel = False
								for (a,b) in orth:
									(ax,ay),(bx,by)=a,b
									if 0<=ax<w and 0<=ay<h and 0<=bx<w and 0<=by<h and self.grid[ax][ay]==TUNNEL and self.grid[bx][by]==TUNNEL:
										make_tunnel = True; break
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
		w,h = self.config.width, self.config.height
		to_fill = []
		for x in range(w):
			for y in range(h):
				if self.grid[x][y] != CAVE:
					continue
				# Count neighbors
				neighbors = [(nx,ny) for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)) if 0<=nx<w and 0<=ny<h]
				rooms = sum(1 for nx,ny in neighbors if self.grid[nx][ny]==ROOM)
				tunnels = sum(1 for nx,ny in neighbors if self.grid[nx][ny]==TUNNEL)
				# Pattern 3: one room + one tunnel, rest caves
				if rooms==1 and tunnels==1:
					to_fill.append((x,y)); continue
				# Pattern 2: straight corridor line with a missing center (check horizontal and vertical)
				# Horizontal T T C T or T C C T (we just check immediate neighbors both sides are tunnels)
				if ((0<=x-1<w and self.grid[x-1][y]==TUNNEL) and (0<=x+1<w and self.grid[x+1][y]==TUNNEL)):
					to_fill.append((x,y)); continue
				if ((0<=y-1<h and self.grid[x][y-1]==TUNNEL) and (0<=y+1<h and self.grid[x][y+1]==TUNNEL)):
					to_fill.append((x,y)); continue
				# Pattern 1: ROOM neighbor and tunnel two steps away in line: ROOM - CAVE(x,y) - CAVE? - TUNNEL or ROOM - WALL - CAVE(x,y) - TUNNEL
				for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
					ax,ay = x+dx, y+dy
					bx,by = x+2*dx, y+2*dy
					cx,cy = x+3*dx, y+3*dy
					if 0<=ax<w and 0<=ay<h and self.grid[ax][ay] in (ROOM,WALL):
						# look outward for tunnel
						if 0<=bx<w and 0<=by<h and self.grid[bx][by]==CAVE and 0<=cx<w and 0<=cy<h and self.grid[cx][cy]==TUNNEL:
							to_fill.append((x,y)); break
		# Apply changes
		for (x,y) in to_fill:
			# Safety: ensure converting to tunnel will not create a WALL with >1 tunnel neighbor (wall overwrite test).
			# Inspect adjacent walls; if any wall already has 1 tunnel neighbor and would gain a second because of this fill,
			# skip conversion.
			w,h = self.config.width, self.config.height
			create_violation = False
			for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
				if 0<=nx<w and 0<=ny<h and self.grid[nx][ny]==WALL:
					# count existing tunnel neighbors (excluding current cell which is still CAVE)
					cnt = 0
					for ax,ay in ((nx+1,ny),(nx-1,ny),(nx,ny+1),(nx,ny-1)):
						if 0<=ax<w and 0<=ay<h and self.grid[ax][ay]==TUNNEL:
							cnt += 1
					if cnt >= 1:  # adding one more would make >=2
						create_violation = True; break
			if not create_violation:
				self.grid[x][y] = TUNNEL

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
	'CAVE','ROOM','WALL','TUNNEL','DOOR','SECRET_DOOR','LOCKED_DOOR'
]

if __name__ == '__main__':  # manual quick smoke
	d = Dungeon(seed=1234, size=(60,60,1))
	print(d.to_ascii())
	print(d.metrics)
