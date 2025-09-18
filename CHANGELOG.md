# Changelog

## [0.2.0] - 2025-09-18
### Added
- Chatbox UI: Title bar removed, collapse button moved to tab row.
- Chatbox: Input box now anchored at the bottom, improved layout.

### Changed
- Chatbox uses flex layout for better usability and appearance.

### Fixed
- Chatbox expand/collapse works with new tabbed UI.
- Chatbox color scheme matches dashboard.
Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

## [0.2.0] - 2025-09-17

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

## [0.1.0] - 2025-09-16

### Added
- Initial CLI with `server` and `admin` commands; `.env` support.
- Flask app with login, registration, dashboard, and character creation.
- Item catalog seeding; starter inventory and coins; character cards.
- Logging to `instance/app.log` and debug mode flag.
- Basic error page for 500s.

---

[0.2.0]: https://example.com/releases/0.2.0
[0.1.0]: https://example.com/releases/0.1.0
