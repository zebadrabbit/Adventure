# Adventure Architecture

```mermaid
graph TD
  A[Client Browser] -->|HTTP/HTTPS| B[Flask App]
  A -->|WebSocket| S[Socket.IO]
  B -->|Blueprints| R1[auth]
  B --> R2[main]
  B --> R3[dashboard]
  B --> R4[dungeon_api]
  B --> R5[seed_api]
  B --> R6[config_api]
  B -->|ORM| DB[(SQLite / SQLAlchemy)]
  S --> B
  subgraph Generation
    G1[Dungeon Pipeline\n(seed -> grid)] --> G2[Door Repair & Invariants]
  end
  R4 -->|uses| G1
  R4 -->|uses| G2
```

## Components
- **Flask Blueprints**: Modular route grouping (auth, main site, dashboard UI, dungeon APIs, seed management, config exposure).
- **Socket.IO**: Real-time events (lobby/gameplay expansion) sharing app context.
- **Dungeon Generation**: Deterministic multi-phase pipeline (see README) producing cached `Dungeon` instances keyed by (seed,size).
- **Persistence**: `DungeonInstance` stores seed and player position; other models hold user & progression data.
- **Pre-Commit Tooling**: Enforces frontend hygiene (no inline styles/scripts, cache-busting helper usage) to keep diffs clean.

## Request Flow (Map Fetch)
1. Client calls `/api/dungeon/seed` (POST) to set or regenerate a seed.
2. Client retrieves `/api/dungeon/map`.
3. Server loads or creates `DungeonInstance`, fetches cached `Dungeon`, applies entrance relocation if needed.
4. Returns 2D grid + player position + seed.
5. Client optionally calls `/api/dungeon/state` to populate description & exits before movement.

## Movement Flow
1. Client posts `/api/dungeon/move` with direction.
2. Server validates walkable cell; updates `DungeonInstance` coordinates.
3. Returns new position, description, exits.

## Determinism & Caching
- Seed hashing (string -> first 8 bytes of SHA-256) ensures reproducibility.
- In-process cache stores recent Dungeon objects (LRU-ish manual cap) minimizing regeneration cost.

## Extension Points
- Feature Assignment Phase can inject encounter hooks, loot tables, biome theming.
- Socket.IO channels for party chat, combat events, live admin monitoring.
- Additional blueprints for stats, leaderboards, content authoring.

## Security Considerations
- Login required for all dungeon/seed routes.
- Future: rate-limit movement, sanitize user-generated content, add CSRF tokens for form endpoints.

## Testing Strategy Link
See README "Testing & Invariants" section for invariant coverage (door rules, seed persistence) and regeneration determinism.
