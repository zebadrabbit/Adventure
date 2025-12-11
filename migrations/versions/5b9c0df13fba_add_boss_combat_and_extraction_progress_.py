"""Add boss combat and extraction progress tracking

Revision ID: 5b9c0df13fba
Revises: 27d036aa8a43
Create Date: 2025-12-10
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5b9c0df13fba"
down_revision = "27d036aa8a43"
branch_labels = None
depends_on = None


def upgrade():
    # Add progress tracking columns to dungeon_instance
    op.add_column("dungeon_instance", sa.Column("bosses_total", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("dungeon_instance", sa.Column("elites_defeated", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("dungeon_instance", sa.Column("monsters_defeated", sa.Integer(), nullable=False, server_default="0"))

    # Ensure bosses_defeated and extraction_available have proper defaults
    op.alter_column(
        "dungeon_instance", "bosses_defeated", existing_type=sa.Integer(), nullable=False, server_default="0"
    )
    op.alter_column(
        "dungeon_instance", "extraction_available", existing_type=sa.Boolean(), nullable=False, server_default="false"
    )


def downgrade():
    # Remove added columns
    op.drop_column("dungeon_instance", "monsters_defeated")
    op.drop_column("dungeon_instance", "elites_defeated")
    op.drop_column("dungeon_instance", "bosses_total")

    # Revert changes to existing columns
    op.alter_column(
        "dungeon_instance", "bosses_defeated", existing_type=sa.Integer(), nullable=True, server_default=None
    )
    op.alter_column(
        "dungeon_instance", "extraction_available", existing_type=sa.Boolean(), nullable=True, server_default=None
    )
