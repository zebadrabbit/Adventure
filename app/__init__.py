# ruff: noqa: E402
"""
project: Adventure MUD
module: __init__.py
https://github.com/zebadrabbit/Adventure
License: MIT

Flask application factory and core extensions setup.

This module wires together the Flask app, SQLAlchemy, Flask-Login, and
Flask-SocketIO. Configuration is sourced from environment variables with
reasonable defaults for development. A local `instance/` directory is used
for SQLite and other runtime data.
"""

import logging
import os
import pathlib  # moved up (cache bust helper)  # noqa: E402
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Load .env if present so `SECRET_KEY`, `DATABASE_URL`, etc. can be supplied
# without exporting shell variables during development.
load_dotenv()

# Create the Flask app with instance-relative config so we can use ./instance
# for local data (e.g., SQLite database at ./instance/mud.db)
app = Flask(__name__, instance_relative_config=True)

# Ensure instance directory exists for SQLite and other runtime files
try:
    os.makedirs(app.instance_path, exist_ok=True)
except OSError:
    # In some constrained environments this might fail; ignore
    pass

# Load configuration from environment with sensible defaults. If DATABASE_URL
# isn't provided, default to a SQLite file in the instance folder.
DEFAULT_SECRET_KEY = "dev-secret-change-me"


def _check_secret_key(secret_key: str, flask_env: str) -> None:
    """Refuse to start with the default SECRET_KEY when FLASK_ENV=production.

    FLASK_ENV=production is this project's existing production marker (see
    docker-compose.yml, Dockerfile, and .env.example), so the guard hooks
    into that convention rather than inventing a new one.
    """
    if secret_key == DEFAULT_SECRET_KEY and (flask_env or "").lower() == "production":
        raise RuntimeError("SECRET_KEY must be set in production (see .env.example)")


secret_key = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
_check_secret_key(secret_key, os.getenv("FLASK_ENV", ""))
database_url = os.getenv("DATABASE_URL")

# During pytest runs, isolate to a separate test database to reduce locking
if not database_url:
    is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    db_filename = "mud_test.db" if is_pytest else "mud.db"
    db_path = Path(app.instance_path) / db_filename
    # Use POSIX path for SQLAlchemy URI compatibility across OS
    database_url = f"sqlite:///{db_path.as_posix()}"

app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
    # Dungeon generation feature flags / metrics
    DUNGEON_ALLOW_HIDDEN_AREAS=bool(os.getenv("DUNGEON_ALLOW_HIDDEN_AREAS", "0") == "1"),
    DUNGEON_ENABLE_GENERATION_METRICS=bool(os.getenv("DUNGEON_ENABLE_GENERATION_METRICS", "1") == "1"),
)

# PostgreSQL connection pooling options
engine_opts = {
    "pool_pre_ping": True,  # Verify connections before using
    "pool_recycle": 300,  # Recycle connections after 5 minutes
}

db = SQLAlchemy(app, session_options={"expire_on_commit": False}, engine_options=engine_opts)
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):  # pragma: no cover - simple loader
    from app.models.models import User

    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


# Let Flask-SocketIO select best async_mode based on installed deps (eventlet/gevent/threading)
socketio = SocketIO(
    app,
    async_mode=os.getenv("SOCKETIO_ASYNC_MODE") or None,
    cors_allowed_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*"),
    engineio_logger=bool(os.getenv("ENGINEIO_LOGGER", "1") == "1"),
    ping_interval=20,
    ping_timeout=10,
    transports=["websocket", "polling"],
)

# Apply SQLite pragmatic tuning (WAL + busy timeout) once the engine is created.
try:  # pragma: no cover - lightweight, defensive
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: D401
        # Only apply PRAGMA commands to SQLite connections
        if hasattr(dbapi_connection, "cursor") and "sqlite" in str(type(dbapi_connection)).lower():
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=10000")  # 10 seconds
                cursor.close()
            except Exception:
                pass

except Exception:
    pass


# Register HTTP blueprints (import after app/db created but keep near top for clarity)
from flask_login import current_user  # noqa: E402

from app.services import rate_limiter as _rl  # noqa: E402

