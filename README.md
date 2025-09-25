# Adventure

_Formerly: Adventure MUD (Multi-User Dungeon)_

[![CI](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml/badge.svg)](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml)

A modern web-based multiplayer dungeon adventure game built with Python (Flask, Flask-SocketIO), SQLite, and Bootstrap.

## Experimental Generator Invariants (Current Phase)
The dungeon generator is in an experimental phase introducing room type semantics and secret/locked door variants. During this phase several legacy guarantees are intentionally relaxed:
- Full reachability: A small number of rooms may be unreachable; tests track this with xfail markers rather than hard failures.
- Strict per-seed structural determinism: High-level metrics (seed echo, >0 rooms) remain stable, but exact room counts and layout may fluctuate while augmentation ordering is stabilized.
- Movement guarantees: Immediate movement in a direction may no-op more often; API focuses on correctness (no error) over forced displacement.
- Advanced pruning metrics: Legacy metrics (`door_clusters_reduced`, `tunnels_pruned`, etc.) may be absent or zeroed.

Temporary test strategy:
- Deprecated strict tests converted to `xfail` (non-strict) for visibility without blocking CI.
- A soft determinism smoke test ensures seeds echo and basic metrics are sensible; mismatch in room count triggers an xfail instead of failure.

Roadmap to re-tighten invariants:
1. Enforce deterministic ordering for augmentation passes (sort candidate collections before RNG draws).
2. Introduce a bounded unreachable ratio (< 5%) test to replace full reachability assertion.
3. Reinstate door cluster pruning with deterministic selection logic.
4. Replace movement no-op tolerance with directional intent validation once pathing heuristics mature.

---

## Loot System (Experimental)
The new loot subsystem introduces level-aware, rarity-weighted item placements generated lazily the first time a dungeon map is requested for a given seed. Loot nodes are deterministic per seed (placement coordinates and item selection derive from a PRNG seeded with `seed ^ 0xA5F00D`) yet responsive to party progression via an average party level window (±2 levels). This keeps rewards relevant while preserving replay determinism for a given progression state.

### Item Metadata
`Item` records now include:
* `level` (int, 0 = utility/no-scaling items like basic potions or tools)
* `rarity` (enum string) – one of: `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythic`

Bulk item seeds (weapons, armor, potions, misc) live under `sql/`. Startup loads these `.sql` files idempotently; items without explicit `level`/`rarity` fallback to heuristic inference (name keywords) until the SQL is enriched with explicit columns. You can safely re-run the server; existing slugs are skipped.

### Rarity Weights
Current default relative spawn weights (higher = more common):
```
common: 100
uncommon: 55
rare: 25
epic: 10
legendary: 3
mythic: 1
```
These weights apply within the candidate item pool after level filtering. Adjusting them changes the expected long-run distribution but individual dungeons remain small samples (streaks possible). Future tuning will surface these in a config table / admin UI.

### Placement Algorithm (Summary)
1. Determine average party level (simple mean of active characters; placeholder currently – may extend to median or weighted).
2. Compute level window `(avg-2, avg+2)` clamped to `[1,20]`.
3. Candidate pool: all items whose `level` is inside the window OR `level==0` (utility) to avoid starving baseline supplies.
4. Determine target loot node count: baseline (24) + small area scaler (≤ +10) but never more than 15% of walkable tiles.
5. Shuffle walkable tiles deterministically; keep a `spread_factor` slice (default 0.85) to reduce clustering bias.
6. Select every Nth tile to reach target count, skipping coordinates already containing loot (idempotence).
7. Weighted rarity roulette to assign one item per chosen tile.
8. Persist placements to `dungeon_loot`.

Calling the generator again for the same seed is idempotent: existing `(x,y,z)` rows are detected and not duplicated.

### API Endpoints
```
GET  /api/dungeon/loot                -> { loot: [ {id,x,y,z,slug,name,rarity,level}, ... ] }
POST /api/dungeon/loot/claim/<id>     -> { claimed: true, item: { slug, name } }
```
Both require authentication; claiming currently lacks proximity checks (TODO) and simply marks the node claimed. Claimed loot disappears from subsequent list calls.

### Tuning Knobs (Current / Planned)
| Knob | Status | Effect |
|------|--------|--------|
| `desired_chests` | code constant | Baseline loot node target per map before scaling |
| `spread_factor` | code constant | Fraction of shuffled walkables considered for sampling (lower = more dispersed) |
| Rarity weights | code constant | Relative frequency among candidate pool |
| Level window width | fixed (±2) | Determines progression tightness; wider window dilutes relevance |
| Max tile density (15%) | code constant | Upper bound on loot saturation to avoid clutter |
| Heuristic inference | startup function | Temporary level/rarity assignment for legacy SQL without metadata |

Planned future surfacing: move these constants into a `game_config` table with admin editing or environment overrides, plus per-depth modifiers (e.g., deeper seeds bias toward higher rarity).

### Extending
To add new items with explicit metadata, update (or create) an `.sql` file including `level` and `rarity` columns, or insert via an admin management route (future). Re-run the server; migration logic will not duplicate rows.

### Testing Strategy
Upcoming tests will validate:
* Idempotence (second generation produces zero new rows).
* Presence of at least one loot item for typical map sizes.
* Rarity distribution sanity over a batched seed sample (statistical tolerance, not strict).
* Level window filtering (no items above `avg+2`).

