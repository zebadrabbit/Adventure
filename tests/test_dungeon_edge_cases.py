import json
import pytest
from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import User

@pytest.fixture()
def edge_client(test_app):
    from werkzeug.security import generate_password_hash
    with test_app.app_context():
        db.create_all()
        u = User.query.filter_by(username='edgeuser').first()
        if not u:
            u = User(username='edgeuser', password=generate_password_hash('pass'))
            db.session.add(u)
            db.session.commit()
        uid = u.id
        inst = DungeonInstance.query.filter_by(user_id=uid).first()
        if not inst:
            inst = DungeonInstance(user_id=uid, seed=1, pos_x=0, pos_y=0, pos_z=0)
            db.session.add(inst)
            db.session.commit()
        inst_id = inst.id
    c = test_app.test_client()
    c.post('/login', data={'username':'edgeuser','password':'pass'}, follow_redirects=True)
    with c.session_transaction() as sess:
        sess['dungeon_instance_id'] = inst_id
    return c


def test_dungeon_map_relocates_invalid_start(edge_client):
    # Force player position to an invalid wall far away (simulate stale DB values)
    with edge_client.application.app_context():
        inst = DungeonInstance.query.first()
        inst.pos_x = 0
        inst.pos_y = 0
        db.session.commit()
    r = edge_client.get('/api/dungeon/map')
    assert r.status_code == 200
    data = r.get_json()
    # Player should have been moved to a valid entrance (not 0,0) and within bounds
    pos = data['player_pos']
    assert pos != [0,0,0]
    assert 0 <= pos[0] < data['width']
    assert 0 <= pos[1] < data['height']


def test_dungeon_move_noop_and_invalid_dir(edge_client):
    # No-op move (empty direction) should return current position
    r0 = edge_client.post('/api/dungeon/move', json={'dir': ''})
    assert r0.status_code == 200
    pos0 = r0.get_json()['pos']
    # Invalid direction ignored
    r_bad = edge_client.post('/api/dungeon/move', json={'dir': 'zzz'})
    assert r_bad.status_code == 200
    pos_bad = r_bad.get_json()['pos']
    assert pos0 == pos_bad


def test_dungeon_move_and_state(edge_client):
    # Prime map to ensure valid placement
    edge_client.get('/api/dungeon/map')
    # Fetch state (should not move)
    st = edge_client.get('/api/dungeon/state')
    assert st.status_code == 200
    data = st.get_json()
    pos_before = data['pos']
    # Try moving north (may or may not succeed depending on map); ensure response shape
    mv = edge_client.post('/api/dungeon/move', json={'dir': 'n'})
    assert mv.status_code == 200
    data_mv = mv.get_json()
    assert set(data_mv.keys()) == {'pos','desc','exits'}
    assert isinstance(data_mv['exits'], list)
    # State again should reflect persisted position
    st2 = edge_client.get('/api/dungeon/state')
    assert st2.status_code == 200
    pos_after = st2.get_json()['pos']
    # Either moved or remained; both acceptable depending on walkability, but structure must hold
    assert len(pos_after) == 3
    assert all(isinstance(i, int) for i in pos_after)
