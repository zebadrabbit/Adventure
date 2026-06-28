def test_deposit_currency(client, logged_in_user, test_character_with_coins):
    char = test_character_with_coins  # has 2g 0s 0c in stats
    resp = client.post(
        "/api/hoard/currency",
        json={
            "character_id": char.id,
            "direction": "deposit",
            "gold": 1,
            "silver": 0,
            "copper": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["hoard_copper"] == 10000  # 1g in copper
    assert data["char_gold"] == 1  # 1g remains on char


def test_withdraw_currency(client, logged_in_user, test_character, test_hoard_with_copper):
    # hoard has 5000c (50s), char has 0
    resp = client.post(
        "/api/hoard/currency",
        json={
            "character_id": test_character.id,
            "direction": "withdraw",
            "gold": 0,
            "silver": 50,
            "copper": 0,
        },
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["success"] is True
    assert data["hoard_copper"] == 0
    assert data["char_silver"] == 50


def test_deposit_insufficient_funds(client, logged_in_user, test_character):
    resp = client.post(
        "/api/hoard/currency",
        json={
            "character_id": test_character.id,
            "direction": "deposit",
            "gold": 100,
            "silver": 0,
            "copper": 0,
        },
    )
    assert resp.status_code == 400


def test_withdraw_insufficient_hoard(client, logged_in_user, test_character):
    resp = client.post(
        "/api/hoard/currency",
        json={
            "character_id": test_character.id,
            "direction": "withdraw",
            "gold": 999,
            "silver": 0,
            "copper": 0,
        },
    )
    assert resp.status_code == 400
