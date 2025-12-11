"""add damage tracking to combat

Revision ID: 27d036aa8a43
Revises: 95ff19b9fe00
Create Date: 2025-12-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "27d036aa8a43"
down_revision = "95ff19b9fe00"
branch_labels = None
depends_on = None


def upgrade():
    # Add damage tracking field to combat_session table
    op.add_column("combat_session", sa.Column("last_damage_json", sa.Text(), nullable=True))


def downgrade():
    # Remove damage tracking field
    op.drop_column("combat_session", "last_damage_json")
