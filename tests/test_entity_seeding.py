def test_entity_seeding_idempotent(auth_client):
    # First map call should seed entities
    r1 = auth_client.get("/api/dungeon/map")
    assert r1.status_code == 200
    data1 = r1.get_json()
    entities1 = {e["id"] for e in data1.get("entities", [])}
    # Second map call should return same entity ids (no duplicate seeding)
    r2 = auth_client.get("/api/dungeon/map")
    data2 = r2.get_json()
    entities2 = {e["id"] for e in data2.get("entities", [])}
    assert entities1 == entities2, "Entity IDs changed between identical map calls; seeding not idempotent"
    # Expect at least one monster or treasure entity
    types = {e["type"] for e in data1.get("entities", [])}
    assert any(t in types for t in ("monster", "treasure")), "Expected seeded monster or treasure entities"


def test_map_entities_present(auth_client):
    r_map = auth_client.get("/api/dungeon/map")
    assert r_map.status_code == 200
    ents = r_map.get_json().get("entities", [])
    # Basic sanity: unique ids and valid coords
    ids = [e["id"] for e in ents]
    assert len(ids) == len(set(ids)), "Duplicate entity ids in /api/dungeon/map payload"
    for e in ents:
        assert all(k in e for k in ("id", "type", "x", "y"))


def test_treasure_claim_endpoint(auth_client):
    # Ensure map seeded (treasure entities may or may not exist depending on sample size)
    r1 = auth_client.get("/api/dungeon/map")
    data = r1.get_json()
    treasures = [e for e in data.get("entities", []) if e.get("type") == "treasure"]
    if not treasures:
        # Accept absence (small maps / rare sampling); skip to avoid flaky failure
        import pytest

        pytest.skip("No treasure entities seeded for this seed; sampling heuristic produced zero")
    target = treasures[0]
    cid = target["id"]
    # Ensure proximity: move player adjacent/same tile by patching instance directly
    from app import db
    from app.models.dungeon_instance import DungeonInstance

    inst = DungeonInstance.query.first()
    inst.pos_x, inst.pos_y = target["x"], target["y"]  # same tile to satisfy dist<=1
    db.session.commit()
    claim = auth_client.post(f"/api/dungeon/treasure/claim/{cid}")
    assert claim.status_code == 200, claim.get_json()
    payload = claim.get_json()
    assert payload.get("claimed") is True
    # Second claim should 404
    claim2 = auth_client.post(f"/api/dungeon/treasure/claim/{cid}")
    assert claim2.status_code == 404
