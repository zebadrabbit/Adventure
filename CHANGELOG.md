# [0.3.4] - 2025-09-21
### Added
- Lightweight SVG normalization hook (`optimize_svgs`) stripping non-license comments and trimming whitespace across 2,693 SVG icon assets.
- CI badge and workflow alignment (`build-test` job id) plus explicit pre-commit + pytest steps.
- Asset Optimization section in README and architecture docs link retained after branding update.

### Changed
- Repository renamed from `adventure-mud` to `Adventure`; README heading simplified and prior name noted for continuity.
- CI workflow hardened: ensures pre-commit dependencies installed; unified job name referenced by badge.

### Fixed
- Prevents large unintentional SVG whitespace churn by normalizing format at commit time.

### Notes
- Future enhancement: enforce coverage threshold (placeholder in CI for adding `--cov` gating) and adopt `ruff` for lint (planned next).

# [0.3.3] - 2025-09-21
### Added
- `/api/dungeon/state` endpoint for initial cell description & exits (removes need for blank move request).
- In-memory dungeon generation cache (seed,size) to reduce regeneration overhead.
- Pytest test suite (movement endpoints, seed determinism) and dev requirements.
- GitHub Actions CI: installs deps, runs pre-commit (if configured) and pytest with optional coverage.
 - Player marker reintroduced (sword/shield) with CSS-based zoom scaling (exponential) & glow.
 - Adjacency rule enforcement: tunnels no longer directly touch rooms; separation by wall or door only.
 - Guarantee pass: every room is ensured at least one door (creates a tunnel outward if necessary).
 - Connectivity repair: post-generation BFS ensures every room is reachable; isolated rooms get minimal connecting corridors.
 - Multiple door exception: rooms can now legitimately have multiple doors when distinct corridors/tunnels terminate at different wall tiles.
 - Orphan door repair pass: ensures every door has exactly one adjacent room and at least one adjacent tunnel/door; invalid doors are downgraded or a tunnel is carved outward to preserve invariants.
 - Refactored door normalization into shared helper with probabilistic outward carve guard (prevents runaway tunnel carving and reduces duplication between early and final passes).

### Changed
- Adventure client now calls `/api/dungeon/state` after map load instead of sending an empty move.
- Refactored dungeon API to use cached dungeon objects across map/move/state routes.
 - Marker styling extracted to utilities.css; scaling formula uses `scale = 1.2^zoom` (clamped) with smooth transform transitions.
 - Room/tunnel separation refined: instead of sealing all tunnel adjacency, qualifying tunnel endpoints adjacent to a single room are promoted to door cells (supports multiple distinct entry points per room).

### Notes
- Cache is a simple in-process dictionary with small cap (8 entries); suitable for single-process dev. Consider a smarter LRU or external cache for scaling.
 - Post-generation pass normalizes any tunnel adjacent to a room into a wall to enforce clearer room boundaries.

# [0.3.2] - 2025-09-21
### Added
- Compass movement pad (north/east/south/west) with dynamic exit enablement.
- Keyboard movement toggle (WASD + Arrow keys) with ARIA labels & focus enhancements.
- Movement request queue + 120ms rate limiting to prevent rapid spam and race conditions.
- ARIA live region announcing concise room updates (screen-reader friendly).
- Centralized class color palette exposed as CSS custom properties and via `/api/config/class_colors`.

### Changed
- Initial movement/exits fetch deferred until after map render to avoid race on load.
- Adventure JS modularized further (queue, toggle, rendering functions separated logically).

### Fixed
- Movement buttons previously stayed disabled on initial load due to early blank move call; now triggered post map load.

### Notes
- Future: Consider separate endpoint for initial cell state to avoid empty-direction move semantics.

# [0.3.1] - 2025-09-21
### Added
- Cache-busting helper `asset_url()` for all static assets (mtime-based versioning) eliminating manual `?v=` tokens.
- Frontend governance scripts & pre-commit checks enforcing:
  - No inline `style="..."` attributes in templates
  - No inline `<script>` code blocks (all JS externalized)
  - No manual static version query strings (must use `asset_url()`)
- Central `utilities.css` consolidating layout, icon, spacing, and effect helpers.
- Favicon and `<link rel="icon">` reference to remove 404 noise.

