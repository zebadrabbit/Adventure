"""Aggregate a character's unlocked *passive* skill effects into stat bonuses.

Passive skills store their bonuses in Skill.effect_json (e.g. {"con": 2}). Active
skills are used as combat actions instead and are excluded here. The returned keys
match the gear-affix vocabulary (str/dex/int/con/wis/cha, damage/armor/speed/mana/
max_hp) so callers can fold passives in alongside gear_bonuses.
"""

from __future__ import annotations

import json

from app import db
from app.models.skill import CharacterSkill, Skill


def passive_bonuses(character_id: int) -> dict:
    """Sum effect_json across a character's unlocked passive skills -> {stat: total}."""
    totals: dict[str, float] = {}
    rows = (
        db.session.query(Skill)
        .join(CharacterSkill, CharacterSkill.skill_id == Skill.id)
        .filter(CharacterSkill.character_id == character_id, Skill.skill_type == "passive")
        .all()
    )
    for s in rows:
        try:
            eff = json.loads(s.effect_json or "{}")
        except Exception:
            continue
        if not isinstance(eff, dict):
            continue
        for stat, val in eff.items():
            if isinstance(val, (int, float)):
                totals[stat] = totals.get(stat, 0) + val
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}
