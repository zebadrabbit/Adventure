from app import db
from app.models.models import Character, User


def ensure_character_id(app, user_id, name="Hero", char_class="fighter"):
    """Return an existing or newly created Character id without returning detached instance."""
    with app.app_context():
        existing = Character.query.filter_by(user_id=user_id).with_entities(Character.id).first()
        if existing:
            return existing[0]
        stats = {
            "str": 10,
            "dex": 8,
            "int": 6,
            "wis": 6,
            "hp": 20,
            "mana": 5,
            "gold": 5,
            "silver": 20,
            "copper": 50,
            "class": char_class,
        }
        c = Character(user_id=user_id, name=name, stats=json_dumps(stats), gear="[]", items="[]")
        db.session.add(c)
        db.session.commit()
        return c.id


def json_dumps(obj):  # local helper to avoid importing main route module
    import json

    return json.dumps(obj)


def test_seed_persists_through_start_adventure(auth_client, test_app):
    """Set a seed via API, create a character, start adventure; seed should remain unchanged."""
    # 1. Set explicit seed via API
    target_seed = 43210
    resp = auth_client.post("/api/dungeon/seed", json={"seed": target_seed})
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["seed"] == target_seed

    # 2. Ensure we have at least one character; create if needed
    with test_app.app_context():
        user = User.query.filter_by(username="tester").with_entities(User.id).first()
        assert user is not None
        user_id = user[0] if isinstance(user, tuple) else user.id
    char_id = ensure_character_id(test_app, user_id)

    # 3. Start adventure selecting this character
    form_data = {"form": "start_adventure", "party_ids": str(char_id)}
    start_resp = auth_client.post("/dashboard", data=form_data, follow_redirects=False)
    # Expect redirect to /adventure
    assert start_resp.status_code in (302, 303)

    # 4. Fetch map; its reported seed must match previously set seed
    map_resp = auth_client.get("/api/dungeon/map")
    assert map_resp.status_code == 200
    map_data = map_resp.get_json()
    assert map_data["seed"] == target_seed, f"Seed changed after start_adventure: {map_data['seed']} != {target_seed}"

    # 5. Call state endpoint as additional sanity (should succeed)
    state_resp = auth_client.get("/api/dungeon/state")
    assert state_resp.status_code == 200
