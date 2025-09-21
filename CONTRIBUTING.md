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

### Coverage & Lint
- Continuous Integration enforces a minimum coverage threshold (currently 80%). New or significantly modified modules should not lower overall coverage; target ≥80% locally before submitting. Strive for near 100% on pure/deterministic utility code (e.g., XP tables, seed coercion helpers, moderation helpers).
- `ruff` is used for lint/import ordering. Run locally:
   ```bash
   ruff check .
   ```
   Auto-fix import order & simple issues:
   ```bash
   ruff check --fix .
   ```

Useful selective runs:
```bash
pytest tests/test_seed_persistence.py::test_dashboard_seed_flow -q
pytest -k orphan -q
pytest -k multi_door -q
```

## Adding Assets (Icons, Images)
- SVGs are auto-normalized on commit by the `optimize_svgs` pre-commit hook (comment stripping, whitespace trim). Run manually:
   ```bash
   python scripts/optimize_svgs.py path/to/icon.svg
   ```
- For advanced optimization (path merging, precision reduction) you may still optionally run an external tool like `svgo` before committing.
- Do not commit mechanical whitespace-only changes to large batches of existing SVGs; revert them to keep diffs reviewable.
- Group related new icons in a single commit with a rationale.

## Database
- Migrations currently manual; if you change models, document upgrade path in the PR/commit.
- Test DB is ephemeral (SQLite). Avoid relying on production-only features.
 - Lightweight migration helper (`_run_migrations`) adds missing columns idempotently (used for moderation fields like `banned`, `ban_reason`, `notes`, `banned_at`). Tests should exercise new branches when adding fields.

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
2. Bump version using the helper script (see Versioning section below).
3. All tests green in CI.
4. Review for large accidental asset churn.
5. Tag and draft release notes.

### Versioning & Bump Script
Project version lives in the `VERSION` file and is surfaced by the CLI (`python run.py --version`). Use the helper script to manage semantic bumps and auto-insert an UNRELEASED section stub in `CHANGELOG.md`:

```bash
python scripts/bump_version.py patch   # 0.3.4 -> 0.3.5
python scripts/bump_version.py minor   # 0.3.4 -> 0.4.0
python scripts/bump_version.py major   # 0.x.y -> 1.0.0
python scripts/bump_version.py set 0.3.7  # explicit version
```

Behavior:
- Requires a clean git working tree (prevents partial bumps).
- Updates `VERSION` file.
- Inserts (or ensures) a `## [UNRELEASED]` section at top of `CHANGELOG.md` if absent.
- Prints the previous and new version for visibility.

Guidelines:
- Bump immediately after merging user-visible changes; group small internal changes until a meaningful increment.
- Only use `major` when making backward incompatible changes.
- Keep CHANGELOG entries concise: one bullet per logical change (feat/fix/docs/perf/security).

After bumping, commit the result:
```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump version to $(cat VERSION)"
```

## Questions
Open a discussion or issue if you're unsure about direction or invariants.

Happy hacking! 🚀
