"""Per-user generated quest pool for daily and weekly quests."""

from __future__ import annotations

from datetime import datetime

from app import db


class UserQuestPool(db.Model):
    """Per-user quest pool for a specific period (e.g., daily or weekly).

    One row per (user_id, period_type, period_key) combination.
    quests_json stores the list of active quests for that period.
    """

    __tablename__ = "user_quest_pool"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    period_type = db.Column(db.String(10), nullable=False)  # "daily" | "weekly"
    period_key = db.Column(db.String(20), nullable=False)  # "2026-06-27" | "2026-W26"
    quests_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    __table_args__ = (db.UniqueConstraint("user_id", "period_type", "period_key", name="uq_user_quest_pool"),)

    @classmethod
    def get_or_none(cls, user_id: int, period_type: str, period_key: str) -> UserQuestPool | None:
        """Return the quest pool for the given user+period, or None if absent."""
        return cls.query.filter_by(user_id=user_id, period_type=period_type, period_key=period_key).first()
