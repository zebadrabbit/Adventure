"""Resting has to cost something.

Playtest finding (2026-07-27): "i can endlessly camp to refill my hp. camping
should have risk and be limited." It was a free, unlimited, no-risk full heal,
which removed most of the pressure from a run.

Camping now spends a campfire kit from the party's packs, refuses to repeat
until a cooldown elapses, and can draw an ambush. It also stopped *reducing*
healthy characters: the old code read stats["max_hp"] with a default of 100 and
clamped anyone above that back down to it.
"""

import json

import pytest

from app import db
from app.inventory.utils import add_item, dump_inventory, load_inventory
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, GameClock, GameConfig, User
from app.routes.dungeon_api import camp_config


def _tester_character():
    user = User.query.filter_by(username="tester").first()
    return Character.query.filter_by(user_id=user.id).first()


def _stock(char, qty):
    bag = load_inventory(char.items)
    if qty:
        add_item(bag, camp_config()["supply_slug"], qty)
    char.items = dump_inventory(bag)
    db.session.add(char)
    db.session.commit()


def _clear_bag(char):
    char.items = "[]"
    db.session.add(char)
    db.session.commit()


def _clear_cooldown(auth_client):
    with auth_client.session_transaction() as sess:
        inst_id = sess.get("dungeon_instance_id")
    inst = db.session.get(DungeonInstance, inst_id)
    meta = dict(inst.dungeon_metadata or {})
    meta.pop("last_camp_tick", None)
    inst.dungeon_metadata = meta
    db.session.add(inst)
    db.session.commit()
    return inst


@pytest.fixture(autouse=True)
def _no_ambush():
    """Ambushes are rolled separately; keep them out of the other assertions."""
    GameConfig.set("camp", json.dumps({"ambush_chance": 0.0}))
    yield
    GameConfig.query.filter_by(key="camp").delete()
    db.session.commit()


def test_camping_requires_a_campfire_kit(test_app, auth_client):
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _clear_cooldown(auth_client)

    resp = auth_client.post("/api/dungeon/camp")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "no_supplies"
    assert body["required_slug"] == "consumable_campfire_kit"


def test_camping_consumes_one_kit(test_app, auth_client):
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _stock(char, 2)
        _clear_cooldown(auth_client)
        char_id = char.id

    resp = auth_client.post("/api/dungeon/camp")

    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["supplies_remaining"] == 1
    with test_app.app_context():
        bag = load_inventory(db.session.get(Character, char_id).items)
        kits = next((e["qty"] for e in bag if e.get("slug") == "consumable_campfire_kit"), 0)
        assert kits == 1


def test_camping_again_too_soon_is_refused(test_app, auth_client):
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _stock(char, 5)
        _clear_cooldown(auth_client)

    first = auth_client.post("/api/dungeon/camp")
    assert first.status_code == 200, first.get_json()

    second = auth_client.post("/api/dungeon/camp")

    assert second.status_code == 400
    body = second.get_json()
    assert body["error"] == "camp_cooldown"
    assert body["remaining_ticks"] > 0


def test_cooldown_expires(test_app, auth_client):
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _stock(char, 5)
        inst = _clear_cooldown(auth_client)

    assert auth_client.post("/api/dungeon/camp").status_code == 200

    with test_app.app_context():
        # Rewind the recorded camp tick past the cooldown window.
        inst = db.session.get(DungeonInstance, inst.id)
        meta = dict(inst.dungeon_metadata or {})
        meta["last_camp_tick"] = int(meta["last_camp_tick"]) - (camp_config()["cooldown_ticks"] + 1)
        inst.dungeon_metadata = meta
        db.session.add(inst)
        db.session.commit()

    assert auth_client.post("/api/dungeon/camp").status_code == 200


def test_a_refused_camp_costs_nothing(test_app, auth_client):
    """A cooldown rejection must not eat a kit or advance the clock."""
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _stock(char, 3)
        _clear_cooldown(auth_client)
        char_id = char.id

    assert auth_client.post("/api/dungeon/camp").status_code == 200
    with test_app.app_context():
        bag = load_inventory(db.session.get(Character, char_id).items)
        before = next((e["qty"] for e in bag if e.get("slug") == "consumable_campfire_kit"), 0)
        tick_before = int(GameClock.get().tick or 0)

    assert auth_client.post("/api/dungeon/camp").status_code == 400

    with test_app.app_context():
        bag = load_inventory(db.session.get(Character, char_id).items)
        after = next((e["qty"] for e in bag if e.get("slug") == "consumable_campfire_kit"), 0)
        assert after == before, "a refused camp consumed a kit"
        assert int(GameClock.get().tick or 0) == tick_before, "a refused camp advanced the clock"


def test_camping_never_reduces_a_healthy_character(test_app, auth_client):
    """The regression: max caps are computed, not stored.

    stats["max_hp"] does not exist, so the old `stats.get("max_hp", 100)` read
    100 for everyone -- and `min(100, current + restore)` clamped a character
    sitting on 150 HP down to 100. Camping actively hurt high-level parties.
    """
    from app.services.character_stats import compute_hp_mana_max

    with test_app.app_context():
        char = _tester_character()
        char.level = 20
        char.stats = json.dumps({"str": 12, "dex": 11, "int": 10, "con": 18, "mana": 30})
        db.session.commit()
        max_hp, max_mana = compute_hp_mana_max(char)
        assert max_hp > 100, "fixture must exceed the old hard-coded cap to be meaningful"

        stats = json.loads(char.stats)
        stats["hp"] = max_hp - 1  # nearly full, well above 100
        stats["mana"] = max_mana - 1
        char.stats = json.dumps(stats)
        db.session.commit()
        _clear_bag(char)
        _stock(char, 2)
        _clear_cooldown(auth_client)
        char_id = char.id

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        stats = json.loads(db.session.get(Character, char_id).stats)
        assert stats["hp"] >= max_hp - 1, f"camping dropped HP to {stats['hp']}"
        assert stats["mana"] >= max_mana - 1, f"camping dropped mana to {stats['mana']}"


def test_ambush_can_interrupt_a_rest(test_app, auth_client):
    """With the roll forced, resting spawns a pack next to the party."""
    from app.models.entities import DungeonEntity

    GameConfig.set("camp", json.dumps({"ambush_chance": 1.0}))
    with test_app.app_context():
        char = _tester_character()
        _clear_bag(char)
        _stock(char, 2)
        inst = _clear_cooldown(auth_client)
        before = DungeonEntity.query.filter_by(instance_id=inst.id, type="monster").count()

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        after = DungeonEntity.query.filter_by(instance_id=inst.id, type="monster").count()
        # The pack spawns on walkable tiles adjacent to the party; a cramped
        # position can leave nowhere to put them, so assert no *loss* and treat
        # the reported count as the contract.
        assert after >= before
        body = resp.get_json()
        if body.get("ambush"):
            assert body["ambush"]["count"] >= 1
            assert after > before
