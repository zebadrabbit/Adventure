"""Adventure MUD CLI entry point.

Provides subcommands for running the Socket.IO server and launching the
interactive admin shell. Accepts configuration via flags and environment
variables, with optional .env loading.

Run `python run.py --help` for details.
"""

import argparse
import os
import signal
import sys
from textwrap import dedent

try:  # Optional color support
    from colorama import Fore, Style
    from colorama import init as _color_init

    _color_init()  # pragma: no cover
    _COLOR_ENABLED = True
except Exception:  # pragma: no cover

    class _Dummy:
        RESET_ALL = ""

    class _Fore:
        RED = GREEN = CYAN = MAGENTA = YELLOW = BLUE = WHITE = ""

    class _Style:
        BRIGHT = NORMAL = RESET_ALL = ""

    Fore = _Fore()
    Style = _Style()
    _COLOR_ENABLED = False

# Disable colors if output is not a real terminal (e.g., during pytest capture)
if "_COLOR_ENABLED" in globals():  # safety
    try:
        if _COLOR_ENABLED and not sys.stdout.isatty():  # pragma: no cover - environment dependent
            _COLOR_ENABLED = False
    except Exception:  # pragma: no cover
        _COLOR_ENABLED = False


def _load_version() -> str:
    try:
        with open("VERSION", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.3.4"


__version__ = _load_version()

try:
    # Optional: load .env automatically if available
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is optional
    load_dotenv = None


def parse_args(argv: list[str]) -> argparse.Namespace:
    description = """
    Adventure MUD Game Server

    Run the real-time Flask-SocketIO server or launch the interactive admin shell
    to manage users. Configuration can be provided via CLI flags or environment
    variables. If both are present, CLI flags take precedence.
    """

    epilog = dedent(
        """
        Environment variables:
          HOST            Bind address for the web server (default: 0.0.0.0)
          PORT            Port for the web server (default: 5000)
          DATABASE_URL    SQLAlchemy database URI (default: sqlite:///instance/mud.db)

        Examples:
          # Run the server on the default host and port
          python run.py server

          # Run the server on a custom port
          python run.py server --port 8080

          # Bind to localhost only and use a different database
          python run.py server --host 127.0.0.1 --db sqlite:///instance/dev.db

          # Load variables from .env then run the server
          python run.py --env-file .env server

          # Launch the interactive admin shell
          python run.py admin

        Admin shell quick reference:
          help                                 Show help inside the shell
          create user <username> [<password>]  Create user (default password: changeme)
          list users                           List all users
          delete user <username>               Delete a user
                    reset password <username> <password> Reset a user's password
          exit                                 Leave the admin shell
        """
    )

    parser = argparse.ArgumentParser(
        prog="Adventure",
        description=dedent(description),
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Path to a .env file to load before processing flags",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Adventure MUD Server {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # server subcommand
    server_parser = subparsers.add_parser(
        "server",
        help="Run the Socket.IO web server",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Run the real-time Flask/Socket.IO server",
    )
    server_parser.add_argument(
        "--host",
        default=None,
        help="Host interface to bind (default: env HOST or 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to listen on (default: env PORT or 5000)",
    )
    server_parser.add_argument(
        "--db",
        dest="db_uri",
        default=None,
        help="Database URI (default: env DATABASE_URL or sqlite:///instance/mud.db)",
    )
    server_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode with verbose error pages",
    )
    server_parser.set_defaults(command="server")

    # admin subcommand
    admin_parser = subparsers.add_parser(
        "admin",
        help="Launch the interactive admin shell",
        formatter_class=argparse.RawTextHelpFormatter,
        description=dedent(
            """
            Launch the interactive admin shell for managing users while the
            application context is loaded.

            Inside the shell, use commands such as:
              help                                 Show help inside the shell
              create user <username> [<password>]  Create a user (default pass: changeme)
              list users                           List all users
              delete user <username>               Delete a user
              exit                                 Leave the admin shell
            """
        ),
    )
    admin_parser.set_defaults(command="admin")

    # admin-tui subcommand (Textual)
    tui_parser = subparsers.add_parser(
        "admin-tui",
        help="Launch the Textual admin console (VT102-compatible)",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Run the terminal UI for admin: users, seeds, chat, and logs.",
    )
    tui_parser.add_argument(
        "--server",
        dest="server_url",
        default=None,
        help="Server URL for Socket.IO chat (default: http://127.0.0.1:5000)",
    )
    tui_parser.set_defaults(command="admin-tui")

    # reseed-items subcommand
    seed_parser = subparsers.add_parser(
        "reseed-items",
        help="Rebuild Item catalog from sql/*.sql files",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Clear (optional) and import armor/weapons/potions/misc item SQL seed files.",
    )
    seed_parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not delete existing categorized rows before import (default deletes).",
    )
    seed_parser.set_defaults(command="reseed-items")

    # import-items-csv
    import_items_parser = subparsers.add_parser(
        "import-items-csv",
        help="Import/Upsert items from a CSV file (same columns as admin UI)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    import_items_parser.add_argument("path", help="Path to items CSV file")
    import_items_parser.set_defaults(command="import-items-csv")

    # import-monsters-csv
    import_monsters_parser = subparsers.add_parser(
        "import-monsters-csv",
        help="Import/Upsert monsters from a CSV file (same columns as admin UI)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    import_monsters_parser.add_argument("path", help="Path to monsters CSV file")
    import_monsters_parser.set_defaults(command="import-monsters-csv")

    # config-get
    cfg_get_parser = subparsers.add_parser(
        "config-get",
        help="Print a GameConfig value by key",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    cfg_get_parser.add_argument("key", help="Config key")
    cfg_get_parser.set_defaults(command="config-get")

    # config-set
    cfg_set_parser = subparsers.add_parser(
        "config-set",
        help="Set a GameConfig key to a value (raw string)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    cfg_set_parser.add_argument("key", help="Config key")
    cfg_set_parser.add_argument("value", help="Raw value (quote JSON externally)")
    cfg_set_parser.set_defaults(command="config-set")

    # make-admin
    mk_admin = subparsers.add_parser(
        "make-admin",
        help="Promote a user to admin role (creates if missing with password 'changeme')",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    mk_admin.add_argument("username", help="Username to promote")
    mk_admin.set_defaults(command="make-admin")

    # If no subcommand provided, default to server
    if len(argv) == 0:
        argv = ["server"]

    args = parser.parse_args(argv)
    return args


def main(argv: list[str]) -> int:
    # Load .env if requested and available
    args = parse_args(argv)
    if args and getattr(args, "env_file", None) and load_dotenv:
        load_dotenv(args.env_file)
    elif load_dotenv:
        # Load default .env if present (no error if missing)
        load_dotenv()

    # Resolve configuration from CLI flags or env vars
    env_host = os.getenv("HOST", "0.0.0.0")
    env_port = int(os.getenv("PORT", "5000"))
    env_db = os.getenv("DATABASE_URL")

    host = getattr(args, "host", None) or env_host
    port = int(getattr(args, "port", None) or env_port)
    db_uri_cli = getattr(args, "db_uri", None)

    # Make DATABASE_URL available to the Flask app BEFORE importing it,
    # but only if explicitly provided via CLI or already set in the env.
    if db_uri_cli:
        os.environ["DATABASE_URL"] = db_uri_cli
    # If env_db is already set, leave it as-is (do not override with a relative default)

    # For display purposes only
    db_banner = db_uri_cli or env_db or "auto (instance/mud.db)"

    def handle_sigint(sig, frame):
        print("\n[INFO] Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    mode = (getattr(args, "command", None) or "server").lower()

    # Import server entrypoints only after environment is ready
    from app.server import start_admin_shell, start_server

    # Startup banner
    # Build colored banner lines
    title = (
        f"{Fore.CYAN}{Style.BRIGHT}MUD Game Server Bootup{Style.RESET_ALL}"
        if _COLOR_ENABLED
        else "MUD Game Server Bootup"
    )

    def label(text: str) -> str:
        return f"{Fore.YELLOW}{text}{Style.RESET_ALL}" if _COLOR_ENABLED else text

    def value(val: str | int) -> str:
        return f"{Fore.GREEN}{val}{Style.RESET_ALL}" if _COLOR_ENABLED else str(val)

    divider = (Fore.MAGENTA + "=" * 40 + Style.RESET_ALL) if _COLOR_ENABLED else "=" * 40
    lines = [
        divider,
        f"  {title}",
        divider,
        f"  {label('Mode:'):12} {value(mode.upper())}",
        f"  {label('Host:'):12} {value(host)}",
        f"  {label('Port:'):12} {value(port)}",
        f"  {label('Database:'):12} {value(db_banner)}",
        f"  {label('WebSockets:'):12} {value('enabled')}",
        f"  {label('Flask-Login:'):12} {value('enabled')}",
        f"  {label('Admin Shell:'):12} {value('YES' if mode == 'admin' else 'NO')}",
        divider,
        "",
    ]
    print("\n".join(lines))
    try:
        from app.logging_utils import log

        log.info(event="startup", mode=mode, host=host, port=port, db=db_banner)
    except Exception:
        pass

    if mode == "admin":
        start_admin_shell()
        return 0
    elif mode == "admin-tui":
        # Lazy import so running the web server doesn't require Textual
        try:
            from app.admin_tui import run_admin_tui  # type: ignore
        except ModuleNotFoundError:
            print(
                "[ERROR] The 'textual' package is not installed. Install it with:\n  pip install textual python-socketio\nOr add it via requirements and reinstall your venv."
            )
            return 1
        run_admin_tui(server_url=getattr(args, "server_url", None))
        return 0
    elif mode == "reseed-items":
        from app.seed_items import reseed_items

        clear = not getattr(args, "no_clear", False)
        reseed_items(clear_first=clear, verbose=True)
        return 0
    elif mode == "import-items-csv":
        from app import db
        from app.models.models import Item
        from app.routes.admin import (
            REQUIRED_ITEM_COLUMNS,
            _parse_csv,
            _validate_item_rows,
        )

        path = getattr(args, "path")
        if not os.path.exists(path):
            print(f"[ERROR] File not found: {path}")
            return 1
        from app import create_app

        app = create_app()
        with app.app_context():
            with open(path, "rb") as f:
                rows, parse_errors = _parse_csv(f, REQUIRED_ITEM_COLUMNS)
            if parse_errors:
                for e in parse_errors:
                    print("ERROR:", e)
                return 1
            val_errors = _validate_item_rows(rows)
            if val_errors:
                for e in val_errors:
                    print("ERROR:", e)
                return 1
            changed = 0
            for r in rows:
                slug = r["slug"]
                obj = Item.query.filter_by(slug=slug).first()
                if not obj:
                    obj = Item(slug=slug)
                    db.session.add(obj)
                obj.name = r["name"]
                obj.type = r["type"]
                obj.description = r.get("description") or ""
                obj.value_copper = int(r["value_copper"])
                obj.level = int(r["level"])
                obj.rarity = (r.get("rarity") or "common").lower()
                w_raw = r.get("weight")
                if w_raw not in (None, ""):
                    try:
                        obj.weight = float(w_raw)
                    except Exception:
                        pass
                changed += 1
            db.session.commit()
            print(f"Imported/updated {changed} items.")
            return 0
    elif mode == "import-monsters-csv":
        from app import db
        from app.models.models import MonsterCatalog
        from app.routes.admin import (
            REQUIRED_MONSTER_COLUMNS,
            _parse_csv,
            _validate_monster_rows,
        )

        path = getattr(args, "path")
        if not os.path.exists(path):
            print(f"[ERROR] File not found: {path}")
            return 1
        from app import create_app

        app = create_app()
        with app.app_context():
            with open(path, "rb") as f:
                rows, parse_errors = _parse_csv(f, REQUIRED_MONSTER_COLUMNS)
            if parse_errors:
                for e in parse_errors:
                    print("ERROR:", e)
                return 1
            val_errors = _validate_monster_rows(rows)
            if val_errors:
                for e in val_errors:
                    print("ERROR:", e)
                return 1
            changed = 0
            for r in rows:
                slug = r["slug"]
                obj = MonsterCatalog.query.filter_by(slug=slug).first()
                if not obj:
                    obj = MonsterCatalog(slug=slug)
                    db.session.add(obj)
                obj.name = r["name"]
                obj.level_min = int(r["level_min"])
                obj.level_max = int(r["level_max"])
                obj.base_hp = int(r["base_hp"])
                obj.base_damage = int(r["base_damage"])
                obj.armor = int(r["armor"])
                obj.speed = int(r["speed"])
                obj.rarity = (r.get("rarity") or "common").lower()
                obj.family = r.get("family") or "neutral"
                obj.traits = r.get("traits") or None
                obj.loot_table = r.get("loot_table") or None
                obj.special_drop_slug = r.get("special_drop_slug") or None
                obj.xp_base = int(r["xp_base"])
                b_raw = (r.get("boss") or "").strip().lower()
                if b_raw in ("1", "true", "yes"):
                    obj.boss = True
                elif b_raw in ("0", "false", "no"):
                    obj.boss = False
                if r.get("resistances"):
                    obj.resistances = r.get("resistances")
                if r.get("damage_types"):
                    obj.damage_types = r.get("damage_types")
                changed += 1
            db.session.commit()
            print(f"Imported/updated {changed} monsters.")
            return 0
    elif mode == "config-get":
        from app import create_app
        from app.models.models import GameConfig

        app = create_app()
        with app.app_context():
            val = GameConfig.get(getattr(args, "key"))
            if val is None:
                print("[NOT FOUND]")
                return 1
            print(val)
            return 0
    elif mode == "config-set":
        from app import create_app
        from app import db as _db
        from app.models.models import GameConfig

        app = create_app()
        with app.app_context():
            key = getattr(args, "key")
            value = getattr(args, "value")
            row = GameConfig.query.filter_by(key=key).first()
            if not row:
                row = GameConfig(key=key, value=value)
                _db.session.add(row)
            else:
                row.value = value
            _db.session.commit()
            print("[OK]")
            return 0
    elif mode == "make-admin":
        from werkzeug.security import generate_password_hash

        from app import create_app
        from app import db as _db
        from app.models.models import User

        app = create_app()
        username = getattr(args, "username")
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=generate_password_hash("changeme"), role="admin")
                _db.session.add(user)
                _db.session.commit()
                print(f"Created new admin user '{username}' with password 'changeme'")
            else:
                user.role = "admin"
                _db.session.commit()
                print(f"Promoted '{username}' to admin")
        return 0
    else:
        info_prefix = f"{Fore.CYAN}[INFO]{Style.RESET_ALL}" if _COLOR_ENABLED else "[INFO]"
        print(f"{info_prefix} Listening for connections... Press Ctrl+C to stop.")
        # Determine debug flag before logging
        debug = bool(getattr(args, "debug", False) or os.getenv("FLASK_DEBUG") == "1")
        try:
            from app.logging_utils import log

            log.info(event="listen", host=host, port=port, debug=debug)
        except Exception:
            pass
        # Note: db_uri is read by the Flask app on import via app config/env
        start_server(host=host, port=port, debug=debug)
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
