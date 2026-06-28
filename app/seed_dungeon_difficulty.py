"""Idempotent seeding for dungeon difficulty tiers and starter affixes."""

from __future__ import annotations

from app import app as flask_app, db
from app.models.dungeon_tier import DungeonAffix, DungeonTier

TIERS = [
    {
        "tier": 1,
        "name": "Normal",
        "min_level": 1,
        "max_level": 99,
        "monster_level_modifier": 0,
        "loot_quality_bonus": 0.0,
        "xp_multiplier": 1.0,
        "description": "Standard difficulty. No modifiers.",
    },
    {
        "tier": 2,
        "name": "Heroic",
        "min_level": 1,
        "max_level": 99,
        "monster_level_modifier": 1,
        "loot_quality_bonus": 0.15,
        "xp_multiplier": 1.5,
        "description": "Monsters are one level higher. +15% loot quality, ×1.5 XP.",
    },
    {
        "tier": 3,
        "name": "Mythic",
        "min_level": 1,
        "max_level": 99,
        "monster_level_modifier": 2,
        "loot_quality_bonus": 0.30,
        "xp_multiplier": 2.0,
        "description": "Monsters are two levels higher. +30% loot quality, ×2.0 XP.",
    },
]

AFFIXES = [
    {
        "affix_id": "swarming",
        "name": "Swarming",
        "threat_weight": 2,
        "monster_count_multiplier": 1.2,
        "xp_multiplier": 1.1,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.0,
        "color": "#e74c3c",
        "description": "+20% more monsters, +10% XP.",
    },
    {
        "affix_id": "bulwark",
        "name": "Bulwark",
        "threat_weight": 2,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.3,
        "monster_damage_multiplier": 1.0,
        "color": "#3498db",
        "description": "Monsters have +30% HP.",
    },
    {
        "affix_id": "savage",
        "name": "Savage",
        "threat_weight": 2,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.2,
        "color": "#e67e22",
        "description": "Monsters deal +20% damage.",
    },
    {
        "affix_id": "thinned",
        "name": "Thinned Ranks",
        "threat_weight": 1,
        "monster_count_multiplier": 0.9,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.1,
        "monster_damage_multiplier": 1.1,
        "color": "#95a5a6",
        "description": "-10% monsters, but each is +10% stronger.",
    },
    {
        "affix_id": "bloodthirsty",
        "name": "Bloodthirsty",
        "threat_weight": 3,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.0,
        "color": "#c0392b",
        "description": "Monsters regenerate 2% HP per round.",
        "special_effect": '{"regen_pct": 0.02}',
    },
    {
        "affix_id": "cursed",
        "name": "Cursed",
        "threat_weight": 3,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.0,
        "color": "#8e44ad",
        "description": "Players take +15% damage.",
        "special_effect": '{"player_damage_taken_multiplier": 1.15}',
    },
    {
        "affix_id": "gilded",
        "name": "Gilded",
        "threat_weight": 1,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.15,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.0,
        "color": "#f1c40f",
        "description": "+15% XP, -10% loot quality.",
        "special_effect": '{"loot_quality_bonus": -0.10}',
    },
    {
        "affix_id": "fortified",
        "name": "Fortified",
        "threat_weight": 2,
        "monster_count_multiplier": 1.0,
        "xp_multiplier": 1.0,
        "monster_hp_multiplier": 1.0,
        "monster_damage_multiplier": 1.0,
        "color": "#1abc9c",
        "description": "Bosses have +50% HP.",
        "special_effect": '{"boss_hp_multiplier": 1.5}',
    },
]


def seed_dungeon_difficulty(verbose: bool = False) -> None:
    with flask_app.app_context():
        for spec in TIERS:
            existing = DungeonTier.query.filter_by(tier=spec["tier"]).first()
            if existing:
                for k, v in spec.items():
                    setattr(existing, k, v)
            else:
                db.session.add(DungeonTier(**spec))
            if verbose:
                print(f"  tier {spec['tier']}: {spec['name']}")

        for spec in AFFIXES:
            existing = DungeonAffix.query.filter_by(affix_id=spec["affix_id"]).first()
            if existing:
                for k, v in spec.items():
                    setattr(existing, k, v)
            else:
                db.session.add(DungeonAffix(**spec))
            if verbose:
                print(f"  affix {spec['affix_id']}: {spec['name']}")

        db.session.commit()
        if verbose:
            print("Done.")


if __name__ == "__main__":
    seed_dungeon_difficulty(verbose=True)
