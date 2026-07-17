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

# Boss loot multipliers
_BOSS_DROP_MULTIPLIER = 3  # Bosses drop 3x more items
_BOSS_SPECIAL_CHANCE = 0.75  # 75% chance for special drops from bosses


def _is_boss(monster: Dict[str, Any]) -> bool:
    """Check if monster is a boss."""
    return monster.get("archetype") == "Boss" or monster.get("is_boss", False)


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

    # Boss loot enhancement
    is_boss = _is_boss(monster)
    max_drops = _MAX_BASE_DROPS * _BOSS_DROP_MULTIPLIER if is_boss else _MAX_BASE_DROPS
    special_chance_override = _BOSS_SPECIAL_CHANCE if is_boss else _DEFAULT_SPECIAL_CHANCE

    # Collect raw drops in a list first then collapse to mapping slug->qty for stable representation.
    drops: List[str] = []
    rolls_meta: Dict[str, Any] = {
        "base_pool": items_ordered,
        "weights": weights,
        "special": None,
        "is_boss": is_boss,
    }

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
        chance = 1.0 if guaranteed else special_chance_override
        rolled = rng.random() < chance
        if rolled:
            drops.append(special_slug)
        rolls_meta["special"] = {"slug": special_slug, "rolled": rolled, "chance": chance}

    # Base table sampling (simple: up to max_drops unique entries, weighted w/out replacement)
    pool = [slug for slug in items_ordered if slug not in drops]
    if pool and weights:
        total_w = sum(weights.get(slug, 0.0) for slug in pool)
        # Up to max draws
        draws = min(max_drops, len(pool))
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

    # Boss always drops a key (33% rusty, 50% master, 17% boss key)
    if is_boss:
        key_roll = rng.random()
        if key_roll < 0.33:
            drops.append("rusty-key")
        elif key_roll < 0.83:
            drops.append("master-key")
        else:
            drops.append("boss-key")

    # Collapse to quantity mapping; maintain legacy compatibility by also returning list under items_list.
    qty_map: Dict[str, int] = {}
    for slug in drops:
        qty_map[slug] = qty_map.get(slug, 0) + 1

    # Procedural gear drops (instances with affixes).
    from app.loot.generator import generate_item

    level = int(monster.get("level", 1) or 1)
    n_gear = 1
    rarity_hint = None
    # Use a proper random.Random for generate_item (which needs .choice); fall back to
    # a fresh instance if the caller passed a limited mock rng.
    gear_rng = rng if isinstance(rng, random.Random) else random.Random()
    if is_boss:
        n_gear = 2
        rarity_hint = gear_rng.choice(["rare", "epic", "legendary"])
    gear_drops = [generate_item(level=level, rarity=rarity_hint, rng=gear_rng) for _ in range(n_gear)]

    return {"items": qty_map, "items_list": drops, "gear": gear_drops, "rolls": rolls_meta}


def _item_display_name(slug: str) -> str:
    """Look up an item's catalog display name; fall back to a title-cased slug."""
    from app.models.models import Item

    item = Item.query.filter_by(slug=slug).first()
    if item and item.name:
        return item.name
    return slug.replace("-", " ").replace("_", " ").title()


def _loot_summary(rewards: Dict[str, Any] | None) -> str:
    """Render a human-readable combat-log summary of a loot roll.

    ``rewards`` is the dict returned by :func:`roll_loot` (or ``{}``): quantity
    items under "items" as "N× Display Name", gear instances under "gear" as
    "Name (rarity)". Returns "no loot" when both are empty.
    """
    rewards = rewards or {}
    parts: List[str] = []

    items = rewards.get("items") or {}
    for slug, qty in items.items():
        parts.append(f"{qty}× {_item_display_name(slug)}")

    for inst in rewards.get("gear") or []:
        if not isinstance(inst, dict):
            continue
        name = inst.get("name") or _item_display_name(inst.get("base", "item"))
        rarity = inst.get("rarity") or "common"
        parts.append(f"{name} ({rarity})")

    return ", ".join(parts) if parts else "no loot"


def gear_bonuses(gear: dict | None) -> dict:
    """Sum affix values across all equipped instances -> {stat: total}.

    A "broken" instance (durability == 0) contributes a reduced share of its
    affixes (``broken_bonus_multiplier`` from durability config) — reduced, not
    removed. Instances without durability tracking count at full value.
    """
    totals: dict[str, float] = {}
    if not isinstance(gear, dict):
        return totals

    try:
        from app.services.durability import durability_config

        broken_mult = float(durability_config().get("broken_bonus_multiplier", 0.5))
    except Exception:
        broken_mult = 0.5

    for inst in gear.values():
        if not isinstance(inst, dict):
            continue
        affixes = inst.get("affixes")
        if not isinstance(affixes, list):
            continue
        mult = broken_mult if inst.get("durability") == 0 else 1.0
        for a in affixes:
            if not isinstance(a, dict):
                continue
            stat = a.get("stat")
            val = a.get("val")
            if not stat or not isinstance(val, (int, float)):
                continue
            totals[stat] = totals.get(stat, 0) + val * mult
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}


def add_gear_to_character(character, instances: list[dict]) -> None:
    """Append gear instances to character.items (JSON list), preserving existing."""
    import json

    try:
        items = json.loads(character.items) if character.items else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    for inst in instances or []:
        if isinstance(inst, dict) and inst.get("uid"):
            items.append(inst)
    character.items = json.dumps(items)


__all__ = ["roll_loot"]
