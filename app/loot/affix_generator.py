"""Procedural affix generation for loot items.

Implements the affix rolling algorithm from DESIGN.md:
1. Roll rarity tier (determines affix count)
2. Select base item
3. Roll affix count from rarity min/max
4. Randomly select affixes (no duplicates)
5. Roll values within affix ranges + level scaling
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from app.models.affix import ItemAffix, ProceduralAffix
from app.models.models import Item

# Rarity tier affix count ranges (from loot_rarities.csv)
RARITY_AFFIX_COUNTS = {
    "common": (0, 1),
    "uncommon": (1, 2),
    "rare": (2, 3),
    "epic": (3, 4),
    "legendary": (3, 5),
    "mythic": (4, 6),
}


def apply_procedural_affixes(
    item: Item,
    item_level: int,
    dungeon_seed: int,
    coords: Optional[Tuple[int, int, int]] = None,
    rng: Optional[random.Random] = None,
) -> List[ItemAffix]:
    """Apply procedural affixes to an item based on its rarity.

    Args:
        item: Base item to modify
        item_level: Level of the item (affects affix scaling)
        dungeon_seed: Dungeon seed for tracking
        coords: (x, y, z) coordinates where item was placed
        rng: Random number generator (for determinism)

    Returns:
        List of ItemAffix instances (not yet committed to DB)
    """
    if rng is None:
        rng = random.Random()

    # Get affix count range for this rarity
    min_affixes, max_affixes = RARITY_AFFIX_COUNTS.get(item.rarity, (0, 1))
    affix_count = rng.randint(min_affixes, max_affixes)

    if affix_count == 0:
        return []

    # Get eligible affixes for this item type
    all_affixes = ProceduralAffix.query.all()
    eligible = [a for a in all_affixes if a.is_allowed_for_type(item.type)]

    if not eligible:
        return []

    # Weighted selection without replacement
    selected_affixes = _weighted_sample(eligible, affix_count, rng)

    # Roll values for each affix
    result = []
    x, y, z = coords if coords else (None, None, None)

    for affix in selected_affixes:
        rolled_value = affix.roll_value(item_level)
        item_affix = ItemAffix(
            item_id=item.id,
            affix_id=affix.affix_id,
            rolled_value=rolled_value,
            dungeon_seed=dungeon_seed,
            x=x,
            y=y,
            z=z,
        )
        result.append(item_affix)

    return result


def _weighted_sample(
    affixes: List[ProceduralAffix],
    count: int,
    rng: random.Random,
) -> List[ProceduralAffix]:
    """Select affixes using weighted sampling without replacement.

    Args:
        affixes: Pool of available affixes
        count: Number to select
        rng: Random number generator

    Returns:
        List of selected affixes (no duplicates)
    """
    if not affixes:
        return []

    count = min(count, len(affixes))
    selected = []
    pool = affixes.copy()

    for _ in range(count):
        if not pool:
            break

        weights = [a.rarity_weight for a in pool]
        total = sum(weights)

        # Roulette wheel selection
        r = rng.randint(1, total)
        cumulative = 0

        for i, affix in enumerate(pool):
            cumulative += weights[i]
            if r <= cumulative:
                selected.append(affix)
                pool.pop(i)
                break

    return selected


def generate_item_name(item: Item, affixes: List[ItemAffix]) -> str:
    """Generate procedural item name with affix prefixes/suffixes.

    Examples:
        'Iron Longsword' + Brutal + of Precision
        -> 'Brutal Iron Longsword of Precision'

    Args:
        item: Base item
        affixes: Applied affixes

    Returns:
        Full procedural item name
    """
    if not affixes:
        return item.name

    # Load affix templates to get prefix/suffix info
    affix_map = {
        a.affix_id: a
        for a in ProceduralAffix.query.filter(ProceduralAffix.affix_id.in_([ia.affix_id for ia in affixes])).all()
    }

    prefixes = []
    suffixes = []

    for item_affix in affixes:
        affix_template = affix_map.get(item_affix.affix_id)
        if not affix_template:
            continue

        if affix_template.slot.lower() == "prefix":
            prefixes.append(affix_template.name)
        else:
            suffixes.append(affix_template.name)

    # Build name: [Prefix] BaseName [of Suffix] [and Suffix2]
    parts = []

    if prefixes:
        parts.append(" ".join(prefixes))

    parts.append(item.name)

    if suffixes:
        if len(suffixes) == 1:
            parts.append(suffixes[0])
        else:
            # Multiple suffixes: "of X and Y"
            parts.append(suffixes[0])
            parts.append("and")
            parts.append(" and ".join(suffixes[1:]))

    return " ".join(parts)


def get_affix_stats(affixes: List[ItemAffix]) -> dict[str, float]:
    """Extract stat bonuses from applied affixes.

    Args:
        affixes: List of applied affixes

    Returns:
        Dictionary of stat_key -> total_value
    """
    stats = {}

    affix_map = {
        a.affix_id: a
        for a in ProceduralAffix.query.filter(ProceduralAffix.affix_id.in_([ia.affix_id for ia in affixes])).all()
    }

    for item_affix in affixes:
        affix_template = affix_map.get(item_affix.affix_id)
        if not affix_template:
            continue

        stat_key = affix_template.affected_stat
        current = stats.get(stat_key, 0.0)
        stats[stat_key] = current + item_affix.rolled_value

    return stats
