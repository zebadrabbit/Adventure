"""add_unlocked_doors_tracking

Revision ID: ed130ef69bb4
Revises: 5b9c0df13fba
Create Date: 2025-12-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ed130ef69bb4"
down_revision = "5b9c0df13fba"
branch_labels = None
depends_on = None


def upgrade():
    # Add unlocked_doors_json column to dungeon_instance table
    op.add_column("dungeon_instance", sa.Column("unlocked_doors_json", sa.Text(), nullable=True))


def downgrade():
    # Remove unlocked_doors_json column
    op.drop_column("dungeon_instance", "unlocked_doors_json")
