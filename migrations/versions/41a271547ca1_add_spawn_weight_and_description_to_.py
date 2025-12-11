"""add spawn_weight and description to enemy_archetype

Revision ID: 41a271547ca1
Revises: b8e4c2f6d9a3
Create Date: 2025-01-13
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "41a271547ca1"
down_revision = "b8e4c2f6d9a3"
branch_labels = None
depends_on = None


def upgrade():
    # Add spawn_weight and description columns to enemy_archetype
    op.add_column("enemy_archetype", sa.Column("spawn_weight", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("enemy_archetype", sa.Column("description", sa.Text(), nullable=True))


def downgrade():
    # Remove spawn_weight and description columns
    op.drop_column("enemy_archetype", "description")
    op.drop_column("enemy_archetype", "spawn_weight")
