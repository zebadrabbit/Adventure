"""add monsters_json to combat_session

Revision ID: d7e2c4a91b30
Revises: c9405725c1f4
Create Date: 2026-07-30

Combat phase 1: an encounter fields 1-6 monsters instead of exactly one.
``monsters_json`` is a JSON list and becomes the source of truth; each entry is
an ordinary spawn payload plus a session-local ``id``, a current ``hp`` and an
``hp_max``.

Nullable and deliberately not backfilled. ``combat_service._monsters()`` derives
the list from the legacy ``monster_json``/``monster_hp`` pair whenever this
column is NULL, which covers both historical rows and any session that is live
at the moment the app upgrades -- a data migration would have to be run against
sessions mid-fight to achieve the same thing, and could not cover a session
started between the migration and the deploy.

``monster_json`` and ``monster_hp`` are deliberately left in place rather than
dropped: they stay as a denormalised view of the first monster so every existing
reader keeps working through the transition (the design spec asks for exactly
that).

Guarded (inspector check) like c8f1a2b3d4e5: in this codebase ``create_all``
runs before the upgrade and already creates model columns, and ``db_isolation``
tests rebuild the schema mid-suite into the "tables-but-no-alembic_version"
shape -- an unguarded add_column then re-runs against a table that already has
the column, and blocks on other test connections' locks. ALL revisions here
need the same guard.
"""

import sqlalchemy as sa
from alembic import op

revision = "d7e2c4a91b30"
down_revision = "c9405725c1f4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("combat_session")}
    if "monsters_json" not in cols:
        op.add_column("combat_session", sa.Column("monsters_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("combat_session", "monsters_json")
