"""Tests for app.dungeon.room_events.seed_room_events and hidden-type filtering."""

from app import db
from app.dungeon.dungeon import Dungeon
from app.dungeon.room_events import EVENT_TUNING, seed_room_events
from app.models.dungeon_instance import DungeonInstance
from app.models.entities import DungeonEntity


def _make_instance(user_id, seed):
    inst = DungeonInstance(user_id=user_id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(inst)
    db.session.commit()
    return inst


def _dungeon(seed=42):
    return Dungeon(seed=seed, size=(40, 40, 1))


def test_seed_room_events_creates_expected_counts(logged_in_user):
    dungeon = _dungeon(seed=1001)
    instance = _make_instance(logged_in_user.id, seed=1001)

    created = seed_room_events(instance, dungeon)

    rows = DungeonEntity.query.filter_by(instance_id=instance.id).all()
    shrines = [r for r in rows if r.type == "shrine"]
    traps = [r for r in rows if r.type == "trap"]
    ambushes = [r for r in rows if r.type == "ambush"]

    assert len(shrines) == EVENT_TUNING["shrines_per_instance"]
    assert len(traps) == EVENT_TUNING["traps_per_instance"]
    assert len(ambushes) == EVENT_TUNING["ambushes_per_instance"]
    assert created == len(shrines) + len(traps) + len(ambushes)

    # Distinct, walkable tiles, no duplicate coords, entrance already occupied
    # so events must not land on it.
    coords = [(r.x, r.y) for r in rows]
    assert len(coords) == len(set(coords)), "room events must occupy distinct tiles"

    walkable = set(dungeon.grid[x][y] for x, y in coords)
    from app.dungeon.tiles import DOOR, ROOM, TUNNEL

    assert walkable <= {ROOM, TUNNEL, DOOR}

    for r in shrines:
        assert r.name == "Ancient Shrine"
        assert r.slug == "shrine"
    for r in traps:
        assert r.name == "Hidden Trap"
    for r in ambushes:
        assert r.name is None


def test_seed_room_events_idempotent(logged_in_user):
    dungeon = _dungeon(seed=2002)
    instance = _make_instance(logged_in_user.id, seed=2002)

    first = seed_room_events(instance, dungeon)
    assert first > 0
    count_after_first = DungeonEntity.query.filter_by(instance_id=instance.id).count()

    second = seed_room_events(instance, dungeon)
    assert second == 0
    count_after_second = DungeonEntity.query.filter_by(instance_id=instance.id).count()

    assert count_after_first == count_after_second


def test_seed_room_events_deterministic_across_instances(logged_in_user):
    seed = 3003
    dungeon_a = _dungeon(seed=seed)
    dungeon_b = _dungeon(seed=seed)

    instance_a = _make_instance(logged_in_user.id, seed=seed)
    instance_b = _make_instance(logged_in_user.id, seed=seed)

    seed_room_events(instance_a, dungeon_a)
    seed_room_events(instance_b, dungeon_b)

    rows_a = DungeonEntity.query.filter_by(instance_id=instance_a.id).all()
    rows_b = DungeonEntity.query.filter_by(instance_id=instance_b.id).all()

    coords_a = sorted((r.type, r.x, r.y) for r in rows_a)
    coords_b = sorted((r.type, r.x, r.y) for r in rows_b)

    assert coords_a == coords_b


def test_dungeon_entities_route_hides_trap_and_ambush(auth_client):
    from app import db as _db
    from app.dungeon.room_events import seed_room_events
    from app.models.dungeon_instance import DungeonInstance

    # Ensure a dungeon instance + map is seeded first (normal spawns/treasure).
    r = auth_client.get("/api/dungeon/map")
    assert r.status_code == 200

    with auth_client.session_transaction() as _s:
        inst_id = _s.get("dungeon_instance_id")
    instance = _db.session.get(DungeonInstance, inst_id)

    from app.dungeon.dungeon import Dungeon

    dungeon = Dungeon(seed=instance.seed, size=(40, 40, 1))
    seed_room_events(instance, dungeon)

    resp = auth_client.get("/api/dungeon/entities")
    assert resp.status_code == 200
    payload = resp.get_json()
    types = {e["type"] for e in payload["entities"]}
    assert "trap" not in types
    assert "ambush" not in types

    # Shrines (if any were placed) must remain visible.
    raw_rows = DungeonEntity.query.filter_by(instance_id=instance.id, type="shrine").all()
    if raw_rows:
        assert "shrine" in types


def test_dungeon_map_route_hides_trap_and_ambush(auth_client):
    from app import db as _db
    from app.dungeon.dungeon import Dungeon
    from app.dungeon.room_events import seed_room_events
    from app.models.dungeon_instance import DungeonInstance

    r = auth_client.get("/api/dungeon/map")
    assert r.status_code == 200

    with auth_client.session_transaction() as _s:
        inst_id = _s.get("dungeon_instance_id")
    instance = _db.session.get(DungeonInstance, inst_id)

    dungeon = Dungeon(seed=instance.seed, size=(40, 40, 1))
    seed_room_events(instance, dungeon)

    resp2 = auth_client.get("/api/dungeon/map")
    assert resp2.status_code == 200
    payload = resp2.get_json()
    types = {e["type"] for e in payload["entities"]}
    assert "trap" not in types
    assert "ambush" not in types
