"""Single-stat prefixes. `slots`/`categories` gate eligibility; `weight` biases
selection; values scale with item level in the generator."""

# Each: name, stat, (min,max) base value, scaling_per_level, weight,
# slots (which equipment slots), categories (None = any category in those slots).
PREFIXES = [
    # weapon damage tiers (share stat 'damage'; tier implied by value/weight)
    {
        "name": "Sharp",
        "stat": "damage",
        "min": 1,
        "max": 3,
        "scale": 0.3,
        "weight": 120,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Keen",
        "stat": "damage",
        "min": 2,
        "max": 5,
        "scale": 0.4,
        "weight": 90,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Brutal",
        "stat": "damage",
        "min": 4,
        "max": 8,
        "scale": 0.6,
        "weight": 60,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Savage",
        "stat": "damage",
        "min": 6,
        "max": 12,
        "scale": 0.8,
        "weight": 35,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Cruel",
        "stat": "damage",
        "min": 9,
        "max": 16,
        "scale": 1.0,
        "weight": 18,
        "slots": ["weapon"],
        "categories": None,
    },
    # armor
    {
        "name": "Sturdy",
        "stat": "armor",
        "min": 2,
        "max": 5,
        "scale": 0.3,
        "weight": 110,
        "slots": ["offhand", "head", "chest", "hands", "feet"],
        "categories": None,
    },
    {
        "name": "Reinforced",
        "stat": "armor",
        "min": 4,
        "max": 9,
        "scale": 0.5,
        "weight": 60,
        "slots": ["offhand", "head", "chest", "hands", "feet"],
        "categories": None,
    },
    # speed / crit / utility
    {
        "name": "Quick",
        "stat": "speed",
        "min": 1,
        "max": 3,
        "scale": 0.1,
        "weight": 70,
        "slots": ["weapon", "feet"],
        "categories": None,
    },
    {
        "name": "Deadly",
        "stat": "crit",
        "min": 1,
        "max": 4,
        "scale": 0.2,
        "weight": 55,
        "slots": ["weapon", "ring", "amulet"],
        "categories": None,
    },
    {
        "name": "Warding",
        "stat": "resist",
        "min": 2,
        "max": 6,
        "scale": 0.3,
        "weight": 60,
        "slots": ["offhand", "head", "chest", "hands", "feet", "ring", "amulet"],
        "categories": None,
    },
    {
        "name": "Vampiric",
        "stat": "lifesteal",
        "min": 1,
        "max": 3,
        "scale": 0.1,
        "weight": 25,
        "slots": ["weapon"],
        "categories": None,
    },
    # elemental damage (use 'damage' stat; flavor via name)
    {
        "name": "Flaming",
        "stat": "damage",
        "min": 2,
        "max": 6,
        "scale": 0.4,
        "weight": 40,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Frozen",
        "stat": "damage",
        "min": 2,
        "max": 6,
        "scale": 0.4,
        "weight": 40,
        "slots": ["weapon"],
        "categories": None,
    },
    {
        "name": "Shocking",
        "stat": "damage",
        "min": 2,
        "max": 6,
        "scale": 0.4,
        "weight": 40,
        "slots": ["weapon"],
        "categories": None,
    },
]


def prefixes_for(slot: str, category: str) -> list[dict]:
    out = []
    for p in PREFIXES:
        if slot not in p["slots"]:
            continue
        if p["categories"] is not None and category not in p["categories"]:
            continue
        out.append(p)
    return out
