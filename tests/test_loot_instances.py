import random

from app.services.loot_service import roll_loot


def _monster(level=5, boss=False):
    return {"slug": "m", "name": "M", "level": level, "boss": boss, "loot_table": "", "special_drop_slug": None}


def test_roll_loot_includes_generated_gear():
    out = roll_loot(_monster(level=8), rng=random.Random(1))
    gear = out.get("gear", [])
    assert isinstance(gear, list)
    assert gear and all("affixes" in g and "slot" in g for g in gear)


def test_boss_skews_higher_rarity():
    from app.loot.data.rarities import RARITY_ORDER

    idx = {r: i for i, r in enumerate(RARITY_ORDER)}
    boss_max = 0
    for s in range(30):
        out = roll_loot(_monster(level=15, boss=True), rng=random.Random(s))
        for g in out.get("gear", []):
            boss_max = max(boss_max, idx[g["rarity"]])
    assert boss_max >= idx["rare"]
