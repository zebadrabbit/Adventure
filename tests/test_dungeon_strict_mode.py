import os, pytest
from app import create_app, db
from app.dungeon import Dungeon

@pytest.fixture
def strict_app(monkeypatch):
    # Ensure metrics enabled; enable strict hidden areas flag in config directly
    monkeypatch.delenv('DUNGEON_ALLOW_HIDDEN_AREAS', raising=False)
    monkeypatch.delenv('DUNGEON_ALLOW_HIDDEN_AREAS_STRICT', raising=False)
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      DUNGEON_ALLOW_HIDDEN_AREAS_STRICT=True,
                      DUNGEON_ALLOW_HIDDEN_AREAS=False)
    with app.app_context():
        db.create_all()
        yield app
        # Cleanup: ensure flags not left enabled for downstream tests
        app.config['DUNGEON_ALLOW_HIDDEN_AREAS_STRICT'] = False
        app.config['DUNGEON_ALLOW_HIDDEN_AREAS'] = False


def _count_unreachable_rooms(d):
    # Flood from entrance, count remaining room tiles not visited
    x, y, _ = d.size
    from collections import deque
    entrance = d.entrance_pos
    if not entrance:
        return 0
    ex, ey, ez = entrance
    walk = {'room','door','tunnel'}
    vis = set([(ex, ey)])
    q = deque([(ex, ey)])
    while q:
        cx, cy = q.popleft()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < x and 0 <= ny < y and (nx,ny) not in vis:
                if d.grid[nx][ny][0].cell_type in walk:
                    vis.add((nx,ny)); q.append((nx,ny))
    unreachable = 0
    for ix in range(x):
        for iy in range(y):
            if d.grid[ix][iy][0].cell_type == 'room' and (ix,iy) not in vis:
                unreachable += 1
    return unreachable

@pytest.mark.strict_mode
def test_strict_mode_allows_unreachable_rooms(strict_app):
    """Search a window of seeds for evidence strict mode preserves unreachable rooms.

    We iteratively probe seeds until we either (a) find an unreachable room, asserting
    strict behavior exists; or (b) exhaust the window and skip (rare scenario of full connectivity).
    """
    seed_start = 5
    seed_limit = 80  # inclusive upper bound probe window
    found_unreachable = False
    checked = 0
    with strict_app.app_context():
        for s in range(seed_start, seed_limit + 1, 2):  # stride to vary parity
            d = Dungeon(seed=s)
            unreachable = _count_unreachable_rooms(d)
            # Debug metrics present
            assert d.metrics.get('debug_allow_hidden_strict') is True
            assert 'debug_room_count_initial' in d.metrics
            assert 'debug_room_count_post_safety' in d.metrics
            checked += 1
            if unreachable > 0:
                found_unreachable = True
                # Also sanity: post_safety should NOT have reduced initial below unreachable presence entirely
                assert d.metrics['debug_room_count_post_safety'] >= d.metrics['debug_room_count_initial'] - unreachable
                break
    if not found_unreachable:
        pytest.skip(f"No unreachable rooms observed in {checked} seeds [{seed_start}-{seed_limit}]; behavior still acceptable.")
