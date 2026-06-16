"""Rarity tiers: affix-count ranges + UI colors."""

RARITIES = {
    "common": {"affixes": (0, 1), "color": "#9d9d9d", "value_mult": 1.0},
    "uncommon": {"affixes": (1, 2), "color": "#1eff00", "value_mult": 1.6},
    "rare": {"affixes": (2, 3), "color": "#0070dd", "value_mult": 2.6},
    "epic": {"affixes": (3, 4), "color": "#a335ee", "value_mult": 4.2},
    "legendary": {"affixes": (3, 5), "color": "#ff8000", "value_mult": 7.0},
    "mythic": {"affixes": (4, 6), "color": "#e6cc80", "value_mult": 12.0},
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def rarity_affix_range(rarity: str) -> tuple[int, int]:
    return RARITIES.get(rarity, {"affixes": (0, 1)})["affixes"]
