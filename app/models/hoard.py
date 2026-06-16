"""Per-user Hoard: persistent secured gear + currency (account-level vault)."""

from __future__ import annotations

from app import db


class Hoard(db.Model):
    """One row per user. Survives character permadeath.

    items_json uses the canonical inventory format from app/inventory/utils.py:
    a JSON list mixing {"slug","qty"} stacks and procedural gear instance dicts
    (with a "uid"). copper is the safe currency (smallest unit; see Spec 1).
    """

    __tablename__ = "hoard"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False, index=True)
    items_json = db.Column(db.Text, nullable=False, default="[]")
    copper = db.Column(db.Integer, nullable=False, default=0)

    @staticmethod
    def get_or_create(user_id: int) -> "Hoard":
        """Return the user's hoard, creating (and adding to the session) if absent."""
        hoard = Hoard.query.filter_by(user_id=user_id).first()
        if hoard is None:
            hoard = Hoard(user_id=user_id, items_json="[]", copper=0)
            db.session.add(hoard)
            db.session.flush()
        return hoard
