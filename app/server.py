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

import glob
import logging
import os
import queue
import sys
import threading
from logging.handlers import RotatingFileHandler

from sqlalchemy import text as _text
from werkzeug.security import generate_password_hash

from app import app, db, socketio
from app.models.models import Item, User

# Global event queue for admin shell. The Flask app reads this to publish
# events (e.g., auth route emits) to the admin shell printer thread.
admin_event_queue = queue.Queue()
app.config["ADMIN_EVENT_QUEUE"] = admin_event_queue


def start_server(host="0.0.0.0", port=5000, debug: bool = False):  # pragma: no cover (integration / runtime only)
    """Start the Socket.IO server and ensure DB tables exist.

    When debug=True, Flask's debugger and reloader provide verbose tracebacks.
    Also configures application logging to a rotating file and console.
    """
    with app.app_context():
        db.create_all()
        _run_migrations()
        seed_items()
        _run_migrations()  # ensure new columns after seeds
        _load_sql_item_seeds()
        _run_migrations()  # ensure after bulk load
        _seed_game_config()
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
    log_path = os.path.join(log_dir, "app.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Rotating file handler
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    # Console handler (for terminals/tasks that show output)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

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
        _load_sql_item_seeds()
        _seed_game_config()
        _configure_logging()
    admin_shell()


def seed_items():
    """Seed initial catalog items if they don't already exist."""
    # Defensive: ensure new columns (like weight) exist before querying
    try:
        from sqlalchemy import inspect, text

        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("item")}
        if "weight" not in cols:
            db.session.execute(text("ALTER TABLE item ADD COLUMN weight FLOAT NOT NULL DEFAULT 1.0"))
            db.session.commit()
    except Exception:
        db.session.rollback()
        pass
    existing = {i.slug: i for i in Item.query.all()}
    seeds = [
        dict(
            slug="short-sword",
            name="Short Sword",
            type="weapon",
            description="A simple steel short sword.",
            value_copper=500,
            level=1,
            rarity="common",
        ),
        dict(
            slug="dagger",
            name="Dagger",
            type="weapon",
            description="A lightweight dagger.",
            value_copper=250,
            level=1,
            rarity="common",
        ),
        dict(
            slug="oak-staff",
            name="Oak Staff",
            type="weapon",
            description="A sturdy oak staff for channeling magic.",
            value_copper=400,
            level=1,
            rarity="common",
        ),
        dict(
            slug="wooden-shield",
            name="Wooden Shield",
            type="armor",
            description="A round wooden shield.",
            value_copper=300,
            level=1,
            rarity="common",
        ),
        dict(
            slug="leather-armor",
            name="Leather Armor",
            type="armor",
            description="Basic protective leather armor.",
            value_copper=600,
            level=1,
            rarity="common",
        ),
        dict(
            slug="potion-healing",
            name="Potion of Healing",
            type="potion",
            description="Restores a small amount of HP.",
            value_copper=150,
            level=0,
            rarity="common",
        ),
        dict(
            slug="potion-mana",
            name="Potion of Mana",
            type="potion",
            description="Restores a small amount of mana.",
            value_copper=150,
            level=0,
            rarity="common",
        ),
        dict(
            slug="lockpicks",
            name="Lockpicks",
            type="tool",
            description="Useful for opening tricky locks.",
            value_copper=200,
            level=0,
            rarity="uncommon",
        ),
        dict(
            slug="hunting-bow",
            name="Hunting Bow",
            type="weapon",
            description="A simple bow for hunting.",
            value_copper=550,
            level=2,
            rarity="common",
        ),
        dict(
            slug="herbal-pouch",
            name="Herbal Pouch",
            type="tool",
            description="Druidic herbs and salves.",
            value_copper=180,
            level=0,
            rarity="common",
        ),
    ]
    created = 0
    for s in seeds:
        if s["slug"] not in existing:
            db.session.add(Item(**s))
            created += 1
        else:
            # Backfill level/rarity if missing (legacy rows)
            row = existing[s["slug"]]
            changed = False
            if getattr(row, "level", 0) == 0 and s["level"]:
                row.level = s["level"]
                changed = True
            if getattr(row, "rarity", "common") == "common" and s["rarity"] != "common":
                row.rarity = s["rarity"]
                changed = True
            if changed:
                created += 0  # no new row, but we update
    if created:
        db.session.commit()


