import json

from app.services.loot_service import add_gear_to_character


class _Char:
    def __init__(self):
        self.items = "[]"


def test_add_gear_appends_instance():
    c = _Char()
    inst = {"uid": "abc", "slot": "weapon", "name": "Brutal Shortsword", "affixes": []}
    add_gear_to_character(c, [inst])
    items = json.loads(c.items)
    assert any(isinstance(i, dict) and i.get("uid") == "abc" for i in items)


def test_add_gear_preserves_existing_consumables():
    c = _Char()
    c.items = json.dumps([{"slug": "potion-healing", "qty": 2}])
    add_gear_to_character(c, [{"uid": "z", "slot": "ring", "affixes": []}])
    items = json.loads(c.items)
    assert any(i.get("slug") == "potion-healing" for i in items)
    assert any(i.get("uid") == "z" for i in items)
