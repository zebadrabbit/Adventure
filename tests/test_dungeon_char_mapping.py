import unittest
from app.dungeon import Dungeon, DungeonConfig, ROOM, WALL, TUNNEL, DOOR, CAVE
from app.routes import dungeon_api

class TestDungeonCharMapping(unittest.TestCase):
    def test_char_to_type(self):
        self.assertEqual(dungeon_api._char_to_type(ROOM), 'room')
        self.assertEqual(dungeon_api._char_to_type(TUNNEL), 'tunnel')
        self.assertEqual(dungeon_api._char_to_type(DOOR), 'door')
        self.assertEqual(dungeon_api._char_to_type(WALL), 'wall')
        self.assertEqual(dungeon_api._char_to_type(CAVE), 'cave')

    def test_generated_grid_translation(self):
        d = Dungeon(DungeonConfig(seed=101))
        # Ensure at least one room, wall, tunnel, or door maps correctly
        seen_types = set()
        for x in range(d.config.width):
            for y in range(d.config.height):
                seen_types.add(dungeon_api._char_to_type(d.grid[x][y]))
        # minimal expectation
        self.assertIn('room', seen_types)
        self.assertIn('wall', seen_types)

if __name__ == '__main__':
    unittest.main()
