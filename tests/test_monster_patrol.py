import random

from app.services.monster_patrol import maybe_patrol


class DummyDungeon:
    def __init__(self, width=5, height=5, fill="R"):
        self.width = width
        self.height = height
        # grid[x][y]
        self.grid = [[fill for _ in range(height)] for _ in range(width)]
        # Place a DOOR and TELEPORT for exclusion checks
        if width > 2 and height > 2:
            self.grid[2][2] = "D"  # door
            self.grid[3][2] = "P"  # teleport


def test_patrol_no_move_when_disabled(monkeypatch, test_app):
    from app.models import GameConfig

    with test_app.app_context():
        GameConfig.set("monster_ai", "{}")  # patrol_enabled false
        d = DummyDungeon()
        m = {"x": 1, "y": 1, "name": "Scout"}
        moved = maybe_patrol(m, d, rng=random.Random(0))
        assert not moved
        assert m["x"] == 1 and m["y"] == 1


def test_patrol_moves_with_forced_chance(monkeypatch, test_app):
    import json

    from app.models import GameConfig

    with test_app.app_context():
        GameConfig.set(
            "monster_ai",
            json.dumps({"patrol_enabled": True, "patrol_step_chance": 1.0, "patrol_radius": 2}),
        )
        d = DummyDungeon()
        m = {"x": 1, "y": 1, "name": "Scout"}
        r = random.Random(42)
        moved = maybe_patrol(m, d, rng=r)
        assert moved, "Expected movement with 100% step chance"
        # Within radius 2 relative to origin (1,1)
        assert max(abs(m["x"] - 1), abs(m["y"] - 1)) <= 2
        # Ensure origin recorded
        assert m.get("patrol_origin") == [1, 1]


def test_patrol_skips_door_and_teleport(monkeypatch, test_app):
    import json

    from app.models import GameConfig

    with test_app.app_context():
        GameConfig.set(
            "monster_ai",
            json.dumps({"patrol_enabled": True, "patrol_step_chance": 1.0, "patrol_radius": 4}),
        )
        d = DummyDungeon()
        # Place monster adjacent to door and teleport so candidates include restricted tiles
        m = {"x": 2, "y": 1, "name": "Scout"}
        # Force deterministic neighbor selection ordering using seeded RNG
        r = random.Random(7)
        # Execute several steps; ensure never steps onto door or teleport tile
        for _ in range(5):
            maybe_patrol(m, d, rng=r)
            assert (m["x"], m["y"]) not in [(2, 2), (3, 2)], "Monster moved onto restricted tile"
