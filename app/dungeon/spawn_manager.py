"""Dungeon Spawn Management System.

Provides a configurable, deterministic spawn system for managing entities in dungeons.
Replaces the old ad-hoc spawning logic with a structured, time-based approach.

Features:
- Ambient spawns (random encounters in walkable areas)
- Patrol spawns (monsters that move on game clock ticks)
- Elite spawns (positioned in specific rooms/chokepoints)
- Boss spawns (in boss lairs with guaranteed positioning)
- Movement scheduling based on game clock

Architecture:
- SpawnConfig: Configuration dataclass for spawn parameters
- SpawnBehavior: Enum defining spawn behavior types
- SpawnEntry: Individual spawn tracking with position and behavior
- SpawnManager: Central manager coordinating all spawns for a dungeon instance
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from app.dungeon.dungeon import Dungeon
    from app.models.dungeon_instance import DungeonInstance


__all__ = ["SpawnManager", "SpawnConfig", "SpawnBehavior", "SpawnEntry"]


class SpawnBehavior(Enum):
    """Entity spawn behavior types."""

    AMBIENT = "ambient"  # Randomly placed, no movement
    PATROL = "patrol"  # Moves periodically based on game clock
    GUARD = "guard"  # Stays in place, but aggros on proximity
    ELITE = "elite"  # Positioned strategically, patrol behavior
    BOSS = "boss"  # Fixed position in boss room, no movement
    WANDERER = "wanderer"  # Random walk pattern, ignores patrol routes


@dataclass
class SpawnConfig:
    """Configuration for spawn system."""

    # Density controls
    ambient_density: float = 0.004  # Spawns per walkable tile (~4 per 1000 tiles)
    elite_per_region: int = 2  # Elites per major region
    boss_per_dungeon: int = 1  # Bosses per dungeon (increases with tier)

    # Behavior probabilities
    patrol_chance: float = 0.40  # % of ambient spawns that patrol
    guard_chance: float = 0.20  # % of ambient spawns that guard
    wanderer_chance: float = 0.10  # % of ambient spawns that wander

    # Movement settings
    patrol_interval_ticks: int = 5  # Ticks between patrol movements
    wander_interval_ticks: int = 3  # Ticks between wander movements
    patrol_range: int = 8  # Max distance from spawn point for patrols

    # Level scaling
    min_spawns: int = 4  # Minimum spawns regardless of density
    max_spawns: int = 30  # Maximum spawns per dungeon

    # Boss settings
    boss_room_buffer: int = 5  # Min distance from boss to entrance

    def __post_init__(self):
        """Validate configuration values."""
        self.ambient_density = max(0.0, min(1.0, self.ambient_density))
        self.patrol_chance = max(0.0, min(1.0, self.patrol_chance))
        self.guard_chance = max(0.0, min(1.0, self.guard_chance))
        self.wanderer_chance = max(0.0, min(1.0, self.wanderer_chance))


@dataclass
class SpawnEntry:
    """Individual spawn tracking with behavior and state."""

    x: int
    y: int
    z: int = 0
    behavior: SpawnBehavior = SpawnBehavior.AMBIENT
    archetype: str = "Trash"  # Enemy archetype (Trash, Elite, Boss, etc.)
    level: int = 1
    slug: Optional[str] = None
    name: Optional[str] = None
    hp_current: Optional[int] = None
    hp_max: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    # Behavior state
    spawn_x: int = 0  # Original spawn position for patrol range
    spawn_y: int = 0
    last_move_tick: int = 0  # Last game clock tick when moved
    move_interval: int = 5  # Ticks between movements
    patrol_route: List[Tuple[int, int]] = field(default_factory=list)  # Planned patrol waypoints
    in_combat: bool = False  # Locked during combat

    def __post_init__(self):
        """Initialize spawn position tracking."""
        if self.spawn_x == 0 and self.spawn_y == 0:
            self.spawn_x = self.x
            self.spawn_y = self.y

    def to_dict(self) -> Dict[str, Any]:
        """Serialize spawn entry for storage."""
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "behavior": self.behavior.value,
            "archetype": self.archetype,
            "level": self.level,
            "slug": self.slug,
            "name": self.name,
            "hp_current": self.hp_current,
            "hp_max": self.hp_max,
            "data": self.data,
            "spawn_x": self.spawn_x,
            "spawn_y": self.spawn_y,
            "last_move_tick": self.last_move_tick,
            "move_interval": self.move_interval,
            "patrol_route": self.patrol_route,
            "in_combat": self.in_combat,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpawnEntry":
        """Deserialize spawn entry from storage."""
        behavior_str = data.get("behavior", "ambient")
        behavior = SpawnBehavior(behavior_str) if isinstance(behavior_str, str) else SpawnBehavior.AMBIENT

        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            z=data.get("z", 0),
            behavior=behavior,
            archetype=data.get("archetype", "Trash"),
            level=data.get("level", 1),
            slug=data.get("slug"),
            name=data.get("name"),
            hp_current=data.get("hp_current"),
            hp_max=data.get("hp_max"),
            data=data.get("data", {}),
            spawn_x=data.get("spawn_x", data.get("x", 0)),
            spawn_y=data.get("spawn_y", data.get("y", 0)),
            last_move_tick=data.get("last_move_tick", 0),
            move_interval=data.get("move_interval", 5),
            patrol_route=data.get("patrol_route", []),
            in_combat=data.get("in_combat", False),
        )


class SpawnManager:
    """Manages all entity spawns for a dungeon instance."""

    def __init__(
        self,
        dungeon: "Dungeon",
        instance: "DungeonInstance",
        config: Optional[SpawnConfig] = None,
        rng: Optional[random.Random] = None,
    ):
        """Initialize spawn manager.

        Args:
            dungeon: Dungeon layout object
            instance: DungeonInstance for persistence
            config: Spawn configuration (uses defaults if None)
            rng: Random number generator (deterministic with seed)
        """
        self.dungeon = dungeon
        self.instance = instance
        self.config = config or SpawnConfig()
        self.rng = rng or random.Random(instance.seed ^ 0x5341574E)  # ^ "SPAWN"

        self.spawns: List[SpawnEntry] = []
        self._initialized = False

    def initialize_spawns(self, party_level: int = 1) -> List[SpawnEntry]:
        """Generate all spawns for the dungeon.

        Args:
            party_level: Average party level for scaling

        Returns:
            List of created spawn entries
        """
        if self._initialized:
            return self.spawns

        self.spawns = []

        # Calculate spawn counts
        walkable_tiles = self._get_walkable_tiles()
        total_spawns = self._calculate_spawn_count(len(walkable_tiles))

        # Allocate spawn types
        boss_count = self._calculate_boss_count()
        elite_count = self._calculate_elite_count()
        ambient_count = total_spawns - boss_count - elite_count

        # Generate spawns
        self._generate_boss_spawns(party_level, boss_count)
        self._generate_elite_spawns(party_level, elite_count)
        self._generate_ambient_spawns(party_level, ambient_count, walkable_tiles)

        self._initialized = True
        return self.spawns

    def update_spawns(self, current_tick: int) -> List[SpawnEntry]:
        """Update spawn positions based on game clock.

        Args:
            current_tick: Current game clock tick

        Returns:
            List of spawns that moved this update
        """
        moved_spawns = []

        for spawn in self.spawns:
            if spawn.in_combat:
                continue

            # Check if spawn should move
            if not self._should_move(spawn, current_tick):
                continue

            # Move based on behavior
            old_x, old_y = spawn.x, spawn.y

            if spawn.behavior == SpawnBehavior.PATROL:
                self._move_patrol(spawn)
            elif spawn.behavior == SpawnBehavior.WANDERER:
                self._move_wanderer(spawn)

            # Track movement
            if (spawn.x, spawn.y) != (old_x, old_y):
                spawn.last_move_tick = current_tick
                moved_spawns.append(spawn)

        return moved_spawns

    def get_spawn_at(self, x: int, y: int, z: int = 0) -> Optional[SpawnEntry]:
        """Find spawn at coordinates."""
        for spawn in self.spawns:
            if spawn.x == x and spawn.y == y and spawn.z == z:
                return spawn
        return None

    def remove_spawn(self, spawn: SpawnEntry) -> bool:
        """Remove a spawn (e.g., when defeated)."""
        try:
            self.spawns.remove(spawn)
            return True
        except ValueError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize spawn manager state."""
        return {
            "spawns": [s.to_dict() for s in self.spawns],
            "initialized": self._initialized,
        }

    @classmethod
    def from_dict(cls, dungeon: "Dungeon", instance: "DungeonInstance", data: Dict[str, Any]) -> "SpawnManager":
        """Deserialize spawn manager state."""
        manager = cls(dungeon, instance)
        manager._initialized = data.get("initialized", False)
        manager.spawns = [SpawnEntry.from_dict(s) for s in data.get("spawns", [])]
        return manager

    # Private helper methods

    def _get_walkable_tiles(self) -> List[Tuple[int, int]]:
        """Get all walkable coordinates from dungeon."""
        from app.dungeon.tiles import DOOR, ROOM, TUNNEL

        walkable_chars = {ROOM, TUNNEL, DOOR}
        tiles = []

        for x in range(self.dungeon.config.width):
            for y in range(self.dungeon.config.height):
                if self.dungeon.grid[x][y] in walkable_chars:
                    tiles.append((x, y))

        return tiles

    def _calculate_spawn_count(self, walkable_count: int) -> int:
        """Calculate total spawns based on density and limits."""
        density_spawns = int(walkable_count * self.config.ambient_density)
        return max(self.config.min_spawns, min(self.config.max_spawns, density_spawns))

    def _calculate_boss_count(self) -> int:
        """Calculate boss spawns based on tier."""
        tier = getattr(self.instance, "tier", 1) or 1
        base = self.config.boss_per_dungeon

        # Scale with tier: T1=1, T3=2, T5=3, T7=4
        return base + (tier - 1) // 2

    def _calculate_elite_count(self) -> int:
        """Calculate elite spawns based on dungeon size."""
        room_count = len(self.dungeon.rooms) if hasattr(self.dungeon, "rooms") else 8
        regions = max(1, room_count // 4)  # 1 region per 4 rooms
        return regions * self.config.elite_per_region

    def _generate_boss_spawns(self, party_level: int, count: int):
        """Generate boss spawns in boss rooms."""
        if not hasattr(self.dungeon, "rooms") or not hasattr(self.dungeon, "room_types"):
            return

        # Find boss rooms
        boss_rooms = [
            self.dungeon.rooms[i] for i, room_type in enumerate(self.dungeon.room_types) if room_type == "boss"
        ]

        for i in range(min(count, len(boss_rooms))):
            room = boss_rooms[i]
            # Place boss in center of room
            x = room.x + room.w // 2
            y = room.y + room.h // 2

            spawn = SpawnEntry(
                x=x,
                y=y,
                behavior=SpawnBehavior.BOSS,
                archetype="Boss",
                level=party_level + 2,  # Bosses are higher level
            )

            self.spawns.append(spawn)

    def _generate_elite_spawns(self, party_level: int, count: int):
        """Generate elite spawns at strategic locations."""
        if not hasattr(self.dungeon, "rooms") or not hasattr(self.dungeon, "room_types"):
            return

        # Find connector rooms (high traffic areas)
        connector_rooms = [
            self.dungeon.rooms[i] for i, room_type in enumerate(self.dungeon.room_types) if room_type == "connector"
        ]

        # Add treasure rooms as elite spawn locations
        treasure_rooms = [
            self.dungeon.rooms[i] for i, room_type in enumerate(self.dungeon.room_types) if room_type == "treasure"
        ]

        candidate_rooms = connector_rooms + treasure_rooms
        self.rng.shuffle(candidate_rooms)

        for i in range(min(count, len(candidate_rooms))):
            room = candidate_rooms[i]
            # Place near entrance of room
            x = room.x + 1
            y = room.y + 1

            spawn = SpawnEntry(
                x=x,
                y=y,
                behavior=SpawnBehavior.ELITE,
                archetype="Elite",
                level=party_level + 1,  # Elites are slightly higher level
                move_interval=self.config.patrol_interval_ticks,
            )

            self.spawns.append(spawn)

    def _generate_ambient_spawns(self, party_level: int, count: int, walkable_tiles: List[Tuple[int, int]]):
        """Generate ambient monster spawns."""
        if count <= 0 or not walkable_tiles:
            return

        # Sample random walkable tiles
        sample_size = min(count, len(walkable_tiles))
        selected_tiles = self.rng.sample(walkable_tiles, sample_size)

        for x, y in selected_tiles:
            # Roll behavior
            roll = self.rng.random()

            if roll < self.config.patrol_chance:
                behavior = SpawnBehavior.PATROL
                move_interval = self.config.patrol_interval_ticks
            elif roll < self.config.patrol_chance + self.config.wanderer_chance:
                behavior = SpawnBehavior.WANDERER
                move_interval = self.config.wander_interval_ticks
            elif roll < self.config.patrol_chance + self.config.wanderer_chance + self.config.guard_chance:
                behavior = SpawnBehavior.GUARD
                move_interval = 999  # Guards don't move
            else:
                behavior = SpawnBehavior.AMBIENT
                move_interval = 999  # Ambient don't move

            spawn = SpawnEntry(
                x=x,
                y=y,
                behavior=behavior,
                archetype="Trash",  # Default archetype
                level=party_level,
                move_interval=move_interval,
            )

            self.spawns.append(spawn)

    def _should_move(self, spawn: SpawnEntry, current_tick: int) -> bool:
        """Check if spawn should move this tick."""
        if spawn.behavior in (SpawnBehavior.AMBIENT, SpawnBehavior.GUARD, SpawnBehavior.BOSS):
            return False

        ticks_elapsed = current_tick - spawn.last_move_tick
        return ticks_elapsed >= spawn.move_interval

    def _move_patrol(self, spawn: SpawnEntry):
        """Move a patrolling spawn."""
        from app.dungeon.tiles import DOOR, ROOM, TUNNEL

        walkable_chars = {ROOM, TUNNEL, DOOR}

        # Simple patrol: move randomly within range of spawn point
        distance = abs(spawn.x - spawn.spawn_x) + abs(spawn.y - spawn.spawn_y)

        # If too far, move back toward spawn point
        if distance >= self.config.patrol_range:
            dx = 1 if spawn.spawn_x > spawn.x else -1 if spawn.spawn_x < spawn.x else 0
            dy = 1 if spawn.spawn_y > spawn.y else -1 if spawn.spawn_y < spawn.y else 0
        else:
            # Random walk
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            dx, dy = self.rng.choice(directions)

        new_x = spawn.x + dx
        new_y = spawn.y + dy

        # Validate movement
        if 0 <= new_x < self.dungeon.config.width and 0 <= new_y < self.dungeon.config.height:
            if self.dungeon.grid[new_x][new_y] in walkable_chars:
                # Check if another spawn is there
                if not self.get_spawn_at(new_x, new_y):
                    spawn.x = new_x
                    spawn.y = new_y

    def _move_wanderer(self, spawn: SpawnEntry):
        """Move a wandering spawn (random walk)."""
        from app.dungeon.tiles import DOOR, ROOM, TUNNEL

        walkable_chars = {ROOM, TUNNEL, DOOR}

        # Pure random walk
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        dx, dy = self.rng.choice(directions)

        new_x = spawn.x + dx
        new_y = spawn.y + dy

        # Validate movement
        if 0 <= new_x < self.dungeon.config.width and 0 <= new_y < self.dungeon.config.height:
            if self.dungeon.grid[new_x][new_y] in walkable_chars:
                # Check if another spawn is there
                if not self.get_spawn_at(new_x, new_y):
                    spawn.x = new_x
                    spawn.y = new_y
