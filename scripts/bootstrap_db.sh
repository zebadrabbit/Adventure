#!/usr/bin/env bash
# Create/seed a clean Adventure database. Usage:
#   DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure ./scripts/bootstrap_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?set DATABASE_URL to the target database}"
echo "Bootstrapping $DATABASE_URL"
.venv/bin/python - <<'PY'
from app import app, db
with app.app_context():
    db.create_all()
    try:
        from app.server import _run_migrations, _seed_game_config
        _run_migrations()
        _seed_game_config()
    except Exception as e:
        print("migration/config warning:", e)
print("schema + config ready")
PY
.venv/bin/python run.py reseed-items
echo "Bootstrap complete."
