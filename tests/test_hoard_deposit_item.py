import json
import uuid

from app import db
from tests.factories import create_character, create_user


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def test_deposit_item_moves_item_to_hoard(client):
    """Test that an item can be deposited from a character's bag to the hoard."""
    user = create_user("deposit_a_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=["potion-healing"])
    _login(client, user)

    resp = client.post("/api/hoard/deposit-item", json={"character_id": char.id, "slug": "potion-healing"})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["success"] is True
    assert any(i.get("slug") == "potion-healing" for i in data["hoard_items"])
    assert not any(i.get("slug") == "potion-healing" for i in data["char_bag"])


def test_deposit_item_rejects_unknown_character(client):
    """Test that depositing to a non-existent character returns 404."""
    user = create_user("deposit_b_" + uuid.uuid4().hex[:8])
    _login(client, user)

    resp = client.post("/api/hoard/deposit-item", json={"character_id": 99999, "slug": "potion-healing"})
    assert resp.status_code == 404


def test_deposit_item_rejects_missing_item(client):
    """Test that depositing a non-existent item returns 400."""
    user = create_user("deposit_c_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=[])
    _login(client, user)

    resp = client.post("/api/hoard/deposit-item", json={"character_id": char.id, "slug": "nonexistent-slug"})
    assert resp.status_code == 400


def test_get_hoard_party_gold_from_stats_json(client):
    """Test that GET /api/hoard reads party gold from character stats JSON."""
    user = create_user("hoard_stats_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero")
    # Set stats with gold, silver, copper values
    char.stats = json.dumps({"gold": 1, "silver": 0, "copper": 0})
    db.session.commit()
    _login(client, user)

    resp = client.get("/api/hoard")
    assert resp.status_code == 200
    data = resp.get_json()
    # 1 gold = 10000 copper
    assert data["party_gold"] == 10000
    assert "1g" in data["party_gold_display"]


def test_get_hoard_party_gold_with_multiple_coin_types(client):
    """Test that GET /api/hoard correctly sums gold, silver, and copper."""
    user = create_user("hoard_multi_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero")
    # 1 gold + 5 silver + 50 copper = 10000 + 500 + 50 = 10550
    char.stats = json.dumps({"gold": 1, "silver": 5, "copper": 50})
    db.session.commit()
    _login(client, user)

    resp = client.get("/api/hoard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["party_gold"] == 10550
    assert "1g" in data["party_gold_display"]
    assert "5s" in data["party_gold_display"]
    assert "50c" in data["party_gold_display"]


def test_get_hoard_party_gold_fallback_to_all_characters(client):
    """Test that GET /api/hoard falls back to all owned characters when no party in session."""
    user = create_user("hoard_fallback_" + uuid.uuid4().hex[:8])
    char1 = create_character(user, name="Hero1")
    char2 = create_character(user, name="Hero2")
    char1.stats = json.dumps({"gold": 1, "silver": 0, "copper": 0})
    char2.stats = json.dumps({"gold": 2, "silver": 0, "copper": 0})
    db.session.commit()
    _login(client, user)

    resp = client.get("/api/hoard")
    assert resp.status_code == 200
    data = resp.get_json()
    # 1 gold + 2 gold = 3 gold = 30000 copper
    assert data["party_gold"] == 30000
