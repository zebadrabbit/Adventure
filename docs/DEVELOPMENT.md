# Development Workflow

Central reference for setting up the environment, running tests, formatting, and common maintenance tasks. See the [README](../README.md) for the project pitch and gameplay overview.

## Environment Setup

Requires **Python 3.10+** and **PostgreSQL 13+** (SQLite is not supported).

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional interactive bootstrap (idempotent — safe to re-run):
```bash
python scripts/setup_adventure.py --yes
```
Generates/updates `.env` (SECRET_KEY, DATABASE_URL, CORS origins), ensures `instance/` exists, runs migrations, and can create/rotate an admin user.

Flags:
```
--yes / -y                Accept all defaults (non-interactive)
--non-interactive         Non-interactive mode (fails if required value missing)
--json                    Emit machine-readable JSON summary only
--no-admin                Skip ensuring/creating admin user
--admin-username NAME     Set admin username in non-interactive runs
--admin-password PASS     Set admin password (use with care; consider env injection)
--generate-admin-password Auto-generate a secure password (printed once)
--alembic                 Run `alembic upgrade head` after DB init if migrations present
--quiet-routes            Suppress route map printing during setup
--quiet / --verbose       Output verbosity
--log-level <level>       debug|info|warn|error|silent
```

Key environment variables (`.env`, auto-loaded):
- `SECRET_KEY` — Flask secret key. The setup script detects placeholder values and auto-generates a secure token.
- `DATABASE_URL` — PostgreSQL connection URI.
- `CORS_ALLOWED_ORIGINS` — Allowed origins for Socket.IO (default: `*`).

## Running the Server

```bash
python run.py server
```
Visit http://localhost:5000 (default `PORT=5000`, override with `--port` or the `PORT` env var).

```bash
python run.py server --host 127.0.0.1 --port 8080
python run.py --env-file .env server   # load vars from a specific .env file
```

VS Code: a "Run Adventure (bg)" task and recommended extensions (Python, Pylance, Ruff, Black) are preconfigured in `.vscode/`.

Suppress the startup route-map print with `ADVENTURE_SUPPRESS_ROUTE_MAP=1` or `app.config['SUPPRESS_ROUTE_MAP'] = True`.

## Admin Shell & CLI

```bash
python run.py admin
python run.py --help
python run.py server --help
```

### Moderation Commands (interactive admin shell)

| Command | Description |
|---------|-------------|
| `create user <username> [<password>]` | Create user (default password `changeme` if omitted) |
| `list users` | List all users with role and ban status |
| `delete user <username>` | Delete a user |
| `reset password <username> <new_password>` / `passwd <username> <new_password>` | Reset password |
| `set role <username> <admin\|mod\|user>` | Change role |
| `ban <username> [reason..]` | Ban user with optional reason |
| `unban <username>` | Lift a ban |
| `list banned` | Show all banned users |
| `show user <username>` | Detailed user info (role, email, ban state, notes) |
| `set email <username> <email\|none>` | Set or clear email |
| `note user <username> <text>` | Append a timestamped moderation note |

Banned accounts are blocked at login with a flash message including the ban reason if present.

### Admin & Data Management (web)

Route prefix `/admin`; requires `User.role == 'admin'` (non-admins get HTTP 403, unauthenticated get 401/redirect).

- `/admin/` — landing page with links to users, game config, item/monster catalogs
- `/admin/users` — list (50/page), change role, ban/unban (self-role-change and self-ban are blocked)
- `/admin/game-config` — key/value editor for `GameConfig` rows
- `/admin/items`, `/admin/monsters` — CSV upload (≤500KB, ≤5000 rows; validated all-or-nothing, no partial writes)

JSON workflows:
```
POST /admin/users/<id>/role {"role":"mod"}
POST /admin/users/<id>/ban  {"action":"ban","reason":"abuse"}
POST /admin/users/<id>/ban  {"action":"unban"}
```

CSV required columns — items: `slug,name,type,description,value_copper,level,rarity` (+optional `weight`); monsters: `slug,name,level_min,level_max,base_hp,base_damage,armor,speed,rarity,family,xp_base` (+optional `traits,loot_table,special_drop_slug,boss,resistances,damage_types`). `rarity` for monsters also accepts `elite`/`boss`.

The same validation logic backs CLI parity commands:
```bash
python run.py import-items-csv path/to/items.csv
python run.py import-monsters-csv path/to/monsters.csv
python run.py make-admin alice
python run.py config-set encumbrance '{"base_capacity":12,"per_str":6}'
python run.py config-get encumbrance
```
On failure each validation error prints (`ERROR: ...`) with a non-zero exit code; no partial writes ever occur, so retries after fixing errors are always safe.

