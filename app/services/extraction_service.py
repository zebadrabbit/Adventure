"""Extraction mechanics service.

Handles dungeon extraction, permadeath, locked-in-dungeon states, and extraction penalties.
"""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.models.dungeon_instance import DungeonInstance
from app.models.hoard import Hoard
from app.models.models import Character


def check_extraction_available(instance: DungeonInstance) -> Tuple[bool, str]:
    """Check if extraction is available for this dungeon instance.

    Returns:
        (available: bool, reason: str)
    """
    if instance.extraction_available:
        return True, "Hearthstone Portal is active (all bosses defeated)"

    # Early extraction always possible but with penalties
    return True, "Early extraction available with penalties"


def calculate_extraction_penalties(instance: DungeonInstance, early: bool = True) -> Dict[str, float]:
    """Calculate extraction penalties.

    Args:
        instance: Dungeon instance being extracted from
        early: Whether this is an early extraction (before all bosses defeated)

    Returns:
        Dict with penalty multipliers:
        - xp_multiplier: Multiplier for XP gained (1.0 = no penalty, 0.7 = 30% loss)
        - loot_quality_multiplier: Multiplier for loot quality (0.8 = 20% reduction)
    """
    if not early or instance.extraction_available:
        # No penalties if all bosses defeated
        return {"xp_multiplier": 1.0, "loot_quality_multiplier": 1.0}

    # Early extraction penalties from DESIGN.md
    # -30% XP, -20% loot quality
    return {"xp_multiplier": 0.7, "loot_quality_multiplier": 0.8}


def is_full_clear(instance: DungeonInstance) -> bool:
    """Boss(es) dead AND no monster entities left on the map.

    ponytail: entities are deleted when combat *starts* (finite pool), so a
    fled encounter still counts toward the clear; upgrade path is a real
    kill counter on the instance if flee-abuse ever matters.
    """
    total = int(getattr(instance, "bosses_total", 0) or 0)
    if total <= 0 or int(instance.bosses_defeated or 0) < total:
        return False
    from app.models.entities import DungeonEntity  # match trigger_collision_combat's import path

    remaining = DungeonEntity.query.filter_by(instance_id=instance.id, type="monster").count()
    return remaining == 0


