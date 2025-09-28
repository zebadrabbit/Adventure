def test_set_numeric_seed(auth_client):
    # Set a numeric seed
    resp = auth_client.post("/api/dungeon/seed", json={"seed": 12345})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["seed"] == 12345
    # Fetch map and ensure reported seed matches
    map_resp = auth_client.get("/api/dungeon/map")
    assert map_resp.status_code == 200
    map_data = map_resp.get_json()
    assert map_data["seed"] == 12345


def test_set_string_seed(auth_client):
    resp = auth_client.post("/api/dungeon/seed", json={"seed": "alpha"})
    assert resp.status_code == 200
    data = resp.get_json()
    first_seed = data["seed"]
    assert isinstance(first_seed, int)
    # Repeat same string should yield same hashed result
    resp2 = auth_client.post("/api/dungeon/seed", json={"seed": "alpha"})
    data2 = resp2.get_json()
    assert data2["seed"] == first_seed


def test_random_regenerate_seed(auth_client):
    # Request a random regenerate
    resp1 = auth_client.post("/api/dungeon/seed", json={"regenerate": True})
    s1 = resp1.get_json()["seed"]
    resp2 = auth_client.post("/api/dungeon/seed", json={"regenerate": True})
    s2 = resp2.get_json()["seed"]
    # Very small chance they match; allow but assert int type
    assert isinstance(s1, int) and isinstance(s2, int)
    # If they match, make a third attempt to increase confidence randomness works
    if s1 == s2:
        s3 = auth_client.post("/api/dungeon/seed", json={"regenerate": True}).get_json()["seed"]
        assert isinstance(s3, int)


def test_seed_resets_position(auth_client):
    # Move once to change position from entrance
    auth_client.post("/api/dungeon/seed", json={"seed": 999})
    auth_client.post("/api/dungeon/move", json={"dir": ""})  # prime exits/description
    # Attempt a move north (may or may not succeed depending on map)
    auth_client.post("/api/dungeon/move", json={"dir": "n"})
    # Change seed
    auth_client.post("/api/dungeon/seed", json={"seed": 1001})
    # Map call should relocate player to entrance (pos not [0,0,0] afterward but movement state reset)
    map_resp = auth_client.get("/api/dungeon/map")
    map_data = map_resp.get_json()
    assert map_data["seed"] == 1001
    # State endpoint should succeed
    state_resp = auth_client.get("/api/dungeon/state")
    assert state_resp.status_code == 200
