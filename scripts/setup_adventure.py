#!/usr/bin/env python3
"""
Adventure MUD Setup Script

Interactive, colorful bootstrap utility to configure environment, initialize the
SQLite database (or other configured DB), run (lightweight) migrations, and
create an initial admin user.

Safe to re-run: existing values become defaults; existing admin user can be
skipped or password rotated.
"""
from __future__ import annotations
import os, sys, re, json, getpass, textwrap, subprocess, argparse
from pathlib import Path
from typing import Optional

# Ensure project root on sys.path early
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Color / style helpers (fallback gracefully if terminal not supporting ANSI)
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDER = '\033[4m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    def wrap(msg, color):
        return f"{color}{msg}{C.RESET}"

def supports_color():
    return sys.stdout.isatty() and os.getenv('NO_COLOR') is None

def c(msg, color):
    if supports_color():
        return C.wrap(msg, color)
    return msg

INSTANCE_DIR = PROJECT_ROOT / 'instance'
ENV_FILE = PROJECT_ROOT / '.env'

# Load existing .env if present
existing_env = {}
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if not line.strip() or line.strip().startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            existing_env[k.strip()] = v.strip()

DEFAULT_SECRET = existing_env.get('SECRET_KEY', 'dev-secret-change-me')
DEFAULT_DB = existing_env.get('DATABASE_URL', f'sqlite:///{(INSTANCE_DIR / "mud.db").as_posix()}')
DEFAULT_CORS = existing_env.get('CORS_ALLOWED_ORIGINS', '*')

# Parse flags early (affects interactive prompts)
parser = argparse.ArgumentParser(description="Interactive / non-interactive setup for Adventure MUD")
parser.add_argument('--yes','-y', action='store_true', help='Accept all defaults (non-interactive).')
parser.add_argument('--non-interactive', action='store_true', help='Fail if a value is required and no default is available.')
parser.add_argument('--json', action='store_true', help='Emit JSON summary only (suppresses decorative output except errors).')
parser.add_argument('--no-admin', action='store_true', help='Skip ensuring admin user.')
parser.add_argument('--admin-username', help='Admin username (non-interactive).')
parser.add_argument('--admin-password', help='Admin password (non-interactive; will not auto-generate unless --generate-admin-password).')
parser.add_argument('--generate-admin-password', action='store_true', help='Generate a secure admin password (printed once).')
parser.add_argument('--alembic', action='store_true', help='Run alembic upgrade head if migrations directory present.')
parser.add_argument('--quiet-routes', action='store_true', help='Suppress route map printing during import.')
args, unknown = parser.parse_known_args()

if args.quiet_routes:
    os.environ['ADVENTURE_SUPPRESS_ROUTE_MAP'] = '1'

NON_INTERACTIVE = args.yes or args.non_interactive
EMIT_JSON = args.json

# Override supports_color when emitting JSON or non-interactive
if EMIT_JSON:
    def supports_color():
        return False

# Adjust prompt function for non-interactive

def prompt(prompt_text: str, default: Optional[str]=None, secret: bool=False, validator=None):
    if NON_INTERACTIVE:
        # Accept default or empty; enforce validator if provided
        val = default or ''
        if validator:
            ok, err = validator(val)
            if not ok and not args.yes:
                print(json.dumps({'error': f'Validation failed for {prompt_text}: {err}'}))
                sys.exit(2)
        return val
    while True:
        suffix = f" [{default}]" if default else ''
        raw = getpass.getpass(c(prompt_text+suffix+': ', C.CYAN) if secret else c(prompt_text+suffix+': ', C.CYAN)) if secret else input(c(prompt_text+suffix+': ', C.CYAN))
        if not raw and default is not None:
            raw = default
        if validator:
            ok, err = validator(raw)
            if not ok:
                print(c(f"  ! {err}", C.RED))
                continue
        return raw

if not EMIT_JSON:
    print(c("\nAdventure MUD Setup", C.BOLD + C.MAGENTA))
    print(c("──────────────────────", C.MAGENTA))
    print(c("This script will help you configure the environment and bootstrap the database.", C.GRAY))
    print()

# Ensure instance directory
INSTANCE_DIR.mkdir(exist_ok=True)

# Gather configuration
secret_key = prompt("Secret key (used for sessions & CSRF)", DEFAULT_SECRET, secret=False, validator=lambda v: (len(v)>=8, 'Must be at least 8 chars'))
database_url = prompt("Database URL", DEFAULT_DB)
cors = prompt("CORS allowed origins (comma or space separated; * for all)", DEFAULT_CORS)

# Admin user bootstrap
if args.no_admin:
    create_admin = 'n'
    admin_username = ''
    admin_password = ''
