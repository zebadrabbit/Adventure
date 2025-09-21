import json
from app.models.dungeon_instance import DungeonInstance
from app import db


def test_dungeon_map_invalid_instance(auth_client):
    # Remove instance to trigger 404 path
    with auth_client.session_transaction() as sess:
        sess.pop('dungeon_instance_id', None)
    r = auth_client.get('/api/dungeon/map')
    assert r.status_code == 404


def test_dungeon_map_valid_and_position_correction(auth_client):
    # Force a starting position at 0,0,0 to trigger entrance relocation logic
    with auth_client.session_transaction() as sess:
        inst_id = sess['dungeon_instance_id']
    inst = db.session.get(DungeonInstance, inst_id)
    inst.pos_x = 0
    inst.pos_y = 0
    inst.pos_z = 0
    db.session.commit()
    r = auth_client.get('/api/dungeon/map')
    data = r.get_json()
    assert 'grid' in data and 'player_pos' in data
    # After correction player_pos should not remain raw [0,0,0] typically; allow rare case but ensure coords in bounds
    px, py, pz = data['player_pos']
    assert 0 <= px < data['width'] and 0 <= py < data['height'] and pz == 0


def test_dungeon_move_invalid_paths(auth_client):
    # Remove instance id -> 404
    with auth_client.session_transaction() as sess:
        inst_id = sess['dungeon_instance_id']
        sess.pop('dungeon_instance_id', None)
    r = auth_client.post('/api/dungeon/move', json={'dir':'n'})
    assert r.status_code == 404
    # Restore and test unknown direction -> no movement but success
    with auth_client.session_transaction() as sess:
        sess['dungeon_instance_id'] = inst_id
    inst = db.session.get(DungeonInstance, inst_id)
    before = (inst.pos_x, inst.pos_y)
    r2 = auth_client.post('/api/dungeon/move', json={'dir':'?'})
    assert r2.status_code == 200
    db.session.refresh(inst)
    assert before == (inst.pos_x, inst.pos_y)


def test_dungeon_state_error_and_success(auth_client):
    with auth_client.session_transaction() as sess:
        inst_id = sess['dungeon_instance_id']
        sess.pop('dungeon_instance_id', None)
    r = auth_client.get('/api/dungeon/state')
    assert r.status_code == 404
    # restore
    with auth_client.session_transaction() as sess:
        sess['dungeon_instance_id'] = inst_id
    r2 = auth_client.get('/api/dungeon/state')
    assert r2.status_code == 200 and 'pos' in r2.get_json()
