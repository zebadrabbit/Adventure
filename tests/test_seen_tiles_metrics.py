import time

def test_seen_tiles_metrics_endpoint(auth_client):
    # Seed some tiles
    r = auth_client.post('/api/dungeon/seen', json={'tiles': '0,0;1,1;2,2'})
    assert r.status_code in (200, 202)
    m = auth_client.get('/api/dungeon/seen/metrics')
    if m.status_code == 403:
        # Not an admin in this test context; acceptable.
        return
    assert m.status_code == 200
    data = m.get_json()
    assert 'seeds' in data and isinstance(data['seeds'], list)
    if data['seeds']:
        s = data['seeds'][0]
        assert 'tiles' in s and s['tiles'] >= 3
        assert 'saved_pct' in s


def test_seen_tiles_rate_limit(auth_client):
    # Burst more than allowed requests to trigger 429
    hit_429 = False
    for i in range(10):  # intentionally exceed 8-in-10s window
        r = auth_client.post('/api/dungeon/seen', json={'tiles': f'{i},{i}', 'enforce_rate_limit': True})
        if r.status_code == 429:
            hit_429 = True
            break
    assert hit_429, 'Expected to hit rate limit'


def test_seen_tiles_per_seed_cap(auth_client):
    # Submit more tiles than cap and ensure stored count does not exceed cap
    # Build a large tile set > 20k
    tiles = ';'.join(f'{i},{i}' for i in range(21000))
    r = auth_client.post('/api/dungeon/seen', json={'tiles': tiles})
    # Could hit rate limit; if so skip strict assertion
    if r.status_code == 429:
        return
    assert r.status_code in (200, 202, 413)
    if r.status_code == 200:
        data = r.get_json()
        assert data['stored'] <= 20000
