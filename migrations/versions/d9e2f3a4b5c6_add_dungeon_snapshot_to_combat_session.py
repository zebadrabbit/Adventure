"""add dungeon_snapshot_json to combat_session

Revision ID: d9e2f3a4b5c6
Revises: c8f1a2b3d4e5
Create Date: 2026-07-27

combat_service.start_session has always written a dungeon snapshot only
``if hasattr(CombatSession, "dungeon_snapshot_json")`` -- and the column was
never on the model, so it silently never wrote one. Everything downstream that
reads it back (boss/elite/monster kill tracking and the extraction unlock in
_check_end, /api/dungeon/restore_from_combat) was therefore dead code.

Guarded (inspector check) like the revisions before it: create_all runs before
the upgrade and already creates model columns.
"""

import sqlalchemy as sa
from alembic import op

revision = "d9e2f3a4b5c6"
down_revision = "c8f1a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("combat_session")}
    if "dungeon_snapshot_json" not in cols:
        op.add_column("combat_session", sa.Column("dungeon_snapshot_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("combat_session", "dungeon_snapshot_json")