else:
    if NON_INTERACTIVE and args.admin_username:
        admin_username = args.admin_username
        if args.admin_password:
            admin_password = args.admin_password
        elif args.generate_admin_password:
            import secrets
            admin_password = secrets.token_urlsafe(16)
        else:
            admin_password = ''  # will auto-generate below
        create_admin = 'y'
    else:
        create_admin = prompt("Create/ensure admin user? (y/n)", 'y', validator=lambda v: (v.lower() in ('y','n'), 'Enter y or n'))
        admin_username = 'admin'
        admin_password = None
    if create_admin.lower() == 'y':
        if not (NON_INTERACTIVE and args.admin_username):
            admin_username = prompt("Admin username", existing_env.get('ADMIN_USERNAME','admin'), validator=lambda v: (bool(re.match(r'^[A-Za-z0-9_]{3,32}$', v)), '3-32 chars alnum/underscore'))
        if not (NON_INTERACTIVE and (args.admin_password or args.generate_admin_password)):
            admin_password = prompt("Admin password (leave blank to auto-generate)", None, secret=True)
        if not admin_password:
            import secrets
            admin_password = secrets.token_urlsafe(16)
            if not EMIT_JSON:
                print(c(f"  Generated password: {admin_password}", C.YELLOW))

# Write .env (preserve comments, simple merge)
new_env = existing_env.copy()
new_env.update({
    'SECRET_KEY': secret_key,
    'DATABASE_URL': database_url,
    'CORS_ALLOWED_ORIGINS': cors,
    'ADMIN_USERNAME': admin_username if create_admin=='y' else '',
})

# Serialize .env
lines = [f"{k}={v}" for k,v in new_env.items() if v is not None]
ENV_FILE.write_text('\n'.join(lines) + '\n')
if not EMIT_JSON:
    print(c(f"✓ Wrote {ENV_FILE.relative_to(PROJECT_ROOT)}", C.GREEN))

# Initialize Flask app context for DB operations
os.environ.setdefault('FLASK_ENV','development')
os.environ.setdefault('PYTHONPATH', str(PROJECT_ROOT))

# Import application lazily
try:
    # Import module then extract Flask app instance; fall back to factory
    import app as app_module  # noqa: F401
    from app import db, create_app  # type: ignore
    from app.models.models import User
    # Attempt to access app_module.app if present
    flask_app = getattr(app_module, 'app', None)
    if flask_app is None or not hasattr(flask_app, 'app_context'):
        # Use factory
        flask_app = create_app()
except Exception as e:
    print(c("Failed to import app – ensure dependencies installed (pip install -r requirements.txt).", C.RED))
    print(e)
    sys.exit(1)

# Run lightweight runtime migrations (already part of server startup via app.server import)
try:
    # Force import of server to trigger _run_migrations if defined there
    import importlib
    import app.server  # noqa: F401
except Exception as e:
    print(c(f"Warning: could not run runtime migrations automatically: {e}", C.YELLOW))

created_admin = False
with flask_app.app_context():
    db.create_all()
    if create_admin.lower() == 'y':
        existing = User.query.filter_by(username=admin_username).first()
        from werkzeug.security import generate_password_hash
        if existing:
            if not EMIT_JSON:
                print(c(f"Admin user '{admin_username}' already exists." , C.BLUE))
            # Offer password rotation
            rotate = 'n'
            if not NON_INTERACTIVE:
                rotate = prompt("Rotate admin password? (y/n)", 'n', validator=lambda v: (v.lower() in ('y','n'), 'y or n'))
            if rotate.lower() == 'y' and admin_password:
                existing.password = generate_password_hash(admin_password)
                db.session.commit()
                if not EMIT_JSON:
                    print(c("  ✓ Password updated", C.GREEN))
        else:
            u = User(username=admin_username, password=generate_password_hash(admin_password), role='admin')
            db.session.add(u)
            db.session.commit()
            created_admin = True
            if not EMIT_JSON:
                print(c(f"✓ Created admin user '{admin_username}'", C.GREEN))

summary = {
    'database_url': database_url,
    'secret_key_set': secret_key != DEFAULT_SECRET,
    'cors_origins': cors,
    'admin_created': bool(create_admin.lower()=='y' and created_admin),
    'admin_username': admin_username if create_admin.lower()=='y' else None,
    'admin_password': admin_password if create_admin.lower()=='y' and created_admin else None,
}
if not EMIT_JSON:
    print()
    print(c("Setup Summary", C.BOLD + C.MAGENTA))
    print(c("──────────────", C.MAGENTA))
    print(c(f"Database URL: {database_url}", C.CYAN))
    print(c(f"Secret Key: {'(hidden)' if summary['secret_key_set'] else secret_key}", C.CYAN))
    print(c(f"CORS Origins: {cors}", C.CYAN))
    if create_admin.lower()=='y':
        if created_admin:
            print(c(f"Admin Credentials: {admin_username} / {admin_password}", C.YELLOW))
        else:
            print(c("Admin Credentials: (unchanged)", C.YELLOW))
    print()
    print(c("Next steps:", C.BOLD))
    print(c("  1. (Optional) Create a virtualenv & install dependencies: pip install -r requirements.txt", C.GRAY))
    print(c("  2. Run the server: python run.py", C.GRAY))
    print(c("  3. Login with the admin account and explore!", C.GRAY))
    print()
    print(c("Done. Happy adventuring!", C.GREEN))

# Run alembic upgrade if requested and migrations directory present
if args.alembic:
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        with flask_app.app_context():
            command.upgrade(alembic_cfg, "head")
        if not EMIT_JSON:
            print(c("✓ Ran alembic migrations to latest revision", C.GREEN))
    except Exception as e:
        if not EMIT_JSON:
            print(c(f"Warning: could not run alembic migrations: {e}", C.YELLOW))

if EMIT_JSON:
    print(json.dumps(summary))
