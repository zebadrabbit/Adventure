import json
import json as _json

from app import db
from app.loot.generator import LootConfig, generate_loot_for_seed
from app.models.loot import DungeonLoot
from app.models.models import GameConfig


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


def _set_floor_loot(chance):
    GameConfig.set("floor_loot", _json.dumps({"procedural_gear_chance": chance}))


def _tiles(n=40):
    return [(i, 0) for i in range(n)]


def test_all_procedural_when_chance_one():
    _set_floor_loot(1.0)
    seed = 777001
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    created = generate_loot_for_seed(cfg, _tiles())
    assert created > 0
    rows = DungeonLoot.query.filter_by(seed=seed).all()
    assert rows and all(r.item_id is None and r.instance_json for r in rows)
    assert all(_json.loads(r.instance_json).get("uid") for r in rows)


def test_all_catalog_when_chance_zero():
    _set_floor_loot(0.0)
    seed = 777002
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    created = generate_loot_for_seed(cfg, _tiles())
    assert created > 0
    rows = DungeonLoot.query.filter_by(seed=seed).all()
    assert rows and all(r.item_id is not None and r.instance_json is None for r in rows)


def test_placement_is_deterministic():
    _set_floor_loot(1.0)
    seed = 777003
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    generate_loot_for_seed(cfg, _tiles())
    first = sorted(
        (r.x, r.y, _json.loads(r.instance_json)["uid"]) for r in DungeonLoot.query.filter_by(seed=seed).all()
    )
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    generate_loot_for_seed(cfg, _tiles())
    second = sorted(
        (r.x, r.y, _json.loads(r.instance_json)["uid"]) for r in DungeonLoot.query.filter_by(seed=seed).all()
    )
    assert first == second
