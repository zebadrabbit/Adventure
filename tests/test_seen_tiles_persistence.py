import json
from app import db
from app.models.models import User


def test_seen_tiles_round_trip(auth_client):
    # Ensure clean state for this seed by clearing (empty tiles submission)
    auth_client.post('/api/dungeon/seen', json={'tiles': ''})
    # Initial GET may not be empty if prior tests populated; capture baseline
    r = auth_client.get('/api/dungeon/seen')
    assert r.status_code == 200
    data = r.get_json()
    seed = data['seed']
    baseline_tiles = set(data['tiles'].split(';')) if data['tiles'] else set()

    # Post some tiles
    payload = {'tiles': '1,2;3,4;5,6'}
    r2 = auth_client.post('/api/dungeon/seen', json=payload)
    assert r2.status_code in (200, 202)
    stored = r2.get_json()['stored']
    assert stored >= 3

    # Post overlapping / new tiles (merge test)
    r3 = auth_client.post('/api/dungeon/seen', json={'tiles': '3,4;7,8'})
    assert r3.status_code in (200, 202)
    merged_count = r3.get_json()['stored']
    assert merged_count >= len(baseline_tiles | {'1,2','3,4','5,6','7,8'})

    # Final GET should reflect union
    r4 = auth_client.get('/api/dungeon/seen')
    assert r4.status_code == 200
    data2 = r4.get_json()
    final_tiles = set(data2['tiles'].split(';')) if data2['tiles'] else set()
    assert {'1,2','3,4','5,6','7,8'} <= final_tiles


def test_seen_tiles_bad_format(auth_client):
    r = auth_client.post('/api/dungeon/seen', json={'tiles': 'not_a_tile'})
    assert r.status_code == 400
