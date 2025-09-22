import unittest
from app.dungeon import Dungeon, DungeonConfig, ROOM, TUNNEL, DOOR

class TestDungeonLegacyCtor(unittest.TestCase):
    def test_seed_and_size_tuple(self):
        d = Dungeon(seed=777, size=(40,40,1))
        self.assertEqual(d.config.width, 40)
        self.assertEqual(d.config.height, 40)
        self.assertEqual(d.metrics['seed'], 777)
        # basic tile sanity
        flat = sum(d.grid, [])
        self.assertTrue(any(t==ROOM for col in d.grid for t in col), 'Expected at least one room tile')

    def test_determinism_same_seed(self):
        d1 = Dungeon(seed=1234, size=(50,50,1))
        d2 = Dungeon(seed=1234, size=(50,50,1))
        self.assertEqual([''.join(d1.grid[x][y] for x in range(d1.config.width)) for y in range(d1.config.height)],
                         [''.join(d2.grid[x][y] for x in range(d2.config.width)) for y in range(d2.config.height)])

    def test_config_override_seed(self):
        cfg = DungeonConfig(width=30, height=30, seed=42)
        d = Dungeon(cfg, seed=99)  # explicit seed param should override
        self.assertEqual(d.metrics['seed'], 99)
        self.assertEqual(d.config.seed, 99)

if __name__ == '__main__':
    unittest.main()
