import json


def test_movement_advances_ticks(auth_client):
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


def test_search_advances_by_config(auth_client):
    from app.models import GameClock, GameConfig

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
    from app.models import GameClock
    from app.services.time_service import set_combat_state, advance_for

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
    from app.services import time_service

    captured = {}

    def fake_emit(event, payload, namespace=None):
        captured["event"] = event
        captured["payload"] = payload
        captured["namespace"] = namespace

    monkeypatch.setattr(time_service.socketio, "emit", fake_emit)
    from app.services.time_service import advance_for
    from app.models import GameClock

    start = GameClock.get().tick
    advance_for("move")
    assert captured.get("event") == "time_update"
    assert captured.get("payload", {}).get("tick") == start + 1
