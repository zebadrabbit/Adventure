"""Every level should give a character something to look forward to.

The trees stopped at `required_level` 5. That was survivable when the cap was 50
and levels were a flat grind nobody expected much from; with the cap at 20 it
meant **fifteen of the twenty levels granted nothing but stat points** -- three
quarters of the ladder with no new button. Talent points made it worse: they
accrue one per level to 20, while every skill a character could reach cost 13
between them, so seven points had nothing to buy.

These read the seed definitions rather than the database. `db_isolation` tests
rebuild the schema mid-suite, so asserting against seeded rows is
order-dependent (docs/TESTING.md, and see test_monster_catalogue_coverage.py).
"""

import ast
import collections
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parent.parent / "app" / "seed_skills.py"
CAP = 20
TALENT_POINTS_AT_CAP = 20  # progression grants one per level


def _load():
    """SKILLS and TREES as literals, without importing the module (which pulls
    in the app and a database connection)."""
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    skills, trees = [], []
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign):
            target = getattr(node.targets[0], "id", None)
        elif isinstance(node, ast.AugAssign):
            target = getattr(node.target, "id", None)
        if target == "SKILLS":
            skills += ast.literal_eval(node.value)
        elif target == "TREES":
            trees += ast.literal_eval(node.value)
    return skills, trees


SKILLS, TREES = _load()
ARCHETYPE_TREES = [t["name"] for t in TREES if t["class_requirement"]]
UNIVERSAL_TREES = [t["name"] for t in TREES if not t["class_requirement"]]


def test_the_seed_parses():
    """A guard on the guards: no skills means every assertion below is vacuous."""
    assert len(SKILLS) > 40, f"only parsed {len(SKILLS)} skills"
    assert UNIVERSAL_TREES, "no universal tree found"
    assert len(ARCHETYPE_TREES) >= 6


def test_nothing_unlocks_past_the_level_cap():
    over = [s["name"] for s in SKILLS if s["required_level"] > CAP]
    assert not over, f"unreachable skills: {over}"


def test_no_long_stretch_of_levels_grants_nothing():
    """The specific failure this file exists for: levels 6-20 used to be empty.
    A gap of five or more consecutive levels with no unlock anywhere is a
    stretch of the game where levelling is just a bigger number."""
    unlock_levels = sorted({s["required_level"] for s in SKILLS})

    gaps = []
    previous = 1
    for level in unlock_levels + [CAP]:
        if level - previous >= 5:
            gaps.append(f"{previous}->{level}")
        previous = level
    assert not gaps, f"no skill unlocks across {gaps}"


@pytest.mark.parametrize("tree", ARCHETYPE_TREES)
def test_every_class_keeps_unlocking_into_the_late_game(tree):
    """Reaching level 20 in a tree whose last word was at level 5 is fifteen
    levels of nothing for whoever plays that class."""
    levels = [s["required_level"] for s in SKILLS if s["tree"] == tree]

    assert levels, f"{tree} has no skills at all"
    assert max(levels) >= 15, f"{tree} stops unlocking at level {max(levels)}"
    assert any(level >= 10 for level in levels), f"{tree} has nothing in the second half of the game"


def test_a_build_costs_more_than_a_character_can_afford():
    """Points must be a choice. Every skill reachable used to cost 13 against
    the 20 a character earns -- buy everything, with seven left over."""
    universal = sum(s["cost"] for s in SKILLS if s["tree"] in UNIVERSAL_TREES)

    for tree in ARCHETYPE_TREES:
        archetype = sum(s["cost"] for s in SKILLS if s["tree"] == tree)
        reachable = universal + archetype
        assert reachable > TALENT_POINTS_AT_CAP, (
            f"a {tree} character can buy every skill they can reach "
            f"({reachable} points of skills, {TALENT_POINTS_AT_CAP} points earned)"
        )


def test_every_skill_uses_an_effect_the_engine_can_execute():
    """A skill whose effect nothing reads is a dead button. Actives run
    damage / spell_damage / heal; passives are folded by _derive_stats from a
    fixed stat vocabulary."""
    passive_keys = {
        "str", "dex", "int", "con", "wis", "cha",
        "max_hp", "mana", "damage", "armor", "speed",
        "crit", "lifesteal", "resist",
    }  # fmt: skip
    active_keys = {"damage", "spell_damage", "heal"}

    bad = []
    for s in SKILLS:
        allowed = active_keys if s["skill_type"] == "active" else passive_keys
        for key in s["effect"]:
            if key not in allowed:
                bad.append(f"{s['name']} ({s['skill_type']}) grants '{key}', which nothing reads")
    assert not bad, bad


def test_prerequisites_point_at_a_real_skill_in_the_same_tree():
    by_tree = collections.defaultdict(set)
    for s in SKILLS:
        by_tree[s["tree"]].add(s["name"])

    broken = [
        f"{s['name']} requires {s['required_skill']!r}, absent from {s['tree']}"
        for s in SKILLS
        if s.get("required_skill") and s["required_skill"] not in by_tree[s["tree"]]
    ]
    assert not broken, broken


def test_a_prerequisite_is_never_gated_later_than_the_skill_it_unlocks():
    """Otherwise the chain is unbuyable: you meet the child's level before the
    parent's and can never satisfy the requirement."""
    level_of = {s["name"]: s["required_level"] for s in SKILLS}

    inverted = [
        f"{s['name']} (L{s['required_level']}) requires {s['required_skill']} (L{level_of[s['required_skill']]})"
        for s in SKILLS
        if s.get("required_skill") and level_of.get(s["required_skill"], 0) > s["required_level"]
    ]
    assert not inverted, inverted
