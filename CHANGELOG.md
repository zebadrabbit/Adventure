# [0.7.7] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.6] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.5] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Looter-extract economy & progression (Path A, Specs 1–5)
- **Currency**: copper-internal with 3-tier (g/s/c) display (`app/economy/currency.py`).
- **Hoard**: per-user persistent vault of gear + copper (`app/models/hoard.py`,
  `app/economy/hoard_service.py`, `app/routes/hoard_api.py`). Run-purse (`Character.gold`)
  is at-risk; extraction pools the haul into the Hoard; party wipe loses it.
- **Trading** repointed to the Hoard; `seed-merchants` CLI; `POST /api/trade/repair`.
- **Procedural floor loot**: `DungeonLoot` can hold generated gear instances; config-driven
  drop chance + rarity weights (deterministic per seed).
- **Durability & repair**: gentle, config-driven gear wear; broken = reduced bonuses.
- **Progression**: XP→levels→talent+stat points (`app/services/progression.py`); awarded on
  kills and extraction; gated `level-up` allocation.
- **Skills**: starter seeder (`seed-skills`); passive effects feed combat/dashboard stats;
  active skills as combat actions (`POST /api/combat/<id>/cast_skill`).
- **Persistent status effects**: poison now survives past combat (decays via the overworld
  game clock instead of vanishing at combat end, floored at 1 HP outside combat), plus slow
  passive HP/MP regen while exploring (tunable via `GameConfig` `regen_rates`). Foundation
  for richer character-card UI in a future release.
- New docs: `docs/ECONOMY_PROGRESSION.md`.

### Fixed
- Skill/trade/level-up endpoints hardened (auth + ownership; admin-gated talent grant).
- Test suite fully green: fixed `combat_persistence` (initiative determinism) and
  `encounter_config` (monster seed) flakiness; `conftest` binds the test DB before import;
  untracked stale `.pyc` files; `manage.sh` uses `.venv` + Alembic and seeds merchants/skills.
- Test isolation: the suite now wraps every test in a real per-test transaction (commit and
  rollback both redirected to a SAVEPOINT at the database-driver level), so tests can no
  longer leak permanent writes into the shared test database regardless of how many times a
  test or its fixtures call `commit()`/`rollback()`.
- Migrations: the dev/test database bootstrap now self-stamps Alembic to `head` the first
  time it's ever touched, so `db.create_all()`'s import-time convenience and a real
  `alembic upgrade head` no longer fight each other on a fresh checkout.

## [0.7.0] - 2025-12-02

### Added
- Purple gradient glass-morphism theme system with centralized CSS architecture
- `base.css` - Core theme system with CSS custom properties and utilities (281 lines)
- `glass-theme.css` - Reusable glass-morphism components library (870+ lines)
- Glass-morphism styling for navbar with purple accent colors and backdrop blur
- Glass-morphism styling for footer with purple brand colors and hover effects
- SVG icons: `plus-circle.svg`, `people-fill.svg`, `shuffle.svg`, `dice-5.svg`

