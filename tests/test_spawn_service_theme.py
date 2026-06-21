"""Tests for spawn_service.pick_monster_family (deterministic per-seed
dungeon enemy theme selection)."""

from app.services.spawn_service import MONSTER_THEME_FAMILIES, pick_monster_family


def test_pick_monster_family_is_deterministic():
    result_a = pick_monster_family(seed=12345)
    result_b = pick_monster_family(seed=12345)
    assert result_a == result_b


def test_pick_monster_family_returns_valid_family():
    for seed in (1, 2, 3, 4, 5, 100, 999999):
        assert pick_monster_family(seed=seed) in MONSTER_THEME_FAMILIES


def test_pick_monster_family_varies_across_seeds():
    results = {pick_monster_family(seed=s) for s in range(50)}
    # With 7 possible families and 50 different seeds, expect more than
    # one distinct result -- this is not a strict uniformity test, just
    # a sanity check that the function isn't accidentally constant.
    assert len(results) > 1
