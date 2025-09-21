# Adventure

_Formerly: Adventure MUD (Multi-User Dungeon)_

[![CI](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml/badge.svg)](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml)

A modern web-based multiplayer dungeon adventure game built with Python (Flask, Flask-SocketIO), SQLite, and Bootstrap.

## Features
- User authentication (login/register)
- Character management (stats, gear, items)
- Multiplayer via WebSockets
- Procedural dungeon generation (deterministic by seed)
- Persistent dungeon state (database-backed)
- Fog-of-war with persistent explored tile memory (local + server sync)
- API-driven config for name pools, starter items, base stats, and class map
- Dynamic UI: party selection, adventure map, and real-time chat
- Responsive Bootstrap frontend
 - Centralized Seed API for deterministic or random dungeon regeneration

## Dungeon Generation Pipeline (Overview)
The procedural dungeon system is deterministic per (seed, size) and built from a multi-phase pipeline. Each phase is pure with respect to the prior phase's grid (aside from controlled mutations) enabling reproducibility and targeted testing.

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

## Testing & Invariants
Key automated tests (pytest) protect the generation contract:

| Test | Purpose |
|------|---------|
| Seed persistence test | Ensures dashboard-selected seed matches the adventure instance seed (deterministic replay). |
| Multi-door presence sweep | Confirms that across a sampled seed range, rooms can legitimately present multiple door placements where distinct corridors meet. |
| No orphan doors invariant | Validates every door satisfies adjacency rules (one room neighbor + at least one corridor/door neighbor). |

Future candidates: cycle length distribution, corridor branching factor bounds, entrance accessibility proofs.

### Coverage
Continuous Integration enforces a minimum line coverage threshold of **80%** (raised from 60% after broadening test focus to admin shell, websocket edge cases, and moderation features). The suite currently meets or exceeds this mark with critical generation logic and XP progression at or near 100%. New contributions must not drop overall coverage below 80%; add focused tests for any new dungeon pipeline branch, seed handling logic, websocket behavior, or admin moderation path.

## Architecture Diagram

See `docs/architecture.md` for a high-level Mermaid diagram of core components (Flask blueprints, Socket.IO layer, dungeon generation pipeline, persistence), plus request and movement flows and extension points.

## Asset Optimization
SVG icon assets are automatically normalized on commit (whitespace + non-license comment stripping) via a lightweight pre-commit hook (`optimize_svgs`). For deeper path/precision optimization you can still run external tools (e.g., svgo) before committing.

## Contributing & Development
See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for coding conventions, pre-commit policy (no inline styles/scripts), asset guidelines, and test instructions.


## What's New (v0.3.4 latest)
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
