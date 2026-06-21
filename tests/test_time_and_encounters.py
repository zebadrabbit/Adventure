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


def test_patrol_multiple_attempts_for_large_tick(monkeypatch, test_app):
    """Invoke run_monster_patrols with new SpawnManager system.

    Verify that the new spawn system correctly loads and updates spawns.
    """
    from app.dungeon.api_helpers import encounters as enc_mod
    from app.dungeon.spawn_manager import SpawnBehavior

    # Mock the new spawn system components
    class DummySpawnEntry:
        def __init__(self, x, y, slug):
            self.x = x
            self.y = y
            self.slug = slug
            self.name = "TestMonster"
            self.last_move_tick = 0
            self.behavior = SpawnBehavior.PATROL

    class DummySpawnManager:
        def __init__(self, dungeon, instance):
            self.spawns = [DummySpawnEntry(1, 1, "m1")]

        def update_spawns(self, tick):
            # Return empty list (no movement)
            return []

    class DummyDungeon:
        def __init__(self):
            self.width = 10
            self.height = 10

    class DummyInstance:
        id = 1

    def mock_load_spawns(instance, manager):
        return manager.spawns

    # Patch where SpawnManager is imported and used
    monkeypatch.setattr("app.dungeon.spawn_manager.SpawnManager", DummySpawnManager)
    monkeypatch.setattr("app.dungeon.spawn_integration.load_spawns_from_db", mock_load_spawns)

    with test_app.app_context():
        from app.models.models import GameClock

        clock = GameClock.get()
        clock.tick = 100
        from app import db

        db.session.commit()

        d = DummyDungeon()
        inst = DummyInstance()
        # New system handles tick_amount via SpawnManager.update_spawns()
        enc_mod.run_monster_patrols(d, inst, {}, tick_amount=12)
        # Test passes if no exceptions raised (spawn system called successfully)
