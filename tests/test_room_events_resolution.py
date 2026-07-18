"""Tests for app.dungeon.room_events.resolve_events_at and its movement hook."""

import json

from app import db
from app.dungeon.dungeon import Dungeon
from app.dungeon.room_events import resolve_events_at
from app.dungeon.tiles import DOOR, ROOM, TUNNEL
from app.models.entities import DungeonEntity
from app.models.status_effect import CharacterStatusEffect
from tests.factories import create_character, create_instance, create_user

WALKABLE = {ROOM, TUNNEL, DOOR}


def _set_stats(char, **overrides):
    stats = json.loads(char.stats)
    stats.update(overrides)
    char.stats = json.dumps(stats)
    db.session.add(char)
    db.session.commit()


def _place(instance, etype, x, y, name=None, slug=None):
    ent = DungeonEntity(
        user_id=instance.user_id,
        instance_id=instance.id,
        seed=instance.seed,
        type=etype,
        slug=slug,
        name=name,
        x=x,
        y=y,
        z=0,
    )
    db.session.add(ent)
    db.session.commit()
    return ent


def _walkable_tile_with_neighbors(dungeon, min_neighbors=2):
    w = len(dungeon.grid)
    h = len(dungeon.grid[0])
    for x in range(1, w - 1):
        for y in range(1, h - 1):
            if dungeon.grid[x][y] not in WALKABLE:
                continue
            n = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    if dungeon.grid[x + dx][y + dy] in WALKABLE:
                        n += 1
            if n >= min_neighbors:
                return x, y
    raise AssertionError("no suitable tile found")


def test_shrine_restores_mana_and_grants_regen_buff(test_app):
    with test_app.app_context():
        user = create_user("shrine_1")
        inst = create_instance(user, seed=7001)
        char = create_character(user, name="Hero")
        _set_stats(char, hp=50, max_hp=50, mana=10, max_mana=100)

        ent = _place(inst, "shrine", 5, 5, name="Ancient Shrine", slug="shrine")
        ent_id = ent.id

        events = resolve_events_at(inst, 5, 5)

        assert len(events) == 1
        assert events[0]["kind"] == "shrine"
        # +50% of 100 max_mana instant restore, capped.
        assert json.loads(db.session.get(type(char), char.id).stats)["mana"] == 60
        assert CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").count() == 1
        assert db.session.get(DungeonEntity, ent_id) is None


def test_trap_avoided_when_leader_perception_high(test_app):
    with test_app.app_context():
        user = create_user("trap_avoid")
        inst = create_instance(user, seed=7002)
        char = create_character(user, name="Sharp")
        _set_stats(char, hp=100, max_hp=100, perception=50)

        ent = _place(inst, "trap", 6, 7, name="Hidden Trap")
        ent_id = ent.id

        events = resolve_events_at(inst, 6, 7)

        assert events[0]["kind"] == "trap_avoided"
        assert json.loads(db.session.get(type(char), char.id).stats)["hp"] == 100
        assert CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").count() == 0
        assert db.session.get(DungeonEntity, ent_id) is None


def test_trap_hit_applies_floored_damage_and_poison(test_app):
    with test_app.app_context():
        user = create_user("trap_hit")
        inst = create_instance(user, seed=7003)
        char = create_character(user, name="Dull")
        _set_stats(char, hp=100, max_hp=100, perception=-50)

        _place(inst, "trap", 8, 9, name="Hidden Trap")

        events = resolve_events_at(inst, 8, 9)

        assert events[0]["kind"] == "trap_hit"
        # 10% of 100 max_hp = 10 damage.
        assert json.loads(db.session.get(type(char), char.id).stats)["hp"] == 90
        assert CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").count() == 1


def test_trap_never_kills_outright(test_app):
    with test_app.app_context():
        user = create_user("trap_floor")
        inst = create_instance(user, seed=7004)
        char = create_character(user, name="Frail")
        _set_stats(char, hp=1, max_hp=100, perception=-50)

        _place(inst, "trap", 2, 3, name="Hidden Trap")

        resolve_events_at(inst, 2, 3)

        assert json.loads(db.session.get(type(char), char.id).stats)["hp"] == 1


def test_ambush_spawns_adjacent_monsters_and_consumes_marker(test_app):
    with test_app.app_context():
        user = create_user("ambush_1")
        inst = create_instance(user, seed=7005)
        create_character(user, name="Hero")

        dungeon = Dungeon(seed=7005, size=(40, 40, 1))
        x, y = _walkable_tile_with_neighbors(dungeon, min_neighbors=3)
        ent = _place(inst, "ambush", x, y)
        ent_id = ent.id

        events = resolve_events_at(inst, x, y, dungeon=dungeon)

        assert events[0]["kind"] == "ambush"
        monsters = DungeonEntity.query.filter_by(instance_id=inst.id, type="monster").all()
        assert 2 <= len(monsters) <= 3
        for m in monsters:
            assert max(abs(m.x - x), abs(m.y - y)) == 1
        assert db.session.get(DungeonEntity, ent_id) is None


def test_no_event_tile_returns_empty_list(test_app):
    with test_app.app_context():
        user = create_user("empty_tile")
        inst = create_instance(user, seed=7006)
        assert resolve_events_at(inst, 11, 12) == []


def test_movement_response_carries_events(client, logged_in_user):
    """The shared movement path merges resolved events into the response."""
    from app.dungeon.movement_handler import get_cached_dungeon

    user = logged_in_user
    inst = create_instance(user, seed=7007)
    create_character(user, name="Hero")

    dungeon = get_cached_dungeon(inst.seed, (75, 75, 1))
    grid = dungeon.grid

    # Find a walkable tile whose north neighbour is also walkable.
    start = None
    for x in range(1, 74):
        for y in range(1, 73):
            if grid[x][y] in WALKABLE and grid[x][y + 1] in WALKABLE:
                start = (x, y)
                break
        if start:
            break
    assert start is not None
    sx, sy = start

    inst.pos_x, inst.pos_y, inst.pos_z = sx, sy, 0
    db.session.commit()

    # Shrine on the tile the player will step onto (north).
    _place(inst, "shrine", sx, sy + 1, name="Ancient Shrine", slug="shrine")

    with client.session_transaction() as sess:
        sess["dungeon_instance_id"] = inst.id

    resp = client.post("/api/dungeon/move", json={"dir": "n"})
    body = resp.get_json()

    assert body["moved"] is True
    assert body["pos"][0] == sx and body["pos"][1] == sy + 1
    assert "events" in body
    assert body["events"][0]["kind"] == "shrine"
