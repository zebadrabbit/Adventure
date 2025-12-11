"""
Seed enemy scaling data (archetypes, tiers, affixes) into the database.
"""

from app import create_app, db
from app.models.dungeon_tier import DungeonAffix, DungeonTier
from app.models.enemy_archetype import EnemyArchetype


def seed_enemy_archetypes():
    """Seed 8 enemy archetypes from enemy_templates.csv"""
    archetypes = [
        {
            "archetype": "Trash",
            "rank": "normal",
            "base_hp": 25,
            "hp_per_level": 10,
            "base_damage": 4,
            "damage_per_level": 2.0,
            "armor_class_base": 10,
            "armor_class_per_level": 0.5,
            "xp_base": 15,
            "xp_per_level": 5,
            "loot_multiplier": 1.0,
            "spawn_weight": 45,
            "description": "Common fodder enemies with basic stats",
        },
        {
            "archetype": "Skirmisher",
            "rank": "normal",
            "base_hp": 35,
            "hp_per_level": 12,
            "base_damage": 6,
            "damage_per_level": 2.5,
            "armor_class_base": 11,
            "armor_class_per_level": 0.6,
            "xp_base": 20,
            "xp_per_level": 7,
            "loot_multiplier": 1.1,
            "spawn_weight": 30,
            "description": "Fast, agile enemies with moderate offense",
        },
        {
            "archetype": "Brute",
            "rank": "normal",
            "base_hp": 55,
            "hp_per_level": 16,
            "base_damage": 8,
            "damage_per_level": 3.0,
            "armor_class_base": 12,
            "armor_class_per_level": 0.7,
            "xp_base": 25,
            "xp_per_level": 9,
            "loot_multiplier": 1.2,
            "spawn_weight": 15,
            "description": "Heavily armored, high HP tanks",
        },
        {
            "archetype": "Caster",
            "rank": "normal",
            "base_hp": 30,
            "hp_per_level": 11,
            "base_damage": 10,
            "damage_per_level": 3.5,
            "armor_class_base": 10,
            "armor_class_per_level": 0.4,
            "xp_base": 28,
            "xp_per_level": 10,
            "loot_multiplier": 1.2,
            "spawn_weight": 10,
            "description": "Low HP, high damage spellcasters",
        },
        {
            "archetype": "Elite",
            "rank": "elite",
            "base_hp": 120,
            "hp_per_level": 30,
            "base_damage": 16,
            "damage_per_level": 5.0,
            "armor_class_base": 14,
            "armor_class_per_level": 1.0,
            "xp_base": 80,
            "xp_per_level": 25,
            "loot_multiplier": 2.0,
            "spawn_weight": 4,
            "description": "Powerful enemies with enhanced stats",
        },
        {
            "archetype": "Champion",
            "rank": "elite",
            "base_hp": 160,
            "hp_per_level": 36,
            "base_damage": 18,
            "damage_per_level": 6.0,
            "armor_class_base": 15,
            "armor_class_per_level": 1.1,
            "xp_base": 120,
            "xp_per_level": 35,
            "loot_multiplier": 2.5,
            "spawn_weight": 2,
            "description": "Rare, formidable foes with unique abilities",
        },
        {
            "archetype": "Miniboss",
            "rank": "boss",
            "base_hp": 260,
            "hp_per_level": 50,
            "base_damage": 22,
            "damage_per_level": 7.0,
            "armor_class_base": 16,
            "armor_class_per_level": 1.2,
            "xp_base": 200,
            "xp_per_level": 50,
            "loot_multiplier": 3.0,
            "spawn_weight": 1,
            "description": "Major threats with boss-tier mechanics",
        },
        {
            "archetype": "Boss",
            "rank": "boss",
            "base_hp": 400,
            "hp_per_level": 70,
            "base_damage": 26,
            "damage_per_level": 8.5,
            "armor_class_base": 18,
            "armor_class_per_level": 1.3,
            "xp_base": 400,
            "xp_per_level": 100,
            "loot_multiplier": 4.0,
            "spawn_weight": 0,
            "description": "Ultimate dungeon bosses with devastating power",
        },
    ]

    for data in archetypes:
        existing = db.session.query(EnemyArchetype).filter_by(archetype=data["archetype"]).first()
        if existing:
            print(f"  Archetype '{data['archetype']}' already exists, skipping.")
            continue

        archetype = EnemyArchetype(**data)
        db.session.add(archetype)
        print(f"  Added archetype: {data['archetype']}")

    db.session.commit()


