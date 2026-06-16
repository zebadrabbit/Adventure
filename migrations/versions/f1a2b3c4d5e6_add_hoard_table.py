"""add hoard table

Revision ID: f1a2b3c4d5e6
Revises: ed130ef69bb4
Create Date: 2026-06-16

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "ed130ef69bb4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoard",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("copper", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_hoard_user_id"), "hoard", ["user_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_hoard_user_id"), table_name="hoard")
    op.drop_table("hoard")