### Roadmap
1. Proximity & line-of-sight checks for claiming.
2. Inventory integration (add claimed item to character stash / equipment slots where relevant).
3. Config-surfaced rarity weights & dynamic scaling by dungeon depth or seed entropy.
4. Explicit SQL seed metadata (remove heuristic inference fallback).
5. Weighted drop tables by item type (e.g., potion bias in early levels).

---

## Features
- User authentication (login/register)
- Character management (stats, gear, items)
	- Autofill endpoint to instantly create a 4-character party (`POST /autofill_characters`)
- Multiplayer via WebSockets
- Procedural dungeon generation (deterministic by seed)
- Persistent dungeon state (database-backed)
- Fog-of-war with persistent explored tile memory (local + server sync)
- API-driven config for name pools, starter items, base stats, and class map
- Dynamic UI: party selection, adventure map, and real-time chat
- Responsive Bootstrap frontend
 - Centralized Seed API for deterministic or random dungeon regeneration

## Dungeon Generation Pipeline (Overview)
> NOTE: A simplified char-grid generator (rooms + wall rings + tunnel connectors) is now the default runtime implementation exposed via `from app.dungeon import Dungeon`. The detailed multi-phase pipeline described below is retained as historical documentation and for potential future reintroduction of advanced features. Current tests assert only the simplified invariants: room connectivity, no orphan doors (each door has one room neighbor and at least one walkable neighbor), and deterministic seed layout.

### Simplified Generator (Current Default)
The active generator focuses on speed, determinism, and clarity:
* Places a set of non-overlapping rectangular rooms (seeded RNG).
* Wraps each room with a single-tile wall ring (no layered thickness logic).
* Connects rooms using a minimal spanning tree of centers, carving straight (or simple L-shaped) tunnels.
* Inserts doors at room–tunnel interfaces (single-tile) without chain/cluster reduction heuristics.
* Produces a 2D char grid using symbols: `R` (room), `W` (wall), `T` (tunnel), `D` (door), `C` (cave/unused).

Intentionally removed (legacy-only) behaviors:
* Door chain collapsing & dense cluster pruning.
* Hidden area / unreachable room retention toggles.
* Multi-phase repair & inference passes (orphan repair now trivial: generation avoids creating them).
* Detailed metrics (only high-level tile counts + seed, unreachable room count, wall anomalies retained).

Rationale: The simplified model drastically reduces maintenance overhead and aligns with current gameplay needs (movement + fog-of-war) while keeping space for future expansion phases to be reintroduced incrementally.

---
The procedural dungeon system is deterministic per (seed, size) and built from a multi-phase pipeline. Each phase is implemented in a dedicated module under `app/dungeon/` to keep responsibilities isolated and testable. The pipeline orchestrator (`app/dungeon/pipeline.py`) wires the phases together; helper modules are intentionally free of Flask/web concerns for ease of profiling and future reuse.

1. Grid Initialization – Allocate empty cell matrix and seed RNG.
2. BSP Partitioning – Recursively subdivide space into candidate room regions (rejecting undersized leaves).
3. Room Placement – Carve rooms inside accepted leaves using jitter to avoid rigid alignment.
4. Corridor Graph – Build a k-nearest graph across room centroids, generate an MST for baseline connectivity, then probabilistically add loop edges.
5. Corridor Carving – For each graph edge, carve a path (L-shaped or occasionally irregular) ensuring minimal wall tunneling.
6. Early Normalization – Clean stray artifacts, ensure corridors interface cleanly with room perimeters.
7. Feature Assignment – (Future expansion) Hooks for populating decorative / gameplay features.
8. Accessibility Pruning – Remove dead-end noise if it does not reduce required connectivity.
9. Room–Tunnel Separation Enforcement – Prevent accidental room fusion by reintroducing separating walls where needed.
10. Door Guarantee – Ensure every distinct room connectivity set has at least one viable door to a corridor network.
11. Connectivity Repair – Detect and bridge any isolated reachable sets still remaining (safety net).
12. Final Repair & Validation – Invoke `_repair_and_validate_doors` which:
	- Repairs orphan doors (a door with no adjacent corridor/tunnel).
	- Optionally carves a minimal tunnel if repairable via a single cell carve.
	- Applies a probabilistic carve guard (e.g., 0.4) to avoid explosive late-stage expansion.
	- Gathers diagnostic statistics (debug hooks) and enforces final invariants.

### Door Invariants
A door cell must:
* Border exactly one room cell (prevents door-in-room or door-floating cases).
* Border at least one traversable corridor/door cell (prevents orphan doors).
* Not create direct room-to-room adjacency bypassing a corridor.

Violations detected during final repair are either fixed (if a single carve resolves them within guard probability) or the door is downgraded/removed.

### Probabilistic Carve Guard
Late-stage carving uses a probability threshold to prevent the normalization pass from aggressively expanding narrow corridors simply to satisfy seldom edge cases. This maintains layout character while still repairing the majority of structural issues.

### Determinism & Caching
The pipeline is deterministic for a given (seed, size). Generated `Dungeon` instances are cached in-memory keyed by these parameters allowing instant retrieval for repeat visits or seed replays.

### Hidden Areas Flags
Two configuration flags influence late-stage connectivity behavior (set in Flask config):

