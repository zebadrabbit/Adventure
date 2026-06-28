"""Lazy generator for per-user daily and weekly quests."""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime

from app import db
from app.models.user_quest_pool import UserQuestPool


def period_key_daily() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def period_key_weekly() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# (weight, title, description_template, objective_type, target_range)
_DAILY_TEMPLATES = [
    (3, "Thin the Ranks", "Defeat {n} enemies in the dungeon.", "kill_count", (10, 30)),
    (2, "Veteran's Trial", "Defeat {n} elite or boss enemies.", "kill_elite", (2, 6)),
    (3, "Back in One Piece", "Complete {n} dungeon runs.", "run_complete", (2, 4)),
    (2, "Clean Sweep", "Extract successfully {n} times without a wipe.", "run_extract", (1, 3)),
]


def _avg_level(user_id: int) -> int:
    from app.models.models import Character

    chars = Character.query.filter_by(user_id=user_id).all()
    if not chars:
        return 1
    return max(1, round(sum(c.level for c in chars) / len(chars)))


def _roll_rewards(avg_level: int, template_type: str) -> dict:
    xp = random.randint(200, 500)
    potions = [{"slug": random.choice(["potion-healing", "potion-mana"]), "qty": random.randint(1, 2)}]
    return {
        "xp": xp,
        "potions": potions,
        "gear_roll": random.random() < 0.15,
    }


def _generate_dailies(avg_level: int) -> list[dict]:
    weights = [t[0] for t in _DAILY_TEMPLATES]
    chosen = random.choices(_DAILY_TEMPLATES, weights=weights, k=3)
    quests = []
    for weight, title, desc_tpl, obj_type, (lo, hi) in chosen:
        n = random.randint(lo, hi)
        quests.append(
            {
                "id": str(uuid.uuid4()),
                "template": obj_type,
                "title": title,
                "description": desc_tpl.format(n=n),
                "objective": {"type": obj_type, "target": n, "current": 0},
                "rewards": _roll_rewards(avg_level, obj_type),
                "status": "active",
                "claimed_at": None,
            }
        )
    return quests


def _generate_weekly() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "template": "weekly_dailies",
        "title": "Weekly Devotion",
        "description": "Complete 10 daily quests this week.",
        "objective": {"type": "daily_completions", "target": 10, "current": 0},
        "rewards": {
            "xp": 1500,
            "potions": [{"slug": "potion-healing", "qty": random.randint(3, 5)}],
            "gear_roll": True,
            "copper": 500,
        },
        "status": "active",
        "claimed_at": None,
    }


def get_or_generate_daily(user_id: int) -> list[dict]:
    """Return today's 3 daily quests for the user, generating them if needed."""
    key = period_key_daily()
    pool = UserQuestPool.get_or_none(user_id, "daily", key)
    if pool:
        return json.loads(pool.quests_json)

    avg = _avg_level(user_id)
    quests = _generate_dailies(avg)
    pool = UserQuestPool(
        user_id=user_id,
        period_type="daily",
        period_key=key,
        quests_json=json.dumps(quests),
        created_at=datetime.now(),
    )
    db.session.add(pool)
    db.session.commit()
    return quests


def get_or_generate_weekly(user_id: int) -> dict:
    """Return this week's weekly quest for the user, generating if needed."""
    key = period_key_weekly()
    pool = UserQuestPool.get_or_none(user_id, "weekly", key)
    if pool:
        quests = json.loads(pool.quests_json)
        return quests[0] if quests else _generate_weekly()

    quest = _generate_weekly()
    pool = UserQuestPool(
        user_id=user_id,
        period_type="weekly",
        period_key=key,
        quests_json=json.dumps([quest]),
        created_at=datetime.now(),
    )
    db.session.add(pool)
    db.session.commit()
    return quest