def extract_party(
    instance: DungeonInstance, character_ids: List[int], user_id: int
) -> Tuple[bool, str, Dict[str, any]]:
    """Extract characters from dungeon.

    Args:
        instance: DungeonInstance to extract from
        character_ids: List of character IDs to extract
        user_id: User ID performing extraction

    Returns:
        (success: bool, message: str, result: dict)
        result contains:
        - extracted: list of character names extracted
        - left_behind: list of character names left behind (permadeath)
        - penalties: dict of applied penalties
    """
    # Get all user's characters in this dungeon
    all_chars = Character.query.filter_by(user_id=user_id, locked_dungeon_id=instance.id).all()

    if not all_chars:
        return False, "No characters in this dungeon", {}

    # Check if extraction is early
    early_extraction = not instance.extraction_available

    # Calculate penalties
    penalties = calculate_extraction_penalties(instance, early=early_extraction)

    # Split characters into extracting and left behind
    extracting_chars = [c for c in all_chars if c.id in character_ids]
    left_behind_chars = [c for c in all_chars if c.id not in character_ids]

    if not extracting_chars:
        return False, "Must select at least one character to extract", {}

    hoard = Hoard.get_or_create(user_id)
    secured_copper = 0
    secured_items = 0

    from app.services import progression

    cfg = progression.progression_config()
    # Whole-run bonus: every monster + the boss slain this run.
    full_clear = is_full_clear(instance)

    # Apply penalties to extracting characters
    for char in extracting_chars:
        # Apply XP penalty
        if penalties["xp_multiplier"] < 1.0:
            char.xp = int(char.xp * penalties["xp_multiplier"])

        # Unlock character from dungeon
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

        # Revive if dead (successfully extracted)
        if char.is_dead:
            char.is_dead = False
            # Restore health in stats
            try:
                stats = json.loads(char.stats) if isinstance(char.stats, str) else char.stats
                hp_max = stats.get("hp_max", stats.get("HP", 100))
                stats["hp"] = hp_max
                stats["HP"] = hp_max
                char.stats = json.dumps(stats)
            except Exception:
                pass

        # Award extraction XP (scaled by the same early-extraction multiplier),
        # applying any resulting level-ups + talent points.
        extraction_xp = int(cfg.get("extraction_xp", 0))
        if full_clear:
            extraction_xp = int(extraction_xp * (1 + float(cfg.get("full_clear_xp_bonus", 0.5))))
        if extraction_xp > 0:
            progression.grant_xp(char, int(extraction_xp * penalties["xp_multiplier"]))

        # Pool this character's run haul (bag + run-purse) into the hoard
        moved = hoard_service.pool_run_haul(hoard, char)
        secured_copper += moved["copper"]
        secured_items += moved["items"]

    # Full-clear copper multiplier: apply to what actually lands in the hoard,
    # not just the reported number -- pool_run_haul already deposited the base
    # copper, so top up the hoard by the bonus delta and report the total.
    if full_clear and not early_extraction and secured_copper > 0:
        boosted = int(secured_copper * float(cfg.get("full_clear_copper_mult", 1.25)))
        hoard_service.deposit_copper(hoard, boosted - secured_copper)
        secured_copper = boosted

    # Mark left behind characters as permadeath
    for char in left_behind_chars:
        char.permadeath = True
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

    db.session.commit()

    try:
        from app.services import quest_progress_service

        quest_progress_service.record_run_complete(user_id, extracted=True)
    except Exception:
        pass

    # Achievement hooks — dungeon difficulty & affix milestones
    # Wrapped in a nested savepoint so any DB error here cannot taint the
    # outer transaction (extraction already committed above).
    try:
        from app.models.dungeon_tier import DungeonAffix as _Affix
        from app.services.achievement_service import check_achievements as _check_ach

        affix_ids = instance.get_affixes()
        tier = instance.tier or 1

        sp = db.session.begin_nested()
        try:
            weights = {a.affix_id: a.threat_weight for a in _Affix.query.all()}
            sp.commit()
        except Exception:
            sp.rollback()
            weights = {}

        threat_score = sum(weights.get(a, 1) for a in affix_ids) + (tier - 1) * 2

        # Each event_type maps to exactly one achievement slug; fire only when
        # the condition holds so we don't unlock the wrong achievement.
        _events = [
            ("dungeon_heroic", tier >= 2),
            ("dungeon_mythic", tier >= 3),
            ("dungeon_first_affix", len(affix_ids) >= 1),
            ("dungeon_triple_affix", len(affix_ids) >= 3),
            ("dungeon_harrowing", threat_score >= 6),
            ("dungeon_doomed", threat_score >= 15),
            ("dungeon_mythic_multi_affix", tier >= 3 and len(affix_ids) >= 2),
            ("dungeon_death_wish", "cursed" in affix_ids and "savage" in affix_ids),
            ("dungeon_gold_rush", "gilded" in affix_ids and "swarming" in affix_ids),
        ]

        _base_data = {
            "tier": tier,
            "affix_ids": affix_ids,
            "affix_count": len(affix_ids),
            "threat_score": threat_score,
            "count": 1,
        }

        for char in extracting_chars:
            for event_type, condition in _events:
                if condition:
                    _check_ach(char.id, event_type, _base_data)
            if full_clear:
                _check_ach(char.id, "dungeon_full_clear", {"count": 1})
    except Exception:
        import logging as _logging

        _logging.getLogger(__name__).warning("achievement hooks failed", exc_info=True)

    result = {
        "extracted": [c.name for c in extracting_chars],
        "left_behind": [c.name for c in left_behind_chars],
        "penalties": penalties,
        "early_extraction": early_extraction,
        "full_clear": full_clear,
        "secured": {
            "copper": secured_copper,
            "copper_display": format_copper(secured_copper),
            "items": secured_items,
        },
    }

    message = f"Extracted {len(extracting_chars)} character(s)"
    if left_behind_chars:
        message += f", {len(left_behind_chars)} left behind (PERMADEATH)"
    if early_extraction:
        message += f" (Early extraction: {int((1-penalties['xp_multiplier'])*100)}% XP loss)"

    return True, message, result


def handle_character_death(char: Character, instance: DungeonInstance):
    """Handle character death in dungeon.

    Marks character as dead and locks them to the dungeon instance.
    """
    char.is_dead = True
    char.death_count += 1
    char.locked_in_dungeon = True
    char.locked_dungeon_id = instance.id
    db.session.commit()


def revive_character(char: Character) -> Tuple[bool, str]:
    """Revive a dead character (via item, spell, or shrine).

    Args:
        char: Character to revive

    Returns:
        (success: bool, message: str)
    """
    if not char.is_dead:
        return False, "Character is not dead"

    if char.permadeath:
        return False, "Character has permadeath and cannot be revived"

    # Revive character
    char.is_dead = False

    # Restore to low HP
    try:
        stats = json.loads(char.stats) if isinstance(char.stats, str) else char.stats
        hp_max = stats.get("hp_max", stats.get("HP", 100))
        stats["hp"] = max(1, int(hp_max * 0.25))  # Revive at 25% HP
        stats["HP"] = stats["hp"]
        char.stats = json.dumps(stats)
    except Exception:
        pass

    db.session.commit()
    return True, f"{char.name} has been revived!"


def get_extraction_status(instance: DungeonInstance, user_id: int) -> Dict[str, any]:
    """Get current extraction status for a dungeon instance.

    Returns dict with:
    - extraction_available: bool
    - reason: str
    - characters: list of character info
    - penalties: dict of potential penalties
    """
    available, reason = check_extraction_available(instance)

    # Get all characters in this dungeon
    chars = Character.query.filter_by(user_id=user_id, locked_dungeon_id=instance.id).all()

    char_info = []
    for c in chars:
        char_info.append(
            {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "is_dead": c.is_dead,
                "locked_in_dungeon": c.locked_in_dungeon,
                "permadeath": c.permadeath,
            }
        )

    penalties = calculate_extraction_penalties(instance, early=not instance.extraction_available)

    return {
        "extraction_available": available,
        "reason": reason,
        "all_bosses_defeated": instance.extraction_available,
        "bosses_defeated": instance.bosses_defeated,
        "characters": char_info,
        "penalties": penalties,
    }
