"""One place decides what a potion does.

Before this, three code paths each guessed. combat_service.player_use_item
matched three hyphenated slugs exactly; inventory_api.consume_item matched
unanchored substrings ("healing", which the catalogue spells "heal"), so 127 of
154 potions were removed from the bag for zero effect; and the two disagreed on
magnitude by 5x for the one slug they shared.

Spec: docs/superpowers/specs/2026-07-28-combat-item-usage-design.md
"""

import pytest

from app.services.item_effects import REFUSAL_NO_EFFECT, resolve_potion_effect


@pytest.mark.parametrize(
    "slug,expected",
    [
        ("potion_heal_l1", {"kind": "restore_hp", "amount": 10}),
        ("potion_heal_l2", {"kind": "restore_hp", "amount": 15}),
        ("potion_heal_l20", {"kind": "restore_hp", "amount": 105}),
        ("potion_mana_l1", {"kind": "restore_mp", "amount": 4}),
        ("potion_mana_l20", {"kind": "restore_mp", "amount": 42}),
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
        "potion_buff_attack_l3",
        "potion_buff_defense_l1",
        "potion_buff_speed_l20",
        "potion_resist_fire_l2",
        "potion_resist_cold_l1",
        "potion_resist_lightning_l5",
        "potion_resist_poison_l4",
        "potion_antidote_l1",
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
    "slug",
    ["", None, "not-a-potion", "potion_heal", "potion_heal_l", "potion_heal_lx", "sword_of_heal_l3", "POTION_HEAL_L3"],
)
def test_malformed_input_resolves_to_nothing_without_raising(slug):
    assert resolve_potion_effect(slug) is None


def test_tier_is_read_from_the_suffix_not_a_substring():
    """`potion_heal_l11` is tier 11, not tier 1 -- an anchored parse, not a scan."""
    assert resolve_potion_effect("potion_heal_l11")["amount"] == 60


def test_a_refusal_sentence_exists_and_reads_as_prose():
    assert REFUSAL_NO_EFFECT
    assert REFUSAL_NO_EFFECT[0].isupper()
    assert REFUSAL_NO_EFFECT.endswith(".")
    assert "_" not in REFUSAL_NO_EFFECT, "a refusal is prose, not a machine code"


def test_every_catalogue_potion_either_resolves_or_is_refused(test_app):
    """No potion may raise, and the implemented count must be deliberate.

    This is the guard against the original bug: a slug the resolver does not
    recognise must produce None, never an exception and never a wrong effect.
    """
    from app.models.models import Item

    with test_app.app_context():
        slugs = [i.slug for i in Item.query.filter_by(type="potion").all()]

    assert len(slugs) >= 150, "catalogue shrank unexpectedly; check the seed"

    resolved = {s: resolve_potion_effect(s) for s in slugs}
    implemented = {s: e for s, e in resolved.items() if e is not None}

    # 20 heal + 20 mana + 3 legacy hyphenated
    assert len(implemented) == 43, sorted(implemented)
    assert all(e["kind"] in ("restore_hp", "restore_mp", "status") for e in implemented.values())
