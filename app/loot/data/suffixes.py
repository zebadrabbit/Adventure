"""Themed stat-package suffixes ("of the X"). Each maps to a dict of
{stat: relative_weight}; the generator splits the rolled budget across them.
`affinity` lists attribute tags an archetype must share for eligibility
(empty/global means always eligible)."""

SUFFIXES = [
    {"name": "of the Hawk", "stats": {"dex": 2, "con": 1}, "affinity": ["dex"], "weight": 100},
    {"name": "of the Bear", "stats": {"str": 2, "con": 1}, "affinity": ["str"], "weight": 100},
    {"name": "of the Eagle", "stats": {"int": 2, "con": 1}, "affinity": ["int"], "weight": 100},
    {"name": "of the Owl", "stats": {"int": 2, "wis": 1}, "affinity": ["int", "wis"], "weight": 90},
    {"name": "of the Tiger", "stats": {"str": 1, "dex": 1}, "affinity": ["str", "dex"], "weight": 90},
    {"name": "of the Whale", "stats": {"con": 3}, "affinity": [], "weight": 80},
    {"name": "of the Wolf", "stats": {"dex": 2, "wis": 1}, "affinity": ["dex"], "weight": 80},
    {"name": "of the Gorilla", "stats": {"str": 2, "int": 1}, "affinity": ["str", "int"], "weight": 60},
    {"name": "of the Monkey", "stats": {"str": 1, "dex": 2}, "affinity": ["dex"], "weight": 70},
    {"name": "of the Falcon", "stats": {"dex": 2, "str": 1}, "affinity": ["dex", "str"], "weight": 70},
    {"name": "of the Boar", "stats": {"str": 2, "wis": 1}, "affinity": ["str"], "weight": 60},
    {"name": "of the Sorcerer", "stats": {"int": 2, "crit": 1}, "affinity": ["int"], "weight": 55},
    {"name": "of the Mind", "stats": {"int": 2, "mana": 2}, "affinity": ["int", "wis"], "weight": 55},
    {"name": "of the Bandit", "stats": {"dex": 2, "cha": 1}, "affinity": ["dex"], "weight": 50},
    {"name": "of the Champion", "stats": {"str": 1, "con": 1, "dex": 1}, "affinity": ["str", "dex"], "weight": 30},
    {"name": "of the Elder", "stats": {"wis": 2, "con": 1}, "affinity": ["wis"], "weight": 60},
    {"name": "of Vitality", "stats": {"max_hp": 3}, "affinity": [], "weight": 90},
    {"name": "of Warding", "stats": {"resist": 3}, "affinity": [], "weight": 70},
]


def suffixes_for(affinity: list[str]) -> list[dict]:
    aff = set(affinity)
    out = []
    for s in SUFFIXES:
        if not s["affinity"] or aff.intersection(s["affinity"]):
            out.append(s)
    return out
