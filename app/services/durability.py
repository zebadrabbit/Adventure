"""Gentle, config-driven gear durability + repair.

Only procedural gear *instances* (dicts with a "uid") carry durability. Combat
wear reduces it; reaching 0 makes the item "broken" — its affix bonuses are
*reduced* (not removed, never destroyed). Repair restores it for hoard copper.

Tuning lives in GameConfig key "durability" (all optional, safe fallback):
    {
      "enabled": true,
      "max_durability": 100,
      "loss_per_fight": 2,
      "repair_cost_per_point": 1,
      "broken_bonus_multiplier": 0.5
    }
Keep losses small — durability is a gentle gold sink, not a punishment.
"""

from __future__ import annotations

import json

from app.models.models import GameConfig

_DEFAULT_DURABILITY = {
    "enabled": True,
    "max_durability": 100,
    "loss_per_fight": 2,
    "repair_cost_per_point": 1,
    "broken_bonus_multiplier": 0.5,
}


def durability_config() -> dict:
    """Read durability tuning from GameConfig['durability'] with fallback."""
    raw = GameConfig.get("durability")
    if not raw:
        return dict(_DEFAULT_DURABILITY)
    try:
        cfg = json.loads(raw)
    except Exception:
        return dict(_DEFAULT_DURABILITY)
    merged = dict(_DEFAULT_DURABILITY)
    merged.update(cfg or {})
    return merged


def default_max_durability() -> int:
    return int(durability_config().get("max_durability", 100))


def degrade_gear(character, amount: int | None = None) -> bool:
    """Reduce each equipped instance's durability by ``loss_per_fight`` (or amount).

    No-op when durability is disabled. Floors at 0. Mutates Character.gear JSON
    in place. Returns True if anything changed (caller commits).
    """
    cfg = durability_config()
    if not cfg.get("enabled", True):
        return False
    loss = int(amount if amount is not None else cfg.get("loss_per_fight", 0))
    if loss <= 0:
        return False
    try:
        gear = json.loads(character.gear) if character.gear else {}
    except Exception:
        return False
    if not isinstance(gear, dict):
        return False
    changed = False
    for inst in gear.values():
        if isinstance(inst, dict) and "durability" in inst:
            new_val = max(0, int(inst.get("durability", 0)) - loss)
            if new_val != inst.get("durability"):
                inst["durability"] = new_val
                changed = True
    if changed:
        character.gear = json.dumps(gear)
    return changed


def repair_cost(instance: dict) -> int:
    """Copper cost to fully repair one instance."""
    cfg = durability_config()
    maxd = int(instance.get("max_durability", cfg.get("max_durability", 100)))
    cur = int(instance.get("durability", maxd))
    return max(0, maxd - cur) * int(cfg.get("repair_cost_per_point", 1))


def apply_repair(instance: dict) -> None:
    """Restore an instance to full durability (in place)."""
    maxd = int(instance.get("max_durability", default_max_durability()))
    instance["durability"] = maxd
