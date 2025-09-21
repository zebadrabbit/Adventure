import hashlib
from app import db


def test_seed_regenerate_random(auth_client):
    r = auth_client.post('/api/dungeon/seed', json={'regenerate': True})
    data = r.get_json()
    assert 'seed' in data


def test_seed_string_and_numeric(auth_client):
    r = auth_client.post('/api/dungeon/seed', json={'seed':'alpha'})
    s1 = r.get_json()['seed']
    r2 = auth_client.post('/api/dungeon/seed', json={'seed':'alpha'})
    assert s1 == r2.get_json()['seed']
    r3 = auth_client.post('/api/dungeon/seed', json={'seed':'12345'})
    assert r3.get_json()['seed'] == 12345


def test_seed_empty_string(auth_client):
    r = auth_client.post('/api/dungeon/seed', json={'seed':' '})
    assert 'seed' in r.get_json()


def test_seed_null_value(auth_client):
    r = auth_client.post('/api/dungeon/seed', json={'seed': None})
    assert 'seed' in r.get_json()
