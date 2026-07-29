from app.loot.data.rarities import RARITIES, rarity_affix_range, RARITY_ORDER


def test_order_complete():
    assert RARITY_ORDER == ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def test_each_rarity_has_a_valid_affix_range():
    # Colour used to live here too, but it was dead data that had drifted
    # from app/static/css/tokens.css's --rarity-* tokens (the actual source
    # of UI colour now) -- see rarities.py's docstring. Only the affix range
    # is this module's concern.
    for r in RARITY_ORDER:
        spec = RARITIES[r]
        assert "color" not in spec
        lo, hi = spec["affixes"]
        assert 0 <= lo <= hi <= 6


def test_affix_range_helper():
    assert rarity_affix_range("rare") == (2, 3)
    assert rarity_affix_range("nonsense") == (0, 1)