## Formatting & Linting

Tools: **Black** + **Ruff**, unified line length 120 (relaxed from 100/88 to reduce noisy wrapping in tests and data-heavy assertions).

```bash
ruff check . && black --check . && pytest -q   # verify
ruff check --fix . && black .                  # auto-fix
```

Enforced rule families (see `pyproject.toml`): E/W (pycodestyle), F (pyflakes), I (import sorting), UP (pyupgrade), B (bugbear), SIM (simplify), C4 (comprehensions).

Use inline `# noqa: <RULE>` sparingly, only when necessary, with a brief reason (e.g. `# noqa: E501 (example payload clarity)`).

### Docstring Style

Lightweight Google-style variant:

```python
def player_attack(session_id: int, user_id: int, version: int) -> dict:
    """Execute a player attack action.

    Args:
        session_id: Active combat session id.
        user_id: Acting user's id (authorization verified internally).
        version: Optimistic concurrency token; must match current session.version.

    Returns:
        dict: Serialized session delta or version_conflict payload.

    Raises:
        ValueError: If the session is not found or action not permitted.
    """
    ...
```

Guidelines:
1. Module-level docstring: 1–3 line summary + optional longer paragraph on invariants/side effects.
2. Public functions/service entry points get full Args/Returns/Raises sections; obvious internal helpers may use a single sentence.
3. Keep imperative mood, consistent within a file.
4. Document important invariants (idempotence, optimistic-lock behavior) over restating types already in annotations.

### Avoiding Formatting Loops
If pre-commit hooks keep reformatting after a commit attempt:
1. Run `black . && ruff check --fix .` manually.
2. `git add .` then retry commit.
3. Check no IDE auto-formatter is rewriting on save with different settings than `pyproject.toml`.

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Hooks enforce: trailing whitespace/EOF fixers, no inline `style="..."` attributes in templates, no inline `<script>` code blocks, `asset_url()` usage instead of manual cache-busting query strings, SVG normalization.

## Frontend Asset Conventions

- `app/static/js/` — page-specific JS, one focused file per template/feature; no inline `<script>` blocks in templates.
- `app/static/css/` — consolidated stylesheets; prefer a utility class over a new inline `style=` attribute (if used 2+ times, promote to a utility).
- `asset_url(filename)` (Jinja helper) appends `?v=<mtime>` for cache-busting — use it instead of manual version query strings:
  ```jinja2
  <link rel="stylesheet" href="{{ asset_url('css/app.css') }}">
  <script src="{{ asset_url('js/dashboard.js') }}"></script>
  ```
- Check for regressions: `grep -R "style=\"" app/templates || echo "No inline styles found"`.

Full conventions: [docs/STYLE_GUIDE.md](STYLE_GUIDE.md).

### CSS Theming
Class colors are centralized as CSS custom properties (also served via `/api/config/class_colors`):
```css
--class-fighter-bg / --class-fighter-fg / --class-fighter-border
--class-rogue-bg   / --class-rogue-fg   / --class-rogue-border
/* ...one triplet per class */
```
Override by loading a CSS file after defaults that redefines the variables under `:root`.

## Tests

```bash
pytest -q
pytest tests/test_dungeon_teleport_movement.py::test_teleport_activation   # focused
```

