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
- New docs: `docs/ECONOMY_PROGRESSION.md`.

### Fixed
- Skill/trade/level-up endpoints hardened (auth + ownership; admin-gated talent grant).
- Test suite fully green: fixed `combat_persistence` (initiative determinism) and
  `encounter_config` (monster seed) flakiness; `conftest` binds the test DB before import;
  untracked stale `.pyc` files; `manage.sh` uses `.venv` + Alembic and seeds merchants/skills.

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

## [0.6.0] - 2025-09-24

See `docs/CHANGELOG.md` for detailed version history.
