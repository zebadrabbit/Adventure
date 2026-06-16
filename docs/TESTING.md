# Running the Tests

## One-time setup
The project ships a venv at `.venv`. If it lacks pip/pytest, bootstrap it:

    .venv/bin/python -m ensurepip --upgrade
    .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt

## Database
Tests require PostgreSQL. Connection comes from `TEST_DATABASE_URL` (falls back to
`DATABASE_URL`). A local Postgres is expected on port 5433 (see `docker-compose.yml`).

    export $(grep -v '^#' .env | xargs)              # loads DATABASE_URL
    export TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DATABASE_URL}"

Create + migrate the test DB once:

    .venv/bin/python -c "from app import create_app, db; \
      app=create_app(); ctx=app.app_context(); ctx.push(); db.create_all()"

## Run

    .venv/bin/python -m pytest -q

## Pure-generator tests (no DB needed)
Dungeon generation is pure Python and can run without a database:

    .venv/bin/python -m pytest tests/test_dungeon_basic.py \
      tests/test_dungeon_carve_floor.py tests/test_dungeon_golden_seeds.py \
      tests/test_room_connectivity.py -q

## Postgres bootstrap

Start a local Postgres 15 container (skip if one is already running):

    docker run -d --rm --name adv_pg \
      -e POSTGRES_DB=adventure \
      -e POSTGRES_USER=adventure \
      -e POSTGRES_PASSWORD=changeme \
      -p 5434:5432 \
      postgres:15-alpine

Create the target database inside the container (if it does not exist yet):

    docker exec adv_pg psql -U adventure -d adventure -c "CREATE DATABASE adventure;" 2>/dev/null || true

Bootstrap schema + seed data with one command:

    DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure ./scripts/bootstrap_db.sh

This creates all tables, runs any additive migrations, seeds game config, and
loads item/affix/weapon/enemy catalog data. The script is idempotent: re-running
it clears and reloads the catalog rows without touching player data.
