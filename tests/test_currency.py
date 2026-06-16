"""Unit tests for copper -> tiered-currency formatting (no DB required)."""

import pytest

from app.economy.currency import COPPER_PER_GOLD, format_copper, split_copper


@pytest.mark.parametrize(
    "copper,expected",
    [
        (0, "0c"),
        (5, "5c"),
        (100, "1s"),
        (150, "1s 50c"),
        (9999, "99s 99c"),
        (10000, "1g"),
        (120505, "12g 5s 5c"),
        (-5, "0c"),  # negative clamps to zero
    ],
)
def test_format_copper(copper, expected):
    assert format_copper(copper) == expected


def test_format_omits_zero_tiers():
    # 1 gold exactly: no silver/copper noise
    assert format_copper(COPPER_PER_GOLD) == "1g"
    # gold + copper but zero silver: silver tier omitted
    assert format_copper(COPPER_PER_GOLD + 7) == "1g 7c"


def test_split_copper():
    assert split_copper(120505) == {"gold": 12, "silver": 5, "copper": 5}
    assert split_copper(0) == {"gold": 0, "silver": 0, "copper": 0}
    assert split_copper(-100) == {"gold": 0, "silver": 0, "copper": 0}
