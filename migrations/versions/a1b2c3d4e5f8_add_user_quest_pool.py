"""add user_quest_pool table

Revision ID: a1b2c3d4e5f8
Revises: a1b2c3d4e5f7
Create Date: 2026-06-27

"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_quest_pool",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),  # "daily" | "weekly"
        sa.Column("period_key", sa.String(20), nullable=False),  # "2026-06-27" | "2026-W26"
        sa.Column("quests_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period_type", "period_key", name="uq_user_quest_pool"),
    )
    op.create_index("ix_user_quest_pool_user_id", "user_quest_pool", ["user_id"])


def downgrade():
    op.drop_index("ix_user_quest_pool_user_id", table_name="user_quest_pool")
    op.drop_table("user_quest_pool")
