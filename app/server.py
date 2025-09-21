"""
project: Adventure MUD
module: server.py
https://github.com/zebadrabbit/Adventure
License: MIT

Server bootstrap and admin shell utilities.

Exposes helpers to start the Socket.IO server and an interactive admin shell
for basic user management. The admin shell can receive events from the app via
an in-memory queue (e.g., login/logout notifications).
"""

import threading
import queue
import signal
import sys
from app import app, socketio, db
import logging
from logging.handlers import RotatingFileHandler
from app.models.models import User, Item
from werkzeug.security import generate_password_hash
import os

# Global event queue for admin shell. The Flask app reads this to publish
# events (e.g., auth route emits) to the admin shell printer thread.
admin_event_queue = queue.Queue()
app.config['ADMIN_EVENT_QUEUE'] = admin_event_queue

def start_server(host='0.0.0.0', port=5000, debug: bool = False):  # pragma: no cover (integration / runtime only)
    """Start the Socket.IO server and ensure DB tables exist.

    When debug=True, Flask's debugger and reloader provide verbose tracebacks.
    Also configures application logging to a rotating file and console.
    """
    with app.app_context():
        db.create_all()
        _run_migrations()
        seed_items()
        _configure_logging()
    try:
        print(f"[INFO] Starting Socket.IO server on {host}:{port} (async_mode={socketio.async_mode})")
        # Let Flask-SocketIO choose appropriate server (eventlet/gevent/werkzeug)
        socketio.run(app, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user (Ctrl+C)")
        sys.exit(0)

def _configure_logging():
    """Configure logging to both console and a rotating file in instance/.

    The file path will be instance/app.log. Retains a few backups to avoid growth.
    """
    log_dir = app.instance_path
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        pass
    log_path = os.path.join(log_dir, 'app.log')

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Rotating file handler
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

    # Console handler (for terminals/tasks that show output)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

    # Avoid duplicate handlers if reconfigured
    for h in list(root.handlers):
        root.removeHandler(h)

    root.addHandler(file_handler)
    root.addHandler(console)

def start_admin_shell():  # pragma: no cover (interactive)
    """Initialize application context and start the admin shell loop."""
    with app.app_context():
        db.create_all()
        _run_migrations()
        seed_items()
        _configure_logging()
    admin_shell()

def seed_items():
    """Seed initial catalog items if they don't already exist."""
    existing = {i.slug for i in Item.query.all()}
    seeds = [
        # Weapons/Armor
        dict(slug='short-sword', name='Short Sword', type='weapon', description='A simple steel short sword.', value_copper=500),
        dict(slug='dagger', name='Dagger', type='weapon', description='A lightweight dagger.', value_copper=250),
        dict(slug='oak-staff', name='Oak Staff', type='weapon', description='A sturdy oak staff for channeling magic.', value_copper=400),
        dict(slug='wooden-shield', name='Wooden Shield', type='armor', description='A round wooden shield.', value_copper=300),
        dict(slug='leather-armor', name='Leather Armor', type='armor', description='Basic protective leather armor.', value_copper=600),
        # Potions/Consumables
        dict(slug='potion-healing', name='Potion of Healing', type='potion', description='Restores a small amount of HP.', value_copper=150),
        dict(slug='potion-mana', name='Potion of Mana', type='potion', description='Restores a small amount of mana.', value_copper=150),
        # Tools
        dict(slug='lockpicks', name='Lockpicks', type='tool', description='Useful for opening tricky locks.', value_copper=200),
        dict(slug='hunting-bow', name='Hunting Bow', type='weapon', description='A simple bow for hunting.', value_copper=550),
        dict(slug='herbal-pouch', name='Herbal Pouch', type='tool', description='Druidic herbs and salves.', value_copper=180),
    ]
    created = 0
    for s in seeds:
        if s['slug'] not in existing:
            db.session.add(Item(**s))
            created += 1
    if created:
        db.session.commit()

def admin_shell():
    """
    Admin shell for server management.
    Commands:
      help                        Show this help message
      exit                        Exit the admin shell
      create user <username> [<password>]
                                Create a new user with optional password (default: changeme)
      list users                  List all registered users
      delete user <username>      Delete a user by username
            reset password <username> <new_password>
                                                                Reset a user's password
    """
    print("Admin shell. Type 'help' for commands. Type 'exit' to quit.")

    def event_printer():
        while True:
            msg = admin_event_queue.get()
            if msg == '__exit__':
                break
            print(f"\n[EVENT] {msg}")
            print('> ', end='', flush=True)

    printer_thread = threading.Thread(target=event_printer, daemon=True)
    printer_thread.start()

    def print_help():
        print("""
Available commands:
  help                        Show this help message
  exit                        Exit the admin shell
  create user <username> [<password>]
                              Create a new user with optional password (default: changeme)
  list users                  List all registered users
  delete user <username>      Delete a user by username
    reset password <username> <new_password>
                                                            Reset a user's password
    passwd <username> <new_password>
                                                            Alias for password reset
    set role <username> <role>  Set a user's role (admin|mod|user)
    ban <username> [reason..]   Ban a user with optional reason
    unban <username>            Remove ban
    list banned                 List banned users
    show user <username>        Show detailed user info
    set email <username> <email|none>
                                                            Set or clear a user's email
    note user <username> <text> Append a moderation note (timestamped)
Examples:
  create user alice secret123
  list users
  delete user alice
    reset password alice newSecret456
    passwd alice newSecret456
    ban alice Spamming chat
    unban alice
    note user alice Warned about language
""")

    while True:
        try:
            cmd = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting admin shell.")
            admin_event_queue.put('__exit__')
            break
        if not cmd:
            continue
        parts = cmd.split()
        if parts[0] == 'exit':
            admin_event_queue.put('__exit__')
            break
        elif parts[0] == 'help':
            print_help()
            continue
        elif parts[0] == 'create' and len(parts) >= 3 and parts[1] == 'user':
            username = parts[2]
            password = parts[3] if len(parts) > 3 else 'changeme'
            with app.app_context():
                if User.query.filter_by(username=username).first():
                    print(f"[ERROR] User '{username}' already exists.")
                else:
                    user = User(username=username, password=generate_password_hash(password))
                    db.session.add(user)
                    db.session.commit()
                    print(f"[OK] User '{username}' created with password '{password}'.")
            continue
        elif parts[0] == 'list' and len(parts) == 2 and parts[1] == 'users':
            with app.app_context():
                users = User.query.all()
                if not users:
                    print("[INFO] No users found.")
                else:
                    print("Registered users:")
                    for u in users:
                        r = getattr(u, 'role', 'user')
                        banned = ' BANNED' if getattr(u, 'banned', False) else ''
                        print(f"  - {u.username} [{r}]{banned}")
            continue
        elif parts[0] == 'reset' and len(parts) == 4 and parts[1] == 'password':
            username = parts[2]
            new_password = parts[3]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.password = generate_password_hash(new_password)
                    db.session.commit()
                    print(f"[OK] Password for '{username}' has been reset.")
            continue
        elif parts[0] == 'passwd' and len(parts) == 3:
            username = parts[1]
            new_password = parts[2]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.password = generate_password_hash(new_password)
                    db.session.commit()
                    print(f"[OK] Password for '{username}' has been reset.")
            continue
        elif parts[0] == 'delete' and len(parts) == 3 and parts[1] == 'user':
            username = parts[2]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    db.session.delete(user)
                    db.session.commit()
                    print(f"[OK] User '{username}' deleted.")
            continue
        elif parts[0] == 'set' and len(parts) == 4 and parts[1] == 'role':
            username = parts[2]
            role = parts[3]
            if role not in ('admin', 'mod', 'user'):
                print("[ERROR] Role must be one of: admin, mod, user")
                continue
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.role = role
                    db.session.commit()
                    print(f"[OK] Role for '{username}' set to {role}.")
            continue
        elif parts[0] == 'ban' and len(parts) >= 2:
            username = parts[1]
            reason = ' '.join(parts[2:]).strip() if len(parts) > 2 else None
            from datetime import datetime
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.banned = True
                    user.ban_reason = reason
                    user.banned_at = datetime.utcnow()
                    db.session.commit()
                    print(f"[OK] User '{username}' banned." + (f" Reason: {reason}" if reason else ''))
            continue
        elif parts[0] == 'unban' and len(parts) == 2:
            username = parts[1]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.banned = False
                    user.ban_reason = None
                    user.banned_at = None
                    db.session.commit()
                    print(f"[OK] User '{username}' unbanned.")
            continue
        elif parts[0] == 'list' and len(parts) == 2 and parts[1] == 'banned':
            with app.app_context():
                users = User.query.filter_by(banned=True).all()
                if not users:
                    print("[INFO] No banned users.")
                else:
                    print("Banned users:")
                    for u in users:
                        print(f"  - {u.username}" + (f" ({u.ban_reason})" if u.ban_reason else ''))
            continue
        elif parts[0] == 'show' and len(parts) == 3 and parts[1] == 'user':
            username = parts[2]
            from datetime import datetime
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    print(f"User: {user.username}")
                    print(f"  Role: {user.role}")
                    print(f"  Email: {user.email or '-'}")
                    print(f"  Banned: {user.banned}")
                    if user.banned:
                        print(f"  Banned At: {user.banned_at}")
                        print(f"  Ban Reason: {user.ban_reason or '-'}")
                    notes_preview = (user.notes[:120] + '...') if user.notes and len(user.notes) > 120 else (user.notes or '-')
                    print(f"  Notes: {notes_preview}")
            continue
        elif parts[0] == 'set' and len(parts) == 4 and parts[1] == 'email':
            username = parts[2]
            email = parts[3]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.email = None if email.lower() == 'none' else email
                    db.session.commit()
                    print(f"[OK] Email for '{username}' set to {user.email or 'None'}.")
            continue
        elif parts[0] == 'note' and len(parts) >= 3 and parts[1] == 'user':
            username = parts[2]
            text = ' '.join(parts[3:]).strip()
            if not text:
                print('[ERROR] Note text required.')
                continue
            from datetime import datetime
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    stamp = datetime.utcnow().isoformat(timespec='seconds')
                    existing = user.notes or ''
                    new_block = f"[{stamp}] {text}\n"
                    user.notes = (existing + new_block) if existing else new_block
                    db.session.commit()
                    print(f"[OK] Note added for '{username}'.")
            continue
        else:
            print("[ERROR] Unknown or malformed command. Type 'help' for a list of commands.")


def _run_migrations():
    """Very lightweight migration helper for SQLite.

    Adds missing columns using ALTER TABLE if needed. This is safe for
    SQLite and keeps the project simple without Alembic.
    """
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    # Add 'email' column to user if missing
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'email' not in user_cols:
        try:
            db.session.execute(text('ALTER TABLE user ADD COLUMN email VARCHAR(120)'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add 'role' column if missing
    inspector = inspect(db.engine)
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'role' not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add moderation columns if missing: banned, ban_reason, notes, banned_at
    inspector = inspect(db.engine)
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'banned' not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN banned BOOLEAN NOT NULL DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'ban_reason' not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN ban_reason TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'notes' not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN notes TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'banned_at' not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN banned_at DATETIME"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add 'xp' and 'level' columns to character if missing
    char_cols = {c['name'] for c in inspector.get_columns('character')}
    if 'xp' not in char_cols:
        try:
            db.session.execute(text('ALTER TABLE character ADD COLUMN xp INTEGER NOT NULL DEFAULT 0'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    if 'level' not in char_cols:
        try:
            db.session.execute(text('ALTER TABLE character ADD COLUMN level INTEGER NOT NULL DEFAULT 1'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
