from app.loot.data.suffixes import SUFFIXES, suffixes_for

ATTRS = {"str", "dex", "int", "wis", "con", "cha", "crit", "resist", "mana", "max_hp"}


def test_suffix_shape():
    for s in SUFFIXES:
        assert s["name"].startswith("of ")
        assert s["stats"], "suffix must grant at least one stat"
        for stat, weight in s["stats"].items():
            assert stat in ATTRS
            assert weight > 0
        assert s["weight"] > 0


def test_hawk_is_dex_con():
    hawk = next(s for s in SUFFIXES if s["name"] == "of the Hawk")
    assert set(hawk["stats"].keys()) == {"dex", "con"}


def test_eligibility_by_affinity():
    # 'of the Hawk' (dex) should be eligible for a dex archetype
    elig = suffixes_for(["dex"])
    assert any(s["name"] == "of the Hawk" for s in elig)