| Flag | Default | Behavior |
|------|---------|----------|
| `DUNGEON_ALLOW_HIDDEN_AREAS` | `False` | Skips active connectivity carving repairs; unreachable rooms from the structural phase are tolerated during repair, but a final safety sweep still converts unreachable rooms to tunnels so invariants (tests) retain full reachability. |
| `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT` | `False` | Superset of the above: also skips the final unreachable-room conversion, allowing persistent unreachable rooms (use only for manual debugging / experimental secret areas; never enabled in tests). |

If both flags are false the generator performs dynamic connectivity repairs and, if some rooms remain unreachable, downgrades those entire rooms to tunnels (incrementing `rooms_dropped`). If only the non-strict flag is true, repairs are skipped but the final downgrade still normalizes the layout. Strict mode leaves unreachable rooms intact (they will appear as isolated room cells not connected to the entrance component).

### Generation Metrics
When `DUNGEON_ENABLE_GENERATION_METRICS` (default True) is enabled, a metrics dictionary is attached to the dungeon object and exposed via the admin endpoint `/api/dungeon/gen/metrics`.

| Key | Description |
|-----|-------------|
| `doors_created` | Reserved for future proactive placements (currently 0). |
| `doors_downgraded` | Doors converted to wall/tunnel due to invalid adjacency. |
| `doors_inferred` | Tunnel cells promoted to doors by final inference safety pass. |
| `repairs_performed` | Number of connectivity repair attempts executed (skipped when hidden areas flag avoids repair). |
| `chains_collapsed` | Door tiles removed from linear chains along the same wall. |
| `orphan_fixes` | Door fixes (either carving an adjacent tunnel or degrading the door). |
| `rooms_dropped` | Entire rooms converted to tunnels in fallback when still unreachable after repairs. |
| `runtime_ms` | Generation wall-clock duration (ms). |
| `debug_allow_hidden` | Echo of `DUNGEON_ALLOW_HIDDEN_AREAS` at generation time. |
| `debug_allow_hidden_strict` | Echo of `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT`. |
| `debug_room_count_initial` | Room cell count immediately after structural pipeline. |
| `debug_room_count_post_safety` | Room cell count after final safety (may shrink if unreachable rooms were downgraded). |
| `door_clusters_reduced` | Dense (3+ doors in a 2x2) clusters collapsed into a single door. |
| `tunnels_pruned` | Unreachable tunnel cells (not adjacent to any room) removed when hidden areas disabled. |
| `corner_nubs_pruned` | Cosmetic corner tunnel 'nub' cells removed (single-cell tunnels only diagonally touching a room). |
| `phase_ms` | Dict mapping phase name -> duration (ms) when metrics enabled; aids profiling & performance triage. |

These metrics support regression tests and profiling of the consolidated final pass.

### Modular Dungeon Package
As of v0.4.x the former monolithic `app/dungeon.py` has been decomposed into a package:

```
app/dungeon/
	__init__.py        # Re-exports Dungeon, DungeonCell for backwards compatibility
	pipeline.py        # Dungeon dataclass + end-to-end generation orchestration
	generator.py       # Structural phases: grid init, BSP, rooms, corridors
	doors.py           # Door normalization, chain collapse, invariant enforcement
	pruning.py         # Layout cleanup: door clusters, orphan tunnels, corner nubs
	connectivity.py    # Flood fills, reachability repair, safety consolidation
	features.py        # Feature and special-room assignment (entrance, boss, water)
	cells.py           # DungeonCell class & cell-level utilities
	metrics.py         # init_metrics() and metric key centralization
```

Design goals:
1. Separation of concerns – each file focuses on a narrow generation concern.
2. Deterministic, side‑effect contained helpers – pure functions given RNG & grid.
3. Fast iteration – failing invariants can be traced to a specific module.
4. Backwards compatibility – external imports (`from app.dungeon import Dungeon`) still work.

Adding a new phase? Prefer a new function in an existing module (or a new module) and a single call site added to the ordered list inside `Dungeon._run_pipeline()`. Keep any new metrics registered in `metrics.init_metrics()` so tests gain them automatically.

Legacy note: The former monolithic and advanced multi-phase pipeline documentation below represents the prior implementation. The compatibility shim now points to the simplified generator; external imports (`from app.dungeon import Dungeon`) continue to work. Advanced phases can be reintroduced module-by-module without breaking the current API.

### Route Map Suppression
During development the app prints a route map once at startup. Suppress this by setting `ADVENTURE_SUPPRESS_ROUTE_MAP=1` (or `true/yes`) or programmatically via `app.config['SUPPRESS_ROUTE_MAP']=True` before initialization completes.

## Testing & Invariants
Key automated tests (pytest) protect the generation contract:

| Test | Purpose |
|------|---------|
| Seed persistence test | Ensures dashboard-selected seed matches the adventure instance seed (deterministic replay). |
| Multi-door presence sweep | Confirms that across a sampled seed range, rooms can legitimately present multiple door placements where distinct corridors meet. |
| No orphan doors invariant | Validates every door satisfies adjacency rules (one room neighbor + at least one corridor/door neighbor). |
| Strict hidden areas mode | Verifies that when `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT` is enabled unreachable rooms may persist (skips if rare fully-connected range). |
| Performance regression | Guards average generation `runtime_ms` across representative seeds against excessive slowdown. |

Future candidates: cycle length distribution, corridor branching factor bounds, entrance accessibility proofs.

