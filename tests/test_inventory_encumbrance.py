import json

import pytest

from app import app, db
from app.models.models import Item
from tests.factories import create_character, create_instance, create_user, ensure_item


def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.mark.db_isolation
def test_stacking_and_encumbrance(client):
    with app.app_context():
        u = create_user("stacker", "pw")
        create_character(u, "CarryOne", "fighter", items=[])
        sword = ensure_item("short-sword")
        sword.weight = 5.0
        db.session.commit()
    # Login
    login(client, "stacker", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        # Put character in party
        sess["party"] = [{"id": 1, "name": "CarryOne", "class": "Fighter", "hp": 10, "mana": 5}]
    # Seed a dungeon instance and loot row manually
    from app.models.loot import DungeonLoot

    with app.app_context():
        inst = create_instance(u, seed=9999)
        sword = Item.query.filter_by(slug="short-sword").first()
        for i in range(3):
            db.session.add(DungeonLoot(seed=inst.seed, x=i + 1, y=1, z=0, item_id=sword.id, claimed=False))
        db.session.commit()
        with client.session_transaction() as sess:
            sess["dungeon_instance_id"] = inst.id
            sess["dungeon_seed"] = inst.seed
    # Claim each loot piece, last one may exceed capacity
    loot_resp = client.get("/api/dungeon/loot")
    data = loot_resp.get_json()
    loot_ids = [loot_entry["id"] for loot_entry in data["loot"]]  # rename for E741 clarity
    results = []
    for lid in loot_ids:
        r = client.post(f"/api/dungeon/loot/claim/{lid}", json={"character_id": 1})
        results.append((lid, r.status_code, r.get_json()))
    # Fetch character state
    state = client.get("/api/characters/state").get_json()
    chars = state["characters"]
    assert chars
    bag = chars[0]["bag"]
    # Sword should appear once with qty >=1
    sword_entries = [b for b in bag if b["slug"] == "short-sword"]
    assert sword_entries
    qty = sword_entries[0]["qty"]
    assert qty >= 1
    # Encumbrance must be present
    enc = chars[0]["encumbrance"]
    assert "capacity" in enc and "weight" in enc


@pytest.mark.db_isolation
def test_character_state_with_equipped_gear_instance_does_not_crash(client):
    """Procedural gear instances stored in `gear[slot]` are dicts, not slugs.

    `_computed_stats` must not crash when looking up a dict-shaped gear value
    (regression: TypeError: unhashable type: 'dict').
    """
    with app.app_context():
        u = create_user("instance-equipper", "pw")
        char = create_character(u, "InstanceWielder", "fighter", items=[])
        char.gear = json.dumps(
            {
                "weapon": {
                    "uid": "test-uid-equipped",
                    "slug": "rare-sword",
                    "name": "Test Rare Sword",
                    "type": "weapon",
                    "slot": "weapon",
                    "rarity": "rare",
                    "level": 5,
                    "durability": 50,
                    "max_durability": 100,
                    "value": 500,
                    "weight": 3.0,
                    "affixes": [{"stat": "str", "val": 4}],
                }
            }
        )
        db.session.commit()
        char_id = char.id

    login(client, "instance-equipper", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    r = client.get("/api/characters/state")
    assert r.status_code == 200
    chars = r.get_json()["characters"]
    assert chars and "warning" not in chars[0]

    r2 = client.get(f"/api/characters/{char_id}")
    assert r2.status_code == 200
    assert r2.get_json()["gear"]["weapon"]["uid"] == "test-uid-equipped"


@pytest.mark.db_isolation
def test_character_state_exposes_stat_points_and_xp_thresholds(client):
    with app.app_context():
        u = create_user("progression-checker", "pw")
        char = create_character(u, "ProgressionChecker", "fighter", items=[])
        char.level = 3
        char.xp = 1000
        char.stat_points = 4
        db.session.commit()
        char_id = char.id

    login(client, "progression-checker", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    from app.models.xp import xp_for_level

    expected_current = xp_for_level(3)
    expected_next = xp_for_level(4)

    r = client.get(f"/api/characters/{char_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["stat_points"] == 4
    assert body["xp_for_current_level"] == expected_current
    assert body["xp_for_next_level"] == expected_next

    r2 = client.get("/api/characters/state")
    assert r2.status_code == 200
    chars = r2.get_json()["characters"]
    match = next(c for c in chars if c["id"] == char_id)
    assert match["stat_points"] == 4
    assert match["xp_for_current_level"] == expected_current
    assert match["xp_for_next_level"] == expected_next