# Blueprint imports intentionally placed after app/db initialization (runtime dependency ordering).
from app.routes import auth, main  # noqa: E402  # isort: skip
from app.routes.admin_new import bp_admin_new  # noqa: E402  # isort: skip
from app.routes.combat_api import bp_combat  # new combat blueprint  # noqa: E402  # isort: skip
from app.routes.config_api import bp_config  # noqa: E402  # isort: skip
from app.routes.dashboard import bp_dashboard  # noqa: E402  # isort: skip
from app.routes.dungeon_api import bp_dungeon  # noqa: E402  # isort: skip
from app.routes.inventory_api import bp_inventory  # noqa: E402  # isort: skip
from app.routes.loot_api import bp_loot  # noqa: E402  # isort: skip
from app.routes.quest_api import bp_quest  # noqa: E402  # isort: skip
from app.routes.trading_api import bp_trading  # noqa: E402  # isort: skip
from app.routes.party_api import bp_party  # noqa: E402  # isort: skip
from app.routes.skill_api import bp_skill  # noqa: E402  # isort: skip
from app.routes.achievement_api import bp_achievement  # noqa: E402  # isort: skip
from app.routes.seed_api import bp_seed  # noqa: E402  # isort: skip
from app.routes.user_prefs import bp_user_prefs  # noqa: E402  # isort: skip
from app.routes.client_log_api import bp_client_log  # noqa: E402  # isort: skip
from app.routes.account import bp_account  # noqa: E402  # isort: skip
from app.routes.theme_api import bp_theme  # noqa: E402  # isort: skip
from app.routes.extraction_api import bp_extraction  # noqa: E402  # isort: skip
from app.routes.hoard_api import bp_hoard  # noqa: E402  # isort: skip

app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)
app.register_blueprint(bp_dashboard)
app.register_blueprint(bp_dungeon)
app.register_blueprint(bp_seed)
app.register_blueprint(bp_config)
app.register_blueprint(bp_loot)
app.register_blueprint(bp_quest)
app.register_blueprint(bp_trading)
app.register_blueprint(bp_party)
app.register_blueprint(bp_skill)
app.register_blueprint(bp_achievement)
app.register_blueprint(bp_inventory)
app.register_blueprint(bp_user_prefs)
app.register_blueprint(bp_admin_new)  # Single consolidated admin panel
app.register_blueprint(bp_combat)
app.register_blueprint(bp_client_log)
app.register_blueprint(bp_account)
app.register_blueprint(bp_theme)
app.register_blueprint(bp_extraction)
app.register_blueprint(bp_hoard)

_DEFAULT_LIMIT = 120  # requests
_DEFAULT_WINDOW = 60  # seconds


@app.before_request
def _apply_rate_limit():  # pragma: no cover - integration side-effect
    """Apply per-endpoint fixed-window rate limiting to API routes only.

    Design constraints / rationale:
    - We intentionally DO NOT throttle page templates, static assets, or
        websocket (engine.io) handshake/polling endpoints to avoid broken /
        unstyled pages or stalled socket connections.
    - Only JSON-style application endpoints mounted under /api/ are limited.
    - Each (user or ip) x (endpoint) pair gets an independent bucket so a
        chatty endpoint like movement does not starve others.
    - Movement endpoint receives a much larger default allowance because it
        can legitimately fire at a high frequency from the client.
    If you extend API surface outside /api/ ensure you either move it under
    that prefix or replicate the limiter logic explicitly.
    """
    path = request.path or ""
    # Skip entirely for websocket engine.io handshake/polling endpoints and static assets.
    if path.startswith("/socket.io/") or path.startswith("/static/"):
        return None
    # Only rate limit JSON API endpoints (all our API routes live under /api/)
    if not path.startswith("/api/"):
        return None
    endpoint = request.endpoint
    view = app.view_functions.get(endpoint) if endpoint else None
    spec = _rl.resolve_spec(view) if view else None
    limit = spec.limit if spec else _DEFAULT_LIMIT
    window = spec.window if spec else _DEFAULT_WINDOW
    # Provide a slightly larger shared budget for the very chatty movement endpoint if
    # a custom spec wasn't already set (protect against partial page loads due to background
    # polling + user interaction).
    if endpoint == "dungeon.dungeon_move" and (not spec):
        limit = max(limit, 600)  # allow 600 moves per window
    # Key selection prefers authenticated user id to avoid penalizing shared IPs.
    if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
        ident = f"user:{getattr(current_user, 'id', 'anon')}"
    else:
        ident = f"ip:{request.remote_addr}"
    # Separate bucket per endpoint to allow independent budgets while still preventing spam.
    key = f"{ident}:{endpoint}:{window}"
    limited, reset_in = _rl.should_rate_limit(key, limit=limit, window=window)
    if limited:
        resp = jsonify(
            {
                "error": "rate_limited",
                "message": "Too many requests",
                "retry_after": reset_in,
                "limit": limit,
                "window": window,
            }
        )
        resp.status_code = 429
        resp.headers["Retry-After"] = str(reset_in)
        return resp
    return None


