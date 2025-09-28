"""Combat utility helpers.

Currently provides a resistance application helper that adjusts incoming damage
values based on a monster's resistance mapping. This is a forward-looking stub;
future combat turns will import and utilize these functions.

Resistance model:
  Mapping damage_type -> multiplier (e.g., {"fire":0.5, "cold":1.25}). Multipliers
  are applied multiplicatively to the base damage for that type. Values <1 reduce
  damage (resistance), >1 increase (vulnerability).

apply_resistances signature:
  base: int | float (incoming raw damage amount)
  dmg_types: list[str] describing tags of the attack (e.g., ["fire","physical"])
  resist_map: dict[str,float] from the defender (e.g., monster.resistances parsed)
  stacking: 'max' | 'sum' | 'mult' aggregation if multiple resistances apply.

Rules:
  - If no damage types specified, returns base unchanged.
  - Unknown types ignored.
  - Aggregation:
      * 'max': pick the extreme multiplier furthest from 1.0 (largest deviation)
      * 'sum': combine (sum of (m-1) deltas) then apply: final = base * (1 + total_delta)
      * 'mult': multiply all multipliers sequentially
  - Result is clamped to a minimum of 0.
"""

from __future__ import annotations

from typing import Dict, Iterable


def apply_resistances(
    base: float | int, dmg_types: Iterable[str], resist_map: Dict[str, float], stacking: str = "max"
) -> float:
    if base <= 0:
        return 0.0
    types = [t for t in dmg_types if t]
    if not types or not resist_map:
        return float(base)
    multis = [resist_map.get(t) for t in types if isinstance(resist_map.get(t), (int, float))]
    multis = [float(m) for m in multis if m is not None and m > 0]
    if not multis:
        return float(base)
    if stacking == "mult":
        total = 1.0
        for m in multis:
            total *= m
        return max(0.0, base * total)
    if stacking == "sum":
        delta = sum(m - 1.0 for m in multis)
        return max(0.0, base * (1.0 + delta))
    # default 'max': choose the multiplier with greatest absolute deviation from 1
    chosen = max(multis, key=lambda m: abs(m - 1.0))
    return max(0.0, base * chosen)


__all__ = ["apply_resistances"]
