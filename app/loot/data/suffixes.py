"""Themed stat-package suffixes ("of the X"). Each maps to a dict of
{stat: relative_weight}; the generator splits the rolled budget across them.
`affinity` lists attribute tags an archetype must share for eligibility
(empty/global means always eligible)."""

SUFFIXES = [
    # --- Original 18 entries ---
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
    # --- Expansion: animal themes ---
    {"name": "of the Lion", "stats": {"str": 2, "cha": 1}, "affinity": ["str", "cha"], "weight": 85},
    {"name": "of the Fox", "stats": {"dex": 2, "int": 1}, "affinity": ["dex", "int"], "weight": 80},
    {"name": "of the Serpent", "stats": {"dex": 2, "crit": 1}, "affinity": ["dex"], "weight": 75},
    {"name": "of the Ox", "stats": {"str": 2, "con": 2}, "affinity": ["str", "con"], "weight": 75},
    {"name": "of the Raven", "stats": {"int": 2, "dex": 1}, "affinity": ["int", "dex"], "weight": 70},
    {"name": "of the Stag", "stats": {"con": 2, "wis": 1}, "affinity": ["con", "wis"], "weight": 70},
    {"name": "of the Phoenix", "stats": {"int": 2, "max_hp": 2}, "affinity": ["int"], "weight": 55},
    {"name": "of the Mammoth", "stats": {"con": 3, "str": 1}, "affinity": ["con", "str"], "weight": 65},
    {"name": "of the Lynx", "stats": {"dex": 2, "wis": 1}, "affinity": ["dex"], "weight": 65},
    {"name": "of the Cobra", "stats": {"dex": 1, "crit": 2}, "affinity": ["dex"], "weight": 60},
    {"name": "of the Wisp", "stats": {"wis": 2, "mana": 2}, "affinity": ["wis", "int"], "weight": 60},
    {"name": "of the Panther", "stats": {"dex": 3}, "affinity": ["dex"], "weight": 70},
    {"name": "of the Crow", "stats": {"int": 1, "wis": 1, "cha": 1}, "affinity": ["int", "wis"], "weight": 45},
    {"name": "of the Ram", "stats": {"str": 3}, "affinity": ["str"], "weight": 70},
    {"name": "of the Hound", "stats": {"str": 1, "con": 2}, "affinity": ["str", "con"], "weight": 65},
    # --- Expansion: role/class themes ---
    {"name": "of the Berserker", "stats": {"str": 2, "crit": 2}, "affinity": ["str"], "weight": 60},
    {"name": "of the Duelist", "stats": {"dex": 2, "crit": 1}, "affinity": ["dex"], "weight": 60},
    {"name": "of the Scholar", "stats": {"int": 2, "wis": 2}, "affinity": ["int", "wis"], "weight": 55},
    {"name": "of the Templar", "stats": {"str": 2, "wis": 1}, "affinity": ["str", "wis"], "weight": 55},
    {"name": "of the Warden", "stats": {"con": 2, "resist": 1}, "affinity": ["con"], "weight": 60},
    {"name": "of the Magus", "stats": {"int": 2, "mana": 2}, "affinity": ["int"], "weight": 60},
    {"name": "of the Ranger", "stats": {"dex": 2, "wis": 1}, "affinity": ["dex", "wis"], "weight": 65},
    {"name": "of the Paladin", "stats": {"str": 1, "wis": 1, "cha": 1}, "affinity": ["str", "wis"], "weight": 45},
    {"name": "of the Rogue", "stats": {"dex": 2, "cha": 1}, "affinity": ["dex"], "weight": 60},
    {"name": "of the Warlock", "stats": {"int": 1, "cha": 2}, "affinity": ["int", "cha"], "weight": 50},
    {"name": "of the Shaman", "stats": {"wis": 2, "con": 1}, "affinity": ["wis"], "weight": 55},
    # --- Expansion: abstract/thematic ---
    {"name": "of Precision", "stats": {"crit": 3}, "affinity": [], "weight": 65},
    {"name": "of Sanctuary", "stats": {"resist": 2, "max_hp": 2}, "affinity": [], "weight": 60},
    {"name": "of Swiftness", "stats": {"dex": 3}, "affinity": ["dex"], "weight": 70},
    {"name": "of Fortitude", "stats": {"con": 2, "max_hp": 2}, "affinity": ["con"], "weight": 65},
    {"name": "of Charisma", "stats": {"cha": 3}, "affinity": ["cha"], "weight": 55},
    {"name": "of Foresight", "stats": {"wis": 2, "int": 1}, "affinity": ["wis", "int"], "weight": 55},
    {"name": "of Power", "stats": {"str": 3}, "affinity": ["str"], "weight": 70},
    {"name": "of Acumen", "stats": {"int": 3}, "affinity": ["int"], "weight": 70},
    {"name": "of Resilience", "stats": {"con": 2, "resist": 1}, "affinity": ["con"], "weight": 60},
    {"name": "of the Arcane", "stats": {"int": 2, "mana": 1}, "affinity": ["int"], "weight": 65},
]


def suffixes_for(affinity: list[str]) -> list[dict]:
    aff = set(affinity)
    out = []
    for s in SUFFIXES:
        if not s["affinity"] or aff.intersection(s["affinity"]):
            out.append(s)
    return out
