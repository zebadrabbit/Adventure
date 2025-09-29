"""Combat smoke test using direct session creation for determinism."""


def test_combat_smoke(auth_client, monkeypatch):
    import random

    from app.models.models import User
    from app.services import combat_service

    user = User.query.filter_by(username="tester").first()
    assert user
    seq = [10, 10, 10, 10, 10]
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it, 10))
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monster = {
        "slug": "smoke-mob",
        "name": "Smoke Mob",
        "level": 1,
        "hp": 40,
        "damage": 3,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "potion-healing",
        "special_drop_slug": None,
        "xp": 10,
        "boss": False,
    }
    session = combat_service.start_session(user.id, monster)
    cid = session.id
    state = session.to_dict()
    version = state["version"]
    # Attack loop
    for _ in range(10):
        # Determine current actor id (player) for action payload
        init = state.get("initiative", [])
        actor_id = None
        if init:
            first = init[state.get("active_index", 0)]
            if first.get("type") == "player":
                actor_id = first.get("id")
        payload_body = {"action": "attack", "version": version}
        if actor_id is not None:
            payload_body["actor_id"] = actor_id
        rv3 = auth_client.post(f"/api/dungeon/combat/{cid}/action", json=payload_body)
        assert rv3.status_code == 200
        payload = rv3.get_json()
        if payload.get("error") == "version_conflict":
            # reload and continue
            rv4 = auth_client.get(f"/api/dungeon/combat/{cid}")
            version = rv4.get_json()["version"]
            continue
        assert payload.get("ok")
        state = payload["state"]
        version = state["version"]
        if state["status"] != "active":
            # Victory or end
            rewards = state.get("rewards")
            assert isinstance(rewards, dict)
            break
    else:
        assert False, "Combat did not end within 10 actions"
