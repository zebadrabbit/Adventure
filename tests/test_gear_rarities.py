from app.loot.data.rarities import RARITIES, rarity_affix_range, RARITY_ORDER


def test_order_complete():
    assert RARITY_ORDER == ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def test_each_rarity_has_color_and_range():
    for r in RARITY_ORDER:
        spec = RARITIES[r]
        assert spec["color"].startswith("#")
        lo, hi = spec["affixes"]
        assert 0 <= lo <= hi <= 6


def test_affix_range_helper():
    assert rarity_affix_range("rare") == (2, 3)
    assert rarity_affix_range("nonsense") == (0, 1)
