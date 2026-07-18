"""add mana_cost to skill

Revision ID: c8f1a2b3d4e5
Revises: b1c2d3e4f5a6
Create Date: 2026-07-17

Active caster skills now consume mana when cast in combat. Adds a
``mana_cost`` column to the ``skill`` table (default 0 so existing rows and
physical/passive skills remain free).

Guarded (inspector check) like legacy_baseline_guards: in this codebase
``create_all`` runs before the upgrade and already creates model columns, and
``db_isolation`` tests rebuild the schema mid-suite into the
"tables-but-no-alembic_version" shape — an unguarded add_column then re-runs
against a table that already has the column (and blocks on other test
connections' locks). ALL future revisions here need the same guard.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8f1a2b3d4e5"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("skill")}
    if "mana_cost" not in cols:
        op.add_column("skill", sa.Column("mana_cost", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("skill", "mana_cost")
