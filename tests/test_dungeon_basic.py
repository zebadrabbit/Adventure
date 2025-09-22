import unittest
from app.dungeon import Dungeon, DungeonConfig, ROOM, WALL, TUNNEL, DOOR

class TestBasicDungeon(unittest.TestCase):
    def setUp(self):
        self.d = Dungeon(DungeonConfig(seed=42))

    def test_rooms_exist(self):
        self.assertGreater(self.d.metrics['rooms'], 0)

    def test_all_rooms_reachable(self):
        self.assertEqual(self.d.metrics['unreachable_rooms'], 0)

    def test_wall_thickness(self):
        # Every wall must touch at least one room orthogonally
        w = self.d.config.width; h = self.d.config.height
        for x in range(w):
            for y in range(h):
                if self.d.grid[x][y] == WALL:
                    self.assertTrue(any(0 <= nx < w and 0 <= ny < h and self.d.grid[nx][ny] == ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))), f"Wall at {(x,y)} not adjacent to room")

    def test_doors_between_room_and_tunnel(self):
        # Each door should have a room neighbor and a tunnel neighbor
        w = self.d.config.width; h = self.d.config.height
        for x in range(w):
            for y in range(h):
                if self.d.grid[x][y] == DOOR:
                    has_room = any(0 <= nx < w and 0 <= ny < h and self.d.grid[nx][ny] == ROOM for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                    has_tunnel = any(0 <= nx < w and 0 <= ny < h and self.d.grid[nx][ny] == TUNNEL for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
                    self.assertTrue(has_room and has_tunnel, f"Door at {(x,y)} missing room or tunnel adjacency")

if __name__ == '__main__':
    unittest.main()
