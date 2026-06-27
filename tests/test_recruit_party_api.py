import json
import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models.models import Character, User


@pytest.fixture()
def lobby_client(client, test_app):
    with test_app.app_context():
        u = User.query.filter_by(username="lobby_test").first()
        if not u:
            u = User(username="lobby_test", password=generate_password_hash("pw123456"))
            db.session.add(u)
            db.session.commit()
        Character.query.filter_by(user_id=u.id).delete()
        db.session.commit()
    client.post("/login", data={"username": "lobby_test", "password": "pw123456"})
    return client


def _make_char(test_app, user_id, name="TestChar", cls="fighter"):
    with test_app.app_context():
        import json
        from app.routes.main import BASE_STATS

        stats = dict(BASE_STATS.get(cls, BASE_STATS["fighter"]))
        stats["hp"] = 55
        stats["mana"] = 20
        ch = Character(
            user_id=user_id,
            name=name,
            stats=json.dumps({**stats, "class": cls}),
            gear=json.dumps({}),
            items=json.dumps([]),
            xp=0,
            level=1,
        )
        db.session.add(ch)
        db.session.commit()
        return ch.id


def _get_user_id(test_app):
    with test_app.app_context():
        return User.query.filter_by(username="lobby_test").first().id


def test_candidates_returns_four(lobby_client):
    r = lobby_client.get("/api/recruit/candidates")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 4
    for c in data:
        assert "name" in c and "cls" in c and "stats" in c and "gear_slugs" in c


def test_candidate_stats_include_hp_mana(lobby_client):
    r = lobby_client.get("/api/recruit/candidates")
    candidates = r.get_json()
    for c in candidates:
        assert "hp" in c["stats"]
        assert "mana" in c["stats"]


def test_hire_saves_character(lobby_client, test_app):
    uid = _get_user_id(test_app)
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "id" in data
    with test_app.app_context():
        ch = db.session.get(Character, data["id"])
        assert ch is not None
        assert ch.user_id == uid


def test_hire_with_stat_tweaks(lobby_client, test_app):
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    base_str = candidate["stats"].get("str", 10)
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {"str": 2},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    with test_app.app_context():
        ch = db.session.get(Character, data["id"])
        saved_stats = json.loads(ch.stats)
        assert saved_stats["str"] == base_str + 2


def test_hire_rejects_overspend(lobby_client, test_app):
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {"str": 3},
        },
    )
    assert resp.status_code == 400


def test_hire_rejects_full_barracks(lobby_client, test_app):
    uid = _get_user_id(test_app)
    for i in range(15):
        _make_char(test_app, uid, name=f"Char{i}")
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {},
        },
    )
    assert resp.status_code == 400


def test_party_add_updates_session(lobby_client, test_app):
    uid = _get_user_id(test_app)
    cid = _make_char(test_app, uid, name="Slot1")
    resp = lobby_client.post("/api/party/add", json={"char_ids": [cid]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(p["id"] == cid for p in data["party"])


def test_party_remove_updates_session(lobby_client, test_app):
    uid = _get_user_id(test_app)
    cid = _make_char(test_app, uid, name="ToRemove")
    lobby_client.post("/api/party/add", json={"char_ids": [cid]})
    resp = lobby_client.post(f"/api/party/remove/{cid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert not any(p["id"] == cid for p in data["party"])


def test_party_add_respects_four_slot_limit(lobby_client, test_app):
    uid = _get_user_id(test_app)
    ids = [_make_char(test_app, uid, name=f"P{i}") for i in range(5)]
    resp = lobby_client.post("/api/party/add", json={"char_ids": ids})
    assert resp.status_code == 200
    assert len(resp.get_json()["party"]) <= 4
