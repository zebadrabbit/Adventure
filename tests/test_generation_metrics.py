import os
import pytest
from app import create_app, db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import User

@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.setenv('DUNGEON_ENABLE_GENERATION_METRICS', '1')
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', role='admin')
            u.set_password('x')
            db.session.add(u)
            db.session.flush()  # assign id
        inst = DungeonInstance(user_id=u.id, seed=12345, pos_x=10, pos_y=10, pos_z=0)
        db.session.add(inst)
        db.session.commit()
    client = app.test_client()
    # login
    client.post('/login', data={'username':'admin','password':'x'})
    with client.session_transaction() as sess:
        with app.app_context():
            inst = db.session.query(DungeonInstance).first()
            sess['dungeon_instance_id'] = inst.id
    yield client


def test_generation_metrics_endpoint(admin_client):
    r = admin_client.get('/api/dungeon/gen/metrics')
    assert r.status_code == 200
    data = r.get_json()
    assert 'metrics' in data and 'seed' in data
    # Minimal keys
    for k in ['doors_created','doors_downgraded','repairs_performed','chains_collapsed','orphan_fixes','runtime_ms']:
        assert k in data['metrics']
    # Debug keys (added for deterministic flag inspection)
    for k in ['debug_allow_hidden','debug_allow_hidden_strict','debug_room_count_initial','debug_room_count_post_safety']:
        assert k in data['metrics']
        # Basic type sanity
        if k.startswith('debug_room_count'):
            assert isinstance(data['metrics'][k], int)
        elif k.startswith('debug_allow_hidden'):
            assert isinstance(data['metrics'][k], bool)

@pytest.fixture
def hidden_areas_client(monkeypatch):
    monkeypatch.setenv('DUNGEON_ALLOW_HIDDEN_AREAS','1')
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    # Explicitly override config because the app singleton may have been created before env var set
    app.config['DUNGEON_ALLOW_HIDDEN_AREAS'] = True
    # Clear dungeon cache so we don't reuse a dungeon generated without the flag
    try:
        from app.routes.dungeon_api import _dungeon_cache, _dungeon_cache_lock
        with _dungeon_cache_lock:
            _dungeon_cache.clear()
    except Exception:
        pass
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', role='admin')
            u.set_password('x')
            db.session.add(u)
            db.session.flush()
        inst = DungeonInstance(user_id=u.id, seed=54321, pos_x=10, pos_y=10, pos_z=0)
        db.session.add(inst)
        db.session.commit()
    client = app.test_client()
    client.post('/login', data={'username':'admin','password':'x'})
    with client.session_transaction() as sess:
        with app.app_context():
            inst = db.session.query(DungeonInstance).first()
            sess['dungeon_instance_id'] = inst.id
    yield client


def test_hidden_areas_skip_repairs(hidden_areas_client):
    r = hidden_areas_client.get('/api/dungeon/gen/metrics')
    assert r.status_code == 200
    data = r.get_json()
    # When hidden areas allowed we skip repairs; repairs_performed should be 0
    assert data['metrics']['repairs_performed'] == 0
