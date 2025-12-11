"""add extraction and permadeath fields to character

Revision ID: 95ff19b9fe00
Revises: 41a271547ca1
Create Date: 2025-12-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "95ff19b9fe00"
down_revision = "41a271547ca1"
branch_labels = None
depends_on = None


def upgrade():
    # Add extraction-related fields to character table
    op.add_column("character", sa.Column("locked_in_dungeon", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("character", sa.Column("locked_dungeon_id", sa.Integer(), nullable=True))
    op.add_column("character", sa.Column("is_dead", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("character", sa.Column("permadeath", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("character", sa.Column("death_count", sa.Integer(), nullable=False, server_default="0"))

    # Add extraction progress to dungeon_instance
    op.add_column("dungeon_instance", sa.Column("bosses_defeated", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "dungeon_instance", sa.Column("extraction_available", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade():
    # Remove extraction fields
    op.drop_column("dungeon_instance", "extraction_available")
    op.drop_column("dungeon_instance", "bosses_defeated")
    op.drop_column("character", "death_count")
    op.drop_column("character", "permadeath")
    op.drop_column("character", "is_dead")
    op.drop_column("character", "locked_dungeon_id")
    op.drop_column("character", "locked_in_dungeon")
