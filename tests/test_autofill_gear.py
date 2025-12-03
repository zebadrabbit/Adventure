import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models.models import Character, User


@pytest.fixture()
def gear_client(client, test_app):
    with test_app.app_context():
        u = User.query.filter_by(username="gearuser").first()
        if not u:
            u = User(username="gearuser", password=generate_password_hash("pw123456"))
            db.session.add(u)
            db.session.commit()
        # Purge any existing characters for isolation
        Character.query.filter_by(user_id=u.id).delete()
        db.session.commit()
    client.post("/login", data={"username": "gearuser", "password": "pw123456"})
    return client


def test_autofill_characters_have_basic_gear(gear_client):
    r = gear_client.post("/autofill_characters")
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert data["created"] == 4
    for ch in data["characters"]:
        gear = ch.get("gear")
        # gear should be a dict mapping slot -> slug (may omit armor for some classes)
        assert isinstance(gear, dict)
        # Weapon is mandatory if any starter weapon available
        assert "weapon" in gear
        assert isinstance(gear["weapon"], str) and len(gear["weapon"]) > 0
        # Armor is optional; if present must be non-empty string
        if "armor" in gear:
            assert isinstance(gear["armor"], str) and len(gear["armor"]) > 0


def test_manual_character_creation_auto_equip(client, test_app):
    # Ensure manual creation through /create_character path yields auto gear
    with test_app.app_context():
        u = User.query.filter_by(username="manualgear").first()
        if not u:
            u = User(username="manualgear", password=generate_password_hash("pw123456"))
            db.session.add(u)
            db.session.commit()
    client.post("/login", data={"username": "manualgear", "password": "pw123456"})
    form_data = {
        "name": "BladeTest",
        "char_class": "fighter",
    }
    r = client.post("/dashboard", data=form_data, follow_redirects=True)
    assert r.status_code in (200, 302)
    # Fetch characters list endpoint (assuming /api/characters/state or dashboard list)
    state = client.get("/api/characters/state").get_json()
    chars = state["characters"]
    found = [c for c in chars if c["name"] == "BladeTest"]
    assert found
    gear = found[0]["gear"]
    assert isinstance(gear, dict) and "weapon" in gear
    assert gear["weapon"]
