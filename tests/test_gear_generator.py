import random
from app.loot.generator import generate_item
from app.loot.data.rarities import rarity_affix_range


def _rng(seed=1):
    return random.Random(seed)


def test_returns_instance_shape():
    it = generate_item(level=5, rarity="rare", rng=_rng())
    for key in ("uid", "base", "slot", "name", "rarity", "ilvl", "affixes", "value"):
        assert key in it
    assert it["rarity"] == "rare"
    assert it["ilvl"] == 5


def test_affix_count_at_least_rarity_min():
    # affixes include the innate base stat block, so the rarity range is a FLOOR
    for rarity in ("common", "rare", "mythic"):
        lo, hi = rarity_affix_range(rarity)
        for s in range(20):
            it = generate_item(level=10, rarity=rarity, rng=_rng(s))
            assert len(it["affixes"]) >= lo


def test_slot_filter_respected():
    it = generate_item(level=5, slot="weapon", rng=_rng(3))
    assert it["slot"] == "weapon"


def test_affix_stats_are_known():
    known = {
        "str",
        "dex",
        "int",
        "wis",
        "con",
        "cha",
        "damage",
        "armor",
        "crit",
        "resist",
        "speed",
        "mana",
        "max_hp",
        "lifesteal",
    }
    it = generate_item(level=8, rarity="epic", rng=_rng(7))
    for a in it["affixes"]:
        assert a["stat"] in known
        assert a["val"] >= 1


def test_deterministic_under_seed():
    a = generate_item(level=6, rarity="rare", slot="weapon", rng=_rng(42))
    b = generate_item(level=6, rarity="rare", slot="weapon", rng=_rng(42))
    assert a["name"] == b["name"] and a["affixes"] == b["affixes"]


def test_value_scales_with_rarity():
    common = generate_item(level=10, rarity="common", slot="ring", rng=_rng(1))
    myth = generate_item(level=10, rarity="mythic", slot="ring", rng=_rng(1))
    assert myth["value"] > common["value"]
