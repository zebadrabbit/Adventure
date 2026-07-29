"""Rarity tiers: affix-count ranges + value multipliers.

UI colour for each tier lives in app/static/css/tokens.css (--rarity-common
… --rarity-mythic), not here — a duplicate hex per tier is exactly the kind
of second copy that drifts from the token it was cloned from (see
docs/DESIGN_SYSTEM.md, "The one rule")."""

RARITIES = {
    "common": {"affixes": (0, 1), "value_mult": 1.0},
    "uncommon": {"affixes": (1, 2), "value_mult": 1.6},
    "rare": {"affixes": (2, 3), "value_mult": 2.6},
    "epic": {"affixes": (3, 4), "value_mult": 4.2},
    "legendary": {"affixes": (3, 5), "value_mult": 7.0},
    "mythic": {"affixes": (4, 6), "value_mult": 12.0},
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def rarity_affix_range(rarity: str) -> tuple[int, int]:
    return RARITIES.get(rarity, {"affixes": (0, 1)})["affixes"]
