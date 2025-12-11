"""add weapon category system

Revision ID: a9f3b1e5d7c2
Revises: c146a28995f8
Create Date: 2025-12-07

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "a9f3b1e5d7c2"
down_revision = "c146a28995f8"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    # Create weapon_category table if it doesn't exist
    existing_tables = inspector.get_table_names()
    if "weapon_category" not in existing_tables:
        op.create_table(
            "weapon_category",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("weapon_type", sa.String(length=20), nullable=False),
            sa.Column("hands", sa.String(length=10), nullable=False),
            sa.Column("base_dice_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("base_die", sa.Integer(), nullable=False, server_default="6"),
            sa.Column("primary_stat", sa.String(length=40), nullable=False),
            sa.Column("crit_multiplier", sa.Float(), nullable=False, server_default="1.5"),
            sa.Column("attack_speed", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("allowed_classes", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("category_id"),
        )
        op.create_index("idx_weapon_category_id", "weapon_category", ["category_id"], unique=False)

    # Add weapon_category_id column to item table if it doesn't exist
    columns = [col["name"] for col in inspector.get_columns("item")]
    if "weapon_category_id" not in columns:
        op.add_column("item", sa.Column("weapon_category_id", sa.String(length=40), nullable=True))
        op.create_foreign_key(
            "fk_item_weapon_category", "item", "weapon_category", ["weapon_category_id"], ["category_id"]
        )


def downgrade():
    # Drop foreign key and column from item
    op.drop_constraint("fk_item_weapon_category", "item", type_="foreignkey")
    op.drop_column("item", "weapon_category_id")

    # Drop weapon_category table and index
    op.drop_index("idx_weapon_category_id", table_name="weapon_category")
    op.drop_table("weapon_category")
