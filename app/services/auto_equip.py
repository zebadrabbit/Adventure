"""Automatic starter gear selection helper.

Centralizes class-based starter gear preference logic so creation and autofill
paths stay consistent. Future enhancements (rarity tiers, level scaling, DB
config) can extend here without touching route code.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

AUTO_EQUIP_PREFS: Dict[str, Dict[str, List[str]]] = {
    "fighter": {"weapon": ["short-sword", "long-sword", "club"], "armor": ["leather-armor", "chain-shirt"]},
    "rogue": {"weapon": ["dagger", "short-sword"], "armor": ["leather-armor"]},
    "mage": {"weapon": ["oak-staff", "wand"], "armor": []},
    # Put 'oak-staff' first because current cleric STARTER_ITEMS gives them one.
    "cleric": {"weapon": ["oak-staff", "mace", "club"], "armor": ["leather-armor"]},
    "ranger": {"weapon": ["hunting-bow", "short-sword"], "armor": ["leather-armor"]},
    "druid": {"weapon": ["oak-staff", "club"], "armor": ["leather-armor"]},
}


def auto_equip_for(char_class: str, starter_items: Iterable) -> Dict[str, str]:
    """Return a gear mapping {slot: slug} selecting first preferred items present.

    Parameters
    ----------
    char_class: canonical lower-case class key.
    starter_items: iterable of either slug strings or dicts containing at least a
        'slug' (legacy tolerated: may also provide 'name').

    Returns
    -------
    dict: mapping like {"weapon": "short-sword", "armor": "leather-armor"}
          (armor omitted if no preferred armor present).
    """
    prefs = AUTO_EQUIP_PREFS.get(char_class, {})
    weapon_pref = prefs.get("weapon", [])
    armor_pref = prefs.get("armor", [])

    # Normalize starter items to a set for O(1) membership tests
    slugs = []
    for ent in starter_items:
        if isinstance(ent, str):
            slugs.append(ent)
        elif isinstance(ent, dict):
            slug = ent.get("slug") or ent.get("name") or ent.get("id")
            if slug:
                slugs.append(slug)
    present = set(slugs)

    def pick(candidates: List[str]):
        for c in candidates:
            if c in present:
                return c
        return None

    gear: Dict[str, str] = {}
    w = pick(weapon_pref)
    if w:
        gear["weapon"] = w
    a = pick(armor_pref)
    if a:
        gear["armor"] = a
    return gear


__all__ = ["AUTO_EQUIP_PREFS", "auto_equip_for"]
