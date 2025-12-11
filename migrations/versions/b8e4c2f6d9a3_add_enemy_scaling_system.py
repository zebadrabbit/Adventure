"""add enemy scaling system

Revision ID: b8e4c2f6d9a3
Revises: a9f3b1e5d7c2
Create Date: 2025-12-07

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "b8e4c2f6d9a3"
down_revision = "a9f3b1e5d7c2"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create enemy_archetype table
    if "enemy_archetype" not in existing_tables:
        op.create_table(
            "enemy_archetype",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("archetype", sa.String(length=40), nullable=False),
            sa.Column("rank", sa.String(length=20), nullable=False),
            sa.Column("base_hp", sa.Integer(), nullable=False, server_default="25"),
            sa.Column("hp_per_level", sa.Float(), nullable=False, server_default="10.0"),
            sa.Column("base_damage", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("damage_per_level", sa.Float(), nullable=False, server_default="2.0"),
            sa.Column("armor_class_base", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("armor_class_per_level", sa.Float(), nullable=False, server_default="0.3"),
            sa.Column("xp_base", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("xp_per_level", sa.Float(), nullable=False, server_default="5.0"),
            sa.Column("loot_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("archetype"),
        )
        op.create_index("ix_enemy_archetype_archetype", "enemy_archetype", ["archetype"], unique=False)

    # Create dungeon_tier table
    if "dungeon_tier" not in existing_tables:
        op.create_table(
            "dungeon_tier",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tier", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=40), nullable=False),
            sa.Column("min_level", sa.Integer(), nullable=False),
            sa.Column("max_level", sa.Integer(), nullable=False),
            sa.Column("monster_level_modifier", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("loot_quality_bonus", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("xp_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tier"),
        )
        op.create_index("ix_dungeon_tier_tier", "dungeon_tier", ["tier"], unique=False)

    # Create dungeon_affix table
    if "dungeon_affix" not in existing_tables:
        op.create_table(
            "dungeon_affix",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("affix_id", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("monster_hp_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("monster_damage_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("monster_speed_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("player_damage_taken_multiplier", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("special_effect", sa.Text(), nullable=True),
            sa.Column("color", sa.String(length=20), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("affix_id"),
        )
        op.create_index("ix_dungeon_affix_affix_id", "dungeon_affix", ["affix_id"], unique=False)

    # Add tier and affix columns to dungeon_instance table
    columns = [col["name"] for col in inspector.get_columns("dungeon_instance")]
    if "tier" not in columns:
        op.add_column("dungeon_instance", sa.Column("tier", sa.Integer(), nullable=True, server_default="1"))
    if "affix_ids" not in columns:
        op.add_column("dungeon_instance", sa.Column("affix_ids", sa.Text(), nullable=True))


def downgrade():
    # Drop columns from dungeon_instance
    op.drop_column("dungeon_instance", "affix_ids")
    op.drop_column("dungeon_instance", "tier")

    # Drop tables
    op.drop_index("ix_dungeon_affix_affix_id", table_name="dungeon_affix")
    op.drop_table("dungeon_affix")

    op.drop_index("ix_dungeon_tier_tier", table_name="dungeon_tier")
    op.drop_table("dungeon_tier")

    op.drop_index("ix_enemy_archetype_archetype", table_name="enemy_archetype")
    op.drop_table("enemy_archetype")
