# MUD Game (Multi-User Dungeon)

A web-based multiplayer dungeon adventure game built with Python (Flask, Flask-SocketIO), SQLite, and Bootstrap.

## Features

## Getting Started

### 1. Create a virtual environment and install dependencies
```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the server
```
python run.py server
```

### 3. Open in browser
Visit http://localhost:5000


## Project Structure
  - `models/` - Database models
  - `routes/` - Flask routes (auth, main)
  - `websockets/` - WebSocket event handlers
  - `static/` - Static files (JS, CSS)
  - `templates/` - HTML templates


## Notes
# Adventure
A modern multiplayer MUD web game with Flask, WebSockets, Bootstrap, and real-time features.

# MUD Game (Multi-User Dungeon)

A web-based multiplayer dungeon adventure game built with Python (Flask, Flask-SocketIO), SQLite, and Bootstrap.

## Features
- User authentication (login/register)
- Character management (stats, gear, items)
- Multiplayer via WebSockets
- Weekly randomized world/dungeon generation
- SQLite for persistent storage
- Responsive Bootstrap frontend

## Getting Started

### 1. Create a virtual environment and install dependencies
```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the server
```
python run.py server
```

### 3. Open in browser
Visit http://localhost:5000

---

## Project Structure
- `app/` - Main application package
  - `models/` - Database models
  - `routes/` - Flask routes (auth, main)
  - `websockets/` - WebSocket event handlers
  - `static/` - Static files (JS, CSS)
  - `templates/` - HTML templates
- `.github/` - Copilot instructions

---

## Notes
- Replace the `SECRET_KEY` in `app/__init__.py` for production.
- Dungeon/world generation logic to be implemented.
- This is a starter template. Expand as needed!

---

## Command Line Usage

The entry point `run.py` provides a robust CLI with subcommands and flags.

Show help:
```
python run.py --help
python run.py server --help
python run.py admin --help
```

Run server (defaults HOST=0.0.0.0, PORT=5000):
```
python run.py server
python run.py server --host 127.0.0.1 --port 8080
python run.py server --db sqlite:///instance/dev.db
```

Environment variables:
- `HOST` — Bind address (default: 0.0.0.0)
- `PORT` — Port (default: 5000)
- `DATABASE_URL` — SQLAlchemy database URI. If unset, the app uses an absolute
  SQLite path under `./instance/mud.db` (recommended for dev). If you set it,
  prefer an absolute sqlite path like `sqlite:////full/path/to/instance/mud.db`.

You can also load variables from a `.env` file automatically (python-dotenv is included):
```
python run.py --env-file .env server
```

Admin shell:
```
python run.py admin
```
Commands inside the shell:
- `help` — Show help
- `create user <username> [<password>]` — Create a new user (default password: `changeme`)
- `list users` — List all users
- `delete user <username>` — Delete a user
- `reset password <username> <new_password>` — Reset a user's password
- `exit` — Exit the admin shell

---

## Environment configuration

Local development uses a `.env` file (auto-loaded):

- `.env.example` — Template with placeholders and examples
- `.env` — Your local values (gitignored)

Key variables:
- `SECRET_KEY` — Flask session signing key (generate a strong value in prod)
- `DATABASE_URL` — SQLAlchemy URI (defaults to sqlite:///instance/mud.db)
- `HOST`, `PORT` — Bind address and port
- `CORS_ALLOWED_ORIGINS` — Comma-separated origins for Socket.IO

Load explicitly (optional):
```
python run.py --env-file .env server
```

---

## VS Code tasks

Predefined tasks to run the project from the Command Palette:

- Run Adventure (dev) — `python run.py`
- Run Adventure (server) — `python run.py server`
- Run Adventure (admin) — `python run.py admin`

These are defined in `.vscode/tasks.json` and use the selected Python interpreter.

---

## HTTP routes and Socket.IO events

HTTP routes:
- `GET /` — Home
- `GET/POST /login` — Login
- `GET/POST /register` — Register
- `GET /logout` — Logout
- `GET/POST /dashboard` — Character list and creation
- `POST /delete_character/<id>` — Delete a character

Socket.IO events:
- `lobby_chat_message` — Broadcast lobby chat; emits `lobby_chat_message` to all clients
- `join_game` — Join a room; emits `status` in that room
- `leave_game` — Leave a room; emits `status` in that room
- `game_action` — Placeholder action handler; emits `game_update` in that room
