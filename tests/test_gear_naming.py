from app.loot.naming import compose_name


def test_prefix_base_suffix():
    assert compose_name("Brutal", "Shortsword", "of the Hawk") == "Brutal Shortsword of the Hawk"


def test_bare_base():
    assert compose_name(None, "Shortsword", None) == "Shortsword"


def test_prefix_only():
    assert compose_name("Sturdy", "Plate Helm", None) == "Sturdy Plate Helm"


def test_suffix_only():
    assert compose_name(None, "Oak Wand", "of the Owl") == "Oak Wand of the Owl"
