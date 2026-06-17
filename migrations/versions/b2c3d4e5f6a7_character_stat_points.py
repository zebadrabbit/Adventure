"""character stat_points

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character",
        sa.Column("stat_points", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("character", "stat_points")
