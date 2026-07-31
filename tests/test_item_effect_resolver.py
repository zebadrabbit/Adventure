"""One place decides what a potion does.

Before this, three code paths each guessed. combat_service.player_use_item
matched three hyphenated slugs exactly; inventory_api.consume_item matched
unanchored substrings ("healing", which the catalogue spells "heal"), so 127 of
154 potions were removed from the bag for zero effect; and the two disagreed on
magnitude by 5x for the one slug they shared.

Spec: docs/superpowers/specs/2026-07-28-combat-item-usage-design.md
"""

import re

import pytest

from app.services.item_effects import REFUSAL_NO_EFFECT, resolve_potion_effect


@pytest.mark.parametrize(
    "slug,expected",
    [
        # Amounts derived from the curve, not restated: they are tuning values
        # aimed at ~35% of the drinker's pool (see item_effects). What must hold
        # is that they rise with the tier and land where the curve says.
        ("potion_heal_l1", {"kind": "restore_hp", "amount": 24 + 2 * 1}),
        ("potion_heal_l2", {"kind": "restore_hp", "amount": 24 + 2 * 2}),
        ("potion_heal_l20", {"kind": "restore_hp", "amount": 24 + 2 * 20}),
        ("potion_mana_l1", {"kind": "restore_mp", "amount": 14 + 1}),
        ("potion_mana_l20", {"kind": "restore_mp", "amount": 14 + 20}),
        ("potion-healing", {"kind": "restore_hp", "amount": 25}),
        ("potion-mana", {"kind": "restore_mp", "amount": 5}),
    ],
)
def test_implemented_families_resolve(slug, expected):
    assert resolve_potion_effect(slug) == expected


def test_legacy_regen_resolves_to_a_status_effect():
    effect = resolve_potion_effect("potion-regen")

    assert effect["kind"] == "status"
    assert effect["name"] == "regen_buff"
    assert effect["ticks"] == 5
    assert effect["data"] == {"hp_mult": 3.0, "mp_mult": 3.0}


@pytest.mark.parametrize(
    "slug",
    [
        # No mechanic yet, and none of them can be re-themed onto an existing
        # one without a design decision. Refused, never silently destroyed.
        "potion_stamina_l3",
        "potion_perception_l5",
        "potion_group_battle_l2",
        "potion_invis_l1",
        "potion_luck_l4",
        "potion_regen_l2",
    ],
)
def test_unimplemented_families_resolve_to_nothing(slug):
    """Refused, not silently destroyed. Each of these needs a mechanic that
    does not exist yet -- see the spec's family table."""
    assert resolve_potion_effect(slug) is None


@pytest.mark.parametrize(
    "slug,name,expected_data",
    [
        ("potion_buff_attack_l10", "stat_buff", {"scope": "combat", "mods": {"attack": 10}}),
        ("potion_buff_defense_l1", "stat_buff", {"scope": "combat", "mods": {"defense": 1}}),
        # Speed scales at 0.4/tier: the stat is 8 + DEX//2 and barely moves, so
        # a flat +tier would dwarf it while being trivial on attack.
        ("potion_buff_speed_l20", "stat_buff", {"scope": "combat", "mods": {"speed": 8}}),
        # 3 points per tier, so tier 20 lands exactly on the 60-point cap.
        ("potion_resist_fire_l20", "resist_buff", {"scope": "combat", "element": "fire", "resist_points": 60}),
        # "cold" is not an element this engine emits -- the spells say "ice",
        # and apply_resistances silently drops keys it does not know, so
        # keying this family on "cold" would be a five-potion no-op.
        ("potion_resist_cold_l5", "resist_buff", {"scope": "combat", "element": "ice", "resist_points": 15}),
    ],
)
def test_buff_families_resolve_to_scoped_effects(slug, name, expected_data):
    effect = resolve_potion_effect(slug)

    assert effect["kind"] == "status"
    assert effect["name"] == name
    assert effect["ticks"] > 0
    assert effect["data"] == expected_data


def test_every_buff_is_combat_scoped():
    """Combat scope is what makes a buff fall off when the fight ends: the
    write-back deletes these rows and declines to re-add them. A buff that
    resolved without a scope would default to world and outlive its fight."""
    for family in ("buff_attack", "buff_defense", "buff_speed", "resist_fire", "resist_poison"):
        effect = resolve_potion_effect(f"potion_{family}_l5")
        assert effect["data"]["scope"] == "combat", family


def test_antidote_cures_poison():
    effect = resolve_potion_effect("potion_antidote_l1")

    assert effect == {"kind": "cure", "removes": ["poison"]}


def test_a_higher_tier_buff_is_stronger():
    for family, stat in (("buff_attack", "attack"), ("buff_defense", "defense"), ("buff_speed", "speed")):
        values = [resolve_potion_effect(f"potion_{family}_l{t}")["data"]["mods"][stat] for t in range(1, 21)]
        assert values == sorted(values), f"{family} is not monotonic: {values}"
        assert values[-1] > values[0], family


@pytest.mark.parametrize(
    "slug",
    ["", None, "not-a-potion", "potion_heal", "potion_heal_l", "potion_heal_lx", "sword_of_heal_l3", "POTION_HEAL_L3"],
)
def test_malformed_input_resolves_to_nothing_without_raising(slug):
    assert resolve_potion_effect(slug) is None


def test_tier_is_read_from_the_suffix_not_a_substring():
    """`potion_heal_l11` is tier 11, not tier 1 -- an anchored parse, not a scan.

    Asserted as a relationship rather than a magic number: what matters is that
    the parse reads 11, not whatever the heal curve currently pays for it."""
    assert resolve_potion_effect("potion_heal_l11")["amount"] == 24 + 2 * 11
    assert resolve_potion_effect("potion_heal_l11")["amount"] != resolve_potion_effect("potion_heal_l1")["amount"]


def test_a_refusal_sentence_exists_and_reads_as_prose():
    assert REFUSAL_NO_EFFECT
    assert REFUSAL_NO_EFFECT[0].isupper()
    assert REFUSAL_NO_EFFECT.endswith(".")
    assert "_" not in REFUSAL_NO_EFFECT, "a refusal is prose, not a machine code"


def test_every_catalogue_potion_either_resolves_or_is_refused(test_app):
    """No potion may raise, and exactly the implemented families may resolve.

    Asserted as a property of whatever catalogue is loaded rather than a fixed
    count: a db_isolation-marked test elsewhere in the suite reseeds a smaller
    placeholder catalogue, so a hardcoded number makes this test order-dependent.

    (In the full 154-potion seed this works out to 20 heal + 20 mana + 3
    legacy hyphenated = 43, tiers contiguous 1..20 for both families --
    verified directly against the database, not asserted here.)
    """
    from app.models.models import Item

    with test_app.app_context():
        slugs = [i.slug for i in Item.query.filter_by(type="potion").all()]

    assert slugs, "no potions in the catalogue at all"

    expected = {s for s in slugs if re.fullmatch(r"potion_(heal|mana)_l\d+", s)} | (
        {"potion-healing", "potion-mana", "potion-regen"} & set(slugs)
    )
    resolved = {s: resolve_potion_effect(s) for s in slugs}
    implemented = {s: e for s, e in resolved.items() if e is not None}

    assert set(implemented) == expected
    assert all(e["kind"] in ("restore_hp", "restore_mp", "status") for e in implemented.values())
