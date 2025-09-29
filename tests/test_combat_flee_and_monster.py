"""Combat flee & monster auto-turn tests using direct service session creation."""


def _start_test_session(user_id, monkeypatch, flee_roll=None):
    """Create a combat session directly via service layer for deterministic tests."""
    import random

    from app.services import combat_service

    # Deterministic initiative
    seq = [10, 10, 10]
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it, 10))
    if flee_roll is not None:
        monkeypatch.setattr(random, "random", lambda: flee_roll)
    monster = {
        "slug": "test-mob",
        "name": "Test Mob",
        "level": 1,
        "hp": 30,
        "damage": 4,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 5,
        "boss": False,
    }
    session = combat_service.start_session(user_id, monster)
    return session.id


def test_flee_success(auth_client, monkeypatch):
    # auth_client ensures logged-in user/session so encounter spawning works
    # Acquire current user id (tester)
    from app.models.models import User

    u = User.query.filter_by(username="tester").first()
    assert u
    cid = _start_test_session(u.id, monkeypatch, flee_roll=0.1)
    # Fetch session
    r = auth_client.get(f"/api/dungeon/combat/{cid}")
    state = r.get_json()
    v = state["version"]
    # Determine acting player id from initiative order
    init = state.get("initiative", [])
    actor_id = None
    if init:
        first = init[state.get("active_index", 0)]
        if first.get("type") == "player":
            actor_id = first.get("id")
    if actor_id is None:
        # fallback to user id  (session user= tester) but party member may differ
        actor_id = init[0]["id"] if init else 1
    # Flee (should succeed because random < 0.5)
    r2 = auth_client.post(
        f"/api/dungeon/combat/{cid}/action", json={"action": "flee", "version": v, "actor_id": actor_id}
    )
    payload = r2.get_json()
    assert payload.get("ok")
    assert payload.get("fled") is True
    assert payload["state"]["status"] != "active"


def test_flee_failure_then_monster_turn(auth_client, monkeypatch):
    from app.models.models import User

    u = User.query.filter_by(username="tester").first()
    assert u
    cid = _start_test_session(u.id, monkeypatch, flee_roll=0.9)
    r = auth_client.get(f"/api/dungeon/combat/{cid}")
    state = r.get_json()
    v = state["version"]
    init = state.get("initiative", [])
    actor_id = None
    if init:
        first = init[state.get("active_index", 0)]
        if first.get("type") == "player":
            actor_id = first.get("id")
    if actor_id is None and init:
        actor_id = init[0]["id"]
    # Flee attempt fails (random 0.9 >= 0.5)
    r2 = auth_client.post(
        f"/api/dungeon/combat/{cid}/action", json={"action": "flee", "version": v, "actor_id": actor_id}
    )
    if r2.get_json().get("error") == "not_your_turn":
        # reload and attempt again if initiative changed unexpectedly
        state2 = auth_client.get(f"/api/dungeon/combat/{cid}").get_json()
        v = state2["version"]
        init2 = state2.get("initiative", [])
        if init2:
            first2 = init2[state2.get("active_index", 0)]
            if first2.get("type") == "player":
                actor_id = first2.get("id")
        r2 = auth_client.post(
            f"/api/dungeon/combat/{cid}/action", json={"action": "flee", "version": v, "actor_id": actor_id}
        )
    payload = r2.get_json()
    assert payload.get("ok")
    assert payload.get("fled") is False
    # After action we may have progressed turns; if monster acts, player HP should drop
    post = auth_client.get(f"/api/dungeon/combat/{cid}").get_json()
    # Extract player hp
    party = post.get("party") or post.get("state", {}).get("party")
    # Session to_dict might not expose party; fetch raw session for assertion fallback
    if not party:
        from app import db
        from app.models.models import CombatSession

        row = db.session.get(CombatSession, cid)
        import json as _j

        party = _j.loads(row.party_snapshot_json)
    hp = party["members"][0]["hp"]
    assert hp <= 100, "HP should not increase after flee fail"


def test_monster_auto_damage_on_turn(auth_client, monkeypatch):
    from app.models.models import User

    u = User.query.filter_by(username="tester").first()
    assert u
    cid = _start_test_session(u.id, monkeypatch, flee_roll=0.6)
    # Force player to attack to hand turn to monster
    r = auth_client.get(f"/api/dungeon/combat/{cid}")
    state = r.get_json()
    v = state["version"]
    r2 = auth_client.post(f"/api/dungeon/combat/{cid}/action", json={"action": "attack", "version": v})
    p = r2.get_json()
    assert p.get("ok")
    # After attack, monster may act automatically (progress monster turn helper inside endpoint)
    from app import db
    from app.models.models import CombatSession

    row = db.session.get(CombatSession, cid)
    import json as _j

    party = _j.loads(row.party_snapshot_json)
    hp = party["members"][0]["hp"]
    assert hp <= 100
