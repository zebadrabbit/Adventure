import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import User


@pytest.fixture()
def seed_client(test_app):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        db.create_all()
        u = User.query.filter_by(username="seeduser").first()
        if not u:
            u = User(username="seeduser", password=generate_password_hash("pass"))
            db.session.add(u)
            db.session.commit()
    _ = u.id  # noqa: F841
    c = test_app.test_client()
    c.post(
        "/login",
        data={"username": "seeduser", "password": "pass"},
        follow_redirects=True,
    )
    return c


def test_seed_regenerate_without_provided(seed_client):
    # regenerate true and no seed -> should return random int and create instance
    r = seed_client.post("/api/dungeon/seed", json={"regenerate": True})
    assert r.status_code == 200
    data = r.get_json()
    assert "seed" in data and isinstance(data["seed"], int)
    assert data["seed"] > 0


def test_seed_string_numeric(seed_client):
    # numeric string coerced directly
    r = seed_client.post("/api/dungeon/seed", json={"seed": "12345"})
    assert r.status_code == 200
    assert r.get_json()["seed"] == 12345


def test_seed_string_hash(seed_client):
    # non-numeric string hashed deterministically (cannot predict exact value but stable across two calls if same input)
    r1 = seed_client.post("/api/dungeon/seed", json={"seed": "AlphaSeed"})
    r2 = seed_client.post("/api/dungeon/seed", json={"seed": "AlphaSeed"})
    s1 = r1.get_json()["seed"]
    s2 = r2.get_json()["seed"]
    assert s1 == s2


def test_seed_empty_string_random(seed_client):
    r = seed_client.post("/api/dungeon/seed", json={"seed": ""})
    assert r.status_code == 200
    assert r.get_json()["seed"] > 0


def test_seed_instance_update_resets_position(seed_client):
    # First call creates instance with seed 42
    r1 = seed_client.post("/api/dungeon/seed", json={"seed": 42})
    first_id = r1.get_json()["dungeon_instance_id"]
    # Manually move position in DB
    with seed_client.application.app_context():
        inst = db.session.get(DungeonInstance, first_id)
        inst.pos_x = 10
        inst.pos_y = 10
        inst.pos_z = 0
        db.session.commit()
    # Second call updates seed and resets position to 0s
    r2 = seed_client.post("/api/dungeon/seed", json={"seed": 43})
    assert r2.get_json()["dungeon_instance_id"] == first_id, "Expected existing instance to be reused"
    with seed_client.application.app_context():
        inst2 = db.session.get(DungeonInstance, first_id)
        assert inst2.pos_x == 0 and inst2.pos_y == 0 and inst2.pos_z == 0
