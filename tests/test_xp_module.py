from app.models.xp import xp_for_level


def test_xp_lower_bound():
    assert xp_for_level(0) == 0
    assert xp_for_level(-5) == 0


def test_xp_known_table_values():
    # Spot check a few canonical 5e thresholds
    assert xp_for_level(1) == 0
    assert xp_for_level(2) == 300
    assert xp_for_level(5) == 6500
    assert xp_for_level(10) == 64000
    assert xp_for_level(20) == 355000


def test_xp_extrapolation_above_20():
    # 21 should add 50k to base 355000
    assert xp_for_level(21) == 355000 + 50000
    assert xp_for_level(25) == 355000 + (5 * 50000)


def test_xp_with_difficulty_modifier():
    base = xp_for_level(10)
    hard = xp_for_level(10, difficulty_mod=1.5)
    easy = xp_for_level(10, difficulty_mod=0.5)
    assert hard == int(base * 1.5)
    assert easy == int(base * 0.5)