# Import websocket handlers so their event decorators register with Socket.IO (side-effect)
# Cache-busting asset helper: generates a url_for static path with ?v=<mtime>
from flask import url_for  # noqa: E402

from app.websockets import (
    combat as _ws_combat,  # noqa: F401,E402  # registers /adventure namespace
)
from app.websockets import game as _ws_game  # noqa: F401,E402
from app.websockets import lobby as _ws_lobby  # noqa: F401,E402


def asset_url(filename: str) -> str:
    """Return a cache-busted static asset URL by appending the file's mtime.

    Example: asset_url('dashboard.css') -> /static/dashboard.css?v=1695251234
    Falls back to plain url_for if file not found.
    """
    try:
        static_folder = pathlib.Path(app.static_folder or "static")
        file_path = static_folder / filename
        mtime = int(file_path.stat().st_mtime)
        return url_for("static", filename=filename) + f"?v={mtime}"
    except Exception:
        return url_for("static", filename=filename)


app.jinja_env.globals["asset_url"] = asset_url

# --- Schema management: alembic is the single migration path -----------------
# Startup self-migration (dev/prod convenience): create any missing tables via
# create_all, then bring the schema to alembic head programmatically. This
# replaced four legacy guarded-DDL mechanisms (server._run_migrations,
# app.migrations.apply_migrations, _run_lightweight_migrations, and the
# monster_catalog fallback block). All of their DDL now lives in the
# ``b1c2d3e4f5a6_legacy_baseline_guards`` alembic revision.
import structlog  # noqa: E402

_schema_log = structlog.get_logger("app.schema")

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
# Revision immediately preceding the legacy-baseline guard revision. A database
# with tables but no alembic_version (a fresh create_all schema, or a legacy
# pre-alembic deployment) is stamped here before upgrading, so the idempotent
# baseline guards run exactly once and alembic owns versioning thereafter.
_PRE_ALEMBIC_STAMP = "a1b2c3d4e5f9"


def _ensure_schema():
    """Create missing tables and bring the schema to alembic head.

    Wrapped in a single try/except that logs rather than raises, preserving the
    startup resilience of the legacy mechanisms this replaced (a migration
    failure must not crash dev/prod startup).
    """
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
        from sqlalchemy import inspect as sa_inspect

        with app.app_context():
            db.create_all()
            cfg = AlembicConfig(_ALEMBIC_INI)
            if not sa_inspect(db.engine).has_table("alembic_version"):
                alembic_command.stamp(cfg, _PRE_ALEMBIC_STAMP)
            alembic_command.upgrade(cfg, "head")
    except Exception:
        _schema_log.exception("schema_upgrade_failed")
        try:
            db.session.rollback()
        except Exception:
            pass


def _seed_baseline():
    """Seed the catalog/config rows required for a usable app. Idempotent."""
    try:
        from app.server import _seed_game_config, seed_items

        with app.app_context():
            seed_items()
            _seed_game_config()
    except Exception:
        _schema_log.exception("seed_baseline_failed")
        try:
            db.session.rollback()
        except Exception:
            pass


_ensure_schema()
_seed_baseline()


def create_app():
    """Return the Flask app instance, ensuring schema + baseline seeds exist.

    Idempotent safety net for entry points (e.g. the test suite) that build the
    app via the factory; the module-level calls above already run on import.
    """
    _ensure_schema()
    _seed_baseline()
    return app


# Error handling: in non-debug mode, show a simple 500 page and log details
@app.errorhandler(500)
def internal_error(e):
    error_id = uuid.uuid4().hex[:8]
    logging.exception("Unhandled exception (id=%s)", error_id)
    from flask import render_template

    return render_template("500.html", error_id=error_id), 500
