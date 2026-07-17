"""Archetype skill trees seed content."""

from app.models.skill import Skill, SkillTree
from app.seed_skills import seed_skills

EXPECTED_TREES = {
    "Combat": None,
    "Martial": "fighter,barbarian,monk",
    "Arcana": "mage,sorcerer",
    "Divine": "cleric,paladin",
    "Nature": "druid,ranger",
    "Shadow": "rogue,bard",
    "Occult": "warlock",
}
STARTING_ACTIVES = {
    "Martial": "Crushing Blow",
    "Arcana": "Firebolt",
    "Divine": "Smite",
    "Nature": "Thorn Lash",
    "Shadow": "Backstab",
    "Occult": "Eldritch Bolt",
}


def test_seed_creates_all_archetype_trees():
    seed_skills(verbose=False)
    for name, req in EXPECTED_TREES.items():
        tree = SkillTree.query.filter_by(name=name).first()
        assert tree is not None, f"tree {name} missing"
        assert tree.class_requirement == req


def test_every_tree_has_tier1_active_and_prereqs_resolve():
    seed_skills(verbose=False)
    for tree_name, skill_name in STARTING_ACTIVES.items():
        tree = SkillTree.query.filter_by(name=tree_name).first()
        s = Skill.query.filter_by(tree_id=tree.id, name=skill_name).first()
        assert s is not None and s.skill_type == "active" and s.tier == 1 and s.required_level == 1
    # every tier-3 skill has a resolved prerequisite in the same tree
    for s in Skill.query.filter_by(tier=3).all():
        assert s.required_skill_id is not None


def test_seed_is_idempotent():
    n1 = seed_skills(verbose=False)
    n2 = seed_skills(verbose=False)
    assert n1 == n2
    # No duplicate (tree, name) rows after two seed runs.
    skills = Skill.query.all()
    assert len(skills) == len({(s.tree_id, s.name) for s in skills})
