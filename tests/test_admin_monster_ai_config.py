import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models.models import GameConfig, User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["_user_id"] = str(user.id)


@pytest.fixture()
def admin_client(test_app, client):
    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        admin = User.query.filter_by(username="admin_tester").first()
        if not admin:
            admin = User(username="admin_tester", password=generate_password_hash("pass"), role="admin")
            db.session.add(admin)
            db.session.commit()
    _login(client, admin)
    return client


@pytest.fixture()
def normal_client(test_app, client):
    with test_app.app_context():
        user = User.query.filter_by(username="normal_tester").first()
        if not user:
            user = User(username="normal_tester", password=generate_password_hash("pass"), role="user")
            db.session.add(user)
            db.session.commit()
    _login(client, user)
    return client


def test_get_config_missing(admin_client):
    # Ensure config removed
    row = GameConfig.query.filter_by(key="monster_ai").first()
    if row:
        db.session.delete(row)
        db.session.commit()
    resp = admin_client.get("/api/admin/monster_ai_config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("config") == {}
    assert data.get("source") == "missing"


def test_update_and_get_roundtrip(admin_client):
    payload = {"spell_chance": 0.75, "patrol_enabled": True, "patrol_radius": 6}
    resp = admin_client.post("/api/admin/monster_ai_config", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    cfg = data.get("config")
    assert cfg.get("spell_chance") == 0.75
    assert cfg.get("patrol_enabled") is True
    assert cfg.get("patrol_radius") == 6
    # GET should reflect same
    resp2 = admin_client.get("/api/admin/monster_ai_config")
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2.get("config", {}).get("spell_chance") == 0.75


def test_validation_errors(admin_client):
    # Probability out of range
    resp = admin_client.post("/api/admin/monster_ai_config", json={"spell_chance": 2})
    assert resp.status_code == 400
    # Unknown key
    resp2 = admin_client.post("/api/admin/monster_ai_config", json={"unknown_key": 0.5})
    assert resp2.status_code == 400


def test_requires_admin(normal_client):
    resp = normal_client.get("/api/admin/monster_ai_config")
    assert resp.status_code == 403
    resp2 = normal_client.post("/api/admin/monster_ai_config", json={"spell_chance": 0.5})
    assert resp2.status_code == 403
