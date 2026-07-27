# Maze Generation Rewrite + Multi-Floor Dungeons

Date: 2026-07-27. Status: approved (design discussed and accepted in session).

## Problem

Current generator (8–14 rooms on 75×75, MST + L-corridors between room centers)
produces sparse maps (~25% coverage), very long straight corridors, and
predictable layouts. Single floor only. No structured completion goal.

## Goals

1. High map utilization (≥50% of tiles walkable-or-wall, target ~60% room+corridor coverage of the interior).
2. No straight corridor run longer than 10 tiles.
3. Multi-floor dungeons: stack of independently generated 2D floors linked by stairs.
4. Guaranteed completable: deepest floor has a boss and a loot room; killing the
   final boss makes the loot room enterable and the portal back to the lobby usable.

## Non-goals

Cross-floor stair alignment, WFC/prefab rooms, per-floor themes, spawn system
redesign, frontend visual overhaul.

## Design

### 1. Per-floor generation — "rooms and mazes" (Nystrom style)

Replaces internals of `app/dungeon/rooms.py` + `app/dungeon/connect.py`;
`Dungeon` public contract unchanged (`grid[x][y]`, `rooms`, `room_types`,
`metrics`, `is_walkable`, `to_json`, `to_ascii`, tile chars).

Pipeline per floor:

1. **Dense room packing**: many attempts of odd-aligned rectangular rooms
   (odd sizes ~5–11), 1-tile wall gaps, until attempts exhausted. Rooms are
   distinct union-find regions.
2. **Maze fill**: growing-tree/recursive-backtracker maze through all remaining
   odd-aligned cells. Windiness bias plus a hard rule: after 10 straight cells
   the carver must turn. Each maze component is a region.
3. **Region connect**: find all wall cells separating two regions; open one
   connector (DOOR when room↔corridor, TUNNEL when corridor↔corridor) per
   region pair via union-find until fully connected; small chance (~10%) to
   open extra connectors for loops. Connectivity guaranteed by construction.
4. **Dead-end culling**: retract ~80% of maze dead ends (repeatedly remove
   TUNNEL cells with 3+ solid neighbors), keeping winding purposeful corridors.
5. **Walls**: CAVE adjacent to ROOM becomes WALL (unchanged behavior).
6. **Room typing + door variants**: as today (start/boss/treasure/deadend/
   connector, secret/locked doors with connectivity checks), with floor-aware
   placement (below).

### 2. Floors and stairs

- `DungeonConfig` gains `floor: int = 0`, `num_floors: int = 1`.
- Floor z of a dungeon uses RNG seed `floor_seed(base_seed, z)` (deterministic
  mix, stable across processes). `Dungeon` remains one 2D floor.
- New tiles: `<` STAIRS_UP, `>` STAIRS_DOWN (walkable). Floor 0: `>` only
  (entry is the lobby portal). Deepest floor: `<` only. Middle floors: both.
  Stairs are placed in room cells far apart from each other.
- Floor count scales with tier: `num_floors(tier) = min(1 + (tier + 1) // 2, 5)`
  → T1–2: 2, T3–4: 3, T5–6: 4, T7: 5.
- Movement: stepping onto `>` moves the party to floor z+1 at that floor's `<`
  tile (and vice versa). `pos_z` already exists on `DungeonInstance`.
- All per-floor state reuses existing seed-keyed systems by passing the floor
  seed instead of the base seed: dungeon cache, explored tiles, visibility.
  Helper `get_instance_dungeon(instance)` returns the current floor's Dungeon.

### 3. Completion: boss → loot room → portal

- Boss room and treasure ("loot") room are placed only on the deepest floor.
  `bosses_total = 1`; the single boss spawns in the deepest floor's boss room.
  Other floors get elites/ambient spawns only.
- Loot room doors are LOCKED_DOOR at generation; exposed as
  `dungeon.loot_room_doors`. They unlock when `extraction_available` flips
  (existing final-boss-kill hook in combat_service) — movement treats them as
  unlocked when `instance.extraction_available` is true.
- Portal tile `P` sits at the loot room center. Stepping on it with
  `extraction_available` returns the party via the existing extraction flow;
  movement response flags `portal: true` so the client can offer it.

### 4. Spawns per floor

- `SpawnEntry`/`DungeonEntity` already carry `z`. SpawnManager operates on the
  current floor: spawns created with `z = instance.pos_z`, loading filters by z,
  and each floor initializes its spawns on first visit.
- Boss count: 1 on deepest floor, 0 elsewhere.

## Testing

Property tests over ~50 seeds and all floors:
- fully connected (every ROOM/TUNNEL/DOOR reachable from spawn),
- no straight corridor run > 10 tiles,
- interior coverage ≥ 50%,
- stairs present/paired per floor position (0 / middle / deepest),
- deepest floor has boss + loot room; loot room unreachable while its locked
  doors are locked; reachable when treated unlocked; portal tile inside.
Existing dungeon suite stays green (public contract unchanged).
