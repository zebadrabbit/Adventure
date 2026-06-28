"""Update daily/weekly quest progress from dungeon events. Fire-and-forget."""

from __future__ import annotations

import json
import logging

from app import db
from app.models.user_quest_pool import UserQuestPool
from app.services.quest_generator import period_key_daily, period_key_weekly

logger = logging.getLogger(__name__)

# Maps objective type → which event increments it
_KILL_TYPES = {"kill_count", "kill_elite"}
_RUN_TYPES = {"run_complete", "run_extract"}


def _update_pool(user_id: int, period_type: str, period_key: str, predicate, amount: int = 1):
    """Increment objective.current on all matching active quests in pool."""
    pool = UserQuestPool.get_or_none(user_id, period_type, period_key)
    if not pool:
        return
    try:
        quests = json.loads(pool.quests_json)
    except Exception:
        return
    changed = False
    for q in quests:
        if q.get("status") != "active":
            continue
        obj = q.get("objective", {})
        if not predicate(obj):
            continue
        obj["current"] = min(obj.get("current", 0) + amount, obj.get("target", 9999))
        q["objective"] = obj
        if obj["current"] >= obj.get("target", 9999):
            q["status"] = "complete"
        changed = True
    if changed:
        pool.quests_json = json.dumps(quests)
        db.session.add(pool)
        db.session.commit()


def record_kill(user_id: int, is_elite: bool = False) -> None:
    try:
        key = period_key_daily()
        if is_elite:
            _update_pool(user_id, "daily", key, lambda o: o.get("type") == "kill_elite")
        _update_pool(user_id, "daily", key, lambda o: o.get("type") == "kill_count")
    except Exception as e:
        logger.warning("quest_progress_record_kill_failed", extra={"error": str(e)})


def record_run_complete(user_id: int, extracted: bool = True) -> None:
    try:
        key = period_key_daily()
        _update_pool(user_id, "daily", key, lambda o: o.get("type") == "run_complete")
        if extracted:
            _update_pool(user_id, "daily", key, lambda o: o.get("type") == "run_extract")
    except Exception as e:
        logger.warning("quest_progress_record_run_failed", extra={"error": str(e)})


def increment_daily_completions(user_id: int) -> None:
    """Called when a daily quest is claimed; advances the weekly counter."""
    try:
        key = period_key_weekly()
        _update_pool(user_id, "weekly", key, lambda o: o.get("type") == "daily_completions")
    except Exception as e:
        logger.warning("quest_progress_weekly_failed", extra={"error": str(e)})
