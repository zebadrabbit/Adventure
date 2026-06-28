"""Tests for UserQuestPool model."""

from datetime import datetime

import pytest

from app import db
from app.models.user_quest_pool import UserQuestPool
from tests.factories import create_user


def test_create_and_retrieve():
    """Test creating a UserQuestPool and retrieving it with get_or_none."""
    user = create_user("test_user_pool")
    pool = UserQuestPool(
        user_id=user.id,
        period_type="daily",
        period_key="2026-06-27",
        quests_json="[]",
        created_at=datetime.now(),
    )
    db.session.add(pool)
    db.session.commit()

    found = UserQuestPool.get_or_none(user.id, "daily", "2026-06-27")
    assert found is not None
    assert found.period_key == "2026-06-27"
    assert found.period_type == "daily"
    assert found.quests_json == "[]"


def test_get_or_none_missing_returns_none():
    """Test that get_or_none returns None for non-existent pools."""
    result = UserQuestPool.get_or_none(9999, "daily", "2099-01-01")
    assert result is None


def test_unique_constraint_user_period_type_key():
    """Test that (user_id, period_type, period_key) must be unique."""
    user = create_user("test_user_unique")
    pool1 = UserQuestPool(
        user_id=user.id,
        period_type="daily",
        period_key="2026-06-27",
        quests_json="[]",
        created_at=datetime.now(),
    )
    db.session.add(pool1)
    db.session.commit()

    # Attempt to add a second pool with the same user/period_type/period_key
    pool2 = UserQuestPool(
        user_id=user.id,
        period_type="daily",
        period_key="2026-06-27",
        quests_json="[]",
        created_at=datetime.now(),
    )
    db.session.add(pool2)
    with pytest.raises(Exception):  # IntegrityError
        db.session.commit()
    db.session.rollback()


def test_different_periods_same_user():
    """Test that same user can have different period_type/period_key combinations."""
    user = create_user("test_user_periods")
    daily_pool = UserQuestPool(
        user_id=user.id,
        period_type="daily",
        period_key="2026-06-27",
        quests_json="[]",
        created_at=datetime.now(),
    )
    weekly_pool = UserQuestPool(
        user_id=user.id,
        period_type="weekly",
        period_key="2026-W26",
        quests_json="[]",
        created_at=datetime.now(),
    )
    db.session.add(daily_pool)
    db.session.add(weekly_pool)
    db.session.commit()

    daily_found = UserQuestPool.get_or_none(user.id, "daily", "2026-06-27")
    weekly_found = UserQuestPool.get_or_none(user.id, "weekly", "2026-W26")

    assert daily_found is not None
    assert weekly_found is not None
    assert daily_found.period_type == "daily"
    assert weekly_found.period_type == "weekly"
