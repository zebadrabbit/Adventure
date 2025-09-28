# Development Workflow

Central reference for setting up the environment, running tests, formatting, and common maintenance tasks.

## Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
Optional helper script (interactive + idempotent):
```bash
python scripts/setup_adventure.py --yes
```

## Running the Server
```bash
python run.py server
```
Visit: http://localhost:5000

## Admin Shell
```bash
python run.py admin
```
Provides moderation commands (`ban`, `unban`, `set role`, etc.). Type `help` for a list.

## Formatting & Linting
Tools: **Black** + **Ruff** (lint + secondary formatting). Unified line length: 120.

Manual runs:
```bash
black .
ruff check --fix .
ruff format .  # (if using Ruff's formatter for non-Python assets later)
```

Pre-commit install:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Avoiding Formatting Loops
Ensure `pyproject.toml` has consistent line-length for both Black and Ruff. If hooks reformat after commit attempt:
1. Run `black . && ruff check --fix .` manually.
2. `git add .` then retry commit.
3. Verify no local alternative formatter (IDE) rewrites on save with different settings.

## Tests
Run entire suite:
```bash
pytest -q
```
Focused test:
```bash
pytest tests/test_dungeon_teleport_movement.py::test_teleport_activation
```

### DB Isolation Marker
Use `@pytest.mark.db_isolation` only for tests needing a pristine schema. Others reuse a shared DB to keep the suite fast.

### Factories
Provided via `factory` fixture (users, characters, instances, items). Prefer factories over handwritten SQL inserts.

### Websocket Helpers
Deterministic events / snapshots remove timing sleeps. Follow existing test patterns for new realtime features.

## Common Scripts
| Script | Purpose |
|--------|---------|
| `scripts/setup_adventure.py` | Bootstrap .env, ensure admin, migrations (optional) |
| `scripts/bump_version.py` | Semantic version bump & CHANGELOG insertion |
| `scripts/diagnose_seeds.py` | Analyze generation metrics across a seed sample |
| `scripts/upgrade_explored_tiles.py` | Migrate explored tiles persistence format |
| `scripts/profile_doors.py` | Inspect door placement behaviors (legacy interest) |

## Versioning
Automated workflow may bump version based on Conventional Commit types. To bump manually:
```bash
python scripts/bump_version.py patch
```

## Teleports
Logical fallback for unreachable rooms; see `TELEPORTS.md`.

## Dungeon Generation
Overview plus invariants matrix: `DUNGEON_GENERATION.md`.

## Adding a Dependency
1. Add to `requirements.txt`.
2. (Optional) Pin version to avoid surprise breaks.
3. Run `pip install -r requirements.txt` and commit the updated file.

## Troubleshooting
| Issue | Fix |
|-------|-----|
| Black: "No Python files" | Check `include` / `exclude` regex in `pyproject.toml` (should be `\.py$`). |
| Pre-commit keeps reformatting | Run formatters manually until idempotent; inspect hooks altering files. |
| Tests hang on websocket | Ensure deterministic helper used; avoid arbitrary `sleep()`. |
| DB locked errors | Reduce overuse of isolation marker; ensure connections closed in custom scripts. |
| Coverage drop in CI | Add focused tests for new logic branches; avoid large untested modules. |

## Contribution Flow (TL;DR)
1. Branch: `git checkout -b feat/teleports`
2. Code + tests
3. Run `black . && ruff check --fix . && pytest -q`
4. Commit with Conventional Commit message (`feat:`, `fix:`, etc.)
5. Open PR; ensure CI green
6. Merge; auto-bump or run bump script if needed

## Release Quickref
```bash
pytest -q
python scripts/bump_version.py minor
git add VERSION docs/CHANGELOG.md
git commit -m "release: v$(cat VERSION)"
git push && git tag -a v$(cat VERSION) -m "Adventure v$(cat VERSION)" && git push --tags
```

## Future Docs
Potential additions: LOOT_SYSTEM.md, ENCOUNTERS.md, PERFORMANCE.md.
