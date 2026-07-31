from app.loot.data.rarities import RARITIES, RARITY_ORDER, rarity_affix_range, rarity_power


def test_order_complete():
    assert RARITY_ORDER == ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def test_each_rarity_has_a_valid_affix_range():
    # Colour used to live here too, but it was dead data that had drifted
    # from app/static/css/tokens.css's --rarity-* tokens (the actual source
    # of UI colour now) -- see rarities.py's docstring. Only the affix range
    # and the power multiplier are this module's concern.
    for r in RARITY_ORDER:
        spec = RARITIES[r]
        assert "color" not in spec
        lo, hi = spec["affixes"]
        assert 1 <= lo <= hi, f"{r} has a broken affix range {(lo, hi)}"


def test_affix_range_helper():
    # Derived from the table, not restated: these are tuning values.
    assert rarity_affix_range("rare") == RARITIES["rare"]["affixes"]
    assert rarity_affix_range("nonsense") == RARITIES["common"]["affixes"]


def test_every_drop_carries_at_least_one_affix():
    """A common drop used to be able to roll zero affixes, which -- with jewelry
    having no base stat block -- meant 7.4% of all drops had no stats at all,
    and the two most common items in the game were a bare Ring and a bare
    Amulet."""
    for r in RARITY_ORDER:
        assert RARITIES[r]["affixes"][0] >= 1, f"{r} can roll a stat-less item"


def test_rarity_scales_power_and_price_monotonically():
    """Rarity used to change only the affix COUNT and the price, never the
    magnitude -- a common "Longsword of the Bear" at level 20 rolled exactly
    what a mythic one did. Both curves must rise, or rarity is decoration."""
    powers = [rarity_power(r) for r in RARITY_ORDER]
    values = [RARITIES[r]["value_mult"] for r in RARITY_ORDER]

    assert powers == sorted(powers) and powers[0] < powers[-1], powers
    assert values == sorted(values) and values[0] < values[-1], values
    assert rarity_power("common") == 1.0, "common is the baseline the rest scale against"


def test_rarity_power_falls_back_for_nonsense():
    assert rarity_power("nonsense") == rarity_power("common")


# --- the generator's output shape ------------------------------------------
# These need an app context: generate_item reads durability config from the DB.


def _sample(test_app, level=12, n=400, rarity=None):
    import random

    from app.loot.generator import generate_item

    with test_app.app_context():
        rng = random.Random(1234)
        return [generate_item(level=level, rarity=rarity, rng=rng) for _ in range(n)]


def test_no_item_lists_the_same_stat_twice(test_app):
    """Extras are rolled as unnamed prefixes from a small pool, so a weapon
    could land "+20 damage, +5 damage, +11 damage" -- three ways of saying +36,
    which reads as a bug in the tooltip. Worse at high rarity, which rolls more
    affixes, i.e. exactly where the item should feel best."""
    for item in _sample(test_app):
        stats = [a["stat"] for a in item["affixes"]]
        assert len(stats) == len(set(stats)), f"{item['name']} repeats a stat: {item['affixes']}"


def test_every_generated_item_has_at_least_one_stat(test_app):
    for item in _sample(test_app):
        assert item["affixes"], f"{item['name']} ({item['rarity']}) rolled no stats at all"
        assert all(a["val"] >= 1 for a in item["affixes"]), item["affixes"]


def test_a_name_never_says_the_same_word_twice(test_app):
    """ "Warding Plate Gauntlets of Warding" -- the prefix and the suffix theme
    can name the same idea."""
    for item in _sample(test_app):
        words = [w for w in item["name"].lower().split() if w not in ("of", "the")]
        assert len(words) == len(set(words)), f"repeated word in {item['name']!r}"


def test_a_rarer_item_is_actually_stronger(test_app):
    """The whole point. Compares like for like at a fixed level, over enough
    samples that the affix-count spread cannot flip the order."""
    means = {}
    for rarity in RARITY_ORDER:
        items = _sample(test_app, level=20, n=300, rarity=rarity)
        means[rarity] = sum(sum(a["val"] for a in i["affixes"]) for i in items) / len(items)

    ordered = [means[r] for r in RARITY_ORDER]
    assert ordered == sorted(ordered), f"rarity does not track power: {means}"
    assert means["mythic"] > means["common"] * 3, f"mythic is barely better than common: {means}"
