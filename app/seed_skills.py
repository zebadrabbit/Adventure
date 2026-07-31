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

# Caster trees whose active skills consume mana (spell_damage / heal effects).
# Physical trees (Combat, Martial, Shadow) and all passives cost 0.
CASTER_TREES = {"Arcana", "Divine", "Nature", "Occult"}

# Tree definitions: name -> metadata. class_requirement None = available to all.
TREES = [
    {"name": "Combat", "class_requirement": None, "description": "Martial fundamentals.", "max_tier": 6},
    {
        "name": "Martial",
        "class_requirement": "fighter,barbarian,monk",
        "description": "Strength of arms.",
        "max_tier": 6,
    },
    {"name": "Arcana", "class_requirement": "mage,sorcerer", "description": "Arcane study.", "max_tier": 6},
    {"name": "Divine", "class_requirement": "cleric,paladin", "description": "Channel holy power.", "max_tier": 6},
    {"name": "Nature", "class_requirement": "druid,ranger", "description": "The wild answers.", "max_tier": 6},
    {"name": "Shadow", "class_requirement": "rogue,bard", "description": "Guile and precision.", "max_tier": 6},
    {"name": "Occult", "class_requirement": "warlock", "description": "Forbidden bargains.", "max_tier": 6},
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


# --- Levels 6-20 ------------------------------------------------------------
# Everything above stops at required_level 5, which was fine for a 50-level game
# where levels were a flat grind and nobody expected much. With the cap at 20,
# that left FIFTEEN of the twenty levels granting nothing but stat points --
# three quarters of the ladder with no new button. Talent points made it worse:
# they accrue one per level to 20, while every skill a character could reach
# cost 13 between them, so seven points had nothing to buy.
#
# These use only effect kinds the engine already executes: actives are
# damage / spell_damage / heal (which compose in one cast), passives are any
# numeric key `_derive_stats` folds. That vocabulary just grew -- crit,
# lifesteal and resist became real stats when the affix work wired them up --
# so the late passives spend it rather than adding a sixth flavour of "+2 str".
#
# Costs rise with tier, so the 20 points a character earns buy roughly half of
# what they can reach (Combat 16 + one archetype tree 21 = 37). That is the
# point: a build should be a choice, not a checklist.
SKILLS += [
    # Combat -- universal, so every class gets four more decisions.
    {
        "tree": "Combat",
        "name": "Battle Scars",
        "description": "+20 maximum health.",
        "tier": 4,
        "required_level": 7,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"max_hp": 20},
        "required_skill": "Toughness",
    },
    {
        "tree": "Combat",
        "name": "Rally",
        "description": "A second breath, deeper than the first.",
        "tier": 5,
        "required_level": 10,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"heal": 16},
        "required_skill": "Second Wind",
    },
    {
        "tree": "Combat",
        "name": "Killer Instinct",
        "description": "+8% critical chance.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"crit": 8},
        "required_skill": "Power Strike",
    },
    {
        "tree": "Combat",
        "name": "Last Stand",
        "description": "Strike with everything left, and take heart from it.",
        "tier": 6,
        "required_level": 18,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 8,
        "effect": {"damage": 26, "heal": 14},
        "required_skill": "Rally",
    },
    # Martial -- fighter, barbarian, monk.
    {
        "tree": "Martial",
        "name": "Weapon Mastery",
        "description": "+4 weapon damage.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"damage": 4},
        "required_skill": "Iron Body",
    },
    {
        "tree": "Martial",
        "name": "Sunder",
        "description": "Split guard and bone alike.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"damage": 24},
        "required_skill": "Cleave",
    },
    {
        "tree": "Martial",
        "name": "Heavy Plate",
        "description": "+5 armour.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"armor": 5},
        "required_skill": "Bulwark",
    },
    {
        "tree": "Martial",
        "name": "Whirlwind",
        "description": "Turn once, and everything nearby falls.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 8,
        "effect": {"damage": 34},
        "required_skill": "Sunder",
    },
    # Arcana -- mage, sorcerer.
    {
        "tree": "Arcana",
        "name": "Arcane Reservoir",
        "description": "+18 maximum mana.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"mana": 18},
        "required_skill": "Focus",
    },
    {
        "tree": "Arcana",
        "name": "Chain Lightning",
        "description": "The bolt does not stop at the first.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"spell_damage": 22},
        "required_skill": "Frost Lance",
    },
    {
        "tree": "Arcana",
        "name": "Spell Focus",
        "description": "+3 Intelligence, +5% critical chance.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"int": 3, "crit": 5},
        "required_skill": "Clarity",
    },
    {
        "tree": "Arcana",
        "name": "Meteor",
        "description": "Call something down that does not care what it lands on.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 9,
        "effect": {"spell_damage": 34},
        "required_skill": "Chain Lightning",
    },
    # Divine -- cleric, paladin.
    {
        "tree": "Divine",
        "name": "Consecration",
        "description": "+8 resistance to all damage.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"resist": 8},
        "required_skill": "Faith",
    },
    {
        "tree": "Divine",
        "name": "Mass Heal",
        "description": "Light enough for everyone still standing.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 6,
        "effect": {"heal": 26},
        "required_skill": "Healing Word",
    },
    {
        "tree": "Divine",
        "name": "Aegis",
        "description": "+5 armour, +15 maximum health.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"armor": 5, "max_hp": 15},
        "required_skill": "Devotion",
    },
    {
        "tree": "Divine",
        "name": "Judgement",
        "description": "Verdict and mercy in the same breath.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 8,
        "effect": {"spell_damage": 30, "heal": 12},
        "required_skill": "Mass Heal",
    },
    # Nature -- druid, ranger.
    {
        "tree": "Nature",
        "name": "Thick Hide",
        "description": "+4 armour, +12 maximum health.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"armor": 4, "max_hp": 12},
        "required_skill": "Barkskin",
    },
    {
        "tree": "Nature",
        "name": "Wildfire",
        "description": "It spreads the way fire wants to.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"spell_damage": 22},
        "required_skill": "Thorn Lash",
    },
    {
        "tree": "Nature",
        "name": "Pack Instinct",
        "description": "+3 speed, +5% critical chance.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"speed": 3, "crit": 5},
        "required_skill": "Wild Sense",
    },
    {
        "tree": "Nature",
        "name": "Nature's Wrath",
        "description": "The wild stops being patient.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 8,
        "effect": {"spell_damage": 32, "heal": 10},
        "required_skill": "Wildfire",
    },
    # Shadow -- rogue, bard.
    {
        "tree": "Shadow",
        "name": "Deadly Precision",
        "description": "+10% critical chance.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"crit": 10},
        "required_skill": "Nimble",
    },
    {
        "tree": "Shadow",
        "name": "Eviscerate",
        "description": "Find the gap, then widen it.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"damage": 26},
        "required_skill": "Flurry",
    },
    {
        "tree": "Shadow",
        "name": "Shadowstep",
        "description": "+4 speed, +2 Dexterity.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"speed": 4, "dex": 2},
        "required_skill": "Silver Tongue",
    },
    {
        "tree": "Shadow",
        "name": "Death Mark",
        "description": "Name them, and it is already done.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 9,
        "effect": {"damage": 36},
        "required_skill": "Eviscerate",
    },
    # Occult -- warlock. The one tree no other class shares.
    {
        "tree": "Occult",
        "name": "Blood Pact",
        "description": "Attacks return 8% of damage dealt as health.",
        "tier": 4,
        "required_level": 8,
        "cost": 2,
        "skill_type": "passive",
        "effect": {"lifesteal": 8},
        "required_skill": "Dark Pact",
    },
    {
        "tree": "Occult",
        "name": "Drain Soul",
        "description": "What it takes from them, it gives to you.",
        "tier": 5,
        "required_level": 11,
        "cost": 3,
        "skill_type": "active",
        "cooldown": 5,
        "effect": {"spell_damage": 20, "heal": 10},
        "required_skill": "Life Tap",
    },
    {
        "tree": "Occult",
        "name": "Void Armour",
        "description": "+8 resistance to all damage, +12 maximum health.",
        "tier": 5,
        "required_level": 14,
        "cost": 3,
        "skill_type": "passive",
        "effect": {"resist": 8, "max_hp": 12},
        "required_skill": "Void Insight",
    },
    {
        "tree": "Occult",
        "name": "Unmaking",
        "description": "Undo the idea of them.",
        "tier": 6,
        "required_level": 17,
        "cost": 4,
        "skill_type": "active",
        "cooldown": 9,
        "effect": {"spell_damage": 34},
        "required_skill": "Drain Soul",
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
            # Caster-tree actives cost mana scaled by tier (t1=4, t2=8, t3=12).
            # Physical actives and all passives are free.
            if skill.skill_type == "active" and spec["tree"] in CASTER_TREES:
                skill.mana_cost = spec.get("tier", 1) * 4
            else:
                skill.mana_cost = 0
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
