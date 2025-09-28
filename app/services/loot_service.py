"""Loot rolling service for monster encounters.

Interprets a monster instance (as produced by spawn_service.choose_monster) and
produces a list of drop item slugs. This is intentionally lightweight and
pseudo-random; future enhancements may incorporate: player luck stats, zone
modifiers, rarity boosts, guaranteed currency rolls, etc.

Conventions:
  * monster["loot_table"] may be a simple CSV string of item slugs with implied equal weight
    OR a JSON object mapping slug->weight, OR a JSON array of slugs.
  * monster["special_drop_slug"] when present is an item slug that has a high chance
    to appear (default 25%) or can be annotated in the loot_table with the token
    "!guaranteed" for 100% drop. (Minimal DSL for flexibility without full editor.)

Returned structure:
  {
    "items": [slug,...],
    "rolls": {  # diagnostics for UI/logging
       "base_pool": [...],
       "weights": {slug: weight,...},
       "special": {"slug": "foo", "rolled": true/false, "chance": 0.25}
    }
  }
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Tuple

_DEFAULT_SPECIAL_CHANCE = 0.25
_MAX_BASE_DROPS = 3  # cap simple rolls to avoid floods


def _parse_loot_table(raw: str | None) -> Tuple[List[str], Dict[str, float]]:
    """Return ordered list and weight mapping.

    Accepted forms:
      - CSV: "potion-healing, dagger, gold-coin" => equal weights
      - JSON list: ["a","b","c"] => equal weights
      - JSON object: {"a":2, "b":1} => explicit weights
    """
    if not raw:
        return [], {}
    raw = raw.strip()
    # JSON object or array
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                items = [str(x) for x in data if str(x).strip()]
                w = {slug: 1.0 for slug in items}
                return items, w
            if isinstance(data, dict):
                items = [str(k) for k in data.keys() if str(k).strip()]
                w = {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
                return items, w
        except Exception:
            return [], {}
    # Fallback CSV
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return [], {}
    return parts, {p: 1.0 for p in parts}


def roll_loot(monster: Dict[str, Any], rng: random.Random | None = None) -> Dict[str, Any]:
    rng = rng or random
    raw_table = monster.get("loot_table")
    items_ordered, weights = _parse_loot_table(raw_table)
    drops: List[str] = []
    rolls_meta: Dict[str, Any] = {"base_pool": items_ordered, "weights": weights, "special": None}

    # Special drop logic
    special_slug = monster.get("special_drop_slug")
    if special_slug:
        # Could embed directive like "slug!guaranteed" in table for 100% chance
        guaranteed = False
        # If present in loot table with token, treat as guaranteed
        for k in list(weights.keys()):
            if k.startswith(f"{special_slug}!"):
                guaranteed = True
                # normalize key without directive
                weights[special_slug] = weights.pop(k)
                items_ordered = [special_slug if x == k else x for x in items_ordered]
        chance = 1.0 if guaranteed else _DEFAULT_SPECIAL_CHANCE
        rolled = rng.random() < chance
        if rolled:
            drops.append(special_slug)
        rolls_meta["special"] = {"slug": special_slug, "rolled": rolled, "chance": chance}

    # Base table sampling (simple: up to MAX_BASE_DROPS unique entries, weighted w/out replacement)
    pool = [slug for slug in items_ordered if slug not in drops]
    if pool and weights:
        total_w = sum(weights.get(slug, 0.0) for slug in pool)
        # Up to max draws
        draws = min(_MAX_BASE_DROPS, len(pool))
        for _ in range(draws):
            if total_w <= 0:
                break
            pivot = rng.random() * total_w
            acc = 0.0
            chosen = pool[-1]
            for slug in pool:
                w = max(0.0, weights.get(slug, 0.0))
                acc += w
                if pivot <= acc:
                    chosen = slug
                    break
            if chosen not in drops:
                drops.append(chosen)
            # remove chosen & recompute total
            pool = [p for p in pool if p != chosen]
            total_w = sum(weights.get(slug, 0.0) for slug in pool)

    return {"items": drops, "rolls": rolls_meta}


__all__ = ["roll_loot"]
