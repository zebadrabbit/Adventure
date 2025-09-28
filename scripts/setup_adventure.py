#!/usr/bin/env python3
"""
Adventure MUD Setup Script

Interactive, colorful bootstrap utility to configure environment, initialize the
SQLite database (or other configured DB), run (lightweight) migrations, and
create an initial admin user.

Now includes verbosity flags and future secret key auto-generation hook.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDER = "\033[4m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

    def wrap(msg, color):
        return f"{color}{msg}{C.RESET}"


def supports_color():
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def c(msg, color):
    return C.wrap(msg, color) if supports_color() else msg


INSTANCE_DIR = PROJECT_ROOT / "instance"
ENV_FILE = PROJECT_ROOT / ".env"

existing_env = {}
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            existing_env[k.strip()] = v.strip()

DEFAULT_SECRET = existing_env.get("SECRET_KEY", "dev-secret-change-me")
DEFAULT_DB = existing_env.get("DATABASE_URL", f'sqlite:///{(INSTANCE_DIR/"mud.db").as_posix()}')
DEFAULT_CORS = existing_env.get("CORS_ALLOWED_ORIGINS", "*")

parser = argparse.ArgumentParser(description="Interactive / non-interactive setup for Adventure MUD")
parser.add_argument("--yes", "-y", action="store_true", help="Accept all defaults (non-interactive).")
parser.add_argument(
    "--non-interactive",
    action="store_true",
    help="Fail if a value is required and no default is available.",
)
parser.add_argument(
    "--json",
    action="store_true",
    help="Emit JSON summary only (suppresses decorative output except errors).",
)
parser.add_argument("--no-admin", action="store_true", help="Skip ensuring admin user.")
parser.add_argument("--admin-username", help="Admin username (non-interactive).")
parser.add_argument(
    "--admin-password",
    help="Admin password (non-interactive; will not auto-generate unless --generate-admin-password).",
)
parser.add_argument(
    "--generate-admin-password",
    action="store_true",
    help="Generate a secure admin password (printed once).",
)
parser.add_argument(
    "--alembic",
    action="store_true",
    help="Run alembic upgrade head if migrations directory present.",
)
parser.add_argument(
    "--quiet-routes",
    action="store_true",
    help="Suppress route map printing during import.",
)
parser.add_argument(
    "--quiet",
    action="store_true",
    help="Minimal output (overrides verbose unless JSON).",
)
parser.add_argument("--verbose", action="store_true", help="Extra informational output.")
parser.add_argument(
    "--log-level",
    choices=["debug", "info", "warn", "error", "silent"],
    help="Explicit log verbosity (overrides --quiet/--verbose).",
)
args, _ = parser.parse_known_args()

if args.quiet_routes:
    os.environ["ADVENTURE_SUPPRESS_ROUTE_MAP"] = "1"

NON_INTERACTIVE = args.yes or args.non_interactive
EMIT_JSON = args.json

if EMIT_JSON:

    def supports_color():
        return False


if args.log_level:
    LOG_LEVEL = args.log_level
else:
    if args.quiet:
        LOG_LEVEL = "silent"
    elif args.verbose:
        LOG_LEVEL = "debug"
    else:
        LOG_LEVEL = "info"

_ORDER = ["debug", "info", "warn", "error", "silent"]


def _idx(level_key):
    return _ORDER.index(level_key)


def log_enabled(level: str) -> bool:
    if EMIT_JSON or LOG_LEVEL == "silent":
        return False
    return _idx(level) >= _idx(LOG_LEVEL)


def log(msg, level="info", color=None):
    if log_enabled(level):
        print(c(msg, color) if color else msg)


def prompt(
    prompt_text: str,
    default: Optional[str] = None,
    secret: bool = False,
    validator=None,
):
    if NON_INTERACTIVE:
        val = default or ""
        if validator:
            ok, err = validator(val)
            if not ok and not args.yes:
                print(json.dumps({"error": f"Validation failed for {prompt_text}: {err}"}))
                sys.exit(2)
        return val
    while True:
        suffix = f" [{default}]" if default else ""
        raw = (
            getpass.getpass(c(prompt_text + suffix + ": ", C.CYAN))
            if secret
            else input(c(prompt_text + suffix + ": ", C.CYAN))
        )
        if not raw and default is not None:
            raw = default
        if validator:
            ok, err = validator(raw)
            if not ok:
                print(c(f"  ! {err}", C.RED))
                continue
        return raw


if log_enabled("info"):
    log("\nAdventure MUD Setup", "info", C.BOLD + C.MAGENTA)
    log("──────────────────────", "info", C.MAGENTA)
    log(
        "This script will help you configure the environment and bootstrap the database.",
        "info",
        C.GRAY,
    )
    log("", "info")

INSTANCE_DIR.mkdir(exist_ok=True)

secret_key = prompt(
    "Secret key (used for sessions & CSRF)",
    DEFAULT_SECRET,
    validator=lambda v: (len(v) >= 8, "Must be at least 8 chars"),
)
secret_key_generated = False
PLACEHOLDER_VALUES = {
    "dev-secret-change-me",
    "changeme",
    "change-me",
    "secret",
    "placeholder",
}
if secret_key in PLACEHOLDER_VALUES or (secret_key == DEFAULT_SECRET and secret_key.startswith("dev-secret")):
    import secrets

    secret_key = secrets.token_urlsafe(32)
    secret_key_generated = True
    log("Generated secure SECRET_KEY (written to .env)", "warn", C.YELLOW)
database_url = prompt("Database URL", DEFAULT_DB)
cors = prompt("CORS allowed origins (comma or space separated; * for all)", DEFAULT_CORS)

if args.no_admin:
    create_admin = "n"
    admin_username = ""
    admin_password = ""
else:
    if NON_INTERACTIVE and args.admin_username:
        admin_username = args.admin_username
        if args.admin_password:
            admin_password = args.admin_password
        elif args.generate_admin_password:
            import secrets

            admin_password = secrets.token_urlsafe(16)
        else:
            admin_password = ""
        create_admin = "y"
    else:
        create_admin = prompt(
            "Create/ensure admin user? (y/n)",
            "y",
            validator=lambda v: (v.lower() in ("y", "n"), "Enter y or n"),
        )
        admin_username = "admin"
        admin_password = None
        if create_admin.lower() == "y":
            if not (NON_INTERACTIVE and args.admin_username):
                admin_username = prompt(
                    "Admin username",
                    existing_env.get("ADMIN_USERNAME", "admin"),
                    validator=lambda v: (
                        bool(re.match(r"^[A-Za-z0-9_]{3,32}$", v)),
                        "3-32 chars alnum/underscore",
                    ),
                )
            if not (NON_INTERACTIVE and (args.admin_password or args.generate_admin_password)):
                admin_password = prompt("Admin password (leave blank to auto-generate)", None, secret=True)
            if not admin_password:
                import secrets

                admin_password = secrets.token_urlsafe(16)
                log(f"  Generated password: {admin_password}", "warn", C.YELLOW)

new_env = existing_env.copy()
new_env.update(
    {
        "SECRET_KEY": secret_key,
        "DATABASE_URL": database_url,
        "CORS_ALLOWED_ORIGINS": cors,
        "ADMIN_USERNAME": admin_username if create_admin == "y" else "",
    }
)
ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in new_env.items() if v is not None) + "\n")
log(f"✓ Wrote {ENV_FILE.relative_to(PROJECT_ROOT)}", "info", C.GREEN)

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))
try:
    import app as app_module  # noqa: F401
    from app import create_app, db  # type: ignore
    from app.models.models import User

    flask_app = getattr(app_module, "app", None)
    if flask_app is None or not hasattr(flask_app, "app_context"):
        flask_app = create_app()
except Exception as e:
    log(
        "Failed to import app – ensure dependencies installed (pip install -r requirements.txt).",
        "error",
        C.RED,
    )
    log(str(e), "error", C.RED)
    sys.exit(1)

try:
    import app.server  # noqa: F401
except Exception as e:
    log(
        f"Warning: could not run runtime migrations automatically: {e}",
        "warn",
        C.YELLOW,
    )

created_admin = False
with flask_app.app_context():
    db.create_all()
    if create_admin.lower() == "y":
        existing = User.query.filter_by(username=admin_username).first()
        from werkzeug.security import generate_password_hash

        if existing:
            log(f"Admin user '{admin_username}' already exists.", "info", C.BLUE)
            rotate = "n"
            if not NON_INTERACTIVE:
                rotate = prompt(
                    "Rotate admin password? (y/n)",
                    "n",
                    validator=lambda v: (v.lower() in ("y", "n"), "y or n"),
                )
            if rotate.lower() == "y" and admin_password:
                existing.password = generate_password_hash(admin_password)
                db.session.commit()
                log("  ✓ Password updated", "info", C.GREEN)
        else:
            u = User(
                username=admin_username,
                password=generate_password_hash(admin_password),
                role="admin",
            )
            db.session.add(u)
            db.session.commit()
            created_admin = True
            log(f"✓ Created admin user '{admin_username}'", "info", C.GREEN)

summary = {
    "database_url": database_url,
    "secret_key_set": secret_key != DEFAULT_SECRET,
    "secret_key_generated": secret_key_generated,
    "log_level": LOG_LEVEL,
    "cors_origins": cors,
    "admin_created": bool(create_admin.lower() == "y" and created_admin),
    "admin_username": admin_username if create_admin.lower() == "y" else None,
    "admin_password": admin_password if create_admin.lower() == "y" and created_admin else None,
}

if log_enabled("info"):
    log("", "info")
    log("Setup Summary", "info", C.BOLD + C.MAGENTA)
    log("──────────────", "info", C.MAGENTA)
    log(f"Database URL: {database_url}", "info", C.CYAN)
    log(
        f"Secret Key: {'(hidden)' if summary['secret_key_set'] else secret_key}",
        "info",
        C.CYAN,
    )
    log(f"CORS Origins: {cors}", "info", C.CYAN)
    if create_admin.lower() == "y":
        if created_admin:
            log(
                f"Admin Credentials: {admin_username} / {admin_password}",
                "warn",
                C.YELLOW,
            )
        else:
            log("Admin Credentials: (unchanged)", "info", C.YELLOW)
    log("", "info")
    log("Next steps:", "info", C.BOLD)
    log(
        "  1. (Optional) Create a virtualenv & install dependencies: pip install -r requirements.txt",
        "info",
        C.GRAY,
    )
    log("  2. Run the server: python run.py", "info", C.GRAY)
    log("  3. Login with the admin account and explore!", "info", C.GRAY)
    log("", "info")
    log("Done. Happy adventuring!", "info", C.GREEN)

if args.alembic:
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        with flask_app.app_context():
            command.upgrade(alembic_cfg, "head")
        log("✓ Ran alembic migrations to latest revision", "info", C.GREEN)
    except Exception as e:
        log(f"Warning: could not run alembic migrations: {e}", "warn", C.YELLOW)

if EMIT_JSON:
    print(json.dumps(summary))
