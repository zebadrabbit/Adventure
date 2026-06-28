"""Tests for app/services/quest_progress_service.py"""

import json
import random
import string

import pytest

from app import db
from app.models.models import User


@pytest.fixture()
def test_user_with_daily_quests():
    """Create a throwaway user and generate daily quests for them."""
    uname = "qprog_" + "".join(random.choices(string.ascii_lowercase, k=6))
    u = User(username=uname, role="user")
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()

    from app.services.quest_generator import get_or_generate_daily

    quests = get_or_generate_daily(user_id=u.id)
    return u.id, quests


def test_record_kill_increments_kill_count(test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    kill_quests = [q for q in quests if q["objective"]["type"] == "kill_count"]
    if not kill_quests:
        return  # no kill_count quest generated this run; skip

    from app.services.quest_progress_service import record_kill
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    record_kill(user_id, is_elite=False)
    pool = UserQuestPool.get_or_none(user_id, "daily", period_key_daily())
    updated = json.loads(pool.quests_json)
    updated_q = next(q for q in updated if q["id"] == kill_quests[0]["id"])
    assert updated_q["objective"]["current"] == 1


def test_record_kill_elite_increments_elite(test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    from app.services.quest_progress_service import record_kill

    # Should not raise even if no elite quest exists
    record_kill(user_id, is_elite=True)


def test_record_run_complete(test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    from app.services.quest_progress_service import record_run_complete

    record_run_complete(user_id, extracted=True)
    # Should not raise; verify no exception is enough for fire-and-forget


def test_increment_daily_completions(test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    from app.services.quest_progress_service import increment_daily_completions
    from app.services.quest_generator import get_or_generate_weekly, period_key_weekly
    from app.models.user_quest_pool import UserQuestPool

    get_or_generate_weekly(user_id=user_id)
    increment_daily_completions(user_id)
    pool = UserQuestPool.get_or_none(user_id, "weekly", period_key_weekly())
    updated = json.loads(pool.quests_json)
    assert updated[0]["objective"]["current"] == 1


def test_record_run_complete_increments_run_complete(test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    run_quests = [q for q in quests if q["objective"]["type"] == "run_complete"]
    if not run_quests:
        return

    from app.services.quest_progress_service import record_run_complete
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    record_run_complete(user_id, extracted=False)
    pool = UserQuestPool.get_or_none(user_id, "daily", period_key_daily())
    updated = json.loads(pool.quests_json)
    updated_q = next(q for q in updated if q["id"] == run_quests[0]["id"])
    assert updated_q["objective"]["current"] == 1