### Test Infrastructure (Selective DB Isolation & Factories)

Recent test scalability and flakiness work introduced three important utilities:

1. Selective SQLite DB isolation marker: only rebuilds the schema for tests that truly need a pristine database (heavy data mutation / migration cases).
2. Lightweight object factories: fast creation of users, characters, dungeon instances, and ensuring items without repeating boilerplate.
3. Deterministic websocket helpers: eliminate timing races in moderation/admin Socket.IO tests by snapshotting state or forcing actions synchronously.

#### 1. `@pytest.mark.db_isolation`
Placed on a test (or class) to request a fresh database setup before it runs. Non‑isolated tests reuse the shared test database which dramatically cuts suite runtime and avoids excess "database is locked" contention.

Example:
```python
import pytest

@pytest.mark.db_isolation
def test_inventory_encumbrance(factory):
	user = factory.user()
	char = factory.character(user, str_val=10)
	# ... perform heavy write operations safely ...
```

Implementation summary (in `conftest.py`):
* Registered marker `db_isolation` (pytest will show it in `--markers`).
* An autouse session fixture intercepts each test; when the marker is present it drops & recreates tables inside an application context.
* WAL mode & a `busy_timeout` remain enabled globally to mitigate concurrent access blocking.

Guidelines:
* Use the marker only for tests that genuinely depend on a pristine schema or predictable autoincrement IDs.
* Prefer shared DB for pure read tests or those that can tolerate existing rows (factory methods generate unique usernames / slugs).

#### 2. Factories
Exposed via a single `factory` fixture that returns a namespaced helper with methods:
* `user(username=None, role='user', banned=False)`
* `character(user=None, str_val=10, dex_val=10, **overrides)`
* `instance(user=None, seed=12345)` – ensures a `DungeonInstance` row
* `ensure_item(slug, **attrs)` – create or fetch an `Item`

Behavior:
* Commits after each object for simplicity; for very hot paths you can batch by creating inside a transaction block (future optimization if needed).
* Auto‑generates unique usernames / slugs when not provided to avoid collisions in the shared DB mode.

Usage pattern:
```python
def test_party_capacity(factory):
	u = factory.user(role='user')
	c1 = factory.character(u, str_val=14)
	potion = factory.ensure_item('potion-healing', weight=0.5)
	# ... mutate inventory JSON, assert encumbrance ...
```

#### 3. Deterministic Websocket Test Helpers
Race‑prone admin moderation tests (e.g., kicking a user and then validating their absence) previously relied on asynchronous disconnect timing. To stabilize:
* A private snapshot function (`_admin_status_snapshot`) surfaces the in‑memory lobby/admin presence map synchronously for assertions.
* A test‑only Socket.IO event (`__test_force_kick`) triggers the same internal removal logic as a real admin kick but executes inline so the test can immediately assert disconnection without sleeps or polling.

These helpers are guarded so they don't expand production capabilities; they are only invoked by tests importing the lobby module directly or emitting the reserved event name. If you add new realtime moderation flows, mirror this pattern to keep tests deterministic.

#### When to Add Another Isolation Layer
Before adding new global teardown/setup logic ask:
1. Can a factory object with unique identifiers coexist instead?
2. Is the flakiness due to timing? (Prefer a deterministic helper/event.)
3. Does the test really require a clean autoincrement or empty table? (Mark with `db_isolation` if yes.)

This layered approach keeps the majority of tests fast (shared DB) while still offering precise isolation where truly needed.

### Coverage
Continuous Integration enforces a minimum line coverage threshold of **80%** (raised from 60% after broadening test focus to admin shell, websocket edge cases, and moderation features). The suite currently meets or exceeds this mark with critical generation logic and XP progression at or near 100%. New contributions must not drop overall coverage below 80%; add focused tests for any new dungeon pipeline branch, seed handling logic, websocket behavior, or admin moderation path.

## Architecture Diagram

See `docs/architecture.md` for a high-level Mermaid diagram of core components (Flask blueprints, Socket.IO layer, dungeon generation pipeline, persistence), plus request and movement flows and extension points.

## Asset Optimization
SVG icon assets are automatically normalized on commit (whitespace + non-license comment stripping) via a lightweight pre-commit hook (`optimize_svgs`). For deeper path/precision optimization you can still run external tools (e.g., svgo) before committing.

## Contributing & Development
See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for coding conventions, pre-commit policy (no inline styles/scripts), asset guidelines, and test instructions.


## What's New (v0.6.0 latest)
### v0.6.0 (Equipment, Inventory, Search UX)
- Equipment & Bags modal with drag-and-drop equip, per-slot Unequip, and Use actions for consumables.
- Equipment/Bags buttons on both Dashboard and Adventure party cards; improved outline-warning styling.
- New Inventory API: `/api/characters/state`, `/equip`, `/unequip`, `/consume` with computed stats.
- Dungeon perception/search improvements: persistent notice markers; Search enabled after perception; loot is clickable with tooltips.
- Backend hardening: normalized legacy gear shapes and robust user ID extraction to resolve 404/500s on `/api/characters/state`.

