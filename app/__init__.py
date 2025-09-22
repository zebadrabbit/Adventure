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

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import uuid

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
secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-me')
database_url = os.getenv('DATABASE_URL')
if not database_url:
    db_path = Path(app.instance_path) / 'mud.db'
    # Use POSIX path for SQLAlchemy URI compatibility across OS
    database_url = f"sqlite:///{db_path.as_posix()}"

app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
    # Dungeon generation feature flags / metrics
    DUNGEON_ALLOW_HIDDEN_AREAS=bool(os.getenv('DUNGEON_ALLOW_HIDDEN_AREAS','0')=='1'),
    DUNGEON_ENABLE_GENERATION_METRICS=bool(os.getenv('DUNGEON_ENABLE_GENERATION_METRICS','1')=='1'),
)

db = SQLAlchemy(app, session_options={'expire_on_commit': False})
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

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
    # Explicit async mode (eventlet installed) for clarity; can switch to 'gevent' or 'threading' if needed
    async_mode=os.getenv('SOCKETIO_ASYNC_MODE') or None,  # None lets it auto-select; override via env
    # In dev, allow all origins by default; set explicit origins in production
    cors_allowed_origins=os.getenv('CORS_ALLOWED_ORIGINS', '*'),
    # Engine.IO low-level logging to help diagnose 400 handshake / timeout issues (disable in production)
    engineio_logger=bool(os.getenv('ENGINEIO_LOGGER', '1') == '1'),
    # Mitigate rapid reconnect churn by tuning ping timeouts (defaults: ping_interval=25, ping_timeout=20)
    ping_interval=20,
    ping_timeout=10,
    # Allow both transports explicitly; client will attempt websocket upgrade
    transports=['websocket', 'polling']
)


# Register HTTP blueprints
from app.routes import auth, main
from app.routes.dashboard import bp_dashboard
from app.routes.dungeon_api import bp_dungeon
from app.routes.seed_api import bp_seed
from app.routes.config_api import bp_config

app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)
app.register_blueprint(bp_dashboard)
app.register_blueprint(bp_dungeon)
app.register_blueprint(bp_seed)
app.register_blueprint(bp_config)

# Import websocket handlers so their event decorators register with Socket.IO

from app.websockets import game, lobby

# Route map debug output (development aid). Suppress by either:
#   1. Setting env var ADVENTURE_SUPPRESS_ROUTE_MAP=1
#   2. Setting app.config['SUPPRESS_ROUTE_MAP']=True (e.g., in tests or after create_app())
if not (
    os.getenv('ADVENTURE_SUPPRESS_ROUTE_MAP') in ('1','true','yes') or
    app.config.get('SUPPRESS_ROUTE_MAP')
):
    print("Registered routes:")
    print(app.url_map)

# Cache-busting asset helper: generates a url_for static path with ?v=<mtime>
from flask import url_for
import time
import pathlib

def asset_url(filename: str) -> str:
    """Return a cache-busted static asset URL by appending the file's mtime.

    Example: asset_url('dashboard.css') -> /static/dashboard.css?v=1695251234
    Falls back to plain url_for if file not found.
    """
    try:
        static_folder = pathlib.Path(app.static_folder or 'static')
        file_path = static_folder / filename
        mtime = int(file_path.stat().st_mtime)
        return url_for('static', filename=filename) + f'?v={mtime}'
    except Exception:
        return url_for('static', filename=filename)

app.jinja_env.globals['asset_url'] = asset_url

# --- Lightweight schema version tracking (pre-Alembic compatibility) ---------
from sqlalchemy import text

def _ensure_schema_version_table():  # pragma: no cover - simple startup helper
    try:
        with app.app_context():
            db.session.execute(text("CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK (id=1), version INTEGER NOT NULL)"))
            row = db.session.execute(text("SELECT version FROM schema_version WHERE id=1")).fetchone()
            if not row:
                db.session.execute(text("INSERT INTO schema_version (id, version) VALUES (1, 1)"))
            db.session.commit()
    except Exception:
        pass

def _bump_schema_version(new_version: int):  # pragma: no cover
    try:
        with app.app_context():
            db.session.execute(text("UPDATE schema_version SET version=:v WHERE id=1"), { 'v': new_version })
            db.session.commit()
    except Exception:
        pass

def _run_lightweight_migrations():  # pragma: no cover - idempotent guard
    _ensure_schema_version_table()
    # Future placeholder: detect columns / add defaults. Muted column now part of model.
    # Example pattern (kept commented for guidance):
    # from sqlalchemy import inspect
    # insp = inspect(db.engine)
    # if 'user' in insp.get_table_names():
    #     cols = [c['name'] for c in insp.get_columns('user')]
    #     if 'muted' not in cols:
    #         db.session.execute(text('ALTER TABLE user ADD COLUMN muted BOOLEAN NOT NULL DEFAULT 0'))
    #         db.session.commit()

_run_lightweight_migrations()

def create_app():
    return app

# Error handling: in non-debug mode, show a simple 500 page and log details
@app.errorhandler(500)
def internal_error(e):
    error_id = uuid.uuid4().hex[:8]
    logging.exception("Unhandled exception (id=%s)", error_id)
    from flask import render_template
    return render_template('500.html', error_id=error_id), 500
