"""drop party_shared_inventory

Revision ID: e4a91c73b2d8
Revises: d7e2c4a91b30
Create Date: 2026-07-30

Bags are per-character in this game, and per-character encumbrance only binds
if every item sits in somebody's bag -- a shared container is a hole straight
through it. Handing an item to an ally is ``POST /api/characters/<cid>/give``,
which is refused during combat. The four ``/api/party/<id>/inventory*`` routes,
the model, the dashboard tab and its CSS went with this table.

``Party.shared_gold`` and the ``/gold`` endpoints are a separate concept (a
party purse) and are deliberately untouched.

Note ``app/services/character_service.py``'s ``CLEARED_REFERENCES`` used to
contain ``("party_shared_inventory", "added_by")`` and executes raw SQL against
literal table names -- with the table dropped and that entry left in place,
every character deletion would raise UndefinedTable. It was removed in the same
change.

Guarded (inspector check) like c8f1a2b3d4e5: ``create_all`` runs before the
upgrade, and ``db_isolation`` tests rebuild the schema mid-suite into a
"tables-but-no-alembic_version" shape, so an unguarded drop re-runs against a
table that is already gone. ALL revisions here need the same guard.
"""

import sqlalchemy as sa
from alembic import op

revision = "e4a91c73b2d8"
down_revision = "d7e2c4a91b30"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "party_shared_inventory" in set(sa.inspect(bind).get_table_names()):
        op.drop_table("party_shared_inventory")


def downgrade():
    bind = op.get_bind()
    if "party_shared_inventory" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "party_shared_inventory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("party_id", sa.Integer(), sa.ForeignKey("party.id"), nullable=False),
            sa.Column("item_slug", sa.String(length=100), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("added_by", sa.Integer(), sa.ForeignKey("character.id"), nullable=True),
            sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("party_id", "item_slug", name="unique_party_item"),
        )
