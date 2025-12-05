"""add card opacity to theme

Revision ID: 22c97d4882cc
Revises: dbbc4082d8a3
Create Date: 2025-12-04

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "22c97d4882cc"
down_revision = "dbbc4082d8a3"
branch_labels = None
depends_on = None


def upgrade():
    # Check if column already exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("theme")]

    if "card_opacity" not in columns:
        op.add_column("theme", sa.Column("card_opacity", sa.Float(), nullable=False, server_default="0.1"))


def downgrade():
    op.drop_column("theme", "card_opacity")
