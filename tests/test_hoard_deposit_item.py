import uuid

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
