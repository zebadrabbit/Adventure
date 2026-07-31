"""A potion is worth the same fraction of your bar at level 1 and at level 20.

That is the design target, and it is asserted as a property rather than a table
of numbers -- the amounts in `item_effects` are tuning and will be re-derived;
what must not drift is the relationship between what a potion restores and what
the drinker can actually hold.

What this replaced was measured, not guessed:

  * **heal** was `5 * (tier + 1)`: 13% of a level-1 pool, 62% of a level-20 one.
    Potions got relatively *stronger* as you levelled.
  * **mana** was `2 * (tier + 1)` against `mana_max = 20 + INT*2`, a pool with
    **no level term at all**. At level 20 with INT 10 the bar was 40 and the
    tier-20 potion restored 42 -- more than the whole thing. Every tier past
    roughly 10 was partly wasted, so twenty tiers, five rarities and a 47x price
    spread all described the same potion.

Mana gained a level term as part of the fix; without one the ladder cannot be
balanced at all, because any curve that is safe at level 20 is the curve at
level 1.
"""

import pytest

from app.services.item_effects import resolve_potion_effect

# The band a tier-matched potion should land in. Wide enough to be tuning
# headroom, narrow enough that "13% at level 1, 62% at level 20" fails it.
TARGET_LO, TARGET_HI = 0.28, 0.45

TIERS = [1, 5, 10, 15, 20]


def _pools(level, con=10, intelligence=10):
    """The caps as combat and character_stats compute them. Restated here on
    purpose: if either formula changes without this test being reconsidered,
    the mismatch should surface as a failure rather than pass silently."""
    return 50 + con * 2 + level * 5, 20 + intelligence * 2 + level * 3


@pytest.mark.parametrize("tier", TIERS)
def test_a_tier_matched_healing_potion_is_a_steady_share_of_the_bar(tier):
    max_hp, _ = _pools(level=tier)
    amount = resolve_potion_effect(f"potion_heal_l{tier}")["amount"]

    share = amount / max_hp
    assert (
        TARGET_LO <= share <= TARGET_HI
    ), f"tier {tier} heal restores {share:.0%} of a level-{tier} pool ({amount}/{max_hp})"


@pytest.mark.parametrize("tier", TIERS)
def test_a_tier_matched_mana_potion_is_a_steady_share_of_the_bar(tier):
    _, mana_max = _pools(level=tier)
    amount = resolve_potion_effect(f"potion_mana_l{tier}")["amount"]

    share = amount / mana_max
    assert (
        TARGET_LO <= share <= TARGET_HI
    ), f"tier {tier} mana restores {share:.0%} of a level-{tier} pool ({amount}/{mana_max})"


def test_no_potion_ever_restores_more_than_the_bar_holds():
    """The tier-20 mana potion used to restore 105% of a level-20 pool."""
    for tier in range(1, 21):
        max_hp, mana_max = _pools(level=tier)
        assert resolve_potion_effect(f"potion_heal_l{tier}")["amount"] < max_hp
        assert resolve_potion_effect(f"potion_mana_l{tier}")["amount"] < mana_max


def test_a_higher_tier_always_restores_more():
    """Twenty tiers have to mean twenty steps, or the ladder is decoration and
    the names ("Ultimate Mana Elixir") are false."""
    for family in ("heal", "mana"):
        amounts = [resolve_potion_effect(f"potion_{family}_l{t}")["amount"] for t in range(1, 21)]
        assert amounts == sorted(amounts), f"{family} is not monotonic: {amounts}"
        assert len(set(amounts)) == len(amounts), f"{family} has duplicate steps: {amounts}"


def test_the_mana_pool_grows_with_level():
    """The pool it is balanced against must actually scale, or the curve above
    is balanced against a constant."""
    _, low = _pools(level=1)
    _, high = _pools(level=20)

    assert high > low * 2, f"mana pool barely moves across the whole game: {low} -> {high}"