### DB Isolation Marker
`@pytest.mark.db_isolation` forces a fresh schema rebuild before a test runs — use only for tests that genuinely need a pristine database or predictable autoincrement IDs (heavy data mutation, migration cases). Unmarked tests share one session-long database and get per-test transaction rollback (see `tests/conftest.py`'s `_db_transaction_rollback` for the mechanism — it patches `Session.get_bind` plus SAVEPOINT-based commit/rollback at the dialect level, since Flask-SQLAlchemy 3.x ignores a plain sessionmaker `bind=` kwarg).

```python
@pytest.mark.db_isolation
def test_inventory_encumbrance(factory):
    user = factory.user()
    char = factory.character(user, str_val=10)
    # ... heavy write operations, safely isolated ...
```

Before adding a new isolation/teardown layer, ask: can a factory with unique identifiers coexist instead? Is the flakiness actually a timing issue (prefer a deterministic helper)? Does the test really need a clean autoincrement/empty table (then mark `db_isolation`)?

### Factories
Exposed via the `factory` fixture: `factory.user(...)`, `factory.character(user, ...)`, `factory.instance(user, seed=...)`, `factory.ensure_item(slug, **attrs)`. Auto-generates unique usernames/slugs to avoid collisions in the shared-DB mode.

### Deterministic Websocket Helpers
Race-prone admin/moderation Socket.IO tests use synchronous snapshot helpers (e.g. `_admin_status_snapshot`) and test-only events (e.g. `__test_force_kick`) instead of sleep-based polling, so assertions never race real disconnect timing. These are guarded to be test-only; mirror the pattern for new realtime moderation flows.

### Coverage
CI enforces a minimum line coverage threshold of 80%. New contributions must not drop overall coverage below this; add focused tests for new dungeon-pipeline branches, seed handling, websocket behavior, or admin/moderation paths.

## Quality Gates & CI

| Gate | Tool | Expectation |
|------|------|-------------|
| Lint | `ruff check .` | Zero errors |
| Format | `black --check .` | No diffs (line length 120) |
| Imports | Ruff (rule I) | Auto-sorted |
| Tests | `pytest -q` | 100% passing; stochastic tests use deterministic seeds, not tolerated flakiness |
| Coverage | CI report | ≥ 80% line coverage overall |
| Security (light) | Manual review | No hard-coded secrets/credentials |
| Docs | README + docstrings | New public services/routes documented |

Fail fast and fix in the same PR. If a deliberate behavior change breaks a balance/invariant test, update the test with an inline rationale in the diff.

## Common Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_adventure.py` | Bootstrap `.env`, ensure admin, run migrations (optional) |
| `scripts/bump_version.py` | Semantic version bump & CHANGELOG insertion |
| `scripts/diagnose_seeds.py` | Analyze generation metrics across a seed sample |
| `scripts/profile_doors.py` | Inspect door placement behaviors (legacy interest) |

## Database Migrations

Alembic owns schema evolution (`alembic.ini`, `migrations/env.py` + `migrations/versions/`):
```bash
alembic revision --autogenerate -m "add new table"
alembic upgrade head
```
A bootstrap step self-stamps a fresh database to `head` the first time it's ever touched, so `db.create_all()`'s import-time convenience and Alembic's real migration history don't fight each other on a clean checkout. See `app/__init__.py` and `docs/superpowers/specs/2026-06-20-migrations-self-stamp-design.md` for the rationale if you're touching that bootstrap.

## Adding a Dependency
1. Add to `requirements.txt` (pin a version if you want to avoid surprise breaks).
2. `pip install -r requirements.txt` and commit the updated file.

## Versioning & Releases

Semantic Versioning (MAJOR.MINOR.PATCH). See [CHANGELOG.md](../CHANGELOG.md) for the curated release history.

An automated workflow (`auto-bump.yml`) inspects the latest commit on pushes to `main`: if it uses a Conventional Commit type (`feat:`, `fix:`, `perf:`) and `VERSION` wasn't already modified, it bumps (`feat`/`perf` → minor, others → patch), commits, and pushes the updated `VERSION`/`CHANGELOG.md`. Skip it by including a manual version bump in your PR, or use a non-triggering type like `docs:`.

Manual bump:
```bash
python scripts/bump_version.py <patch|minor|major>
```

Release quickref (full checklist: [docs/RELEASING.md](RELEASING.md)):
```bash
pytest -q
python scripts/bump_version.py <patch|minor|major>
git add VERSION CHANGELOG.md && git commit -m "release: v$(cat VERSION)" && git push
git tag -a v$(cat VERSION) -m "Adventure v$(cat VERSION)" && git push --tags
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Black: "No Python files" | Check `include`/`exclude` regex in `pyproject.toml` (should be `\.py$`) |
| Pre-commit keeps reformatting | Run formatters manually until idempotent; check for a conflicting IDE auto-formatter |
| Tests hang on websocket | Use the deterministic helpers above; avoid arbitrary `sleep()` |
| Coverage drop in CI | Add focused tests for new logic branches; avoid large untested modules |
| 403 on `/admin/...` | Confirm the logged-in user has role `admin` |
| CSV import silently reorders rows | Normal (DB commit order isn't guaranteed); verify counts, not order |

## Contribution Flow (TL;DR)

1. Branch: `git checkout -b feat/your-feature`
2. Code + tests
3. `black . && ruff check --fix . && pytest -q`
4. Commit with a Conventional Commit message (`feat:`, `fix:`, etc.)
5. Open PR; ensure CI is green
6. Merge; auto-bump handles `VERSION`/`CHANGELOG.md` unless you did it manually

## Future Docs
Potential additions: LOOT_SYSTEM.md, ENCOUNTERS.md, PERFORMANCE.md.
