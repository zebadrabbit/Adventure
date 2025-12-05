"""add_background_image_to_theme

Revision ID: c146a28995f8
Revises: 22c97d4882cc
Create Date: 2025-12-04 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c146a28995f8"
down_revision = "22c97d4882cc"
branch_labels = None
depends_on = None


def upgrade():
    """Add background image fields to theme table."""
    # Check if columns already exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("theme")]

    if "background_image" not in columns:
        op.add_column("theme", sa.Column("background_image", sa.String(255), nullable=True))
    if "bg_position" not in columns:
        op.add_column("theme", sa.Column("bg_position", sa.String(50), nullable=False, server_default="center"))
    if "bg_size" not in columns:
        op.add_column("theme", sa.Column("bg_size", sa.String(50), nullable=False, server_default="cover"))
    if "bg_repeat" not in columns:
        op.add_column("theme", sa.Column("bg_repeat", sa.String(50), nullable=False, server_default="no-repeat"))
    if "bg_attachment" not in columns:
        op.add_column("theme", sa.Column("bg_attachment", sa.String(50), nullable=False, server_default="scroll"))


def downgrade():
    """Remove background image fields from theme table."""
    op.drop_column("theme", "bg_attachment")
    op.drop_column("theme", "bg_repeat")
    op.drop_column("theme", "bg_size")
    op.drop_column("theme", "bg_position")
    op.drop_column("theme", "background_image")
