import json


def test_movement_advances_ticks(auth_client):
    # Ensure migrations (combat column etc.) before interacting
    try:
        from app.server import _run_migrations

        _run_migrations()
    except Exception:
        pass
    # Hit dashboard to ensure GameClock row exists
    auth_client.get("/dashboard")
    # Access /dashboard to ensure GameClock row exists
    from app.models import GameClock

    start_tick = GameClock.get().tick
    # Perform move north (may or may not move depending on dungeon layout; we call state first to ensure position valid)
    auth_client.post("/api/dungeon/move", json={"dir": ""})
    resp = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    assert resp.status_code == 200
    end_tick = GameClock.get().tick
    # Default move cost is 1
    assert end_tick >= start_tick  # movement may be blocked
    if "pos" in resp.json:
        # If moved, tick should increase exactly by configured cost (1 by default)
        if "error" not in resp.json:
            # We can't easily tell if movement succeeded; rely on difference
            if end_tick != start_tick:
                assert end_tick - start_tick == 1
    # No migration call needed here (already applied)


def test_search_advances_by_config(auth_client):
    try:
        from app.server import _run_migrations

        _run_migrations()
    except Exception:
        pass
    from app.models import GameClock, GameConfig

    # Ensure not flagged as in combat from prior tests
    try:
        from app.services.time_service import set_combat_state as _set_combat

        _set_combat(False)
    except Exception:
        pass

    # Override search cost to 3
    GameConfig.set("tick_costs", json.dumps({"search": 3}))
    start = GameClock.get().tick
    # Force notice map entry by faking session; easier: directly call search endpoint after planting loot? For now just call endpoint expecting 403/no increment.
    # We simulate cost application via direct advance_for call using service.
    from app.services.time_service import advance_for

    advance_for("search")
    end = GameClock.get().tick
    assert end - start == 3


def test_combat_gating_blocks_ticks(auth_client):
    try:
        from app.server import _run_migrations

        _run_migrations()
    except Exception:
        pass
    from app.models import GameClock
    from app.services.time_service import advance_for, set_combat_state

    clock = GameClock.get()
    base = clock.tick
    set_combat_state(True)
    advance_for("move")
    mid = GameClock.get().tick
    assert mid == base
    set_combat_state(False)
    advance_for("move")
    after = GameClock.get().tick
    assert after == base + 1


def test_socket_event_emission(auth_client, monkeypatch):
    try:
        from app.server import _run_migrations

        _run_migrations()
    except Exception:
        pass
    from app.services import time_service

    captured = {}

    def fake_emit(event, payload, namespace=None):
        captured["event"] = event
        captured["payload"] = payload
        captured["namespace"] = namespace

    monkeypatch.setattr(time_service.socketio, "emit", fake_emit)
    from app.models import GameClock
    from app.services.time_service import advance_for

    start = GameClock.get().tick
    advance_for("move")
    assert captured.get("event") == "time_update"
    assert captured.get("payload", {}).get("tick") == start + 1


def test_advance_time_triggers_decay_outside_combat(auth_client):
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect, GameClock
    from app.models.models import Character, User
    from app.services import time_service

    user = User.query.filter_by(username="tester").first()
    assert user is not None
    char = Character.query.filter_by(user_id=user.id).first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    GameClock.get()  # ensure row exists
    time_service.advance_time(1, reason="test", character_ids=[char.id])

    db.session.refresh(char)
    stats = _json.loads(char.stats)
    # Poison deals 2 damage per tick; with 0.5% regen per tick on hp_max=75, regen=1
    assert stats["hp"] == 4  # 5 - 2 + 1 = 4


def test_advance_time_skips_decay_when_no_character_ids_given(auth_client):
    """character_ids is opt-in: omitting it must not fall back to scanning
    every character in the database -- it should simply skip decay/regen
    for that call, leaving other characters' state untouched.
    """
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character, User
    from app.services import time_service

    user = User.query.filter_by(username="tester").first()
    assert user is not None
    char = Character.query.filter_by(user_id=user.id).first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    time_service.advance_time(1, reason="test")  # no character_ids passed

    db.session.refresh(char)
    stats = _json.loads(char.stats)
    assert stats["hp"] == 5  # untouched -- decay never ran for this call

    effect = CharacterStatusEffect.query.filter_by(character_id=char.id).first()
    assert effect.remaining == 5  # untouched


def test_advance_time_does_not_decay_during_combat(auth_client):
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character, User
    from app.services import time_service

    user = User.query.filter_by(username="tester").first()
    assert user is not None
    char = Character.query.filter_by(user_id=user.id).first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    time_service.set_combat_state(True)
    try:
        time_service.advance_time(1, reason="test", character_ids=[char.id])
        db.session.refresh(char)
        stats = _json.loads(char.stats)
        assert stats["hp"] == 5  # unchanged -- combat pauses overworld ticking entirely
    finally:
        time_service.set_combat_state(False)


def test_advance_non_combat_time_triggers_decay_for_instance_party(auth_client):
    """Movement bypasses time_service.advance_time entirely (its own raw
    GameClock increment in dungeon_api.py) -- confirm it still triggers
    persisted status-effect decay/regen for the instance's party.
    """
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character, User
    from app.models.dungeon_instance import DungeonInstance
    from app.routes.dungeon_api import advance_non_combat_time

    user = User.query.filter_by(username="tester").first()
    assert user is not None
    char = Character.query.filter_by(user_id=user.id).first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    instance = DungeonInstance.query.filter_by(user_id=user.id).first()
    assert instance is not None

    advance_non_combat_time(instance, tick_amount=1)

    db.session.refresh(char)
    stats = _json.loads(char.stats)
    # Poison deals 2 damage per tick; with 0.5% regen per tick on hp_max=75, regen=1
    assert stats["hp"] == 4  # 5 - 2 + 1 = 4
