"""Lightweight structured migration system.

Provides incremental, versioned migrations on top of the existing
ad-hoc startup DDL in ``server._run_migrations``. This keeps legacy
bootstrapping (table creation / older column backfills) intact while
allowing newly added schema changes to be expressed as discrete,
idempotent steps that can run in any environment (dev/prod/tests)
exactly once.

Version tracking uses the existing ``schema_version`` single-row table
with (id=1, version=<int>). Legacy deployments that already created
``schema_version`` will start at whatever value was previously stored
(default 1). New migrations must:

  * Declare an integer ``target_version`` greater than the current.
  * Perform idempotent DDL/data changes (guards for existing cols).
  * Bump the stored version only after success.

Usage:
    from app.migrations import apply_migrations
    apply_migrations()

New Migration Template (append at bottom before ``MIGRATIONS`` freeze):

    # def _migration_<n>(db, engine):
    #     # Describe change
    #     # perform guarded DDL
    #     ...
    # MIGRATIONS.append((<n>, _migration_<n>, "short description"))

Keep migrations minimal and *idempotent*. Avoid relying on ORM model
definitions for historical schemas—operate directly via inspector & raw SQL.
"""

from __future__ import annotations

from typing import Callable, List, Tuple

from sqlalchemy import inspect, text

from app import db

MigrationFn = Callable[[any, any], None]


def _ensure_schema_version_table():  # pragma: no cover - simple helper
    try:
        db.session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK (id=1), version INTEGER NOT NULL)"
            )
        )
        row = db.session.execute(text("SELECT version FROM schema_version WHERE id=1")).fetchone()
        if not row:
            db.session.execute(text("INSERT INTO schema_version (id, version) VALUES (1, 1)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _get_current_version() -> int:
    try:
        row = db.session.execute(text("SELECT version FROM schema_version WHERE id=1")).fetchone()
        return int(row[0]) if row else 1
    except Exception:
        return 1


# ------------------------- Migration Definitions ------------------------- #


def _migration_2(db_module, engine):  # Add phase + phase_step columns to combat_session
    insp = inspect(engine)
    if not insp.has_table("combat_session"):
        return  # nothing to do for deployments created after refactor
    cols = {c["name"] for c in insp.get_columns("combat_session")}
    # Guarded adds (older DBs before phased turn engine)
    try:
        if "phase" not in cols:
            db.session.execute(text("ALTER TABLE combat_session ADD COLUMN phase VARCHAR(20) NOT NULL DEFAULT 'start'"))
        if "phase_step" not in cols:
            db.session.execute(text("ALTER TABLE combat_session ADD COLUMN phase_step INTEGER NOT NULL DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()


MIGRATIONS: List[Tuple[int, MigrationFn, str]] = [
    (2, _migration_2, "Add phased turn columns to combat_session (phase, phase_step)"),
]


def _migration_3(db_module, engine):  # Add dungeon_snapshot_json column to combat_session
    insp = inspect(engine)
    if not insp.has_table("combat_session"):
        return
    cols = {c["name"] for c in insp.get_columns("combat_session")}
    if "dungeon_snapshot_json" in cols:
        return
    try:
        db.session.execute(text("ALTER TABLE combat_session ADD COLUMN dungeon_snapshot_json TEXT"))
        db.session.commit()
    except Exception:
        db.session.rollback()


MIGRATIONS.append((3, _migration_3, "Add dungeon_snapshot_json to combat_session"))


def apply_migrations():  # pragma: no cover - thin orchestration
    """Apply any pending migrations in ascending version order."""
    _ensure_schema_version_table()
    current = _get_current_version()
    target = current
    for ver, fn, _desc in sorted(MIGRATIONS, key=lambda x: x[0]):
        if ver <= current:
            continue
        try:
            fn(db, db.engine)
            # If no exception, bump version
            db.session.execute(text("UPDATE schema_version SET version=:v WHERE id=1"), {"v": ver})
            db.session.commit()
            target = ver
        except Exception:
            db.session.rollback()
            # Stop on first failing migration to avoid partial application ordering surprises
            break
    return target


__all__ = ["apply_migrations"]
