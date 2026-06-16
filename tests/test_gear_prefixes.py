from app.loot.data.prefixes import PREFIXES, prefixes_for


def test_prefix_shape():
    for p in PREFIXES:
        assert p["name"]
        assert p["stat"] in {"damage", "armor", "speed", "crit", "resist", "lifesteal"}
        assert p["min"] <= p["max"]
        assert p["weight"] > 0
        assert isinstance(p["slots"], (list, tuple))


def test_filter_by_slot_and_category():
    weapon_dmg = prefixes_for("weapon", "blade")
    assert any(p["stat"] == "damage" for p in weapon_dmg)
    # 'Sturdy' (+armor) should not apply to a caster wand's damage-only prefixes set
    head = prefixes_for("head", "plate")
    assert any(p["stat"] == "armor" for p in head)