### v0.5.0 (Moderation & Performance Insight)
- Dedicated Moderation Panel UI with filtering (All / Banned / Muted), search, and action buttons.
- Temporary mute durations (seconds) with automatic expiry; persistent DB mute flag remains authoritative for hard mutes.
- Dungeon pipeline phase timing metrics (`phase_ms`) for profiling (generate, collapse, consolidation, pruning, safety, invariants, inference, features).
- Conditional invariant re-run optimization (skip second full sweep if corner nub pruning made no changes) improving median generation time and restoring performance regression headroom.
- Admin status payload enriched with `temporary_mutes` map (username -> expiry epoch seconds).

### v0.4.0 (Door & Tunnel Clarity)
### v0.4.0 (Door & Tunnel Clarity)
- Dense 2x2 door cluster reduction (retain one representative door) with preservation of meaningful door pairs.
- Orphan tunnel pruning (unreachable, non-room-adjacent) for cleaner maps when hidden areas disabled.
- New generation metrics: `door_clusters_reduced`, `tunnels_pruned`.
- New pytest marker: `structure` with regression test for clusters & unreachable tunnels.

### v0.3.4 (Maintenance & Tooling)
- Repository renamed to `Adventure` (formerly `adventure-mud`).
- Added lightweight SVG normalization pre-commit hook (trims/strips non-license comments across ~2.7K icons).
- CI workflow aligned with badge (job id `build-test`), explicit pre-commit run before tests.
- README branding & Asset Optimization section added.
- Persistent explored tiles column migration (lazy + script), compression & admin management.
- CHANGELOG entry for maintenance release.

### v0.3.3
**Release date:** 2025-09-21

Highlights across recent patches (0.3.1 → 0.3.3):

### (From previous release) v0.3.3
- New `/api/dungeon/state` endpoint for initial cell description & exits (no blank move hack).
- In-memory dungeon cache (seed,size) → Dungeon object reuse for performance.
- Pytest test suite (movement & seed determinism) + GitHub Actions CI workflow.
- Client updated to call state endpoint post map render.
 - Temporary universal branding/icon now uses `treasure-map.svg` (favicon, navbar, player marker).
 - Centralized `/api/dungeon/seed` endpoint (numeric, string->hash, or random regenerate) with UI controls in adventure view.
 - Cached dungeon entrance coordinate eliminates per-request entrance scan.

### v0.3.2
- Compass movement pad with dynamic exit enablement.
- Keyboard movement toggle + request queue + rate limiting (120ms) + ARIA improvements.
- Centralized class colors as CSS custom properties.

### v0.3.1
- Extraction of all inline CSS/JS to static files & cache-busting via `asset_url()`.
- Pre-commit governance hooks (no inline styles/scripts, enforce asset_url usage).
- Socket.IO version alignment & stability improvements.
- Utility CSS consolidation & favicon addition.

Refer to docs/CHANGELOG.md for full historical details.

## What's New in v0.3.0
- **Modular backend:** All major logic split into blueprints/modules (`dashboard.py`, `dungeon_api.py`, `config_api.py`)
- **Dungeon state in DB:** Player position and dungeon grid are now persistent and not stored in session
- **Deterministic dungeons:** Seed handling supports both alphanumeric and integer seeds
- **Config API:** All game config is now fetched via API endpoints
- **UI overhaul:** WASD/regenerate controls removed, dynamic exit buttons added, improved comments and docstrings
- **Project headers:** All code files now include project name, license, and GitHub info

## Getting Started

### 1. Create a virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the server
```bash
python run.py server
```

### 3. Open in browser
Visit http://localhost:5000

### VS Code tasks (optional)
If you use VS Code, this repo includes ready-to-use tasks and recommendations:
- Run task: "Run Adventure (bg)" to start the server in the background using the workspace venv.
- The workspace is configured to use `.venv/bin/python` automatically.

Recommended extensions are listed in `.vscode/extensions.json` (Python, Pylance, Ruff, Black, Jupyter, Docker).

## Project Structure
- `models/` - Database models
- `routes/` - Flask blueprints (auth, main, dashboard, dungeon_api, config_api)
- `websockets/` - WebSocket event handlers
- `static/` - Static files (JS, CSS)
- `templates/` - HTML templates

## Command Line Usage

The entry point `run.py` provides a robust CLI with subcommands and flags.

Show help:
```bash
python run.py --help
python run.py server --help
python run.py admin --help
```

Run server (defaults HOST=0.0.0.0, PORT=5000):
```bash
python run.py server
python run.py server --host 127.0.0.1 --port 8080
python run.py server --db sqlite:///instance/dev.db
```

You can also load variables from a `.env` file automatically (python-dotenv is included):
```bash
python run.py --env-file .env server
```

Admin shell:
```bash
python run.py admin
```

### Admin / Moderation Commands
The interactive admin shell now includes user moderation helpers in addition to basic CRUD:

| Command | Description |
|---------|-------------|
| `create user <username> [<password>]` | Create user (default password `changeme` if omitted) |
| `list users` | List all users with role and ban status |
| `delete user <username>` | Delete a user |
| `reset password <username> <new_password>` / `passwd <username> <new_password>` | Reset password |
| `set role <username> <admin|mod|user>` | Change role |
| `ban <username> [reason..]` | Ban user with optional reason (stores timestamp & reason) |
| `unban <username>` | Lift a ban |
| `list banned` | Show all banned users |
| `show user <username>` | Detailed user info (role, email, ban state, notes) |
| `set email <username> <email|none>` | Set or clear email |
| `note user <username> <text>` | Append a timestamped moderation note |

