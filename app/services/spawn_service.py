"""Monster spawn selection & scaling service.

Provides utilities to select an appropriate monster from `monster_catalog` for a
given dungeon level and party size. Rarity weighting controls relative frequency.

This is intentionally stateless; future caching or region-specific weighting can
layer on top of these primitives.
"""

from __future__ import annotations

import random
from typing import List, Optional
from app.models import MonsterCatalog

RARITY_WEIGHTS = {
    "common": 1.0,
    "uncommon": 0.55,
    "rare": 0.30,
    "elite": 0.15,
    "boss": 0.02,
}


def _eligible_monsters(level: int, include_boss: bool = False) -> List[MonsterCatalog]:
    q = MonsterCatalog.query
    rows = q.filter(MonsterCatalog.level_min <= level, MonsterCatalog.level_max >= level).all()
    if not include_boss:
        rows = [r for r in rows if not r.boss]
    return rows


def choose_monster(level: int, party_size: int = 1, include_boss: bool = False, rng: Optional[random.Random] = None):
    """Return a scaled monster instance dict for target level.

    Selection steps:
      1. Filter by level band.
      2. Apply rarity weighting.
      3. Randomly choose.
      4. Scale stats for party size.
    Raises ValueError if no eligible monsters.
    """
    rng = rng or random
    pool = _eligible_monsters(level, include_boss=include_boss)
    if not pool:
        raise ValueError(f"No monsters available for level {level}")
    weights = []
    for m in pool:
        w = RARITY_WEIGHTS.get(m.rarity, 0.1)
        # Slight bonus weight if monster's level band tightly matches the requested level midpoint
        midpoint = (m.level_min + m.level_max) / 2.0
        dist = abs(midpoint - level)
        if dist <= 0.5:
            w *= 1.15
        weights.append(max(w, 0.0001))
    total = sum(weights)
    pivot = rng.random() * total
    acc = 0.0
    chosen = pool[-1]
    for m, w in zip(pool, weights):
        acc += w
        if pivot <= acc:
            chosen = m
            break
    # Scale instance (clamp to chosen band)
    return chosen.scaled_instance(level=level, party_size=party_size)


def sample_distribution(level: int, samples: int = 200) -> dict:
    """Return frequency count of chosen monster slugs for diagnostics/testing."""
    freq = {}
    for _ in range(samples):
        inst = choose_monster(level)
        slug = inst["slug"]
        freq[slug] = freq.get(slug, 0) + 1
    return freq
