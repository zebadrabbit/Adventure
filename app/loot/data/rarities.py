"""Rarity tiers: affix-count ranges + value multipliers.

UI colour for each tier lives in app/static/css/tokens.css (--rarity-common
… --rarity-mythic), not here — a duplicate hex per tier is exactly the kind
of second copy that drifts from the token it was cloned from (see
docs/DESIGN_SYSTEM.md, "The one rule")."""

# ``power`` scales the SIZE of every affix, not just how many there are.
# Without it rarity was decorative: a common "Longsword of the Bear" at level 20
# rolled {str: 9, con: 4} -- byte-identical to a mythic one, because neither the
# suffix budget nor the prefix roll ever saw the rarity. All rarity bought was a
# longer list and a higher price, so a legendary drop read as "same sword, more
# words". These multiply the rolled value, so a mythic affix is roughly double a
# common one before the count difference is counted at all.
RARITIES = {
    "common": {"affixes": (1, 2), "value_mult": 1.0, "power": 1.0},
    "uncommon": {"affixes": (2, 3), "value_mult": 1.6, "power": 1.15},
    "rare": {"affixes": (2, 4), "value_mult": 2.6, "power": 1.35},
    "epic": {"affixes": (3, 5), "value_mult": 4.2, "power": 1.6},
    "legendary": {"affixes": (4, 6), "value_mult": 7.0, "power": 1.85},
    "mythic": {"affixes": (5, 7), "value_mult": 12.0, "power": 2.2},
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def rarity_affix_range(rarity: str) -> tuple[int, int]:
    """Affix count range, falling back to common for an unknown rarity.

    Falls back to the real ``common`` entry rather than a literal: the literal
    was a second copy of common's range and silently went stale the moment the
    table changed.
    """
    return RARITIES.get(rarity, RARITIES["common"])["affixes"]


def rarity_power(rarity: str) -> float:
    """Magnitude multiplier for a rolled affix value."""
    return float(RARITIES.get(rarity, RARITIES["common"])["power"])
