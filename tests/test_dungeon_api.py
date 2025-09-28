from app import db  # noqa: E402
from app.models.dungeon_instance import DungeonInstance  # noqa: E402
from app.models.models import User  # noqa: E402


def ensure_instance(app, seed=1234):
    with app.app_context():
        inst = DungeonInstance.query.first()
        if not inst:
            user = User.query.filter_by(username="tester").first()
            if not user:
                # create a fallback user if auth_client fixture not yet invoked
                from werkzeug.security import generate_password_hash

                user = User(username="tester", password=generate_password_hash("pass"))
                db.session.add(user)
                db.session.flush()  # obtain id
            inst = DungeonInstance(user_id=user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
            db.session.add(inst)
            db.session.commit()
        return inst


def test_state_endpoint(auth_client, test_app):
    ensure_instance(test_app)
    r = auth_client.get("/api/dungeon/state")
    assert r.status_code == 200
    data = r.get_json()
    assert set(["pos", "exits"]).issubset(data.keys())


def test_move_endpoint(auth_client, test_app):
    ensure_instance(test_app)
    r = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data.get("pos"), list)
    assert "exits" in data


def test_seed_determinism(auth_client, test_app):
    inst = ensure_instance(test_app, seed=777)
    r1 = auth_client.get("/api/dungeon/map")
    assert r1.status_code == 200
    g1 = r1.get_json()["grid"]
    # Force new request without seed change
    r2 = auth_client.get("/api/dungeon/map")
    g2 = r2.get_json()["grid"]
    assert g1 == g2, f"Dungeon grid changed unexpectedly for fixed seed {inst.seed}"
