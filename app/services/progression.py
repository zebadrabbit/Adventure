"""Character progression: turn earned XP into levels and talent points.

Per-character progression is the at-risk stake in the permadeath model (Spec 2):
a character accrues XP, levels up, and earns talent points to spend on skills.
A permadead character's progression is lost with them.

Tuning lives in GameConfig key "progression" (all optional, safe fallbacks):
    {
      "xp_difficulty_mod": 1.0,        # >1 slower leveling, <1 faster
      "talent_points_per_level": 1,    # talent points granted per level gained
      "extraction_xp": 50              # XP bonus per character on extraction
    }
"""

from __future__ import annotations

import json
from typing import Dict

from app import db
from app.models.models import GameConfig
from app.models.skill import CharacterTalentPoints
from app.models.xp import xp_for_level

_DEFAULT_PROGRESSION = {
    "xp_difficulty_mod": 1.0,
    "talent_points_per_level": 1,
    "stat_points_per_level": 2,
    "extraction_xp": 50,
}

# Upper bound for level search; the xp table extrapolates beyond 20.
_MAX_LEVEL = 50


def progression_config() -> dict:
    """Read progression tuning from GameConfig['progression'] with fallback."""
    raw = GameConfig.get("progression")
    if not raw:
        return dict(_DEFAULT_PROGRESSION)
    try:
        cfg = json.loads(raw)
    except Exception:
        return dict(_DEFAULT_PROGRESSION)
    merged = dict(_DEFAULT_PROGRESSION)
    merged.update(cfg or {})
    return merged


def level_for_xp(xp: int, difficulty_mod: float | None = None) -> int:
    """Highest level (>=1) whose cumulative XP requirement is met by ``xp``."""
    if difficulty_mod is None:
        difficulty_mod = float(progression_config().get("xp_difficulty_mod", 1.0))
    xp = max(0, int(xp))
    level = 1
    for candidate in range(2, _MAX_LEVEL + 1):
        if xp_for_level(candidate, difficulty_mod) <= xp:
            level = candidate
        else:
            break
    return level


def _talent_points(character_id: int) -> CharacterTalentPoints:
    tp = CharacterTalentPoints.query.filter_by(character_id=character_id).first()
    if tp is None:
        tp = CharacterTalentPoints(character_id=character_id, total_earned=0, total_spent=0, available=0)
        db.session.add(tp)
        db.session.flush()
    return tp


def grant_xp(character, amount: int) -> Dict[str, int]:
    """Add XP to a character, applying any resulting level-ups.

    Negative/zero amounts are ignored. On level gain, awards
    ``talent_points_per_level`` talent points per level into the character's
    CharacterTalentPoints. Does not commit (caller commits).

    Returns a summary dict: xp, level, levels_gained, talent_points_awarded.
    """
    cfg = progression_config()
    mod = float(cfg.get("xp_difficulty_mod", 1.0))
    per_level = int(cfg.get("talent_points_per_level", 1))
    stat_per_level = int(cfg.get("stat_points_per_level", 2))

    amount = max(0, int(amount))
    old_level = int(character.level or 1)
    character.xp = int(character.xp or 0) + amount

    new_level = level_for_xp(character.xp, mod)
    levels_gained = max(0, new_level - old_level)
    talent_awarded = 0
    stat_awarded = 0
    if levels_gained > 0:
        character.level = new_level
        talent_awarded = levels_gained * per_level
        if talent_awarded > 0:
            tp = _talent_points(character.id)
            tp.total_earned = (tp.total_earned or 0) + talent_awarded
            tp.available = (tp.available or 0) + talent_awarded
        stat_awarded = levels_gained * stat_per_level
        if stat_awarded > 0:
            character.stat_points = int(character.stat_points or 0) + stat_awarded

    return {
        "xp": character.xp,
        "level": int(character.level or 1),
        "levels_gained": levels_gained,
        "talent_points_awarded": talent_awarded,
        "stat_points_awarded": stat_awarded,
    }


def grant_starting_skill(character):
    """Give a freshly created character its class's tier-1 active, cost-free.

    Chooses the first active tier-1 skill in a class-gated tree that allows
    the character's class (archetype trees are the only class-gated ones);
    falls back to the universal Combat tree. Idempotent; never spends points.

    Returns the granted Skill, or None if a skill was already granted or no
    matching skills are seeded.
    """
    from app.models.skill import CharacterSkill, Skill, SkillTree

    try:
        char_class = (json.loads(character.stats) or {}).get("class")
    except Exception:
        char_class = None

    trees = SkillTree.query.filter_by(is_active=True).all()
    gated = [t for t in trees if t.class_requirement and t.allows_class(char_class)]
    universal = [t for t in trees if not t.class_requirement]
    for tree in gated + universal:
        skill = (
            Skill.query.filter_by(tree_id=tree.id, tier=1, skill_type="active", is_active=True)
            .order_by(Skill.id)
            .first()
        )
        if not skill:
            continue
        existing = CharacterSkill.query.filter_by(character_id=character.id, skill_id=skill.id).first()
        if existing:
            return None
        db.session.add(CharacterSkill(character_id=character.id, skill_id=skill.id, skill_rank=1))
        db.session.commit()
        return skill
    return None
