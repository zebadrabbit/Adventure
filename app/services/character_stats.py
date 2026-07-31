"""
project: Adventure MUD
module: character_stats.py

Single source of truth for the HP/mana cap math, used by the persistent
status-effect decay/regen pass (app/services/status_effects.py) and
dashboard_helpers.build_party_payload. combat_service._derive_stats keeps
an inline copy on purpose: it derives attack/defense/speed from the same
folded attributes in one pass, and its legacy CON default falls back to
STR rather than 10 — see the comment at its cap-formula block.
"""

from __future__ import annotations

import json
from typing import Tuple

from app.models.models import Character


def compute_hp_mana_max(character: Character) -> Tuple[int, int]:
    """Return (hp_max, mana_max) for a character, folding in gear and
    passive skill bonuses the same way combat does.
    """
    try:
        stats = json.loads(character.stats) if character.stats else {}
        if not isinstance(stats, dict):
            stats = {}
    except Exception:
        stats = {}

    level = getattr(character, "level", 1) or 1
    con = int(stats.get("con", stats.get("CON", 10)) or 10)
    intelligence = int(stats.get("int", stats.get("INT", 10)) or 10)

    hp_max = 50 + con * 2 + level * 5
    # Mana gains a level term. Without one the pool was a flat 20 + INT*2 --
    # 40 for a level-20 character with INT 10 -- while the catalogue sells a
    # twenty-tier mana ladder whose top potion restored 42, more than the whole
    # bar. Every tier past about 10 was partly wasted, so twenty tiers, five
    # rarities and a 47x price spread all described the same potion.
    # Mirrored in combat_service._derive_stats; the two must move together.
    mana_max = 20 + intelligence * 2 + level * 3

    from app.services.loot_service import gear_bonuses

    try:
        gear = json.loads(character.gear) if getattr(character, "gear", None) else {}
    except Exception:
        gear = {}
    gb = gear_bonuses(gear)

    try:
        from app.services.skill_effects import passive_bonuses

        for key, value in passive_bonuses(character.id).items():
            gb[key] = gb.get(key, 0) + value
    except Exception:
        pass

    hp_max += int(gb.get("max_hp", 0)) + int(gb.get("con", 0)) * 2
    mana_max += int(gb.get("mana", 0)) + int(gb.get("int", 0)) * 2

    return hp_max, mana_max
