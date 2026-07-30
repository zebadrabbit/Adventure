"""Unit-level checks on the XP table itself.

The *shape* of the curve -- that each level costs more fights than the last --
is pinned separately, against the real monster catalogue, in
`test_xp_curve_shape.py`. That is the test that protects the design. This one
just covers the function's edges.
"""

from app.models.xp import MAX_LEVEL, xp_for_level


def test_xp_lower_bound():
    assert xp_for_level(0) == 0
    assert xp_for_level(-5) == 0


def test_xp_known_table_values():
    # Spot checks. These are derived values, not sacred ones -- if the monster
    # catalogue's XP changes the curve should be re-derived and these updated
    # with it. What must not change is the shape (test_xp_curve_shape.py).
    assert xp_for_level(1) == 0
    assert xp_for_level(2) == 100
    assert xp_for_level(10) == 9_500
    assert xp_for_level(20) == 300_000


def test_there_is_nothing_past_the_cap():
    """The table used to extrapolate +50,000/level to a cap of 50: 30 levels of
    identical grind, fought against a catalogue that stops at 20. The cap is 20
    now, so a level above it has no requirement of its own to report."""
    assert MAX_LEVEL == 20
    assert xp_for_level(21) == xp_for_level(20)
    assert xp_for_level(99) == xp_for_level(20)


def test_xp_with_difficulty_modifier():
    base = xp_for_level(10)
    hard = xp_for_level(10, difficulty_mod=1.5)
    easy = xp_for_level(10, difficulty_mod=0.5)
    assert hard == int(base * 1.5)
    assert easy == int(base * 0.5)


def test_the_difficulty_modifier_applies_at_the_cap_too():
    assert xp_for_level(MAX_LEVEL, 2.0) == xp_for_level(MAX_LEVEL) * 2
