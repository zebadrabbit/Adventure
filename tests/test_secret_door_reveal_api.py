def test_secret_door_reveal_api(secret_door_setup, client):
    """Positive reveal: planted secret door converts to normal door."""
    ctx = secret_door_setup
    x, y = ctx["plant_secret"]()
    resp = client.post("/api/dungeon/reveal", json={"x": x, "y": y})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["revealed"] is True
    assert ctx["dungeon"].grid[x][y] == "D"


def test_secret_door_reveal_too_far(secret_door_setup, client):
    """Negative: reveal fails when player too far (distance >2)."""
    ctx = secret_door_setup
    d = ctx["dungeon"]
    rx, ry = d.rooms[0].center
    # Plant door but move player far away
    x, y = ctx["plant_secret"]()
    # Move player artificially far
    ctx["instance"].pos_x, ctx["instance"].pos_y = rx + 10, ry + 10
    from app import db as _db

    _db.session.commit()
    resp = client.post("/api/dungeon/reveal", json={"x": x, "y": y})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Too far"


def test_secret_door_reveal_not_secret(secret_door_setup, client):
    """Negative: attempting to reveal a tile that is not a secret door."""
    ctx = secret_door_setup
    d = ctx["dungeon"]
    rx, ry = d.rooms[0].center
    # Choose adjacent tile but DO NOT plant secret door
    x, y = rx + 1, ry
    # Force tile to non-secret if variant assignment happened to set it
    if d.grid[x][y] == "S":
        d.grid[x][y] = "T"  # convert to tunnel for test clarity
    ctx["instance"].pos_x, ctx["instance"].pos_y = rx, ry
    from app import db as _db

    _db.session.commit()
    resp = client.post("/api/dungeon/reveal", json={"x": x, "y": y})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Not a secret door"
