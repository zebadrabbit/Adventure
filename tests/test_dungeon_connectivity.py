from app.dungeon import Dungeon

def collect_rooms(d):
    rooms = []
    x = len(d.grid)
    y = len(d.grid[0])
    for i in range(x):
        for j in range(y):
            if d.grid[i][j][0].cell_type == 'room':
                rooms.append((i,j))
    return rooms

def reachable_from_entrance(d):
    from collections import deque
    walk = {'room','door','tunnel'}
    x = len(d.grid)
    y = len(d.grid[0])
    entrance = None
    for i in range(x):
        for j in range(y):
            if 'entrance' in d.grid[i][j][0].features:
                entrance = (i,j); break
        if entrance: break
    assert entrance, 'No entrance feature found'
    q = deque([entrance])
    vis = {entrance}
    while q:
        cx, cy = q.popleft()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < x and 0 <= ny < y and (nx, ny) not in vis:
                if d.grid[nx][ny][0].cell_type in walk:
                    vis.add((nx, ny))
                    q.append((nx, ny))
    return vis

def test_multiple_seed_connectivity():
    seeds = [101, 202, 303, 404, 505]
    for s in seeds:
        d = Dungeon(seed=s, size=(60,60,1))
        rooms = collect_rooms(d)
        reach = reachable_from_entrance(d)
        missing = [r for r in rooms if r not in reach]
        assert not missing, f"Seed {s} has unreachable rooms: {missing[:5]} (showing up to 5)"
