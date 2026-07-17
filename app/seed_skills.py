"""Programmatic, idempotent seeding of starter skill trees and skills.

Like app/seed_merchants.py, this seeds a small starter set via the ORM so the
skill-unlock flow has real data. Idempotent: trees are upserted by name and
skills by (tree, name); prerequisites are resolved by name after skills exist.

Usage:
    from app.seed_skills import seed_skills
    seed_skills()

CLI:
    python run.py seed-skills
"""

from __future__ import annotations

import json

from app import app as flask_app
from app import db
from app.models.skill import Skill, SkillTree

# Tree definitions: name -> metadata. class_requirement None = available to all.
TREES = [
    {"name": "Combat", "class_requirement": None, "description": "Martial fundamentals.", "max_tier": 3},
    {
        "name": "Martial",
        "class_requirement": "fighter,barbarian,monk",
        "description": "Strength of arms.",
        "max_tier": 3,
    },
    {"name": "Arcana", "class_requirement": "mage,sorcerer", "description": "Arcane study.", "max_tier": 3},
    {"name": "Divine", "class_requirement": "cleric,paladin", "description": "Channel holy power.", "max_tier": 3},
    {"name": "Nature", "class_requirement": "druid,ranger", "description": "The wild answers.", "max_tier": 3},
    {"name": "Shadow", "class_requirement": "rogue,bard", "description": "Guile and precision.", "max_tier": 3},
    {"name": "Occult", "class_requirement": "warlock", "description": "Forbidden bargains.", "max_tier": 3},
]

# Skill definitions. effect_json is a dict (serialized on write). required_skill
# is the *name* of a prerequisite skill in the same tree (resolved after insert).
SKILLS = [
    {
        "tree": "Combat",
        "name": "Toughness",
        "description": "+2 Constitution.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"con": 2},
    },
    {
        "tree": "Combat",
        "name": "Power Strike",
        "description": "A heavy blow for bonus damage.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"damage": 5},
    },
    {
        "tree": "Combat",
        "name": "Second Wind",
        "description": "Catch your breath, restoring health.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"heal": 10},
        "required_skill": "Toughness",
    },
    {
        "tree": "Arcana",
        "name": "Focus",
        "description": "+2 Intelligence.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"int": 2},
    },
    {
        "tree": "Arcana",
        "name": "Firebolt",
        "description": "Hurl a bolt of fire.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 2,
        "effect": {"spell_damage": 8},
    },
    {
        "tree": "Arcana",
        "name": "Frost Lance",
        "description": "A piercing shard of ice.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"spell_damage": 14},
    },
    {
        "tree": "Arcana",
        "name": "Clarity",
        "description": "+2 Intelligence, +1 Wisdom.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"int": 2, "wis": 1},
    },
    {
        "tree": "Arcana",
        "name": "Arcane Blast",
        "description": "An overpowering surge of raw magic.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"spell_damage": 22},
        "required_skill": "Frost Lance",
    },
    {
        "tree": "Martial",
        "name": "Crushing Blow",
        "description": "A brutal strike with a weapon.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"damage": 6},
    },
    {
        "tree": "Martial",
        "name": "Iron Body",
        "description": "+2 Constitution.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"con": 2},
    },
    {
        "tree": "Martial",
        "name": "Cleave",
        "description": "A sweeping strike that hits hard.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"damage": 12},
    },
    {
        "tree": "Martial",
        "name": "Bulwark",
        "description": "+2 Strength, +1 Constitution.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"str": 2, "con": 1},
    },
    {
        "tree": "Martial",
        "name": "Execute",
        "description": "A finishing blow against a weakened foe.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"damage": 20},
        "required_skill": "Cleave",
    },
    {
        "tree": "Divine",
        "name": "Smite",
        "description": "Holy force blasts a foe.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"spell_damage": 6},
    },
    {
        "tree": "Divine",
        "name": "Faith",
        "description": "+2 Wisdom.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"wis": 2},
    },
    {
        "tree": "Divine",
        "name": "Healing Word",
        "description": "A whispered prayer mends wounds.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"heal": 12},
    },
    {
        "tree": "Divine",
        "name": "Devotion",
        "description": "+2 Wisdom, +1 Constitution.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"wis": 2, "con": 1},
    },
    {
        "tree": "Divine",
        "name": "Divine Wrath",
        "description": "Righteous fury made manifest.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"spell_damage": 18},
        "required_skill": "Healing Word",
    },
    {
        "tree": "Nature",
        "name": "Thorn Lash",
        "description": "A whip of thorns lashes out.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"spell_damage": 6},
    },
    {
        "tree": "Nature",
        "name": "Wild Sense",
        "description": "+2 Wisdom.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"wis": 2},
    },
    {
        "tree": "Nature",
        "name": "Regrowth",
        "description": "Nature's magic knits flesh together.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"heal": 12},
    },
    {
        "tree": "Nature",
        "name": "Barkskin",
        "description": "+2 Constitution, +1 Wisdom.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"con": 2, "wis": 1},
    },
    {
        "tree": "Nature",
        "name": "Entangling Storm",
        "description": "A tempest of vines and wind.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"spell_damage": 18},
        "required_skill": "Regrowth",
    },
    {
        "tree": "Shadow",
        "name": "Backstab",
        "description": "A strike from the shadows.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"damage": 7},
    },
    {
        "tree": "Shadow",
        "name": "Nimble",
        "description": "+2 Dexterity.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"dex": 2},
    },
    {
        "tree": "Shadow",
        "name": "Flurry",
        "description": "A rapid flurry of strikes.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"damage": 13},
    },
    {
        "tree": "Shadow",
        "name": "Silver Tongue",
        "description": "+2 Charisma, +1 Dexterity.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"cha": 2, "dex": 1},
    },
    {
        "tree": "Shadow",
        "name": "Assassinate",
        "description": "A lethal strike aimed at a vital point.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"damage": 20},
        "required_skill": "Flurry",
    },
    {
        "tree": "Occult",
        "name": "Eldritch Bolt",
        "description": "A crackling bolt of forbidden power.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "active",
        "cooldown": 3,
        "effect": {"spell_damage": 7},
    },
    {
        "tree": "Occult",
        "name": "Dark Pact",
        "description": "+2 Charisma.",
        "tier": 1,
        "required_level": 1,
        "cost": 1,
        "skill_type": "passive",
        "effect": {"cha": 2},
    },
    {
        "tree": "Occult",
        "name": "Life Tap",
        "description": "Drain vitality from a foe to heal.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "active",
        "cooldown": 4,
        "effect": {"heal": 10},
    },
    {
        "tree": "Occult",
        "name": "Void Insight",
        "description": "+2 Charisma, +1 Intelligence.",
        "tier": 2,
        "required_level": 3,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"cha": 2, "int": 1},
    },
    {
        "tree": "Occult",
        "name": "Doom",
        "description": "An inevitable, crushing fate.",
        "tier": 3,
        "required_level": 5,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"spell_damage": 22},
        "required_skill": "Life Tap",
    },
]


