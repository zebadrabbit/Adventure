# Application-factory refactor — design spec

**Status:** proposed (not started). Written during the 2026-07-27 repo-health
pass; see `plans/2026-07-27-repo-health-review.md` §8.

## Problem

`import app` is not a read-only operation. Module import currently:

1. calls `load_dotenv()` (mutates `os.environ` for the whole process),
2. constructs the `Flask` app, `SQLAlchemy`, `LoginManager`, `SocketIO`
   singletons at module level,
3. registers every blueprint and websocket handler,
4. **connects to the database, runs `create_all()` + programmatic alembic
   upgrade (`_ensure_schema`), and seeds baseline rows (`_seed_baseline`)**.

`create_app()` exists but is a facade: it re-runs steps 4 on the
already-built module singleton and returns it.

### Damage this has caused (all documented in TODO_ARCHIVE.md)

- The pytest-wiped-the-dev-DB incident: `load_dotenv()` leaked the dev
  DATABASE_URL into the environment *during import*, after conftest had
  checked it.
- tests/conftest.py must set `DATABASE_URL` from `TEST_DATABASE_URL`
  *before* the first `import app` anywhere, forever — a tripwire any new
  entry point can trip.
- The SAVEPOINT isolation saga: because the engine binds at import, test
  isolation had to be retrofitted via `Session.get_bind` monkey-patching.
- Alembic's own `env.py` importing `app` caused migrations to race the
  import-time `create_all()` (fixed by self-stamping, but the hazard is
  structural).
- The 2026-07-27 fail-fast change can't fully protect a host with a `.env`
  file: import loads it before any check runs.

## Goal

`import app` becomes side-effect free. All construction moves into a real
factory:

```python
def create_app(config: Mapping | None = None) -> Flask: ...
```

- Reads env/config **inside** the factory (dotenv loading opt-in via
  parameter or explicit call in run.py, never at import).
- Extensions (`db`, `login_manager`, `socketio`) become unbound module
  globals initialized with `init_app(app)` — the standard Flask extension
  pattern. They stay importable (`from app import db`) so model/service
  imports don't change.
- Schema management (`_ensure_schema`) and seeding (`_seed_baseline`)
  become explicit calls: run.py invokes them on server start; conftest
  invokes them once per session; alembic's env.py imports models only.
- Blueprint/websocket registration happens in the factory.

## Constraints / known hazards

- **`app` and `db` are imported at module scope in ~100 files** (routes,
  services, tests). The factory must keep those names importable. `db` is
  easy (unbound extension). Bare `app` usage (e.g. `app.config[...]` at
  request time) must migrate to `current_app` — grep shows most uses are
  inside request handlers, which is exactly where `current_app` works.
- `admin_tui.py`, `manage.sh`-driven scripts, `scripts/*.py`, and the
  seed subcommands in run.py each construct/import the app — every entry
  point needs the explicit `create_app()` + context dance.
- Flask-SQLAlchemy 3.x binds engines at `init_app` time; the conftest
  `Session.get_bind` patch should be re-evaluated (it may simplify to a
  plain `bind=connection` sessionmaker once the factory lets tests build
  their own app against the test engine cleanly).
- Socket.IO: `socketio.run(app)` in run.py and the `@socketio.on`
  decorators in app/websockets/* must move to a registration function
  called by the factory (decorator-at-import registers against the
  unbound `socketio` object — Flask-SocketIO supports this, verify the
  namespace objects survive `init_app`).
- Gunicorn entry (`app:app` in docker-compose) needs a WSGI module, e.g.
  `wsgi.py` with `app = create_app()`.

## Suggested task breakdown (TDD, one commit each)

1. Introduce `wsgi.py` + make run.py/gunicorn/docker use it (no factory
   change yet — just the single blessed construction point).
2. Move `load_dotenv()` out of app/__init__.py into run.py/wsgi.py.
3. Convert extensions to `init_app` pattern; factory builds config.
4. Move blueprint + websocket registration into the factory.
5. Make `_ensure_schema`/`_seed_baseline` explicit (run.py server path,
   conftest session fixture, setup script).
6. Re-evaluate conftest isolation machinery against the new shape.
7. Sweep bare `app` imports to `current_app` where they bind at import.

Each step keeps the suite green; the branch is abandonable after any step
(every intermediate state is shippable).

## Acceptance

- `python -c "import app"` performs zero I/O (no env mutation, no DB
  connection, no dotenv read) — enforced by a test that imports `app`
  with `DATABASE_URL` unset and asserts no `RuntimeError` *and* no
  engine creation.
- Full suite green; e2e smoke green; `alembic upgrade head` works against
  a fresh DB without the app import racing it.
