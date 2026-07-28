"""Named monster loot tables.

`monster_catalog.loot_table` holds names like `goblin_basic`, `undead_elite` and
`boss_dragon`. `loot_service._parse_loot_table` treated the whole string as a
CSV of *item slugs*, so `boss_dragon` was looked up as an item literally called
"boss_dragon", matched nothing, and the pool came back empty. Every monster in
the game has therefore always dropped exactly zero catalogue items -- procedural
gear and boss keys still dropped, which is why it went unnoticed.

Rather than hand-authoring ~30 tables of literal slugs (which would rot every
time the item catalogue changes), a name resolves to a *rule*: a tier read off
the name's suffix, filtered against the item catalogue by type, rarity and
level. Adding an item to the catalogue makes it eligible everywhere it fits,
with no table edits.

Naming convention, matching what the catalogue already uses:

    <family>_basic   ordinary kills      common consumables and materials
    <family>_elite   elites/rares        better consumables, tools, scrolls, gems
    <family>_named   named elites        as boss, slightly thinner
    boss_<family>    dungeon bosses      scrolls, gems, the good potions

The `<family>` part is currently *flavour only* -- items carry no family tag, so
there is nothing to filter on. It is preserved in the names so that per-family
drops (bones from undead, cores from constructs) can be added later without
touching the catalogue.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from app.models.models import Item

# Relative likelihood by rarity. Mirrors spawn_service.RARITY_WEIGHTS so monster
# rarity and loot rarity fall off at the same rate.
RARITY_WEIGHTS = {
    "common": 1.0,
    "uncommon": 0.55,
    "rare": 0.30,
    "epic": 0.12,
    "legendary": 0.04,
    "mythic": 0.02,
}

# What each tier draws from. `types` filters Item.type and `rarities` filters
# Item.rarity, but note the catalogue is currently ~98% common (225 of 229
# items, with 2 uncommon, 1 rare, 1 epic and no legendary), so rarity alone
# cannot separate a boss hoard from a rat's pocket today.
#
# `value_percentile` does the separating instead: items matching the type and
# rarity filter are ranked by value_copper and each tier takes a slice. That
# works with the catalogue as it stands and keeps working -- getting strictly
# better -- as rarer, pricier items are added. The bands overlap on purpose: a
# boss dropping a decent potion is fine, a rat handing out the best item in the
# game is not.
TIER_RULES: Dict[str, dict] = {
    "basic": {
        "types": ("potion", "material", "consumable"),
        "rarities": ("common", "uncommon"),
        "value_percentile": (0.0, 0.60),
    },
    "elite": {
        "types": ("potion", "consumable", "material", "tool", "scroll", "gem"),
        "rarities": ("common", "uncommon", "rare"),
        "value_percentile": (0.25, 0.90),
    },
    "named": {
        "types": ("potion", "consumable", "tool", "scroll", "gem"),
        "rarities": ("common", "uncommon", "rare", "epic"),
        "value_percentile": (0.50, 1.0),
    },
    "boss": {
        "types": ("potion", "tool", "scroll", "gem"),
        "rarities": ("common", "uncommon", "rare", "epic", "legendary", "mythic"),
        "value_percentile": (0.60, 1.0),
    },
}

# Items more than this many levels above the monster are excluded, so a level-2
# rat cannot hand out level-18 consumables. Items with level 0 are utility items
# and always eligible.
LEVEL_HEADROOM = 3

_CACHE: Dict[Tuple[str, int], Tuple[float, Dict[str, float]]] = {}
_CACHE_TTL_SECONDS = 30.0


def tier_for(name: str) -> Optional[str]:
    """The tier a loot-table name refers to, or None if it is not a table name.

    Anything that is not recognised is left alone so existing behaviour (a CSV
    of slugs, a JSON list, a single slug) keeps working untouched.
    """
    if not name:
        return None
    key = name.strip().lower()
    if not key or "," in key:
        return None
    if key.startswith("boss_"):
        return "boss"
    for suffix in ("_basic", "_elite", "_named"):
        if key.endswith(suffix):
            return suffix[1:]
    return None


def resolve(name: str, level: int = 1) -> Optional[Dict[str, float]]:
    """Resolve a named table to ``{item_slug: weight}``.

    Returns None when `name` is not a known table name, so callers can fall
    back to their previous parsing. Returns an empty dict when the name *is* a
    table but the catalogue currently has nothing matching -- that is a content
    gap, not a parse failure, and the caller should not retry it as a slug.
    """
    tier = tier_for(name)
    if tier is None:
        return None

    level = max(1, int(level or 1))
    band = min(level, 60)  # cache key; the ceiling keeps the cache bounded
    cached = _CACHE.get((tier, band))
    now = time.time()
    if cached and (now - cached[0]) <= _CACHE_TTL_SECONDS:
        return dict(cached[1])

    rules = TIER_RULES[tier]
    try:
        rows = Item.query.filter(
            Item.type.in_(rules["types"]),
            Item.rarity.in_(rules["rarities"]),
        ).all()
    except Exception:
        return {}

    eligible = [item for item in rows if int(item.level or 0) <= level + LEVEL_HEADROOM]
    # Rank by value and take this tier's slice, so tiers differ even while the
    # catalogue is almost entirely one rarity.
    eligible.sort(key=lambda i: (int(i.value_copper or 0), i.slug))
    lo_pct, hi_pct = rules.get("value_percentile", (0.0, 1.0))
    if eligible:
        lo = int(len(eligible) * lo_pct)
        hi = max(lo + 1, int(round(len(eligible) * hi_pct)))
        eligible = eligible[lo:hi]

    pool: Dict[str, float] = {}
    for item in eligible:
        weight = RARITY_WEIGHTS.get((item.rarity or "common").lower(), 0.1)
        pool[item.slug] = weight

    _CACHE[(tier, band)] = (now, dict(pool))
    if len(_CACHE) > 256:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
    return pool


def clear_cache() -> None:  # pragma: no cover - test/admin helper
    _CACHE.clear()