Login attempts by banned accounts are blocked with a flash message including the ban reason if present.

WebSocket admin events:
- `admin_online_users` (request) -> emits `admin_online_users_response` only to the requesting admin's socket (renamed response event to avoid accidental delivery to non-admin listeners).
	- NOTE: Legacy event name `admin_online_users` is still emitted (to the requesting admin only) for a transitional period. A TODO deprecation marker is present; clients should migrate to `admin_online_users_response`.

## Environment configuration
### Quick Start Setup Script
An interactive, colorful bootstrap script is provided:
```
python scripts/setup_adventure.py
```
Features:
- Generates / updates `.env` with sensible defaults (SECRET_KEY, DATABASE_URL, CORS origins)
- Ensures `instance/` directory exists
- Runs lightweight runtime migration logic (via importing server module)
- Creates or updates an admin user (optional) and can rotate password
- Shows compression & fog features already enabled in the codebase during normal runtime

Re-run safe: existing values become defaults; choose whether to rotate the admin password.

Flags / automation:
```
--yes / -y                Accept all defaults (non-interactive)
--non-interactive         Non-interactive mode (fails if required value missing)
--json                    Emit machine-readable JSON summary only
--no-admin                Skip ensuring/creating admin user
--admin-username NAME     Set admin username in non-interactive runs
--admin-password PASS     Set admin password (use with care; consider env injection)
--generate-admin-password Auto-generate a secure password (printed once)
--alembic                 Run `alembic upgrade head` after DB init if migrations present
--quiet-routes            Suppress route map printing during setup
--quiet                   Minimal output (suppresses normal info; errors still shown)
--verbose                 Extra informational output (sets log-level debug)
--log-level <level>       Explicit verbosity: debug|info|warn|error|silent
```
Example CI usage:
```
python scripts/setup_adventure.py --yes --no-admin --alembic --quiet-routes --json > setup_summary.json
```


Local development uses a `.env` file (auto-loaded):

Key variables:
- `SECRET_KEY` - Flask secret key. If a placeholder value (dev-secret-change-me, changeme, etc.) is detected, the setup script auto-generates a secure random 32-byte urlsafe token and writes it to `.env` (reported in JSON summary as `secret_key_generated: true`).
- `DATABASE_URL` - SQLAlchemy database URI (default: SQLite in ./instance/mud.db)
- `CORS_ALLOWED_ORIGINS` - Allowed origins for Socket.IO (default: *)

## Explored Tiles Persistence (Fog-of-War Memory)

### Door Placement & Pruning (v0.4.0+)
Door tiles are refined to maximize clarity while preserving organic branching:

1. Linear chain collapse removes long straight runs of doors along the same wall (retains boundary door).
2. Dense cluster pruning detects 2x2 windows containing 3+ doors (all bordering the same room) and collapses them to a single door.
3. Legitimate adjacent door pairs (e.g., corridor forks/junctions) are preserved to maintain expressive connectivity.
4. Orphan tunnel pruning removes unreachable tunnel pockets not adjacent to a room (skipped when hidden areas flags are enabled), reducing map clutter.
5. Corner tunnel nub pruning removes single-cell tunnel pixels that only diagonally touch a room creating a visual corner artifact without meaningful traversal value.

Metrics `door_clusters_reduced` and `tunnels_pruned` quantify pruning impact for regression tracking.

Explored dungeon tiles are stored per user and seed to allow long-term mapping memory across sessions and devices.

Storage layers:
- Client: `localStorage` (fast immediate recall) keyed by `adventureSeenTiles:<seed>`.
- Server: `user.explored_tiles` TEXT column (JSON object mapping seed -> compressed or raw tile list).

API contract:
```
GET  /api/dungeon/seen        -> { seed:<int>, tiles:"x,y;x,y;..." }
POST /api/dungeon/seen        -> { stored:<int>, compressed:<bool> }
POST /api/dungeon/seen/clear  -> Admin-only clear ({ username?, seed? })
```

Compression:
- Tile lists may be delta-compressed automatically (prefix `D:`). The server transparently decompresses before returning to clients.
- If compression doesn't reduce size, raw form is stored.

Admin management:
- Admins can clear all or a single seed's tiles for a user with `/api/dungeon/seen/clear`.
- Payload examples:
	- Clear current user's all seeds: `{}`
	- Clear current seed for user `alice`: `{ "username": "alice", "seed": 12345 }`

Migration:
- Column added automatically on startup via lightweight `_run_migrations()`.
- Manual script available: `python scripts/upgrade_explored_tiles.py` (idempotent).

Fallback safety:
- If persistence temporarily unavailable, API returns HTTP 202 with a warning instead of failing gameplay.

### Rate Limiting & Payload Guards
`POST /api/dungeon/seen` is rate limited per user (in-memory, per process) to 8 requests per 10s window. Exceeding the limit returns HTTP 429:
```
{ "error": "rate limit exceeded", "retry_after": 10 }
```
Additional guards:
- Single request tile submission hard limit: 4000 tiles (HTTP 413 if exceeded)
- Per-seed retained tile cap: 20,000 (excess silently truncated, oldest coordinates dropped after sort)
- Global per-user seed cap: 12 seeds; least-recently updated seeds are evicted (LRU) when exceeded.

