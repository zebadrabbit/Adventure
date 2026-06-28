"""Achievement service — internal (non-HTTP) entry point.

Call ``check_achievements(character_id, event_type, event_data)`` from any
service that needs to fire achievement events without going through HTTP.
The logic mirrors the ``/api/characters/<id>/achievements/check`` route.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

log = logging.getLogger(__name__)


def check_achievements(character_id: int, event_type: str, event_data: Dict[str, Any]) -> List[Dict]:
    """Fire an achievement event for *character_id*.

    Finds all active achievements whose ``requirement_type`` matches
    *event_type*, increments their progress by ``event_data.get("count", 1)``,
    and unlocks those that reach ``requirement_value``.

    Returns a list of newly-unlocked achievement dicts (may be empty).
    """
    from app import db
    from app.models.achievement import Achievement, CharacterAchievement
    from app.models.models import Character

    try:
        character = db.session.get(Character, character_id)
        if character is None:
            log.warning("check_achievements: character %s not found", character_id)
            return []

        matching = Achievement.query.filter_by(requirement_type=event_type, is_active=True).all()
        newly_unlocked: List[Dict] = []
        increment = event_data.get("count", 1)

        for achievement in matching:
            progress = CharacterAchievement.query.filter_by(
                character_id=character_id, achievement_id=achievement.id
            ).first()

            if not progress:
                progress = CharacterAchievement(
                    character_id=character_id,
                    achievement_id=achievement.id,
                    progress=0,
                    unlocked=False,
                )
                db.session.add(progress)

            if progress.unlocked:
                continue

            progress.progress += increment

            if progress.progress >= achievement.requirement_value:
                progress.unlocked = True
                progress.unlocked_at = datetime.utcnow()
                progress.notified = False

                if achievement.reward_gold > 0:
                    character.gold = (character.gold or 0) + achievement.reward_gold

                newly_unlocked.append(
                    {
                        "id": achievement.id,
                        "slug": achievement.slug,
                        "name": achievement.name,
                    }
                )

        db.session.flush()
        return newly_unlocked

    except Exception:
        log.exception("check_achievements failed for character %s event %s", character_id, event_type)
        return []
