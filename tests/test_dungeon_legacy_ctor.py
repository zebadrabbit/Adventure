import unittest


from app.dungeon import ROOM, Dungeon, DungeonConfig


class TestDungeonLegacyCtor(unittest.TestCase):
    def test_seed_and_size_tuple(self):
        d = Dungeon(seed=777, size=(40, 40, 1))
        self.assertEqual(d.config.width, 40)
        self.assertEqual(d.config.height, 40)
        self.assertEqual(d.metrics["seed"], 777)
        # basic tile sanity
        self.assertTrue(
            any(t == ROOM for col in d.grid for t in col),
            "Expected at least one room tile",
        )

    def test_determinism_same_seed(self):
        seed = 13579
        runs = [Dungeon(seed=seed, size=(40, 40, 1)) for _ in range(3)]
        rooms_counts = {d.metrics["rooms"] for d in runs}
        door_counts = {d.metrics["tiles_door"] for d in runs}
        wall_counts = {d.metrics["tiles_wall"] for d in runs}
        # Expect stability of core metrics across repeated generations with identical seed
        assert len(rooms_counts) == 1, f"Room count nondeterministic for seed {seed}: {rooms_counts}"
        assert len(door_counts) == 1, f"Door count nondeterministic for seed {seed}: {door_counts}"
        assert len(wall_counts) == 1, f"Wall count nondeterministic for seed {seed}: {wall_counts}"

    def test_config_override_seed(self):
        cfg = DungeonConfig(width=30, height=30, seed=42)
        d = Dungeon(cfg, seed=99)  # explicit seed param should override
        self.assertEqual(d.metrics["seed"], 99)
        self.assertEqual(d.config.seed, 99)


if __name__ == "__main__":
    unittest.main()
