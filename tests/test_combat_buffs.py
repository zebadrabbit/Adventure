"""A drunk buff has to reach the numbers combat reads, and leave when it should.

The resolver tests prove a potion *resolves* to an effect. That is not the same
as the effect doing anything: before this, five families resolved to nothing at
all, and an effect sitting in a participant's `effects` list changes no damage
unless something folds it into the derived stats every code path actually reads.

Two rules, both the owner's:
  * expiry rides the existing game clock -- no second timebase;
  * **combat buffs fall off when combat ends, regardless of ticks remaining.**

The second is implemented by omission rather than by a clearing pass: the
end-of-combat write-back deletes every persisted effect row and simply declines
to re-add the combat-scoped ones. That is easy to get right and easy to break
silently, which is why it is pinned here.
"""

import pytest

from app.services.combat_service import PERSISTED_EFFECT_NAMES, apply_effect_modifiers
from app.services.item_effects import resolve_potion_effect
from app.services.status_effects import replace_effect


def _member(**over):
    m = {
        "name": "Tester",
        "attack": 20,
        "defense": 10,
        "speed": 12,
        "resist_points": 0,
        "resistances": {},
        "effects": [],
    }
    m.update(over)
    return m


def _drink(member, slug):
    effect = resolve_potion_effect(slug)
    assert effect and effect["kind"] == "status", slug
    member["effects"] = replace_effect(member["effects"], effect["name"], effect["ticks"], **effect["data"])
    return apply_effect_modifiers(member)


def test_an_attack_buff_raises_attack():
    member = _member()

    _drink(member, "potion_buff_attack_l10")

    assert member["attack"] == 30, "the buff never reached the stat combat reads"


def test_a_speed_buff_raises_speed_and_leaves_attack_alone():
    member = _member()

    _drink(member, "potion_buff_speed_l20")

    assert member["speed"] == 20
    assert member["attack"] == 20


def test_drinking_the_same_buff_twice_replaces_rather_than_stacks():
    """replace_effect, not add_effect. Stacking is semantics nobody asked for,
    and `add_effect` has no callers anywhere in the app."""
    member = _member()

    _drink(member, "potion_buff_attack_l10")
    _drink(member, "potion_buff_attack_l10")

    assert member["attack"] == 30, "the buff stacked with itself"
    assert len([e for e in member["effects"] if e["name"] == "stat_buff"]) == 1


def test_folding_is_idempotent():
    """apply_effect_modifiers runs at hydration, on drinking, and at turn start.
    If it were not idempotent a buff would grow every time a turn began."""
    member = _member()
    _drink(member, "potion_buff_attack_l10")

    for _ in range(5):
        apply_effect_modifiers(member)

    assert member["attack"] == 30


def test_an_expired_buff_stops_applying():
    member = _member()
    _drink(member, "potion_buff_attack_l10")
    assert member["attack"] == 30

    for eff in member["effects"]:
        eff["remaining"] = 0
    apply_effect_modifiers(member)

    assert member["attack"] == 20, "an expired buff was still being counted"


def test_a_resist_buff_converts_points_to_a_multiplier():
    """apply_resistances takes multipliers, not points. Handing it raw points
    would multiply incoming damage rather than reduce it."""
    member = _member()

    _drink(member, "potion_resist_fire_l10")

    fire = member["resistances"].get("fire")
    assert fire is not None, f"no fire resistance was produced: {member['resistances']}"
    assert 0 < fire < 1, f"resistance must be a damage multiplier below 1, got {fire}"


def test_resistance_is_floored_so_stacking_cannot_reach_immunity():
    """A tier-20 draught is exactly 60 points, which lands on the cap."""
    member = _member(resist_points=60)  # as if from gear
    _drink(member, "potion_resist_fire_l20")  # another 60

    assert member["resistances"]["fire"] >= 0.4, "stacked resistance passed the floor"


def test_gear_and_potion_resistance_sum_before_converting():
    """Summed points, not multiplied multipliers -- 0.8 * 0.75 = 0.60 would
    slip past a 0.4 floor that each source individually respects."""
    gear_only = apply_effect_modifiers(_member(resist_points=30))["resistances"]["fire"]
    both = _drink(_member(resist_points=30), "potion_resist_fire_l10")["resistances"]["fire"]

    assert both < gear_only, "the potion added nothing on top of gear"


# --- the scope rule --------------------------------------------------------


@pytest.mark.parametrize("family", ["buff_attack", "buff_defense", "buff_speed", "resist_fire", "resist_poison"])
def test_every_buff_is_combat_scoped(family):
    assert resolve_potion_effect(f"potion_{family}_l5")["data"]["scope"] == "combat"


def test_buff_names_are_hydrated_into_combat():
    """A buff drunk in the dungeon must be carried into the next fight. If its
    name is missing from this tuple the row exists and is simply ignored."""
    for name in ("stat_buff", "resist_buff"):
        assert name in PERSISTED_EFFECT_NAMES, f"{name} would not survive into a fight"


def test_poison_and_regen_are_still_world_scoped():
    """The pre-existing effects must not have been swept into combat scope --
    a camp's regen buff is supposed to outlive the walk to the next fight."""
    regen = resolve_potion_effect("potion-regen")

    assert regen["name"] == "regen_buff"
    assert (regen.get("data") or {}).get("scope") != "combat"
