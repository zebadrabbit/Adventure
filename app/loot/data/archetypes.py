"""Base item archetypes. Variety comes from rarity + affix rolls, not pre-tiers.

Each archetype: slot, category, optional `damage` (min,max) for weapons,
optional `armor` base for armor, `attack_speed` for weapons, and `affinity`
(attribute tags that bias which themed affixes fit).
"""

SLOTS = ["weapon", "offhand", "head", "chest", "hands", "feet", "ring", "amulet"]

ARCHETYPES = {
    # --- Weapons ---
    "dagger": {
        "slot": "weapon",
        "base_name": "Dagger",
        "category": "blade",
        "damage": (2, 5),
        "attack_speed": 1.4,
        "affinity": ["dex"],
    },
    "shortsword": {
        "slot": "weapon",
        "base_name": "Shortsword",
        "category": "blade",
        "damage": (4, 7),
        "attack_speed": 1.0,
        "affinity": ["str", "dex"],
    },
    "longsword": {
        "slot": "weapon",
        "base_name": "Longsword",
        "category": "blade",
        "damage": (6, 11),
        "attack_speed": 0.9,
        "affinity": ["str"],
    },
    "greatsword": {
        "slot": "weapon",
        "base_name": "Greatsword",
        "category": "blade",
        "damage": (9, 16),
        "attack_speed": 0.7,
        "affinity": ["str"],
    },
    "mace": {
        "slot": "weapon",
        "base_name": "Mace",
        "category": "blunt",
        "damage": (5, 9),
        "attack_speed": 0.9,
        "affinity": ["str"],
    },
    "warhammer": {
        "slot": "weapon",
        "base_name": "Warhammer",
        "category": "blunt",
        "damage": (9, 15),
        "attack_speed": 0.7,
        "affinity": ["str"],
    },
    "greataxe": {
        "slot": "weapon",
        "base_name": "Greataxe",
        "category": "axe",
        "damage": (10, 17),
        "attack_speed": 0.7,
        "affinity": ["str"],
    },
    "spear": {
        "slot": "weapon",
        "base_name": "Spear",
        "category": "polearm",
        "damage": (6, 10),
        "attack_speed": 0.9,
        "affinity": ["str", "dex"],
    },
    "bow": {
        "slot": "weapon",
        "base_name": "Bow",
        "category": "ranged",
        "damage": (5, 9),
        "attack_speed": 1.0,
        "affinity": ["dex"],
    },
    "crossbow": {
        "slot": "weapon",
        "base_name": "Crossbow",
        "category": "ranged",
        "damage": (7, 12),
        "attack_speed": 0.8,
        "affinity": ["dex"],
    },
    "staff": {
        "slot": "weapon",
        "base_name": "Staff",
        "category": "caster",
        "damage": (4, 8),
        "attack_speed": 0.9,
        "affinity": ["int", "wis"],
    },
    "wand": {
        "slot": "weapon",
        "base_name": "Wand",
        "category": "caster",
        "damage": (3, 6),
        "attack_speed": 1.2,
        "affinity": ["int"],
    },
    # --- Offhand ---
    "shield": {
        "slot": "offhand",
        "base_name": "Shield",
        "category": "shield",
        "armor": (4, 9),
        "affinity": ["str", "con"],
    },
    "tome": {"slot": "offhand", "base_name": "Tome", "category": "caster", "armor": (0, 1), "affinity": ["int", "wis"]},
    "orb": {"slot": "offhand", "base_name": "Orb", "category": "caster", "armor": (0, 1), "affinity": ["int"]},
    # --- Armor (material -> base armor) ---
    "cloth_hood": {
        "slot": "head",
        "base_name": "Cloth Hood",
        "category": "cloth",
        "armor": (1, 2),
        "affinity": ["int", "wis"],
    },
    "leather_cap": {
        "slot": "head",
        "base_name": "Leather Cap",
        "category": "leather",
        "armor": (2, 4),
        "affinity": ["dex"],
    },
    "mail_coif": {
        "slot": "head",
        "base_name": "Mail Coif",
        "category": "mail",
        "armor": (3, 6),
        "affinity": ["str", "dex"],
    },
    "plate_helm": {
        "slot": "head",
        "base_name": "Plate Helm",
        "category": "plate",
        "armor": (5, 9),
        "affinity": ["str", "con"],
    },
    "cloth_robe": {
        "slot": "chest",
        "base_name": "Cloth Robe",
        "category": "cloth",
        "armor": (2, 4),
        "affinity": ["int", "wis"],
    },
    "leather_tunic": {
        "slot": "chest",
        "base_name": "Leather Tunic",
        "category": "leather",
        "armor": (4, 7),
        "affinity": ["dex"],
    },
    "mail_hauberk": {
        "slot": "chest",
        "base_name": "Mail Hauberk",
        "category": "mail",
        "armor": (6, 11),
        "affinity": ["str", "dex"],
    },
    "plate_cuirass": {
        "slot": "chest",
        "base_name": "Plate Cuirass",
        "category": "plate",
        "armor": (9, 16),
        "affinity": ["str", "con"],
    },
    "cloth_gloves": {
        "slot": "hands",
        "base_name": "Cloth Gloves",
        "category": "cloth",
        "armor": (1, 2),
        "affinity": ["int"],
    },
    "leather_gloves": {
        "slot": "hands",
        "base_name": "Leather Gloves",
        "category": "leather",
        "armor": (2, 4),
        "affinity": ["dex"],
    },
    "mail_gauntlets": {
        "slot": "hands",
        "base_name": "Mail Gauntlets",
        "category": "mail",
        "armor": (3, 6),
        "affinity": ["str"],
    },
    "plate_gauntlets": {
        "slot": "hands",
        "base_name": "Plate Gauntlets",
        "category": "plate",
        "armor": (4, 8),
        "affinity": ["str"],
    },
    "cloth_slippers": {
        "slot": "feet",
        "base_name": "Cloth Slippers",
        "category": "cloth",
        "armor": (1, 2),
        "affinity": ["int"],
    },
    "leather_boots": {
        "slot": "feet",
        "base_name": "Leather Boots",
        "category": "leather",
        "armor": (2, 4),
        "affinity": ["dex"],
    },
    "mail_boots": {"slot": "feet", "base_name": "Mail Boots", "category": "mail", "armor": (3, 6), "affinity": ["str"]},
    "plate_boots": {
        "slot": "feet",
        "base_name": "Plate Boots",
        "category": "plate",
        "armor": (4, 8),
        "affinity": ["str", "con"],
    },
    # --- Jewelry (pure affix carriers) ---
    "ring": {
        "slot": "ring",
        "base_name": "Ring",
        "category": "jewelry",
        "affinity": ["str", "dex", "int", "wis", "con", "cha"],
    },
    "amulet": {
        "slot": "amulet",
        "base_name": "Amulet",
        "category": "jewelry",
        "affinity": ["str", "dex", "int", "wis", "con", "cha"],
    },
}


def archetypes_for_slot(slot: str) -> list[str]:
    return [k for k, a in ARCHETYPES.items() if a["slot"] == slot]
