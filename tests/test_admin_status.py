import pytest
from app import app, socketio, db
from app.models.models import User

@pytest.fixture()
def anon_client():
    with app.app_context():
        db.create_all()
    import app.websockets.lobby as lobby
    lobby.online.clear()
    c = socketio.test_client(app, flask_test_client=app.test_client())
    c.get_received()
    yield c
    if c.is_connected():
        c.disconnect()

@pytest.fixture()
def admin_client():
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(username='admin_status').first()
        if not user:
            user = User(username='admin_status', password=generate_password_hash('pass'), role='admin')
            db.session.add(user)
            db.session.commit()
        user_id = user.id
    flask_client = app.test_client()
    with flask_client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
    c = socketio.test_client(app, flask_test_client=flask_client)
    c.get_received()
    # Ensure entry is admin
    import app.websockets.lobby as lobby
    for info in lobby.online.values():
        if info.get('username') == 'admin_status':
            info['role'] = 'admin'
            info['legacy_ok'] = True
    yield c
    if c.is_connected():
        c.disconnect()


def _extract(event, received):
    return [p['args'][0] for p in received if p['name'] == event and p['args']]


def test_admin_status_non_admin_blocked(anon_client):
    anon_client.emit('admin_status')
    rec = anon_client.get_received()
    assert not any(p['name'] == 'admin_status' for p in rec), f"Non-admin received admin_status: {rec}"


def test_admin_status_shape(admin_client, monkeypatch):
    class DummyAdmin:
        role = 'admin'
        username = 'admin_status'
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyAdmin())
    # Simulate a couple of active games by creating fake entries in active_games
    import app.websockets.game as game_ws
    game_ws.active_games.clear()
    game_ws.active_games['alpha'] = {'members': set(['sid1','sid2']), 'created': 1234.5}
    game_ws.active_games['beta'] = {'members': set(['sid3']), 'created': 2345.6}
    admin_client.emit('admin_status')
    rec = admin_client.get_received()
    payloads = _extract('admin_status', rec)
    assert payloads, 'Expected admin_status payload'
    payload = payloads[0]
    for key in ('users','counts','active_games','server'):
        assert key in payload, f'Missing key {key}'
    counts = payload['counts']
    for ck in ('total','authenticated','admins','mods'):
        assert ck in counts, f'Missing count key {ck}'
    games = payload['active_games']
    rooms = {g['room'] for g in games}
    assert {'alpha','beta'} <= rooms
    server_meta = payload['server']
    assert server_meta.get('rooms_tracked') == 2
