from app.loot.data.archetypes import SLOTS
from app.loot.data.prefixes import PREFIXES, prefixes_for


def test_prefix_shape():
    for p in PREFIXES:
        assert p["name"]
        assert p["stat"] in {"damage", "armor", "speed", "crit", "resist", "lifesteal"}
        assert p["min"] <= p["max"]
        assert p["weight"] > 0
        assert isinstance(p["slots"], (list, tuple))


def test_prefix_slots_are_canonical():
    """Every `slots` entry must be a real slot from archetypes.SLOTS.

    prefixes_for() matches slot names by exact string, so a typo ("chset",
    or a legacy "armor"/"gloves"/"ring1") does not raise -- it just makes that
    affix unreachable forever, silently, with nothing else failing. This is
    the prefix half of the check test_gear_archetypes already does with
    `a["slot"] in SLOTS`.

    Suffixes need no equivalent: they gate on `affinity`, a list of attribute
    tags (str/dex/int/...), and never mention slots at all.
    """
    for p in PREFIXES:
        stray = set(p["slots"]) - set(SLOTS)
        assert not stray, f"prefix {p['name']!r} lists non-canonical slot(s): {sorted(stray)}"


def test_filter_by_slot_and_category():
    weapon_dmg = prefixes_for("weapon", "blade")
    assert any(p["stat"] == "damage" for p in weapon_dmg)
    # 'Sturdy' (+armor) should not apply to a caster wand's damage-only prefixes set
    head = prefixes_for("head", "plate")
    assert any(p["stat"] == "armor" for p in head)
