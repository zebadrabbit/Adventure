"""Idempotent seed for dungeon difficulty / affix achievements."""

from __future__ import annotations

from app import app as flask_app, db

DUNGEON_ACHIEVEMENTS = [
    {
        "slug": "first-heroic-run",
        "name": "Proving Ground",
        "description": "Complete your first Heroic run.",
        "category": "exploration",
        "icon": "shield",
        "points": 10,
        "hidden": False,
        "requirement_type": "dungeon_heroic",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "first-mythic-run",
        "name": "Into the Abyss",
        "description": "Complete your first Mythic run.",
        "category": "exploration",
        "icon": "skull",
        "points": 25,
        "hidden": False,
        "requirement_type": "dungeon_mythic",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "first-affix-run",
        "name": "Glutton for Punishment",
        "description": "Complete a run with at least one affix active.",
        "category": "exploration",
        "icon": "zap",
        "points": 10,
        "hidden": False,
        "requirement_type": "dungeon_first_affix",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "triple-affix-run",
        "name": "Chaos Incarnate",
        "description": "Complete a run with 3 or more affixes simultaneously.",
        "category": "exploration",
        "icon": "flame",
        "points": 25,
        "hidden": False,
        "requirement_type": "dungeon_triple_affix",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "reach-harrowing",
        "name": "This Is Fine",
        "description": "Reach Threat Rating: Harrowing.",
        "category": "exploration",
        "icon": "alert-triangle",
        "points": 15,
        "hidden": False,
        "requirement_type": "dungeon_harrowing",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "reach-doomed",
        "name": "Absolute Madness",
        "description": "Reach Threat Rating: Doomed.",
        "category": "exploration",
        "icon": "bomb",
        "points": 50,
        "hidden": False,
        "requirement_type": "dungeon_doomed",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "mythic-multi-affix",
        "name": "No Survivors",
        "description": "Complete a Mythic run with 2 or more affixes.",
        "category": "exploration",
        "icon": "crosshair",
        "points": 50,
        "hidden": False,
        "requirement_type": "dungeon_mythic_multi_affix",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "death-wish",
        "name": "Death Wish",
        "description": "Complete a run with both Cursed and Savage active.",
        "category": "exploration",
        "icon": "heart",
        "points": 30,
        "hidden": False,
        "requirement_type": "dungeon_death_wish",
        "requirement_value": 1,
        "reward_gold": 0,
    },
    {
        "slug": "gold-rush",
        "name": "Gold Rush",
        "description": "Complete a run with both Gilded and Swarming active.",
        "category": "exploration",
        "icon": "dollar-sign",
        "points": 30,
        "hidden": False,
        "requirement_type": "dungeon_gold_rush",
        "requirement_value": 1,
        "reward_gold": 0,
    },
]


def seed_dungeon_achievements(verbose: bool = False) -> None:
    from app.models.achievement import Achievement

    with flask_app.app_context():
        created = updated = 0
        for spec in DUNGEON_ACHIEVEMENTS:
            obj = Achievement.query.filter_by(slug=spec["slug"]).first()
            if obj is None:
                obj = Achievement(slug=spec["slug"])
                db.session.add(obj)
                created += 1
            else:
                updated += 1

            for key, val in spec.items():
                if key != "slug":
                    setattr(obj, key, val)
            obj.is_active = True

        db.session.commit()
        if verbose:
            print(f"[seed-dungeon-achievements] created={created} updated={updated}")