### Changed
- **Major CSS consolidation**: Extracted 1400+ lines of inline CSS from templates into static files
- Dashboard page (`dashboard.html`) reduced from 738 to 267 lines
- Profile page (`account/profile.html`) reduced from 560 to 216 lines
- Settings page (`account/settings.html`) reduced from 340 to 190 lines
- Admin dashboard (`admin_dashboard.html`) reduced from 434 to 258 lines
- All pages now use consistent purple gradient (#4c5270 → #5a3a52) background
- Navbar and footer now use glass-morphism effects matching the overall theme
- Moved documentation files to `docs/`: MONSTER_AI.md, CORRIDOR_GAP_FIX.md, DASHBOARD_FIX.md, INFRASTRUCTURE_SUMMARY.md, PROJECT_HEALTH_REPORT.md, STRUCTLOG_PROGRESS.md, exception_report.md

### Improved
- CSS maintainability through centralized theme files
- Consistent visual design across all application pages
- Performance through reduced HTML size and reusable CSS classes
- Code organization with documentation consolidated in docs/ directory

## [Untagged] - Dungeon, Combat & Persistence Expansion (between 0.6.0 and 0.7.0)

> The work below shipped after 0.6.0 and before 0.7.0 but was never cut into a tagged
> release at the time — recorded here under its own heading rather than assigned a
> retroactive version number it never actually had.

### Added
- **HP/MP Persistence Fixes**:
  - `_derive_stats()` reads persisted current HP from `Character.stats['hp']`.
  - Combat sessions start with actual current HP instead of always max HP.
  - Dashboard party payload shows real current HP/MP values (not hardcoded full).
  - Dungeon state API (`/api/dungeon/state`) includes a party array with current HP/MP.
  - Fixes free healing between combats and incorrect HP/MP bars on the adventure screen.
- **Boss Combat System** (`app/services/boss_abilities.py`):
  - Boss-specific abilities: AOE attacks, self-buffs, healing, minion summoning.
  - Phase transitions at 25% HP (enrage) and 10% HP (desperate).
  - Cooldown system for abilities (3–6 turns depending on ability).
  - Level-gated ability unlocks (AOE at 1, buff at 3, summon at 5, heal at 7).
  - Enhanced loot: 3x item drops, 75% special drop chance, guaranteed key drop.
- **Dungeon Extraction System** (`POST /api/dungeon/extract`):
  - Progress tracking: bosses_defeated, bosses_total, elites_defeated, monsters_defeated.
  - Extraction available once all bosses are defeated.
  - Completion rewards: 1000×tier base XP + 50×elites + 10×monsters (capped at 500).
- **Locked Door System** (see `docs/LOCKED_DOORS.md`):
  - Locked doors (`L`) non-walkable until unlocked.
  - Key items: rusty-key (common), master-key (rare), boss-key (epic).
  - Rogue lockpicking: DEX-based skill check (DC = 10 + tier×2), critical failure breaks lockpicks.
  - Unlock API (`POST /api/dungeon/unlock`); unlocked state persists per dungeon instance.
- Combat targeting: monster/boss AI now selects valid alive targets with lowest HP instead
  of a hardcoded index, and AOE abilities skip dead party members.
- Dead characters (HP=0) can no longer take actions; auto-advance turn with an
  "unconscious" message on attempted action.
- Frontend Autofill button on Dashboard (`POST /autofill_characters`), with a richer JSON
  response (stats, coins, inventory).
- Corner tunnel nub pruning and a door-inference safety pass (new metrics:
  `corner_nubs_pruned`, `doors_inferred`); final post-pruning invariant re-run guards
  against late structural changes.
- Modular dungeon package: `app/dungeon/` decomposed into `pipeline.py`, `generator.py`,
  `doors.py`, `pruning.py`, `connectivity.py`, `features.py`, `cells.py`, `metrics.py`.
- Dungeon API decomposed into focused helpers under `app/dungeon/api_helpers/`: movement,
  tile-type mapping, dashboard payload serialization, encounter/patrol logic, perception &
  search, treasure claiming.
- Turn-based combat (initial implementation): session model, initiative ordering, player
  actions (attack, flee, defend, cast_spell, use_item), monster auto-AI turn, loot + XP
  distribution, optimistic concurrency via `version`. Phased turn engine scaffold (`phase`
  field: start → action → end) for future start/end-of-turn triggers.

### Changed
- Adventure client fog-of-war moved entirely client-side (local storage + in-memory sets).
- Admin fog modal simplified to local coverage only.

### Removed
- Legacy seen-tiles subsystem (`/api/dungeon/seen*`): rate limiting, compression, merge,
  metrics, and admin clear endpoints, plus their tests. Breaking change for any external
  clients depending on server-side fog-of-war; migrate to client-managed fog-of-war.

## [0.6.0] - 2025-09-24

### Added
- Equipment & Bags modal with drag-and-drop equip, per-slot Unequip buttons, and consumable Use actions.
- Equipment UI on both Dashboard and Adventure party cards.
- Inventory API: `GET /api/characters/state`, `POST /api/characters/<cid>/equip`,
  `POST /api/characters/<cid>/unequip`, `POST /api/characters/<cid>/consume`.
- Dungeon perception/search flow: persistent notice markers, Search gated after perception,
  tooltipped clickable loot.

### Changed
- Character creation/autofill initialize `gear` as `{}` instead of a list for consistency.

### Fixed
- Hardened `/api/characters/state` against 404/500s: robust user ID extraction, legacy gear
  normalization (list → dict), per-character try/catch shielding for partial results.
- Loot markers removed after claim and persist correctly across refresh.

## [0.5.0] - 2025-09-22

### Added
- Dedicated Moderation Panel (filter All/Banned/Muted, search, direct Ban/Unban/Mute/Unmute).
- Temporary mute durations (in-memory auto-expire; persistent DB `muted` flag remains for hard mutes).
- Dungeon pipeline phase-timing metrics (`phase_ms`) for profiling.
- Deterministic `_admin_status_snapshot()` helper stabilizing ban-visibility regression tests.

### Changed
- Dungeon pipeline: conditional second invariant/inference sweep only runs if corner-nub
  pruning changed cells, recovering performance headroom.
- Removed the legacy monolithic `app/dungeon.py` compatibility shim; imports now target the
  `app.dungeon` package directly (public import path unchanged).
- Door guarantee logic carves outward minimal tunnels for rooms lacking a viable exit.

### Fixed
- Intermittent ban-visibility test failure resolved via the deterministic status helper.
- Performance regression addressed (median runtime back under threshold).

## [0.4.0] - 2025-09-21

### Added
- Dense door cluster pruning (2x2 windows with 3+ doors collapsed to one, preserving
  legitimate fork/junction double-door patterns).
- Orphan tunnel pruning (unreachable, non-room-adjacent tunnels removed when hidden-area
  flags are disabled).
- New metrics: `door_clusters_reduced`, `tunnels_pruned`; `@pytest.mark.structure` regression coverage.

### Fixed
- Eliminated visually noisy door bands and stray disconnected tunnel fragments.

## [0.3.4] - 2025-09-21

### Added
- Lightweight SVG normalization pre-commit hook (`optimize_svgs`) across ~2,700 icon assets.
- CI workflow alignment with badge (`build-test` job id), explicit pre-commit run before tests.

### Changed
- Repository renamed from `adventure-mud` to `Adventure`.

## [0.3.3] - 2025-09-21

### Added
- `/api/dungeon/state` endpoint for initial cell description & exits (no blank-move hack).
- In-memory dungeon cache (seed, size) → Dungeon object reuse for performance.
- Pytest suite (movement & seed determinism) + GitHub Actions CI workflow.
- Centralized `/api/dungeon/seed` endpoint (numeric, string→hash, or random regenerate).
- Door normalization refactored into a shared helper with a probabilistic outward-carve
  guard; orphan door repair, connectivity repair (BFS), and a "guarantee every room has a
  door" pass.

## [0.3.2] - 2025-09-21

### Added
- Compass movement pad with dynamic exit enablement.
- Keyboard movement (WASD + arrows) toggle, request queue, 120ms rate limiting, ARIA improvements.
- Centralized class colors as CSS custom properties.

## [0.3.1] - 2025-09-21

### Added
- Cache-busting `asset_url()` helper for static assets (mtime-based versioning).
- Pre-commit governance: no inline styles/scripts, enforced `asset_url()` usage.
- Socket.IO client/server version alignment and stability tuning.

## [0.3.0] - 2025-09-20

### Added
- **Backend modularization**: split into blueprints (`dashboard.py`, `dungeon_api.py`, `config_api.py`).
- **Dungeon state persistence**: moved from Flask session to a `DungeonInstance` DB model.
- **Deterministic dungeon generation**: seed handling for both alphanumeric and integer seeds.
- **Config API**: name pools, starter items, base stats, class map served via API.

### Fixed
- Session size bug (dungeon state now in DB, not session).
- Seed mismatch between frontend and backend.

## [0.2.1] - 2025-09-19

### Changed
- Enforced 4-player party selection limit on the dashboard; checkboxes disable past 4;
  Begin Adventure enabled only with 1-4 selected; card click toggles selection.

## [0.2.0] - 2025-09-18 / 2025-09-17

> Two releases were tagged `0.2.0` on consecutive days during early rapid iteration; both
> are recorded here as they appeared in project history rather than renumbered.

### Added
- Chatbox UI: title bar removed, collapse button moved to tab row, input anchored at bottom.
- Account & Settings section: update email, change password with current/new/confirm validation.
- Party selection flow: select up to 4 characters via checkbox or card click, "Your Party"
  summary card, Begin Adventure posting the selection with validation.
- Adventure briefing page (`/adventure`) summarizing the selected party.

### Changed
- Chatbox uses flex layout; color scheme matches dashboard.
- Dashboard theme polish for readability and feedback.

## [0.1.0] - 2025-09-16

### Added
- Initial CLI with `server` and `admin` commands; `.env` support.
- Flask app with login, registration, dashboard, and character creation.
- Item catalog seeding; starter inventory and coins; character cards.
