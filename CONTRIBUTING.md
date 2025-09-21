# Contributing to Adventure

Thanks for your interest in improving Adventure! This document captures the lightweight workflow & guardrails that keep the project healthy and reproducible.

## Quick Start
1. Fork & clone the repo.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # if present
   ```
3. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```
4. Run tests:
   ```bash
   pytest -q
   ```

## Branching & Commits
- Use feature branches (`feat/seed-widget`, `fix/orphan-doors`, `docs/pipeline`).
- Keep commits focused; large mechanical changes (e.g., formatting) should be isolated from logic changes.
- Reference issues in commit messages when applicable (`Fixes #42`).

## Code Style & Policies
- Python: Follow PEP 8 (ruff/flake8 style; auto-format with black if configured).
- Templates: No inline `<style>` or `style="..."` attributes, and no inline `<script>` blocks. All styles live in `static/*.css`, scripts in `static/*.js`.
- Use the `asset_url()` helper for all static asset includes to enable cache busting.
- Avoid adding unused vendor libraries; prefer small, well-scoped utilities.

## Dungeon Generation Invariants
Door rules enforced by tests:
- A door must border exactly one room cell.
- A door must border at least one corridor/door cell.
- No direct room-to-room adjacency introduced by a door.

If you alter generation logic, run the full invariant suite:
```bash
pytest -k door -q
```

## Tests
Minimum expectation for new logic:
- Deterministic behavior under a fixed seed.
- Regression test capturing any new invariant or bug fix.
- Avoid tests that rely on timing or real network I/O.

Useful selective runs:
```bash
pytest tests/test_seed_persistence.py::test_dashboard_seed_flow -q
pytest -k orphan -q
pytest -k multi_door -q
```

## Adding Assets (Icons, Images)
- Optimize SVGs (e.g., `svgo`) before committing.
- Do not commit mechanical whitespace-only changes to hundreds of SVGs; revert them to keep diffs reviewable.
- Group related new icons in a single commit with a rationale.

## Database
- Migrations currently manual; if you change models, document upgrade path in the PR/commit.
- Test DB is ephemeral (SQLite). Avoid relying on production-only features.

## Security & Secrets
- Never commit secrets (.env should be local only).
- Use environment variables for sensitive config.

## Pull Requests
A good PR includes:
- Summary of change & motivation.
- Notes on determinism / reproducibility impact (for gen changes).
- Test coverage description.
- Screenshots / terminal captures if UI or CLI behavior changed.

## Release Checklist (Maintainers)
1. Ensure CHANGELOG.md updated.
2. Bump version (if using a version file or tag strategy).
3. All tests green in CI.
4. Review for large accidental asset churn.
5. Tag and draft release notes.

## Questions
Open a discussion or issue if you're unsure about direction or invariants.

Happy hacking! 🚀
