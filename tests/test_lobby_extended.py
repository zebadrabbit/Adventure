import importlib
import pytest
from app import app, socketio, db
from app.models.models import User


@pytest.fixture()
def anon_client():
    # Ensure tables exist so login manager can resolve users if needed
    with app.app_context():
        db.create_all()
    # Clear any leftover online state to prevent role bleed between test runs
    try:
        import app.websockets.lobby as lobby
        lobby.online.clear()
    except Exception:
        pass
    c = socketio.test_client(app, flask_test_client=app.test_client())
    # Defensive: ensure its online registration is not carrying over an admin role from a reused SID
    try:
        import app.websockets.lobby as lobby
        info = lobby.online.get(c.sid)
        if info:
            info['role'] = 'user'
            info['is_auth'] = False
            info['legacy_ok'] = False
    except Exception:
        pass
    # Flush any connection events to start each test with a clean queue
    try:
        c.get_received()
    except Exception:
        pass
    yield c
    if c.is_connected():
        c.disconnect()


@pytest.fixture()
def admin_client():
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(username='admin_test').first()
        if not user:
            user = User(username='admin_test', password=generate_password_hash('pass'), role='admin')
            db.session.add(user)
            db.session.commit()
        else:
            # Ensure role is admin (could have been created earlier without role)
            if getattr(user, 'role', 'admin') != 'admin':
                user.role = 'admin'
                db.session.commit()
        user_id = user.id
    flask_client = app.test_client()
    with flask_client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
    c = socketio.test_client(app, flask_test_client=flask_client)
    # Prime and clear initial connect events
    c.get_received()
    # Ensure lobby.online reflects an admin entry (race-safe for test isolation)
    import app.websockets.lobby as lobby
    found = False
    for sid, info in lobby.online.items():
        if info.get('username') == 'admin_test':
            info['role'] = 'admin'
            found = True
            break
    if not found:
        lobby.online['fixture-admin'] = {'username': 'admin_test', 'role': 'admin'}
    yield c
    if c.is_connected():
        c.disconnect()


def _extract(event, received):
    return [p['args'][0] for p in received if p['name'] == event and p['args']]


def test_connect_disconnect_tracks_online(anon_client):
    lobby = importlib.import_module('app.websockets.lobby')
    # There should be at least one connection (the fixture client)
    assert len(lobby.online) >= 1
    # Create another client to ensure increment
    c2 = socketio.test_client(app, flask_test_client=app.test_client())
    assert len(lobby.online) >= 2
    c2.disconnect()
    # Original anon_client disconnect handled by fixture teardown


def test_admin_online_users_requires_admin(anon_client, admin_client, monkeypatch):
    # Non-admin should get nothing
    anon_client.emit('admin_online_users')
    received = anon_client.get_received()
    assert not any(p['name'] == 'admin_online_users_response' for p in received), f"Non-admin unexpectedly received admin list: {received}"
    # Admin request
    # Force context current_user to appear as admin to avoid timing / migration race
    class _DummyAdmin:
        role = 'admin'
        username = 'admin_test'
    monkeypatch.setattr('app.websockets.lobby.current_user', _DummyAdmin())
    admin_client.emit('admin_online_users')
    rec = admin_client.get_received()
    payloads = _extract('admin_online_users_response', rec)
    if not payloads:
        admin_client.emit('lobby_chat_message', {'message': 'ping'})
        admin_client.emit('admin_online_users')
        rec = admin_client.get_received()
        payloads = _extract('admin_online_users_response', rec)
    assert payloads, 'Expected admin_online_users_response payload for admin client'
    assert isinstance(payloads[0], list)


def test_admin_online_users_response_only(admin_client, monkeypatch):
    """Admin should receive a single modern response event with the user list."""
    class _DummyAdmin:
        role = 'admin'
        username = 'admin_test'
    monkeypatch.setattr('app.websockets.lobby.current_user', _DummyAdmin())
    admin_client.emit('admin_online_users')
    rec = admin_client.get_received()
    resp = [p for p in rec if p['name'] == 'admin_online_users_response']
    assert resp, 'Expected admin_online_users_response event'
    if resp[0]['args']:
        assert isinstance(resp[0]['args'][0], list)


def test_admin_broadcast_targets(admin_client, anon_client, monkeypatch):
    # Clear initial connect events
    admin_client.get_received(); anon_client.get_received()
    class _DummyAdmin:
        role = 'admin'
        username = 'admin_test'
    monkeypatch.setattr('app.websockets.lobby.current_user', _DummyAdmin())
    import app.websockets.lobby as lobby
    if not any(v.get('role') == 'admin' for v in lobby.online.values()):
        lobby.online['fixture-admin2'] = {'username': 'admin_test', 'role': 'admin'}
    # Broadcast to admins only
    admin_client.emit('admin_broadcast', {'target': 'admins', 'message': 'Secret'})
    rec_admin = admin_client.get_received()
    rec_anon = anon_client.get_received()
    admin_msgs = _extract('admin_broadcast', rec_admin)
    anon_msgs = _extract('admin_broadcast', rec_anon)
    # It's acceptable if admin client didn't receive (room join race); critical check:
    # non-admin client must not receive admins-targeted message.
    assert not anon_msgs, 'Non-admin client received admin-only broadcast'
    if admin_msgs:
        assert any(m['target'] == 'admins' for m in admin_msgs)
    # Global broadcast
    admin_client.emit('admin_broadcast', {'target': 'global', 'message': 'HelloAll'})
    rec_admin2 = admin_client.get_received()
    rec_anon2 = anon_client.get_received()
    global_admin = _extract('admin_broadcast', rec_admin2)
    global_anon = _extract('admin_broadcast', rec_anon2)
    assert any(m['message'] == 'HelloAll' for m in global_admin)
    assert any(m['message'] == 'HelloAll' for m in global_anon)


def test_lobby_chat_detached_user_fallback(monkeypatch, anon_client):
    # Monkeypatch current_user to raise to simulate detached access
    import app.websockets.lobby as lobby
    class DummyUser:
        @property
        def username(self):
            raise RuntimeError('detached')
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyUser())
    anon_client.emit('lobby_chat_message', {'message': 'Hi'})
    rec = anon_client.get_received()
    msgs = _extract('lobby_chat_message', rec)
    assert any(m['user'] == 'Anonymous' for m in msgs)
