# Adventure MUD Release Notes

## 0.3.1 (2025-09-21)
Refinement & stabilization release.

Highlights:
- Full externalization of inline template assets (CSS & JS) into `static/`
- Automatic cache busting with `asset_url()` helper
- Pre-commit governance scripts (no inline styles/scripts, no manual version tokens)
- Socket.IO client upgraded to 5.x and server tuning to resolve 400/timeout churn
- Favicon added, macro simplification (removed style arg), utility CSS consolidation

Upgrade notes:
- Run `pip install -r requirements.txt` (same deps, but ensure environment is current)
- If you had local template overrides with inline `<script>` or `style="..."`, migrate them to static files prior to committing.

## 0.3.0 (2025-09-20)
See CHANGELOG.md for major refactor details (modular backend, deterministic dungeons, persistent state).
