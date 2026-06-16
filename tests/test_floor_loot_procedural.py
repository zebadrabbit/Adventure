import json

from app import db
from app.models.loot import DungeonLoot


def test_dungeon_loot_can_store_instance_without_item_id():
    inst = {
        "uid": "abc123",
        "base": "shortsword",
        "slot": "weapon",
        "name": "Test Blade",
        "rarity": "rare",
        "value": 100,
    }
    row = DungeonLoot(seed=12345, x=1, y=2, z=0, item_id=None, instance_json=json.dumps(inst))
    db.session.add(row)
    db.session.commit()
    fetched = DungeonLoot.query.filter_by(seed=12345, x=1, y=2).first()
    assert fetched.item_id is None
    assert json.loads(fetched.instance_json)["uid"] == "abc123"
