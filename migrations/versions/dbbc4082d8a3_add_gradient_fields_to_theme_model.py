"""Add gradient fields to Theme model

Revision ID: dbbc4082d8a3
Revises:
Create Date: 2025-12-02

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "dbbc4082d8a3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Check if theme table exists by trying to add columns
    # If table doesn't exist, create it. If it does, just add the gradient columns.
    from alembic import context
    from sqlalchemy import inspect

    conn = context.get_bind()
    inspector = inspect(conn)

    if "theme" not in inspector.get_table_names():
        # Create theme table if it doesn't exist
        op.create_table(
            "theme",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("primary", sa.String(length=7), nullable=False),
            sa.Column("secondary", sa.String(length=7), nullable=False),
            sa.Column("success", sa.String(length=7), nullable=False),
            sa.Column("danger", sa.String(length=7), nullable=False),
            sa.Column("warning", sa.String(length=7), nullable=False),
            sa.Column("info", sa.String(length=7), nullable=False),
            sa.Column("light", sa.String(length=7), nullable=False),
            sa.Column("dark", sa.String(length=7), nullable=False),
            sa.Column("body_bg", sa.String(length=7), nullable=False),
            sa.Column("body_color", sa.String(length=7), nullable=False),
            sa.Column("link_color", sa.String(length=7), nullable=False),
            sa.Column("link_hover_color", sa.String(length=7), nullable=False),
            sa.Column("border_color", sa.String(length=7), nullable=False),
            sa.Column("card_bg", sa.String(length=7), nullable=False),
            sa.Column("gradient_angle", sa.Integer(), nullable=False),
            sa.Column("gradient_start", sa.String(length=7), nullable=False),
            sa.Column("gradient_end", sa.String(length=7), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["user.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    else:
        # Table exists, add gradient columns if they don't exist
        columns = [col["name"] for col in inspector.get_columns("theme")]

        if "gradient_angle" not in columns:
            op.add_column("theme", sa.Column("gradient_angle", sa.Integer(), nullable=False, server_default="135"))

        if "gradient_start" not in columns:
            op.add_column(
                "theme", sa.Column("gradient_start", sa.String(length=7), nullable=False, server_default="#4c5270")
            )

        if "gradient_end" not in columns:
            op.add_column(
                "theme", sa.Column("gradient_end", sa.String(length=7), nullable=False, server_default="#5a3a52")
            )


def downgrade():
    from alembic import context
    from sqlalchemy import inspect

    conn = context.get_bind()
    inspector = inspect(conn)

    if "theme" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("theme")]

        # Only drop gradient columns, not the whole table (in case it was pre-existing)
        if "gradient_end" in columns:
            op.drop_column("theme", "gradient_end")
        if "gradient_start" in columns:
            op.drop_column("theme", "gradient_start")
        if "gradient_angle" in columns:
            op.drop_column("theme", "gradient_angle")
