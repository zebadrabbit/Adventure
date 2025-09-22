"""Adventure MUD CLI entry point.

Provides subcommands for running the Socket.IO server and launching the
interactive admin shell. Accepts configuration via flags and environment
variables, with optional .env loading.

Run `python run.py --help` for details.
"""

import os
import sys
import signal
import argparse
from textwrap import dedent

try:  # Optional color support
    from colorama import init as _color_init, Fore, Style
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
if '_COLOR_ENABLED' in globals():  # safety
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
    from app.server import start_server, start_admin_shell

    # Startup banner
    # Build colored banner lines
    title = f"{Fore.CYAN}{Style.BRIGHT}MUD Game Server Bootup{Style.RESET_ALL}" if _COLOR_ENABLED else "MUD Game Server Bootup"
    label = lambda L: f"{Fore.YELLOW}{L}{Style.RESET_ALL}" if _COLOR_ENABLED else L
    value = lambda V: f"{Fore.GREEN}{V}{Style.RESET_ALL}" if _COLOR_ENABLED else V
    divider = (Fore.MAGENTA + '='*40 + Style.RESET_ALL) if _COLOR_ENABLED else '='*40
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
        ""
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
    else:
        info_prefix = f"{Fore.CYAN}[INFO]{Style.RESET_ALL}" if _COLOR_ENABLED else "[INFO]"
        print(f"{info_prefix} Listening for connections... Press Ctrl+C to stop.")
        try:
            from app.logging_utils import log
            log.info(event="listen", host=host, port=port, debug=debug)
        except Exception:
            pass
        # Note: db_uri is read by the Flask app on import via app config/env
        debug = bool(getattr(args, "debug", False) or os.getenv("FLASK_DEBUG") == "1")
        start_server(host=host, port=port, debug=debug)
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
