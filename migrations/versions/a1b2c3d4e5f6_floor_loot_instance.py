"""floor loot procedural instance

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-16

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dungeon_loot", sa.Column("instance_json", sa.Text(), nullable=True))
    op.alter_column("dungeon_loot", "item_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("dungeon_loot", "item_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("dungeon_loot", "instance_json")
