import json

import pytest

from app import app, db
from tests.factories import create_character, create_user


def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.mark.db_isolation
def test_character_state_reads_coins_from_stats_json(client):
    """Verify that coins are read from char.stats JSON, not from unused ch.gold column."""
    with app.app_context():
        u = create_user("coin-checker", "pw")
        char = create_character(u, "CoinMaster", "fighter", items=[])
        # Set coins in the stats JSON
        stats = json.loads(char.stats) if char.stats else {}
        stats["gold"] = 2
        stats["silver"] = 5
        stats["copper"] = 10
        char.stats = json.dumps(stats)
        db.session.commit()
        char_id = char.id

    login(client, "coin-checker", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    # Test single character endpoint
    r = client.get(f"/api/characters/{char_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["stats"]["gold"] == 2
    assert body["stats"]["silver"] == 5
    assert body["stats"]["copper"] == 10

    # Test list characters endpoint
    r2 = client.get("/api/characters/state")
    assert r2.status_code == 200
    chars = r2.get_json()["characters"]
    match = next(c for c in chars if c["id"] == char_id)
    assert match["stats"]["gold"] == 2
    assert match["stats"]["silver"] == 5
    assert match["stats"]["copper"] == 10


@pytest.mark.db_isolation
def test_character_state_handles_missing_coin_data(client):
    """Verify that missing coin data defaults to 0."""
    with app.app_context():
        u = create_user("no-coins", "pw")
        char = create_character(u, "NoCoins", "fighter", items=[])
        # stats JSON exists but has no coin fields
        stats = {"str": 10, "dex": 12}
        char.stats = json.dumps(stats)
        db.session.commit()
        char_id = char.id

    login(client, "no-coins", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    # Test single character endpoint
    r = client.get(f"/api/characters/{char_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["stats"]["gold"] == 0
    assert body["stats"]["silver"] == 0
    assert body["stats"]["copper"] == 0

    # Test list characters endpoint
    r2 = client.get("/api/characters/state")
    assert r2.status_code == 200
    chars = r2.get_json()["characters"]
    match = next(c for c in chars if c["id"] == char_id)
    assert match["stats"]["gold"] == 0
    assert match["stats"]["silver"] == 0
    assert match["stats"]["copper"] == 0
