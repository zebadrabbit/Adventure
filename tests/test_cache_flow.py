import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User


def ensure_user_client(client, test_app):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="cachetester").first()
        if not user:
            user = User(username="cachetester", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        char = Character.query.filter_by(user_id=user.id).first()
        if not char:
            char = Character(
                user_id=user.id,
                name="ChestHero",
                stats='{"str":10,"dex":10,"int":10,"mana":20}',
                gear="{}",
                items="[]",
            )
            db.session.add(char)
            db.session.commit()
        inst = DungeonInstance.query.filter_by(user_id=user.id).first()
        if not inst:
            inst = DungeonInstance(user_id=user.id, seed=12345, pos_x=5, pos_y=5, pos_z=0)
            db.session.add(inst)
            db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["_user_id"] = str(user.id)
        sess["dungeon_instance_id"] = inst.id
    return user, char, inst


@pytest.fixture()
def auth_client_cache(test_app, client):
    ensure_user_client(client, test_app)
    return client


def test_cache_open_flow(auth_client_cache, test_app):
    """End-to-end hidden cache open lifecycle.

    Steps:
      1. Fetch map (seeds hidden treasure caches if first time for seed/instance).
      2. Pick a treasure entity row (may be hidden).
      3. Reposition the player directly onto that tile (bypasses long pathing randomness).
      4. Call /api/dungeon/search_tile to reveal (flip hidden False) while on the tile.
      5. Open the cache via /api/dungeon/cache/open/<id> (distance==0 so allowed).
      6. Assert second open returns not_found style error semantics.
    """
    # 1. Trigger seeding
    m1 = auth_client_cache.get("/api/dungeon/map")
    assert m1.status_code == 200
    data = m1.get_json()
    assert "entities" in data
    treasures = [e for e in data.get("entities", []) if e.get("type") == "treasure"]
    if not treasures:
        pytest.skip("No treasure entities seeded (edge case)")
    ent = treasures[0]

    # 2/3. Reposition player onto the treasure tile via test teleport helper (ensures session refresh)
    tp = auth_client_cache.post("/api/test/teleport", json={"x": ent["x"], "y": ent["y"], "z": 0})
    assert tp.status_code == 200, tp.get_json()

    # 4. Reveal at current tile (will clear hidden flag if present)
    r = auth_client_cache.post("/api/dungeon/search_tile")
    assert r.status_code == 200
    rj = r.get_json()
    assert "noticed_loot" in rj

    # 5. Open cache (should now succeed – distance 0)
    # Ensure server reports we are on that tile
    state = auth_client_cache.get("/api/dungeon/state")
    assert state.status_code == 200
    assert state.get_json().get("pos")[:2] == [ent["x"], ent["y"]]
    resp = auth_client_cache.post(f"/api/dungeon/cache/open/{ent['id']}")
    js = resp.get_json()
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {js}"
    # Accept either 'opened' (our wrapper) or legacy 'claimed'
    assert js.get("opened") or js.get("claimed") or js.get("items") is not None
    first_items = js.get("items") or []

    # 6. Second open should not yield a second set (entity removed)
    resp2 = auth_client_cache.post(f"/api/dungeon/cache/open/{ent['id']}")
    js2 = resp2.get_json()
    if resp2.status_code == 200:
        # If helper returns 200 again (unexpected) ensure no duplicate loot set
        assert js2.get("opened") is False, "Cache unexpectedly reopened"
        assert (js2.get("items") or []) == first_items, "Duplicate loot mismatch"
    else:
        assert js2.get("error") in ("not_found", "no_instance", "wrong_type", "not_cache")

    # 7. Sanity: ensure entity row removed from DB
    from app.models import DungeonEntity as _DE

    assert _DE.query.filter_by(id=ent["id"]).first() is None, "Cache entity still present after open"