def _load_sql_item_seeds():
    """Load bulk item seed data from /sql/*.sql files.

    This is idempotent: for each INSERT it relies on the item slug existing or not.
    We wrap in a transaction per file; errors are logged and rolled back without
    aborting startup. If level/rarity columns are not present in the SQL, they
    will default to 0/common and can be backfilled later by heuristics.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # project root assumed one level up from app/ directory
    project_root = os.path.abspath(os.path.join(base_dir, ".."))
    sql_dir = os.path.join(project_root, "sql")
    if not os.path.isdir(sql_dir):
        return
    pattern = os.path.join(sql_dir, "*.sql")
    files = sorted(glob.glob(pattern))
    if not files:
        return
    from app.models.models import Item

    existing = {i.slug for i in Item.query.all()}
    imported = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                sql_text = f.read()
            # Split on semicolons naive; acceptable for simple INSERT sets
            statements = [s.strip() for s in sql_text.split(";") if s.strip()]
            for stmt in statements:
                # Only process INSERTs into item table; ignore others for safety
                low = stmt.lower()
                if "insert" not in low or "into" not in low or "item" not in low:
                    continue
                # Quick slug extract heuristic: look for values ('slug', ...)
                slug_token = None
                # attempt to find first quoted string after VALUES (
                parts = stmt.split("VALUES")
                if len(parts) > 1:
                    vals_part = parts[1]
                    # crude parse for first parenthetical group
                    start = vals_part.find("(")
                    end = vals_part.find(")")
                    if start != -1 and end != -1 and end > start:
                        group = vals_part[start + 1 : end]
                        # slug usually first value
                        first = group.split(",")[0].strip()
                        if first.startswith("'") and first.endswith("'"):
                            slug_token = first.strip("'")
                if slug_token and slug_token in existing:
                    continue
                try:
                    db.session.execute(_text(stmt))
                    if slug_token:
                        existing.add(slug_token)
                        imported += 1
                except Exception:
                    db.session.rollback()
                    continue
            db.session.commit()
        except Exception:
            db.session.rollback()
            continue
    if imported:
        # Backfill simple heuristics for level/rarity based on name keywords
        _infer_levels_and_rarity()


def _infer_levels_and_rarity():
    """Infer level/rarity for items lacking them (level=0) via name heuristics.

    This is a coarse fallback until explicit metadata lives in the SQL files.
    """
    from app.models.models import Item

    items = Item.query.all()
    updated = 0
    for it in items:
        if getattr(it, "level", 0) and getattr(it, "rarity", "common") != "common":
            continue
        name = (it.name or "").lower()
        lvl = getattr(it, "level", 0)
        rar = getattr(it, "rarity", "common")
        if lvl == 0:
            # Very rough mapping
            if any(k in name for k in ["mythic", "ancient", "dragon"]):
                lvl = 18
                rar = "mythic"
            elif any(k in name for k in ["legendary", "phoenix", "celestial"]):
                lvl = 16
                rar = "legendary"
            elif any(k in name for k in ["epic", "demon", "void", "starlight"]):
                lvl = 12
                rar = "epic"
            elif any(k in name for k in ["rare", "arcane", "masters", "veteran"]):
                lvl = 8
                rar = "rare"
            elif any(k in name for k in ["uncommon", "fine", "reinforced", "sturdy"]):
                lvl = 4
                rar = "uncommon"
            else:
                lvl = 1
                rar = "common"
        if getattr(it, "level", 0) != lvl or getattr(it, "rarity", "common") != rar:
            it.level = lvl
            it.rarity = rar
            updated += 1
    if updated:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def _seed_game_config():
    """Insert default gameplay configuration rows if they do not exist yet.

    This provides DB-backed tunable values for encumbrance, capacity, and other
    systems that were previously hard-coded. Safe to call multiple times.
    """
    import json as _json

    from app.models.models import GameConfig

    existing = {row.key: row for row in GameConfig.query.all()}
    defaults = {
        "encumbrance": {
            "base_capacity": 10,  # Base carry capacity before STR scaling
            "per_str": 5,  # Additional capacity per point of STR
            "warn_pct": 1.0,  # At or below this = normal
            "hard_cap_pct": 1.10,  # Above this percentage of capacity: reject new items
            "dex_penalty": 2,  # DEX penalty applied when between warn_pct and hard_cap_pct
        },
        "tick_costs": {
            "move": 1,
            "search": 2,
            "use_item": 1,
            "cast_spell": 1,
            "equip": 0,
            "unequip": 0,
            "consume": 1,
            "loot_claim": 0,
        },
    }
    created = 0
    for k, v in defaults.items():
        if k not in existing:
            row = GameConfig(key=k, value=_json.dumps(v))
            db.session.add(row)
            created += 1
    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


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
            if msg == "__exit__":
                break
            print(f"\n[EVENT] {msg}")
            print("> ", end="", flush=True)

    printer_thread = threading.Thread(target=event_printer, daemon=True)
    printer_thread.start()

    def print_help():
        print(
            """
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
"""
        )

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting admin shell.")
            admin_event_queue.put("__exit__")
            break
        if not cmd:
            continue
        parts = cmd.split()
        if parts[0] == "exit":
            admin_event_queue.put("__exit__")
            break
        elif parts[0] == "help":
            print_help()
            continue
        elif parts[0] == "create" and len(parts) >= 3 and parts[1] == "user":
            username = parts[2]
            password = parts[3] if len(parts) > 3 else "changeme"
            with app.app_context():
                if User.query.filter_by(username=username).first():
                    print(f"[ERROR] User '{username}' already exists.")
                else:
                    user = User(username=username, password=generate_password_hash(password))
                    db.session.add(user)
                    db.session.commit()
                    print(f"[OK] User '{username}' created with password '{password}'.")
            continue
        elif parts[0] == "list" and len(parts) == 2 and parts[1] == "users":
            with app.app_context():
                users = User.query.all()
                if not users:
                    print("[INFO] No users found.")
                else:
                    print("Registered users:")
                    for u in users:
                        r = getattr(u, "role", "user")
                        banned = " BANNED" if getattr(u, "banned", False) else ""
                        print(f"  - {u.username} [{r}]{banned}")
            continue
        elif parts[0] == "reset" and len(parts) == 4 and parts[1] == "password":
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
        elif parts[0] == "passwd" and len(parts) == 3:
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
        elif parts[0] == "delete" and len(parts) == 3 and parts[1] == "user":
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
        elif parts[0] == "set" and len(parts) == 4 and parts[1] == "role":
            username = parts[2]
            role = parts[3]
            if role not in ("admin", "mod", "user"):
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
        elif parts[0] == "ban" and len(parts) >= 2:
            username = parts[1]
            reason = " ".join(parts[2:]).strip() if len(parts) > 2 else None
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
                    print(f"[OK] User '{username}' banned." + (f" Reason: {reason}" if reason else ""))
            continue
        elif parts[0] == "unban" and len(parts) == 2:
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
        elif parts[0] == "list" and len(parts) == 2 and parts[1] == "banned":
            with app.app_context():
                users = User.query.filter_by(banned=True).all()
                if not users:
                    print("[INFO] No banned users.")
                else:
                    print("Banned users:")
                    for u in users:
                        print(f"  - {u.username}" + (f" ({u.ban_reason})" if u.ban_reason else ""))
            continue
        elif parts[0] == "show" and len(parts) == 3 and parts[1] == "user":
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
                    notes_preview = (
                        (user.notes[:120] + "...") if user.notes and len(user.notes) > 120 else (user.notes or "-")
                    )
                    print(f"  Notes: {notes_preview}")
            continue
        elif parts[0] == "set" and len(parts) == 4 and parts[1] == "email":
            username = parts[2]
            email = parts[3]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    user.email = None if email.lower() == "none" else email
                    db.session.commit()
                    print(f"[OK] Email for '{username}' set to {user.email or 'None'}.")
            continue
        elif parts[0] == "note" and len(parts) >= 3 and parts[1] == "user":
            username = parts[2]
            text = " ".join(parts[3:]).strip()
            if not text:
                print("[ERROR] Note text required.")
                continue
            from datetime import datetime

            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    stamp = datetime.utcnow().isoformat(timespec="seconds")
                    existing = user.notes or ""
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
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "email" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add 'role' column if missing
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "role" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add moderation columns if missing: banned, ban_reason, notes, banned_at
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "banned" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN banned BOOLEAN NOT NULL DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "ban_reason" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN ban_reason TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "notes" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN notes TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "banned_at" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN banned_at DATETIME"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Add 'xp' and 'level' columns to character if missing
    # Character table may not exist yet in some minimal test DBs; guard access
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "character" in tables:
        char_cols = {c["name"] for c in inspector.get_columns("character")}
        if "xp" not in char_cols:
            try:
                db.session.execute(text("ALTER TABLE character ADD COLUMN xp INTEGER NOT NULL DEFAULT 0"))
                db.session.commit()
            except Exception:
                db.session.rollback()
                pass
        if "level" not in char_cols:
            try:
                db.session.execute(text("ALTER TABLE character ADD COLUMN level INTEGER NOT NULL DEFAULT 1"))
                db.session.commit()
            except Exception:
                db.session.rollback()
                pass
    # Add 'explored_tiles' persistence column to user (JSON string) if missing
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "explored_tiles" not in user_cols:
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN explored_tiles TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass
    # Track schema version (very lightweight)
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        # Ensure loot table exists (SQLAlchemy create_all will also handle, but explicit for clarity)
        if "dungeon_loot" not in tables:
            db.create_all()  # rely on model metadata
        # Ensure game_clock table exists (created via SQLAlchemy metadata)
        if "game_clock" not in tables:
            try:
                db.create_all()
            except Exception:
                pass
        else:
            # Add combat column if missing
            gc_cols = {c["name"] for c in inspector.get_columns("game_clock")}
            if "combat" not in gc_cols:
                try:
                    db.session.execute(text("ALTER TABLE game_clock ADD COLUMN combat BOOLEAN NOT NULL DEFAULT 0"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        # Add new Item columns if missing
        if "item" in tables:
            item_cols = {c["name"] for c in inspector.get_columns("item")}
            if "level" not in item_cols:
                try:
                    db.session.execute(text("ALTER TABLE item ADD COLUMN level INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            if "rarity" not in item_cols:
                try:
                    db.session.execute(text("ALTER TABLE item ADD COLUMN rarity VARCHAR(20) NOT NULL DEFAULT 'common'"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            if "weight" not in item_cols:
                try:
                    db.session.execute(text("ALTER TABLE item ADD COLUMN weight FLOAT NOT NULL DEFAULT 1.0"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        # Add GameConfig table if missing
        if "game_config" not in tables:
            try:
                db.session.execute(
                    text(
                        "CREATE TABLE game_config (id INTEGER PRIMARY KEY, key VARCHAR(80) UNIQUE NOT NULL, value TEXT NOT NULL)"
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Schema version table creation already handled above
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "schema_version" not in tables:
            db.session.execute(text("CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"))
            db.session.execute(text("INSERT INTO schema_version (id, version) VALUES (1, 1)"))
            db.session.commit()
        else:
            row = db.session.execute(text("SELECT version FROM schema_version WHERE id=1")).fetchone()
            ver = row[0] if row else 0
            target = 1
            if ver < target:
                db.session.execute(
                    text("UPDATE schema_version SET version=:v WHERE id=1"),
                    {"v": target},
                )
                db.session.commit()
        # Monster catalog table (created by raw SQL seeding; ensure exists & backfill columns if added in code first)
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "monster_catalog" in tables:
            mcols = {c["name"] for c in inspector.get_columns("monster_catalog")}
            # Backfill optional JSON-ish columns
            for col, ddl in (
                ("resistances", "ALTER TABLE monster_catalog ADD COLUMN resistances TEXT"),
                ("damage_types", "ALTER TABLE monster_catalog ADD COLUMN damage_types TEXT"),
            ):
                if col not in mcols:
                    try:
                        db.session.execute(text(ddl))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
        else:
            # If seed not yet loaded, create minimal table so ORM queries don't explode (subset of original schema)
            try:
                db.session.execute(
                    text(
                        """
CREATE TABLE monster_catalog (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    level_min INTEGER NOT NULL DEFAULT 1,
    level_max INTEGER NOT NULL DEFAULT 1,
    base_hp INTEGER NOT NULL,
    base_damage INTEGER NOT NULL,
    armor INTEGER NOT NULL DEFAULT 0,
    speed INTEGER NOT NULL DEFAULT 10,
    rarity TEXT NOT NULL DEFAULT 'common',
    family TEXT NOT NULL,
    traits TEXT,
    loot_table TEXT,
    special_drop_slug TEXT,
    xp_base INTEGER NOT NULL DEFAULT 0,
    boss INTEGER NOT NULL DEFAULT 0,
    resistances TEXT,
    damage_types TEXT
)
"""
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        db.session.rollback()
        pass
