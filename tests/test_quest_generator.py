"""Tests for app/services/quest_generator.py"""

import random
import string

import pytest

from app import db
from app.models.models import User


@pytest.fixture()
def test_user():
    """Create a throwaway user for quest generation tests."""
    uname = "quest_tester_" + "".join(random.choices(string.ascii_lowercase, k=6))
    u = User(username=uname, role="user")
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()
    return u


def test_period_key_daily():
    from app.services.quest_generator import period_key_daily

    key = period_key_daily()
    assert len(key) == 10  # "YYYY-MM-DD"
    assert key.count("-") == 2


def test_period_key_weekly():
    from app.services.quest_generator import period_key_weekly

    key = period_key_weekly()
    assert key.startswith("20")
    assert "-W" in key


def test_generate_daily_returns_three_quests(test_user):
    from app.services.quest_generator import get_or_generate_daily

    quests = get_or_generate_daily(user_id=test_user.id)
    assert len(quests) == 3
    for q in quests:
        assert "id" in q
        assert q["objective"]["type"] in ("kill_count", "kill_elite", "run_complete", "run_extract")
        assert q["status"] == "active"


def test_generate_daily_idempotent(test_user):
    from app.services.quest_generator import get_or_generate_daily

    first = get_or_generate_daily(user_id=test_user.id)
    second = get_or_generate_daily(user_id=test_user.id)
    assert [q["id"] for q in first] == [q["id"] for q in second]


def test_generate_weekly_returns_one_quest(test_user):
    from app.services.quest_generator import get_or_generate_weekly

    quest = get_or_generate_weekly(user_id=test_user.id)
    assert quest["objective"]["type"] == "daily_completions"
    assert quest["objective"]["target"] == 10
