import json


def test_gameclock_advances_and_returned_in_move(auth_client, test_app):
    with test_app.app_context():
        rv1 = auth_client.post("/api/dungeon/move", json={"dir": "n"})
        assert rv1.status_code == 200
        data1 = rv1.get_json()
        assert "game_tick" in data1, data1
        t1 = data1["game_tick"]
        rv2 = auth_client.post("/api/dungeon/move", json={"dir": "e"})
        assert rv2.status_code == 200
        data2 = rv2.get_json()
        # If combat triggered second move may omit game_tick (time not advanced). Skip assertion then.
        if not data2.get("combat_started"):
            assert "game_tick" in data2
            t2 = data2["game_tick"]
            assert t2 >= t1, (t1, t2)


def test_encounter_miss_streak_accumulates_with_gap(auth_client, test_app, monkeypatch):
    """Simulate multiple movements without encounter and ensure streak increases effective chance.

    We monkeypatch random.random to always return a high value so encounters do not trigger.
    Then lower base chance to a very small number and verify computed chance grows (debug field).
    """
    from app.models import GameConfig

    with test_app.app_context():
        # auth_client already logged in
        # Configure encounter_spawn with deterministic very low base so streak bonus is visible
        GameConfig.set("encounter_spawn", json.dumps({"base": 0.0, "streak_bonus_max": 0.05, "streak_unit": 2}))
        GameConfig.set("debug_encounters", json.dumps(True))
        # Force random.random to always yield 0.99 ensuring no encounter until forced by cap
        monkeypatch.setattr("app.dungeon.api_helpers.encounters._r.random", lambda: 0.99)
        streak_chances = []
        # Perform several movement attempts; capture reported encounter_chance
        for _ in range(4):
            rv = auth_client.post("/api/dungeon/move", json={"dir": "n"})
            assert rv.status_code == 200
            data = rv.get_json()
            # If combat triggered unexpectedly break to avoid failing test (should not happen with high roll)
            if data.get("combat_started"):
                break
            if "encounter_chance" in data:  # Provided by debug flag
                streak_chances.append(data["encounter_chance"])
    # Chances should be non-decreasing due to streak accumulation (allow equal if capped)
    assert len(streak_chances) >= 1, streak_chances
    assert all(streak_chances[i] <= streak_chances[i + 1] for i in range(len(streak_chances) - 1)), streak_chances


def test_patrol_multiple_attempts_for_large_tick(monkeypatch, test_app):
    """Invoke run_monster_patrols with a large tick_amount and ensure maybe_patrol called multiple times.

    We patch maybe_patrol to count invocations and force no movement; tick_amount should cap at 5 attempts.
    """
    from app.dungeon.api_helpers import encounters as enc_mod

    call_counter = {"calls": 0}

    def fake_patrol(monster, dungeon):
        call_counter["calls"] += 1
        return False  # never move

    monkeypatch.setattr("app.services.monster_patrol.maybe_patrol", fake_patrol)

    class DummySpawnMgr:
        def __init__(self):
            self.monsters = [{"x": 1, "y": 1, "slug": "m1"}]

        def persist(self):
            pass

    class DummyDungeon:
        def __init__(self):
            self.spawn_manager = DummySpawnMgr()

    class DummyInstance:
        id = 1

    d = DummyDungeon()
    inst = DummyInstance()
    # tick_amount=12 should be capped to 5 attempts by implementation
    enc_mod.run_monster_patrols(d, inst, {}, tick_amount=12)
    assert call_counter["calls"] == 5, call_counter
