from app.services.loot_service import gear_bonuses


def test_sums_equipped_affixes():
    gear = {
        "weapon": {"slot": "weapon", "affixes": [{"stat": "damage", "val": 4}, {"stat": "dex", "val": 8}]},
        "amulet": {"slot": "amulet", "affixes": [{"stat": "dex", "val": 3}, {"stat": "con", "val": 5}]},
    }
    b = gear_bonuses(gear)
    assert b["dex"] == 11
    assert b["damage"] == 4
    assert b["con"] == 5


def test_empty_gear():
    assert gear_bonuses({}) == {}
    assert gear_bonuses(None) == {}


def test_ignores_malformed_entries():
    gear = {"weapon": "not-a-dict", "head": {"affixes": "bad"}}
    assert gear_bonuses(gear) == {}