def seed_skills(verbose: bool = True) -> int:
    """Create or update starter skill trees and skills. Returns skill count.

    Idempotent: trees upserted by name, skills by (tree_id, name), prerequisites
    resolved by name afterward.
    """
    with flask_app.app_context():
        # Upsert trees
        tree_by_name = {}
        for spec in TREES:
            tree = SkillTree.query.filter_by(name=spec["name"]).first()
            if not tree:
                tree = SkillTree(name=spec["name"])
                db.session.add(tree)
            tree.class_requirement = spec.get("class_requirement")
            tree.description = spec.get("description")
            tree.max_tier = spec.get("max_tier", 5)
            tree.is_active = True
            db.session.flush()
            tree_by_name[spec["name"]] = tree

        # Upsert skills (without prerequisites first)
        skill_by_name = {}
        for spec in SKILLS:
            tree = tree_by_name[spec["tree"]]
            skill = Skill.query.filter_by(tree_id=tree.id, name=spec["name"]).first()
            if not skill:
                skill = Skill(tree_id=tree.id, name=spec["name"])
                db.session.add(skill)
            skill.description = spec["description"]
            skill.tier = spec.get("tier", 1)
            skill.required_level = spec.get("required_level", 1)
            skill.cost = spec.get("cost", 1)
            skill.skill_type = spec.get("skill_type", "passive")
            skill.cooldown = spec.get("cooldown")
            skill.effect_json = json.dumps(spec.get("effect", {}))
            skill.is_active = True
            skill.required_skill_id = None  # reset; resolved below
            db.session.flush()
            skill_by_name[(spec["tree"], spec["name"])] = skill

        # Resolve prerequisites by name
        for spec in SKILLS:
            req = spec.get("required_skill")
            if req:
                skill = skill_by_name[(spec["tree"], spec["name"])]
                prereq = skill_by_name.get((spec["tree"], req))
                if prereq:
                    skill.required_skill_id = prereq.id

        db.session.commit()
        if verbose:
            print(f"[seed-skills] {len(tree_by_name)} trees, {len(skill_by_name)} skills seeded.")
        return len(skill_by_name)


__all__ = ["seed_skills"]
