"""Flask application factory and core extensions setup.

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
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Let Flask-SocketIO select best async_mode based on installed deps (eventlet/gevent/threading)
socketio = SocketIO(
    app,
    # In dev, allow all origins by default; set explicit origins in production
    cors_allowed_origins=os.getenv('CORS_ALLOWED_ORIGINS', '*')
)

# Register HTTP blueprints
from app.routes import auth, main
app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)

# Import websocket handlers so their event decorators register with Socket.IO
from app.websockets import game, lobby

def create_app():
    return app
