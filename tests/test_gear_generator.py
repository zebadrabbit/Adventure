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
    """Verify name composition against independent ground truth (the affix data pools).

    Validates that:
    - Names have no double/leading/trailing spaces
    - The name is (optional prefix + " ") + base_name + (" " + optional suffix), where
      the prefix/suffix substrings are checked against the actual PREFIXES/SUFFIXES
      pools rather than derived from the name itself. This catches, e.g., a reversed
      prefix/suffix composition order.
    """
    from app.loot.data.archetypes import ARCHETYPES
    from app.loot.data.prefixes import PREFIXES
    from app.loot.data.suffixes import SUFFIXES

    prefix_names = {p["name"] for p in PREFIXES}
    suffix_names = {s["name"] for s in SUFFIXES}

    saw_prefix = False
    saw_suffix = False

    # Generate items across many seeds to capture both prefixed and suffixed items
    for seed in range(200):
        it = generate_item(level=10, rarity="rare", rng=_rng(seed))
        name = it["name"]
        arch_key = it["base"]
        base_name = ARCHETYPES[arch_key]["base_name"]

        # No leading/trailing or double spaces
        assert name == " ".join(name.split()), f"Seed {seed}: Name has improper spacing: {repr(name)}"

        rest = name
        for p in prefix_names:
            if rest == p + " " + base_name or rest.startswith(p + " " + base_name + " "):
                rest = rest[len(p) + 1 :]
                saw_prefix = True
                break

        assert rest == base_name or rest.startswith(
            base_name + " "
        ), f"Seed {seed}: {name!r} does not start with (prefix +) base {base_name!r}"

        rest = rest[len(base_name) :]
        if rest:
            assert rest[1:] in suffix_names, f"Seed {seed}: trailing {rest[1:]!r} in {name!r} is not a known suffix"
            saw_suffix = True

    # Ensure we actually tested both cases
    assert saw_prefix and saw_suffix, "sweep must cover both a prefixed and a suffixed item"
