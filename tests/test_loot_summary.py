from app import app, db
from app.models.models import Item
from app.services.loot_service import _loot_summary


def _ensure_item(slug, name):
    with app.app_context():
        item = Item.query.filter_by(slug=slug).first()
        if not item:
            item = Item(slug=slug, name=name, type="material", value_copper=1)
            db.session.add(item)
            db.session.commit()
        return item


def test_loot_summary_empty_rewards():
    assert _loot_summary({}) == "no loot"
    assert _loot_summary({"items": {}, "gear": []}) == "no loot"


def test_loot_summary_items_only_uses_display_name():
    _ensure_item("cloth-slippers", "Cloth Slippers")
    with app.app_context():
        summary = _loot_summary({"items": {"cloth-slippers": 2}, "gear": []})
    assert summary == "2× Cloth Slippers"


def test_loot_summary_items_only_falls_back_to_slug_when_item_missing():
    with app.app_context():
        summary = _loot_summary({"items": {"unknown-widget": 1}, "gear": []})
    assert summary == "1× Unknown Widget"


def test_loot_summary_gear_only():
    gear = [{"name": "Sturdy Boots", "rarity": "rare", "base": "boots", "uid": "abc123"}]
    with app.app_context():
        summary = _loot_summary({"items": {}, "gear": gear})
    assert summary == "Sturdy Boots (rare)"


def test_loot_summary_boss_with_items_and_gear():
    _ensure_item("boss-treasure-token", "Boss Treasure Token")
    gear = [
        {"name": "Elite Gauntlets", "rarity": "epic", "base": "gauntlets", "uid": "def456"},
        {"name": "Elite Boots", "rarity": "legendary", "base": "boots", "uid": "ghi789"},
    ]
    with app.app_context():
        summary = _loot_summary({"items": {"boss-treasure-token": 1}, "gear": gear})
    assert summary == "1× Boss Treasure Token, Elite Gauntlets (epic), Elite Boots (legendary)"


def test_loot_summary_no_rewards_argument_defaults_are_dict_like():
    # Guard against passing None or missing keys entirely
    assert _loot_summary({"rolls": {"seed": 1}}) == "no loot"
