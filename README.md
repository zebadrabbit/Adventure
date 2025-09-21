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
Continuous Integration enforces a minimum line coverage threshold of **60%** (recent uplift from 50%). The current suite sits around ~76% overall with critical generation logic and XP progression at or near 100%. New contributions should avoid regressing coverage; add focused tests for any new dungeon pipeline branch, seed handling logic, or websocket behavior.

## Architecture Diagram

See `docs/architecture.md` for a high-level Mermaid diagram of core components (Flask blueprints, Socket.IO layer, dungeon generation pipeline, persistence), plus request and movement flows and extension points.

## Asset Optimization
SVG icon assets are automatically normalized on commit (whitespace + non-license comment stripping) via a lightweight pre-commit hook (`optimize_svgs`). For deeper path/precision optimization you can still run external tools (e.g., svgo) before committing.

## Contributing & Development
See [CONTRIBUTING.md](CONTRIBUTING.md) for coding conventions, pre-commit policy (no inline styles/scripts), asset guidelines, and test instructions.


## What's New (v0.3.4 latest)
### v0.3.4 (Maintenance & Tooling)
- Repository renamed to `Adventure` (formerly `adventure-mud`).
- Added lightweight SVG normalization pre-commit hook (trims/strips non-license comments across ~2.7K icons).
- CI workflow aligned with badge (job id `build-test`), explicit pre-commit run before tests.
- README branding & Asset Optimization section added.
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

Refer to CHANGELOG.md for full historical details.

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

## Environment configuration

Local development uses a `.env` file (auto-loaded):

Key variables:
- `SECRET_KEY` - Flask secret key
- `DATABASE_URL` - SQLAlchemy database URI (default: SQLite in ./instance/mud.db)
- `CORS_ALLOWED_ORIGINS` - Allowed origins for Socket.IO (default: *)

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

See `STYLE_GUIDE.md` for the full set of frontend conventions.

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

See CHANGELOG.md for a curated list of notable changes per release.
