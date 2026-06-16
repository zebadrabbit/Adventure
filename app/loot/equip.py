"""Aggregate equipped item-instance affixes into a stat-bonus dict."""

from __future__ import annotations


def gear_bonuses(gear: dict | None) -> dict:
    """Sum affix values across all equipped instances -> {stat: total}."""
    totals: dict[str, float] = {}
    if not isinstance(gear, dict):
        return totals
    for inst in gear.values():
        if not isinstance(inst, dict):
            continue
        affixes = inst.get("affixes")
        if not isinstance(affixes, list):
            continue
        for a in affixes:
            if not isinstance(a, dict):
                continue
            stat = a.get("stat")
            val = a.get("val")
            if not stat or not isinstance(val, (int, float)):
                continue
            totals[stat] = totals.get(stat, 0) + val
    # normalize ints
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}
