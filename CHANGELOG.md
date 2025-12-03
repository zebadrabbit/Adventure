# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
