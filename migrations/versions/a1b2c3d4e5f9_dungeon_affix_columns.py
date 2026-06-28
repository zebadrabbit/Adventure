"""add monster_count_multiplier, xp_multiplier, threat_weight to dungeon_affix

Revision ID: a1b2c3d4e5f9
Revises: a1b2c3d4e5f8
Create Date: 2026-06-27

"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f9"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "dungeon_affix",
        sa.Column(
            "monster_count_multiplier",
            sa.Float(),
            nullable=True,
            server_default="1.0",
        ),
    )
    op.add_column(
        "dungeon_affix",
        sa.Column("xp_multiplier", sa.Float(), nullable=True, server_default="1.0"),
    )
    op.add_column(
        "dungeon_affix",
        sa.Column("threat_weight", sa.Integer(), nullable=True, server_default="1"),
    )


def downgrade():
    op.drop_column("dungeon_affix", "threat_weight")
    op.drop_column("dungeon_affix", "xp_multiplier")
    op.drop_column("dungeon_affix", "monster_count_multiplier")
