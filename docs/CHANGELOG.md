# Changelog
## [Unreleased]
### Added
- Frontend Autofill button on Dashboard invoking `/autofill_characters` endpoint.
- Richer `/autofill_characters` JSON response (stats, coins, inventory) for future SPA enhancements.
- Corner tunnel nub pruning pass removing single-cell tunnel tiles that only diagonally touch rooms.
- New generation metric: `corner_nubs_pruned`.
- Door inference safety pass promoting qualifying tunnel cells to doors where a latent room→corridor interface was missed by structural carving (metric: `doors_inferred`).
- Final post-pruning invariant enforcement pass (door invariants re-run after corner nub pruning) to guard against late structural changes.
- Regression tests: `test_door_invariants.py`, `test_no_room_tunnel_adjacency.py` protecting door rules and separation.
- Modular dungeon package fully exercised via new metrics & invariants (see README Modular Dungeon Package section update).
 - Movement API logic extracted to `app/dungeon/api_helpers/movement.py` (normalize position, attempt move, describe cell/exits) reducing `dungeon_api.py` size.
 - Tile character mapping centralized in `app/dungeon/api_helpers/tiles.py` with backward-compatible `_char_to_type` shim.
 - Dashboard helper module `dashboard_helpers.py` consolidating party serialization, autofill, and rendering utilities.
 - Passive monster patrol update & websocket broadcast (best-effort) after player movement.
 - Inline Search buttons with perception roll attribution (best party member) and persistent notice markers.
 - Encounter spawning & patrol logic extracted to `app/dungeon/api_helpers/encounters.py` (removes inline duplication in `dungeon_api.py`).
 - Perception & search logic extracted to `app/dungeon/api_helpers/perception.py` consolidating notice tracking, rolls, and tile search handling.
 - Treasure claim flow extracted to `app/dungeon/api_helpers/treasure.py` (single responsibility, easier future extension for lockpicking/chest states).

### Changed
 - `/api/dungeon/move` and `/api/dungeon/state` now share helper-based description & exits logic (less duplication, clearer tests).
 - Adventure client fog-of-war relies solely on local storage + in-memory sets (server persistence removed).
 - Admin fog modal simplified to local coverage only (removed server metrics & clear/sync controls).
 - README pruned deprecated seen tiles endpoint docs and clarifies client-only fog-of-war approach.

### Removed
 - Legacy seen tiles subsystem (`/api/dungeon/seen*`) including rate limiting, compression, merge, metrics, and admin clear endpoints.
 - Tests: `test_seen_tiles_persistence.py`, `test_seen_tiles_metrics.py` (feature obsolete).
 - Server sync & merge logic for seen tiles in `adventure.js` and `fog_admin_modal.js`.

### Notes
 - Backward compatibility shim `_char_to_type` remains temporarily to avoid immediate test refactors referencing the old symbol.
 - Future refactor slices planned: extract encounter spawning, loot noticing, treasure claiming into dedicated helpers for further modularity.
 - Removal of seen tiles endpoints is a breaking change for any external clients; migrate to client-managed fog-of-war.

## [0.6.0] - 2025-09-24
### Added
- Equipment & Bags modal with drag-and-drop equip, per-slot Unequip buttons, and consumable Use actions.
- Equipment UI added to both Dashboard and Adventure party cards; improved button styling for visibility.
- Inventory API endpoints:
	- `GET /api/characters/state` for characters, gear, bag, and computed stats.
	- `POST /api/characters/<cid>/equip` to equip items with slot validation and swap handling.
	- `POST /api/characters/<cid>/unequip` to remove equipped items back to the bag.
	- `POST /api/characters/<cid>/consume` for potions (HP/Mana).
- Dungeon perception/search flow: persistent notice markers, Search button gating after perception, and tooltipped clickable loot.

### Changed
- Button handlers in `equipment.js` now bind immediately; state loads lazily on first interaction to avoid dead UI when initial fetch fails.
- Character creation and autofill initialize `gear` as an empty object `{}` instead of a list for consistency.
- Buttons on Dashboard and Adventure restyled to outline-warning for clarity.

### Fixed
- Hardened `/api/characters/state` to avoid 404/500s via:
	- Robust user ID extraction (supports legacy sessions).
	- Legacy gear normalization (list → dict) at the API boundary.
	- Per-character try/catch shielding to keep partial results available.
- Loot markers are removed after claim and persist correctly across refresh.

