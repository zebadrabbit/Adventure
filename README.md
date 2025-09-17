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
  - `models/` - Database models
  - `routes/` - Flask routes (auth, main)
  - `websockets/` - WebSocket event handlers
  - `static/` - Static files (JS, CSS)
  - `templates/` - HTML templates


## Notes


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


## Environment configuration

Local development uses a `.env` file (auto-loaded):


Key variables:

Load explicitly (optional):
```
python run.py --env-file .env server
```


## VS Code tasks

Predefined tasks to run the project from the Command Palette:


These are defined in `.vscode/tasks.json` and use the selected Python interpreter.


## HTTP routes and Socket.IO events

HTTP routes:

Socket.IO events:

## Versioning and Changelog

This project follows Semantic Versioning (SemVer): MAJOR.MINOR.PATCH.

- Increment MINOR for new features that are backwards compatible.
- Increment PATCH for backwards-compatible bug fixes.
- Increment MAJOR if you make incompatible API or data changes.

See CHANGELOG.md for a curated list of notable changes per release.

