"""legacy baseline guards: port all guarded startup DDL into alembic

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f9
Create Date: 2026-07-16

This revision consolidates the four legacy schema-migration mechanisms that
used to run guarded DDL at startup into a single alembic revision:

  * ``app/server._run_migrations`` (guarded ALTER TABLE for user/character/
    combat_session/item/game_clock/monster_catalog columns).
  * ``app/migrations.apply_migrations`` (combat_session phase/phase_step/
    dungeon_snapshot_json columns, versioned via the ``schema_version`` table).
  * ``app/__init__._run_lightweight_migrations`` and the monster_catalog
    fallback block in ``app/__init__`` (monster_catalog.resistances /
    damage_types).

Every one of those column additions is a no-op on any database created by the
current models (``db.create_all`` already produces them), so this revision is
purely a *baseline guard* for pre-existing / legacy databases that predate the
column. Each add is guarded by an inspector check, making the whole revision
idempotent and safe to run against a schema that already has the columns.

Pre-alembic databases (fresh ``create_all`` output, or legacy deployments that
never had an ``alembic_version`` table) are stamped by the application startup
path to ``a1b2c3d4e5f9`` (the revision immediately preceding this one) before
``upgrade head`` runs, so these guards execute exactly once and alembic owns
versioning thereafter.

``downgrade`` is intentionally a no-op: these columns are part of the model
baseline and dropping them would break the application.
"""

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a1b2c3d4e5f9"
branch_labels = None
depends_on = None


# table -> list of (column_name, type, add_column_kwargs). Faithfully ported
# from the legacy guarded startup DDL. Order within a table preserves the
# original mechanism order for readability.
_ADDITIONS = {
    "user": [
        ("email", sa.String(length=120), {}),
        ("role", sa.String(length=20), {"nullable": False, "server_default": "user"}),
        ("banned", sa.Boolean(), {"nullable": False, "server_default": sa.text("false")}),
        ("ban_reason", sa.Text(), {}),
        ("notes", sa.Text(), {}),
        ("banned_at", sa.DateTime(), {}),
        ("muted", sa.Boolean(), {"nullable": False, "server_default": sa.text("false")}),
        ("explored_tiles", sa.Text(), {}),
    ],
    "character": [
        ("xp", sa.Integer(), {"nullable": False, "server_default": "0"}),
        ("level", sa.Integer(), {"nullable": False, "server_default": "1"}),
    ],
    "combat_session": [
        ("combat_turn", sa.Integer(), {"nullable": False, "server_default": "1"}),
        ("initiative_json", sa.Text(), {}),
        ("active_index", sa.Integer(), {"nullable": False, "server_default": "0"}),
        ("party_snapshot_json", sa.Text(), {}),
        ("monster_hp", sa.Integer(), {}),
        ("log_json", sa.Text(), {}),
        ("rewards_json", sa.Text(), {}),
        ("version", sa.Integer(), {"nullable": False, "server_default": "1"}),
        # from apply_migrations (_migration_2 / _migration_3)
        ("phase", sa.String(length=20), {"nullable": False, "server_default": "start"}),
        ("phase_step", sa.Integer(), {"nullable": False, "server_default": "0"}),
        ("dungeon_snapshot_json", sa.Text(), {}),
    ],
    "game_clock": [
        ("combat", sa.Boolean(), {"nullable": False, "server_default": sa.text("false")}),
    ],
    "item": [
        ("level", sa.Integer(), {"nullable": False, "server_default": "0"}),
        ("rarity", sa.String(length=20), {"nullable": False, "server_default": "common"}),
        ("weight", sa.Float(), {"nullable": False, "server_default": "1.0"}),
    ],
    "monster_catalog": [
        ("resistances", sa.Text(), {}),
        ("damage_types", sa.Text(), {}),
    ],
}


def _column_names(insp, table):
    try:
        return {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return set()


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # Legacy plural -> singular rename (deployments that predate the ORM's
    # singular table name). Mirror of the guard in server._run_migrations.
    if "dungeon_instances" in tables and "dungeon_instance" not in tables:
        op.rename_table("dungeon_instances", "dungeon_instance")
        insp = sa.inspect(bind)
        tables = set(insp.get_table_names())

    for table, columns in _ADDITIONS.items():
        if table not in tables:
            # Table creation is owned by create_all / earlier revisions.
            continue
        existing = _column_names(insp, table)
        for name, coltype, kwargs in columns:
            if name in existing:
                continue
            op.add_column(table, sa.Column(name, coltype, **kwargs))


def downgrade():
    # No-op: these columns are part of the model baseline; dropping them would
    # break the application. See module docstring.
    pass
