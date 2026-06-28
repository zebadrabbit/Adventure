"""Integration tests: quest progress hooks in combat and extraction."""

import json
import random
import string

import pytest

from app import db
from app.models.models import User


@pytest.fixture()
def test_user_with_daily_kill_quest():
    """Create a user with daily quests; return (user_id, first kill_count quest or any quest)."""
    uname = "qhook_" + "".join(random.choices(string.ascii_lowercase, k=6))
    u = User(username=uname, role="user")
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()

    from app.services.quest_generator import get_or_generate_daily

    quests = get_or_generate_daily(user_id=u.id)
    kill_quests = [q for q in quests if q["objective"]["type"] == "kill_count"]
    quest = kill_quests[0] if kill_quests else quests[0]
    return u.id, quest


def test_kill_increments_daily_quest(test_user_with_daily_kill_quest):
    """record_kill updates UserQuestPool for a kill_count quest."""
    from app.services.quest_progress_service import record_kill
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    user_id, quest = test_user_with_daily_kill_quest
    if quest["objective"]["type"] != "kill_count":
        pytest.skip("No kill_count quest generated this run")

    initial = quest["objective"]["current"]
    record_kill(user_id, is_elite=False)

    pool = UserQuestPool.get_or_none(user_id, "daily", period_key_daily())
    quests = json.loads(pool.quests_json)
    updated = next(q for q in quests if q["id"] == quest["id"])
    assert updated["objective"]["current"] == initial + 1


def test_run_complete_does_not_raise(test_user_with_daily_kill_quest):
    """record_run_complete with extracted=True does not raise."""
    from app.services.quest_progress_service import record_run_complete

    user_id, _ = test_user_with_daily_kill_quest
    record_run_complete(user_id, extracted=True)


def test_run_failed_does_not_raise(test_user_with_daily_kill_quest):
    """record_run_complete with extracted=False does not raise."""
    from app.services.quest_progress_service import record_run_complete

    user_id, _ = test_user_with_daily_kill_quest
    record_run_complete(user_id, extracted=False)
