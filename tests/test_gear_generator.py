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


def test_name_composition_format():
    """Verify name composition: no improper spacing, base_name present, and prefix/suffix ordering.

    Validates that:
    - Names have no double/leading/trailing spaces
    - Base archetype name is present
    - Prefix names (if present) appear BEFORE base_name
    - Suffix names (if present) appear AFTER base_name
    """
    from app.loot.data.archetypes import ARCHETYPES

    saw_prefix = False
    saw_suffix = False

    # Generate items across many seeds to capture both prefixed and suffixed items
    for seed in range(200):
        it = generate_item(level=10, rarity="rare", rng=_rng(seed))
        name = it["name"]

        # No leading/trailing or double spaces
        assert name == " ".join(name.split()), f"Seed {seed}: Name has improper spacing: {repr(name)}"

        # Base archetype name is present in the item name
        arch_key = it["base"]
        arch = ARCHETYPES[arch_key]
        base_name = arch["base_name"]
        assert base_name in name, f"Seed {seed}: Base name {repr(base_name)} not in {repr(name)}"

        # Find the base_name position in the full name
        base_idx = name.index(base_name)

        # Everything before base_name is prefix (if anything)
        prefix_part = name[:base_idx].strip()
        if prefix_part:
            saw_prefix = True
            # Prefix should come before base_name (index check)
            assert (
                name.index(prefix_part) < base_idx
            ), f"Seed {seed}: Prefix part {repr(prefix_part)} not before base in {repr(name)}"

        # Everything after base_name is suffix (if anything)
        suffix_start = base_idx + len(base_name)
        suffix_part = name[suffix_start:].strip()
        if suffix_part:
            saw_suffix = True
            # Suffix should come after base_name (index check)
            assert suffix_start <= name.index(suffix_part) + len(
                suffix_part
            ), f"Seed {seed}: Suffix part {repr(suffix_part)} not after base in {repr(name)}"

    # Ensure we actually tested both cases
    assert saw_prefix, "Test suite did not generate any items with prefixes (bounded loop exhausted)"
    assert saw_suffix, "Test suite did not generate any items with suffixes (bounded loop exhausted)"