### Compression & Metrics Endpoint
Tiles are delta-compressed automatically if it saves space. The admin metrics endpoint surfaces compression efficiency:
```
GET /api/dungeon/seen/metrics  (admin)
Response:
{
	"user": "alice",
	"seeds": [
		{ "seed": 12345, "tiles": 812, "compressed": true, "raw_size": 5120, "stored_size": 1480, "saved_pct": 71.09, "last_update": "2024-09-22T11:06:22Z" }
	],
	"totals": { "tiles": 812, "raw_size": 5120, "stored_size": 1480, "saved_pct": 71.09 }
}
```
Server responses for POST now include additional metrics:
```
{ "stored": <count>, "compressed": <bool>, "raw_size": <int>, "stored_size": <int>, "compression_saved_pct": <float> }
```

### Pruning Metadata Format
Each seed entry in `user.explored_tiles` now stores an object:
```
{ "<seed>": { "v": "D:<compressed-or-raw>", "ts": <epoch-seconds> }, ... }
```
Backward compatibility: legacy string values (raw or `D:`) are still accepted; they are upgraded to the object form upon next write.

### Admin Fog Modal Enhancements
The Fog & Visibility modal now shows a per-seed metrics table with compression savings, sizes, last update timestamps, and per-seed clear buttons powered by the metrics endpoint.

### Alembic Migration Scaffold
Alembic has been introduced for future schema evolution:
- Config: `alembic.ini`
- Scripts dir: `migrations/` (env.py + versions/)
- Generate a revision (example): `alembic revision --autogenerate -m "add new table"`
- Apply: `alembic upgrade head`

Current lightweight runtime migration logic remains; Alembic will take over for new structural changes. Keep both until all environments are validated under Alembic.


## VS Code tasks

Predefined tasks to run the project from the Command Palette are defined in `.vscode/tasks.json` and use the selected Python interpreter.

## Architecture Notes
- All major backend logic is modular and API-driven for maintainability and DM-driven content
- Dungeon state is persistent and deterministic by seed
- All config is managed via API endpoints for easy customization
- UI is dynamic and adapts to available exits and party state

## Frontend Asset Conventions

Recent refactors consolidated inline JavaScript and CSS into versioned static assets for maintainability:

- `static/js/adventure.js` – Adventure map rendering, movement & exit handling (Leaflet based)
- `static/js/admin-settings.js` – Admin broadcast & online user modal logic (Socket.IO)
- `static/utilities.css` – Reusable utility classes replacing prior inline styles:
	- Typography: `.u-mono`, `.badge-mono`
	- Layout & alignment: `.u-flex-center`, `.mw-240`, `.chat-body-240`, `.chat-header`
	- Icon sizing/effects: `.icon-28`, `.icon-32`, `.icon-dropshadow`
	- Components: `.map-box`, `.dungeon-output`, `.scroll-area-200`
	- Lists & resets: `.list-reset`
	- Currency colors: `.coin-gold`, `.coin-silver`, `.coin-copper`

### Guidelines
1. Prefer adding a utility class in `utilities.css` over introducing new inline `style` attributes.
2. If a style is used 2+ times, convert it into a utility.
3. Avoid one-off color filters on icons; create a semantic class where appropriate.
4. JavaScript tied to a template belongs in `static/js/` with a clear, focused filename.
5. New templated scripts should use a named `<script src=...>` include instead of inline IIFEs.

### Removing Inline Styles
The only previously allowed exception (the `style` param on the `svg_icon` macro) has been removed in favor of class-based styling. Run a grep for `style="` during code review to ensure no regressions:
```bash
grep -R "style=\"" app/templates || echo "No inline styles found"
```

### Cache Busting
Static assets now use an `asset_url(filename)` Jinja helper that appends a `?v=<mtime>` query string based on the file's modification time. Example:
```jinja2
<link rel="stylesheet" href="{{ asset_url('utilities.css') }}">
```
This removes the need to manually bump query tokens. If the file is missing, it gracefully falls back to a normal `url_for('static', ...)` URL.

### Pre-Commit Style Enforcement
A pre-commit hook is provided to block reintroduction of inline `style="..."` attributes in templates.

Install pre-commit locally:
```bash
pip install pre-commit
pre-commit install
```
Run hooks against all files:
```bash
pre-commit run --all-files
```
Hooks included:
- Trailing whitespace removal
- EOF fixer
- Inline style attribute check (fails build if any `style="` appears in templates)
- Inline script block check (disallows inline `<script>` code blocks)
- Manual version token check (enforces `asset_url()` usage)

See `docs/STYLE_GUIDE.md` for the full set of frontend conventions.

## CSS Custom Properties (Theming)
Class color theming is centralized and available both server-side and via `/api/config/class_colors`. Corresponding CSS variables (custom properties) are injected in the stylesheets so you can reskin without hunting through multiple files.

Example variables (one per class):
```
--class-fighter-bg / --class-fighter-fg / --class-fighter-border
--class-rogue-bg   / --class-rogue-fg   / --class-rogue-border
--class-mage-bg    / --class-mage-fg    / --class-mage-border
--class-cleric-bg  / --class-cleric-fg  / --class-cleric-border
--class-druid-bg   / --class-druid-fg   / --class-druid-border
--class-ranger-bg  / --class-ranger-fg  / --class-ranger-border
```
Usage in CSS:
```css
.character-card.class-fighter { background: var(--class-fighter-bg); color: var(--class-fighter-fg); }
.character-card.border-fighter { border-color: var(--class-fighter-border); }
```
Override strategy (create a new CSS file loaded after defaults):
```css
:root {
  --class-mage-bg: #123b52;
  --class-mage-border: #1d6c91;
}
```
You can dynamically fetch colors client-side:
```js
fetch('/api/config/class_colors').then(r=>r.json()).then(colors => console.log(colors.mage.bg));
```

