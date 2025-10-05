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
        # Purge any pre-existing characters so test invariant (0 initial) holds
        Character.query.filter_by(user_id=u.id).delete()
        db.session.commit()
    _ = u.id  # noqa: F841 (documented: retained pattern for possible future id assertion)
    client.post("/login", data={"username": "auto", "password": "pw123456"})
    return client


def test_autofill_creates_four_and_forms_party(auto_client):
    """With 0 initial characters, autofill creates 4 and returns a 4-member party."""
    r = auto_client.post("/autofill_characters")
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert data["created"] == 4
    assert data["party_size"] == 4
    assert len(data["party"]) == 4
    assert data["total_characters"] >= 4
    ids_first = [p["id"] for p in data["party"]]
    # Second call: deterministic party selection (no new creation)
    r2 = auto_client.post("/autofill_characters")
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert data2["created"] == 0
    assert data2["party_size"] == 4
    assert [p["id"] for p in data2["party"]] == ids_first


def test_autofill_partial_creation(client, test_app):
    """Start with 2 existing characters; autofill creates remaining 2 and forms party of 4."""
    with test_app.app_context():
        user = User.query.filter_by(username="auto2").first()
        if not user:
            user = User(username="auto2", password=generate_password_hash("pw123456"))
            db.session.add(user)
            db.session.commit()
        Character.query.filter_by(user_id=user.id).delete()
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
    client.post("/login", data={"username": "auto2", "password": "pw123456"})
    r = client.post("/autofill_characters")
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert data["created"] == 2
    assert data["party_size"] == 4
    assert len(data["party"]) == 4
    assert data["total_characters"] == 4


def test_autofill_requires_auth(client):
    r = client.post("/autofill_characters", follow_redirects=False)
    # New simplified route returns 401 JSON when not authenticated
    assert r.status_code in (302, 401)
