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
