<<<<<<< HEAD
# Adventure
A modern multiplayer MUD web game with Flask, WebSockets, Bootstrap, and real-time features.
=======
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

### 1. Install dependencies
```
pip install flask flask_sqlalchemy flask_login flask_socketio eventlet werkzeug
```

### 2. Run the app
```
python run.py
```

### 3. Open in browser
Visit [http://localhost:5000](http://localhost:5000)

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
>>>>>>> 1842575 (Initial commit: MUD game project scaffold, backend, frontend, and static assets)