### Changed
- Migrated all previously inline CSS/JS in templates to dedicated static files (`chat-widget.js`, `dashboard.js`, `admin-settings.js`, etc.).
- Removed style parameter from `svg_icon` macro; visual effects now applied via utility classes (e.g., `.icon-glow`).
- Upgraded Socket.IO client to 5.x to align with Flask-SocketIO/python-socketio 5.x protocol.
- Added explicit Socket.IO server tuning: transports list, ping interval/timeout, optional engine.io debug logging.

### Fixed
- Eliminated rapid 400 responses and websocket upgrade churn by version aligning client/server and tuning engine settings.
- Removed UndefinedError from improper Jinja block usage in included modal template.
- Resolved macro argument mismatch after simplifying `svg_icon` signature.

### Notes
- Engine.IO low-level logging can be disabled in production by setting `ENGINEIO_LOGGER=0`.
- Future enhancements: namespace separation (`/lobby`, `/game`) and authenticated connection payloads.

# [0.3.0] - 2025-09-20
### Major Refactor & Features
- **Backend modularization:** Split `main.py` into logical blueprints/modules (`dashboard.py`, `dungeon_api.py`, `config_api.py`) for maintainability and extensibility.
- **Dungeon state persistence:** Moved dungeon grid and player position from Flask session to a database model (`DungeonInstance`).
- **Deterministic dungeon generation:** Improved seed handling (alphanumeric and integer) for reproducible dungeons.
- **Config API:** Exposed endpoints for name pools, starter items, base stats, and class map. Frontend now fetches these via API.
- **UI overhaul:**
  - Removed WASD and regenerate map controls from adventure UI.
  - Added dynamic exit buttons based on available exits from backend.
  - Improved dashboard and adventure page comments, docstrings, and formatting.
- **Project headers:** Added/updated project headers, licensing, and GitHub info in all code files.
- **Documentation:** Updated and clarified code comments, docstrings, and file/module headers.

### Changed
- All major logic is now modular and API-driven for easier maintenance and DM-driven content.
- Improved error handling and code clarity throughout the backend.

### Fixed
- Session size bug (dungeon state now in DB, not session).
- Seed mismatch between frontend and backend.

### Notes
- See README.md for updated usage and architecture.

# [0.2.1] - 2025-09-19
### Changed
- Enforce 4-player party selection limit in dashboard.js
- Disable checkboxes after 4 are selected
- Enable Begin Adventure button only when 1-4 are selected
- Character card click toggles selection and syncs with checkbox

# [0.2.0] - 2025-09-18
### Added
- Chatbox UI: Title bar removed, collapse button moved to tab row.
- Chatbox: Input box now anchored at the bottom, improved layout.

### Changed
- Chatbox uses flex layout for better usability and appearance.

### Fixed
- Chatbox expand/collapse works with new tabbed UI.
- Chatbox color scheme matches dashboard.

# [0.2.0] - 2025-09-17

### Added
- Account & Settings section on the dashboard:
  - Update email address (for potential offline notifications; optional, can be cleared).
  - Change password with current/new/confirm validation.
- Lightweight SQLite migration helper to add `user.email` if missing.
- Party selection flow on the dashboard:
  - Select characters (up to 4) via checkboxes or by clicking the entire card.
  - Distinct glow effect and subtle lift for selected cards.
  - “Your Party” card with live count and summary.
  - Begin Adventure action posting selected party, with validation.
- Adventure briefing page (`/adventure`) summarizing selected party.

### Changed
- Dashboard UI enhancements and theme polish for better readability and feedback.

### Notes
- Version string updated to 0.2.0 in the CLI (`run.py --version`).

# [0.1.0] - 2025-09-16

### Added
- Initial CLI with `server` and `admin` commands; `.env` support.
- Flask app with login, registration, dashboard, and character creation.
- Item catalog seeding; starter inventory and coins; character cards.
- Logging to `instance/app.log` and debug mode flag.
- Basic error page for 500s.

---

[0.3.0]: https://example.com/releases/0.3.0
[0.2.1]: https://example.com/releases/0.2.1
[0.2.0]: https://example.com/releases/0.2.0
[0.1.0]: https://example.com/releases/0.1.0
