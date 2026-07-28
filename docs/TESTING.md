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

## Two ways to corrupt the test database

Both of these bit hard on 2026-07-28 and cost hours of confusion, so they are
worth knowing before you debug a mysterious failure.

### Never run two pytest processes against the same database

Tests marked `@pytest.mark.db_isolation` **drop and recreate the whole schema**
mid-run (`tests/conftest.py`, `_conditional_db_isolation`). A second pytest
process pointed at the same `TEST_DATABASE_URL` will be running queries against
tables that vanish underneath it, and the two runs leave the database in an
arbitrary state -- typically with the item and monster catalogues empty.

Symptoms: unrelated tests failing on missing rows; `monster_catalog` at 0;
encounters falling back to "Elite Monster" stubs. Check with:

```bash
psql "$TEST_DATABASE_URL" -tAc \
  "select 'items='||count(*) from item; select 'monsters='||count(*) from monster_catalog;"
```

If a background run was interrupted (a disconnected session, a killed terminal),
check for orphans before starting another: `pgrep -af "python -m pytest"`.

### db_isolation tests leave a *minimal* catalogue

The rebuild reseeds with `app.server.seed_items` -- a small "create the basics if
missing" seeder of ~14 items -- **not** `app.seed_items.reseed_items`, which is
what loads the full 220-item, 105-monster, 8-archetype catalogue. So after any
`db_isolation` test, the database holds a skeleton catalogue.

Consequence: **a test that depends on the full catalogue passes alone and fails
in the suite**, depending purely on ordering. Do not rely on global seed data.
Either create the rows your test needs (see
`tests/test_named_loot_tables.py`, which builds its own item fixtures) or skip
when the catalogue is absent.

To restore a database by hand:

```bash
PYTHONPATH=. DATABASE_URL="$TEST_DATABASE_URL" python run.py reseed-items
```

## Full-run end-to-end tests
`tests/test_full_run_e2e.py` plays complete dungeon runs through the real HTTP
endpoints (entry → exploration → combat → stairs → boss → loot → extract, plus a
wipe run and a hearthstone abandon). It is slower than the rest of the suite
(~60s) and is the only coverage that reaches a run's end state by playing rather
than by setting columns — keep it that way.

    .venv/bin/python -m pytest tests/test_full_run_e2e.py -q

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