### Notes
- Item slot inference remains heuristic; a future update will add explicit slot metadata to items.
- One dungeon test remains intermittently xfail; stability work continues alongside the new equipment system.

## [0.5.0] - 2025-09-22
### Added
- Dedicated Moderation Panel in Server Settings modal with filtering (All / Banned / Muted), search, and direct Ban / Unban / Mute / Unmute buttons (separate from online user list).
- Temporary mute durations (admin can supply `duration` seconds on `admin_mute_user`; in-memory auto-expire while persistent DB `muted` flag remains for hard mutes).
- Phase timing instrumentation in dungeon pipeline (`metrics['phase_ms']`) exposing per-phase milliseconds (generate, pruning, invariants, inference, etc.).
- Internal `_admin_status_snapshot()` helper for deterministic admin status retrieval in tests (stabilizes ban regression test).

### Changed
- Dungeon pipeline optimized: conditional second invariant & inference sweep now only runs if final corner nub pruning changed cells (reduces redundant full-grid scans, recovering performance headroom and restoring performance regression test pass).
- `admin_status` payload now includes `moderation.temporary_mutes` map of username -> expiry epoch for active temporary mutes.

### Fixed
- Intermittent test failure for persistent ban visibility resolved via deterministic status helper.
- Performance regression addressed (median runtime back under 70ms threshold) through conditional invariant pass.

### Notes
- Temporary mutes are ephemeral (in-memory expiry) while DB `muted` flag persists as a hard mute indicator. Future enhancement could distinguish persistent vs temporary in the DB schema.
- Phase timing metrics intended for diagnostics; avoid asserting strict per-phase bounds in tests to keep CI stable.

### Changed
- Navbar updated: replaced legal links (Privacy/Terms/Conduct/Licenses) with player-focused anchors (Getting Started, Classes, Items, Rules).
- Removed legacy monolithic `app/dungeon.py` compatibility shim; all imports now target the `app.dungeon` package.
- Enhanced door guarantee logic to carve outward minimal tunnels for rooms lacking a viable exit (prioritizes entrance room early).

### Notes
- Anchor links are placeholders pending dedicated content sections/pages; legal pages remain accessible via direct URLs.
 - Corner nub pruning is cosmetic; it doesn't alter corridor connectivity, only removes isolated diagonal-only tunnel pixels.
 - Monolith removal is a breaking internal change only; public import path (`from app.dungeon import Dungeon`) remains stable.
 - Hidden area flags still interact deterministically with invariant passes; strict mode skips connectivity repairs but invariants still run.


Moved from project root to `docs/` for repository root decluttering.

```note
Automation: The version bump script now supports the changelog in this location.
```

# [0.4.0] - 2025-09-21
### Added
- Dense door cluster pruning: 2x2 clusters with 3+ doors bordering the same room are reduced to a single door (improves visual clarity while preserving multi-door variety along distinct corridors).
- Orphan tunnel pruning: unreachable tunnel components (not adjacent to a room) are removed when hidden area flags are disabled.
- New generation metrics: `door_clusters_reduced`, `tunnels_pruned`.
- Structural integrity test suite marker (`@pytest.mark.structure`) with regression test ensuring absence of dense door clusters and unreachable tunnel noise.

### Changed
- Relaxed earlier aggressive adjacent-door pruning to permit legitimate fork/junction double-door patterns; only dense clusters are collapsed.
- Updated README with refined pipeline description, pruning behavior, and new metrics.

### Fixed
- Eliminated visually noisy door bands and stray disconnected tunnel fragments reported in prior exploratory sessions.

### Notes
- Hidden areas strict modes bypass orphan tunnel pruning intentionally to allow secret / experimental layouts.
- Metrics are optional (controlled by `DUNGEON_ENABLE_GENERATION_METRICS`) and safe for CI performance gate.

# [0.3.8] - 2025-09-21
### Added
- Placeholder version to align with internal automation; superseded by 0.4.0 feature release on same date.

### Notes
- No standalone release artifacts (rolled into 0.4.0).

# [0.3.7] - 2025-09-21
### Notes
- Skipped (internal sequencing during rapid iteration).

# [0.3.6] - 2025-09-21
### Notes
- Skipped (internal sequencing during rapid iteration).

# [0.3.5] - 2025-09-21
### Notes
- Skipped (internal sequencing during rapid iteration).

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
 - Multiple door exception: rooms can now legitimately have multiple doors when distinct corridors meet.
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
