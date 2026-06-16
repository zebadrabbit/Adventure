"""Extraction mechanics service.

Handles dungeon extraction, permadeath, locked-in-dungeon states, and extraction penalties.
"""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

from app import db
from app.economy import hoard_service
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
        from app.services import progression

        extraction_xp = int(progression.progression_config().get("extraction_xp", 0))
        if extraction_xp > 0:
            progression.grant_xp(char, int(extraction_xp * penalties["xp_multiplier"]))

        # Pool this character's run haul (bag + run-purse) into the hoard
        hoard_service.pool_run_haul(hoard, char)

    # Mark left behind characters as permadeath
    for char in left_behind_chars:
        char.permadeath = True
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

    db.session.commit()

    result = {
        "extracted": [c.name for c in extracting_chars],
        "left_behind": [c.name for c in left_behind_chars],
        "penalties": penalties,
        "early_extraction": early_extraction,
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
