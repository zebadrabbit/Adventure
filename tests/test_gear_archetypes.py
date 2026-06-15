from app.loot.data.archetypes import ARCHETYPES, archetypes_for_slot, SLOTS


def test_eight_slots_present():
    assert set(SLOTS) == {"weapon", "offhand", "head", "chest", "hands", "feet", "ring", "amulet"}
    for slot in SLOTS:
        assert archetypes_for_slot(slot), f"no archetypes for {slot}"


def test_archetype_shape():
    for key, a in ARCHETYPES.items():
        assert a["slot"] in SLOTS
        assert a["base_name"]
        assert a["category"]
        # weapons have a damage range, armor has an armor base, jewelry neither
        if a["slot"] == "weapon":
            assert a["damage"][0] <= a["damage"][1]


def test_shortsword_exists():
    assert ARCHETYPES["shortsword"]["slot"] == "weapon"
    assert ARCHETYPES["shortsword"]["category"] == "blade"