## Adventure Movement UX
The adventure interface now provides:
- Compass movement pad (N/W/E/S) with dynamic enabling based on backend exits
- Keyboard movement (WASD + Arrow keys) toggle (accessible form-switch)
- Movement request queue & 120ms rate limiting to prevent spamming the server
- ARIA live region updating only the non-exit portion of the room description for screen readers

Client flow: initial map render -> `/api/dungeon/state` -> show description & exits -> button/keypress -> queue -> `/api/dungeon/move` -> JSON `{ pos, desc, exits }` -> update marker & enable next directions. Caching avoids regenerating the same dungeon structure each request.

## Seed API

The dungeon seed determines the procedural layout. A central POST endpoint manages creation, hashing, and regeneration so clients and templates no longer manipulate seeds via query parameters.

Endpoint:
```
POST /api/dungeon/seed
```
Body (JSON, all optional):
```
{
	"seed": <int|string|null>,
	"regenerate": <bool>
}
```
Behavior:
- If `regenerate` is true and `seed` is omitted/`null`, a new random seed is generated.
- If `seed` is an integer, it is used directly (clamped to 64-bit signed range for SQLite).
- If `seed` is a string, a deterministic SHA-256 hash (first 8 bytes) is converted to an integer.
- The user's active `DungeonInstance` is updated or created; position resets to `(0,0,0)` so the next map fetch relocates to the entrance.

Response:
```
{
	"seed": <int>,
	"dungeon_instance_id": <int>
}
```

Client Usage (JS):
```js
window.dungeonNewSeed();        // random regenerate
window.dungeonNewSeed('alpha'); // deterministic from string
window.dungeonNewSeed(12345);   // specific numeric seed
```

UI Controls:
- Adventure screen includes a "New Seed" button (random) and an input + Apply button for custom seeds.

Caching:
- Dungeon objects are cached in-process per (seed,size) reducing generation overhead.
- Entrance coordinate is cached within each `Dungeon` instance, removing an O(N^2) scan at map retrieval.

## Versioning and Changelog

This project follows Semantic Versioning (SemVer): MAJOR.MINOR.PATCH.

See docs/CHANGELOG.md for a curated list of notable changes per release.

### Automated Version Bump
An automated workflow (`auto-bump.yml`) examines the latest commit message on pushes to `main`. If the commit uses a Conventional Commit type (e.g., `feat:`, `fix:`, `perf:`) and the `VERSION` file was not modified in that commit, it will:
1. Decide bump type (`feat`/`perf` -> minor, `fix`/others -> patch).
2. Run the bump script (`scripts/bump_version.py <type>`).
3. Commit and push the updated `VERSION` (and `CHANGELOG.md` if modified).

To skip auto-bump, either include a manual version bump in your PR (changing `VERSION`) or use a non-triggering type (like `docs:`) when appropriate.

### Release Process
See `docs/RELEASING.md` for the full release checklist (tests, changelog finalize, version bump, tag & push). A quick TL;DR:
```
pytest -q
python scripts/bump_version.py <patch|minor|major>
git add VERSION docs/CHANGELOG.md && git commit -m "release: v$(cat VERSION)" && git push
git tag -a v$(cat VERSION) -m "Adventure v$(cat VERSION)" && git push --tags
```

## Inventory Stacking & Encumbrance

Inventories use a stacked JSON representation:

```
[ {"slug": "potion-healing", "qty": 3}, {"slug": "short-sword", "qty": 1} ]
```

Legacy inventories stored as a flat slug list are migrated lazily on first load.

Each `Item` has a `weight` (default 1.0). Total carried weight = sum(weight * qty).

Encumbrance configuration lives in the `game_config` table (key = `encumbrance`) and defaults to:
```
{
	"base_capacity": 10,
	"per_str": 5,
	"warn_pct": 1.0,
	"hard_cap_pct": 1.10,
	"dex_penalty": 2
}
```

Capacity = `base_capacity + STR * per_str`.

States:
* normal: weight <= capacity
* encumbered: capacity < weight <= capacity * hard_cap_pct (DEX reduced by `dex_penalty` for computed stats)
* blocked: weight > capacity * hard_cap_pct (new loot claims rejected and endpoint returns HTTP 400 with `error: encumbered`)

Loot claim responses now include post-claim encumbrance snapshot:
```
{
	"claimed": true,
	"item": {"slug": "lockpicks", "name": "Lockpicks"},
	"character_id": 5,
	"encumbrance": {"weight": 27.0, "capacity": 25, "status": "encumbered", "dex_penalty": 2, "hard_cap_pct": 1.1}
}
```

Character state endpoint (`/api/characters/state`) returns stacked bag entries with `qty` and per-character `encumbrance` object. A DEX penalty is applied to base stats prior to gear-derived adjustments when status is `encumbered` or `blocked`.

Tuning: update the JSON in `game_config` (key `encumbrance`) and restart (or hot-reload) the server. Future admin UI will expose these sliders.
