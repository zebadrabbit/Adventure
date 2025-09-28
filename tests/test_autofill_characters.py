import json

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models.models import Character, User


@pytest.fixture()
def auto_client(client, test_app):
    # Create/login a user
    with test_app.app_context():
        u = User.query.filter_by(username="auto").first()
        if not u:
            u = User(username="auto", password=generate_password_hash("pw123456"))
            db.session.add(u)
            db.session.commit()
    _ = u.id  # noqa: F841 (documented: retained pattern for possible future id assertion)
    client.post("/login", data={"username": "auto", "password": "pw123456"})
    return client


def test_autofill_creates_up_to_four(auto_client):
    # Initially user has 0 characters
    r = auto_client.post("/autofill_characters")
    assert r.status_code == 201
    data = r.get_json()
    assert data["created"] == 4
    assert data["total"] == 4
    assert len(data["characters"]) == 4
    sample = data["characters"][0]
    assert "stats" in sample and isinstance(sample["stats"], dict)
    assert "coins" in sample and set(sample["coins"].keys()) == {
        "gold",
        "silver",
        "copper",
    }
    assert "inventory" in sample and isinstance(sample["inventory"], list)
    # Second call: no more created
    r2 = auto_client.post("/autofill_characters")
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert data2["created"] == 0
    assert data2["total"] == 4


def test_autofill_partial_fill(client, test_app):
    # Manually create 2 characters, autofill should add 2 more
    with test_app.app_context():
        from werkzeug.security import generate_password_hash

        user = User.query.filter_by(username="auto2").first()
        if not user:
            user = User(username="auto2", password=generate_password_hash("pw123456"))
            db.session.add(user)
            db.session.commit()
        from app.routes.main import BASE_STATS, STARTER_ITEMS

        for i in range(2):
            stats = BASE_STATS["fighter"]
            c = Character(
                user_id=user.id,
                name=f"Pre{i}",
                stats=json.dumps({**stats, "gold": 5, "silver": 2, "copper": 1, "class": "fighter"}),
                gear=json.dumps([]),
                items=json.dumps(STARTER_ITEMS["fighter"]),
                xp=0,
                level=1,
            )
            db.session.add(c)
        db.session.commit()
    # Login as auto2
    client.post("/login", data={"username": "auto2", "password": "pw123456"})
    r = client.post("/autofill_characters")
    assert r.status_code == 201
    data = r.get_json()
    assert data["created"] == 2
    assert data["total"] == 4
    for ch in data["characters"]:
        assert "stats" in ch and "coins" in ch and "inventory" in ch


def test_autofill_requires_auth(client):
    # Ensure truly unauthenticated (fresh client fixture provides that)
    r = client.post("/autofill_characters", follow_redirects=False)
    assert r.status_code in (302, 401)