def seed_dungeon_tiers():
    """Seed 7 dungeon difficulty tiers"""
    tiers = [
        {
            "tier": 1,
            "name": "Novice",
            "min_level": 1,
            "max_level": 10,
            "monster_level_modifier": 0,
            "xp_multiplier": 1.0,
            "loot_quality_bonus": 0.0,
            "description": "Starter-level dungeons with basic enemies",
        },
        {
            "tier": 2,
            "name": "Apprentice",
            "min_level": 8,
            "max_level": 18,
            "monster_level_modifier": 1,
            "xp_multiplier": 1.1,
            "loot_quality_bonus": 0.05,
            "description": "Moderate difficulty for growing adventurers",
        },
        {
            "tier": 3,
            "name": "Adept",
            "min_level": 15,
            "max_level": 25,
            "monster_level_modifier": 2,
            "xp_multiplier": 1.2,
            "loot_quality_bonus": 0.1,
            "description": "Challenging dungeons for experienced parties",
        },
        {
            "tier": 4,
            "name": "Expert",
            "min_level": 22,
            "max_level": 32,
            "monster_level_modifier": 3,
            "xp_multiplier": 1.3,
            "loot_quality_bonus": 0.15,
            "description": "High-difficulty content for veterans",
        },
        {
            "tier": 5,
            "name": "Master",
            "min_level": 28,
            "max_level": 38,
            "monster_level_modifier": 4,
            "xp_multiplier": 1.4,
            "loot_quality_bonus": 0.2,
            "description": "Elite-tier dungeons with brutal encounters",
        },
        {
            "tier": 6,
            "name": "Heroic",
            "min_level": 35,
            "max_level": 45,
            "monster_level_modifier": 5,
            "xp_multiplier": 1.5,
            "loot_quality_bonus": 0.25,
            "description": "Near-endgame content for the bravest",
        },
        {
            "tier": 7,
            "name": "Mythic",
            "min_level": 42,
            "max_level": 50,
            "monster_level_modifier": 6,
            "xp_multiplier": 1.6,
            "loot_quality_bonus": 0.3,
            "description": "Ultimate endgame challenges for max-level heroes",
        },
    ]

    for data in tiers:
        existing = db.session.query(DungeonTier).filter_by(tier=data["tier"]).first()
        if existing:
            print(f"  Tier {data['tier']} ('{data['name']}') already exists, skipping.")
            continue

        tier = DungeonTier(**data)
        db.session.add(tier)
        print(f"  Added tier: T{data['tier']} {data['name']}")

    db.session.commit()


def seed_dungeon_affixes():
    """Seed 10 dungeon modifier affixes"""
    affixes = [
        {
            "affix_id": "frenzied",
            "name": "Frenzied",
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "monster_speed_multiplier": 1.3,
            "description": "Monsters attack with frenzied speed (+30% attack rate)",
            "color": "#ff6b6b",
            "special_effect": None,
        },
        {
            "affix_id": "bolstered",
            "name": "Bolstered",
            "monster_hp_multiplier": 2.0,
            "monster_damage_multiplier": 1.0,
            "monster_speed_multiplier": 1.0,
            "description": "Monsters have doubled health pools",
            "color": "#4ecdc4",
            "special_effect": None,
        },
        {
            "affix_id": "volcanic",
            "name": "Volcanic",
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.25,
            "monster_speed_multiplier": 1.0,
            "description": "Monsters deal fire damage and inflict burning (+25% damage)",
            "color": "#ff8c42",
            "special_effect": "burning",
        },
        {
            "affix_id": "necrotic",
            "name": "Necrotic",
            "monster_hp_multiplier": 1.2,
            "monster_damage_multiplier": 1.15,
            "monster_speed_multiplier": 1.0,
            "description": "Undead enemies with life drain and cursed strikes",
            "color": "#9b59b6",
            "special_effect": "life_drain",
        },
        {
            "affix_id": "fortified",
            "name": "Fortified",
            "monster_hp_multiplier": 1.5,
            "monster_damage_multiplier": 1.0,
            "monster_speed_multiplier": 0.9,
            "description": "Heavily armored monsters with +50% HP, -10% speed",
            "color": "#95a5a6",
            "special_effect": None,
        },
        {
            "affix_id": "enraged",
            "name": "Enraged",
            "monster_hp_multiplier": 0.8,
            "monster_damage_multiplier": 1.4,
            "monster_speed_multiplier": 1.1,
            "description": "Glass cannon enemies: -20% HP, +40% damage, +10% speed",
            "color": "#e74c3c",
            "special_effect": None,
        },
        {
            "affix_id": "shadowed",
            "name": "Shadowed",
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.15,
            "monster_speed_multiplier": 1.2,
            "description": "Monsters gain evasion and stealth attacks (+15% damage, +20% speed)",
            "color": "#34495e",
            "special_effect": "stealth",
        },
        {
            "affix_id": "corrupted",
            "name": "Corrupted",
            "monster_hp_multiplier": 1.1,
            "monster_damage_multiplier": 1.2,
            "monster_speed_multiplier": 1.0,
            "description": "Players take 20% more damage, monsters gain 10% all stats",
            "color": "#8e44ad",
            "special_effect": "increased_player_damage",
        },
        {
            "affix_id": "swarming",
            "name": "Swarming",
            "monster_hp_multiplier": 0.5,
            "monster_damage_multiplier": 1.0,
            "monster_speed_multiplier": 1.0,
            "description": "50% more monster spawns but with halved HP",
            "color": "#f39c12",
            "special_effect": "spawn_multiplier",
        },
        {
            "affix_id": "chaotic",
            "name": "Chaotic",
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.2,
            "monster_speed_multiplier": 1.1,
            "description": "Unpredictable elemental damage with random effects (+20% dmg, +10% speed)",
            "color": "#e67e22",
            "special_effect": "random_elements",
        },
    ]

    for data in affixes:
        existing = db.session.query(DungeonAffix).filter_by(affix_id=data["affix_id"]).first()
        if existing:
            print(f"  Affix '{data['affix_id']}' already exists, skipping.")
            continue

        affix = DungeonAffix(**data)
        db.session.add(affix)
        print(f"  Added affix: {data['name']} ({data['affix_id']})")

    db.session.commit()


def main():
    app = create_app()
    with app.app_context():
        print("Seeding enemy archetypes...")
        seed_enemy_archetypes()

        print("\nSeeding dungeon tiers...")
        seed_dungeon_tiers()

        print("\nSeeding dungeon affixes...")
        seed_dungeon_affixes()

        # Verify counts
        archetype_count = db.session.query(EnemyArchetype).count()
        tier_count = db.session.query(DungeonTier).count()
        affix_count = db.session.query(DungeonAffix).count()

        print("\n✓ Seeding complete!")
        print(f"  Enemy archetypes: {archetype_count}")
        print(f"  Dungeon tiers: {tier_count}")
        print(f"  Dungeon affixes: {affix_count}")


if __name__ == "__main__":
    main()
