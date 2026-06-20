# Self-Stamping Migration Bootstrap — Design

**Date:** 2026-06-20
**Status:** Design only — not yet planned/implemented.

## Context

The dev `adventure` DB has no `alembic_version` table at all — confirmed via
direct query. `alembic upgrade head` fails against it (and against a freshly
dropped test DB) because of a deeper architectural conflict, not a missing
stamp: `app/__init__.py` runs `db.create_all()` →
`app.server._run_migrations()` (a legacy, pre-Alembic, "SQLite, no Alembic
needed" additive column-adder, per its own docstring) →
`app.migrations.apply_migrations()` (a second, separate versioned migration
system using its own `schema_version` table, not Alembic's
`alembic_version`) → `seed_items()` / `_seed_game_config()` — all as a
**module-level import-time side effect**, wrapped in a bare
try/except-and-rollback so a failure never breaks app boot.

Confirmed directly: running `alembic upgrade head` against a freshly
`db.drop_all()`'d test DB still failed with `DuplicateColumn` on
`enemy_archetype.spawn_weight`, because the moment the Alembic CLI process
imported `migrations/env.py` (which does `from app import db as flask_db`),
the import-time bootstrap re-ran `create_all`/`_run_migrations` and recreated
the column before Alembic's own migration chain got a chance to add it
itself.

Grepped all 14 Alembic migration files for `op.execute`/`bulk_insert` — none
exist. Every migration is pure additive/alter schema DDL, so `create_all`'s
end state and `alembic upgrade head`'s end state are schema-equivalent. This
means the systems aren't producing *wrong* schemas — they just never
communicate `alembic_version`'s state, so Alembic can never accurately report
or rely on where a DB actually stands.

Brainstormed two directions: (a) make the import-time bootstrap self-stamp
Alembic once a DB has never been under its control, or (b) remove the
import-time bootstrap entirely and require an explicit migration step before
running the app. The user picked (a) — lower risk, preserves the existing
zero-config dev/test convenience, fixes the actual symptom (Alembic state
being perpetually stale/absent) without touching the three working systems
that already build the schema correctly.

## Goals

1. After the existing import-time bootstrap (`db.create_all()` →
   `_run_migrations()` → `apply_migrations()` → seeding) finishes, stamp the
   DB to Alembic's `head` revision — but **only** if the DB has never been
   under Alembic's control before (no `alembic_version` table yet).
2. Once `alembic_version` exists (whether created by this stamp or by a real
   future `alembic upgrade`), this logic must never run again for that DB —
   Alembic owns versioning from that point on, untouched by this change.
3. A stamping failure must never break app boot — same safety guarantee the
   existing bootstrap already has (bare try/except-and-rollback).
4. Fix the *current* dev DB's stale state as a one-time manual action
   (`alembic stamp head` via the CLI), justified by the schema-equivalence
   confirmed in Context above.

## Non-goals

- Removing or altering `_run_migrations()`, `apply_migrations()`, or
  `db.create_all()` — they keep building the schema exactly as they do today.
  This change only adds a stamp; it doesn't change what builds the schema.
- Changing test fixtures or `conftest.py` — tests already call
  `create_app()`, which already triggers this bootstrap; no fixture changes
  needed.
- Reconciling the two legacy systems (`_run_migrations()` vs
  `apply_migrations()`) into one — out of scope, they already coexist safely
  today (both idempotent, both guard column existence before altering).
- Production deployment process changes — out of scope; this only affects
  whether `alembic_version` accurately reflects reality, not how schema
  changes actually get applied.

## Architecture

**Code change (`app/__init__.py`):**

Immediately after the existing `seed_items()` / `_seed_game_config()` calls,
inside the same `with app.app_context():` block and the same surrounding
try/except-and-rollback (so a stamping failure is swallowed exactly like
today's bootstrap failures are):

```python
from sqlalchemy import inspect as _sa_inspect

if not _sa_inspect(db.engine).has_table("alembic_version"):
    from alembic import command as _alembic_command
    from alembic.config import Config as _AlembicConfig

    _alembic_cfg = _AlembicConfig(
        os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    )
    _alembic_command.stamp(_alembic_cfg, "head")
```

This uses Alembic's own Python API (`alembic.command.stamp`) rather than
hand-rolling the `alembic_version` table's DDL, so its schema/behavior always
matches whatever a real `alembic stamp` CLI invocation would produce. The
`has_table` check is the only gate — it's what makes this a true one-time
action per DB rather than something that fights a real Alembic-managed
deployment later.

**One-time manual fix for the current dev DB:**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure
alembic stamp head
```

Run once, directly, outside the app — confirmed safe because the dev DB's
schema (built via `create_all`/`_run_migrations`/`apply_migrations` over
time) is schema-equivalent to what `alembic upgrade head` would produce (no
migration does non-additive data work, per the Context section's grep).

## Testing

This is bootstrap/infra code with no isolated unit to test in the traditional
sense — it's exercised implicitly by every test run already, since every
test calls `create_app()`. Verification is manual:

- Drop a test DB completely, import `app` (triggering the bootstrap), then
  run `alembic current` — expect it to report `head`, not empty.
- Re-import / re-run the app a second time against that same DB — expect no
  errors and no double-stamping (the `has_table` check short-circuits).
- Run `alembic upgrade head` against that DB after the stamp — expect it to
  no-op cleanly (already at head), not fail with `DuplicateColumn`.
- Run the full pytest suite — expect no regressions (this change is purely
  additive to the bootstrap, no existing behavior changes).
