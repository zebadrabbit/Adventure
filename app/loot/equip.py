"""Aggregate equipped item-instance affixes into a stat-bonus dict."""

from __future__ import annotations


def gear_bonuses(gear: dict | None) -> dict:
    """Sum affix values across all equipped instances -> {stat: total}.

    A "broken" instance (durability == 0) contributes a reduced share of its
    affixes (``broken_bonus_multiplier`` from durability config) — reduced, not
    removed. Instances without durability tracking count at full value.
    """
    totals: dict[str, float] = {}
    if not isinstance(gear, dict):
        return totals

    # Read the broken multiplier once (lazy import avoids a hard dependency cycle).
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
        # Broken (durability explicitly 0) -> scaled contribution.
        mult = broken_mult if inst.get("durability") == 0 else 1.0
        for a in affixes:
            if not isinstance(a, dict):
                continue
            stat = a.get("stat")
            val = a.get("val")
            if not stat or not isinstance(val, (int, float)):
                continue
            totals[stat] = totals.get(stat, 0) + val * mult
    # normalize ints
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}
