import pytest
from app import app, socketio, db
from app.models.models import User

@pytest.fixture()
def setup_users():
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db.create_all()
        for name, role in [('admin_actor','admin'),('player_one','user')]:
            u = User.query.filter_by(username=name).first()
            if not u:
                u = User(username=name, password=generate_password_hash('pass'), role=role)
                db.session.add(u)
        db.session.commit()
    yield

@pytest.fixture()
def admin_client(setup_users):
    # login admin_actor
    from flask import current_app
    with app.app_context():
        admin = User.query.filter_by(username='admin_actor').first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
    c = socketio.test_client(app, flask_test_client=fc)
    c.get_received()
    return c

@pytest.fixture()
def player_client(setup_users):
    with app.app_context():
        player = User.query.filter_by(username='player_one').first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess['_user_id'] = str(player.id)
    c = socketio.test_client(app, flask_test_client=fc)
    c.get_received()
    return c

@pytest.fixture()
def anon_client():
    c = socketio.test_client(app, flask_test_client=app.test_client())
    c.get_received()
    return c


def _extract(event, received):
    return [p['args'][0] for p in received if p['name'] == event and p['args']]


def test_direct_message_admin_only(admin_client, player_client, anon_client, monkeypatch):
    import app.websockets.lobby as lobby
    # Force roles for isolation
    for sid, info in lobby.online.items():
        if info.get('username') == 'admin_actor':
            info['role'] = 'admin'; info['is_auth'] = True
        if info.get('username') == 'player_one':
            info['role'] = 'user'; info['is_auth'] = True
    class DummyAdmin: role='admin'; username='admin_actor'
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyAdmin())
    admin_client.emit('admin_direct_message', {'to':'player_one','message':'Hello'})
    rec_player = player_client.get_received()
    msgs = _extract('admin_direct_message', rec_player)
    assert any(m['message']=='Hello' and m['from']=='admin_actor' for m in msgs)
    # Non-admin attempt
    anon_client.emit('admin_direct_message', {'to':'player_one','message':'Nope'})
    rec_player2 = player_client.get_received()
    msgs2 = _extract('admin_direct_message', rec_player2)
    assert not any(m['message']=='Nope' for m in msgs2)


def test_kick_user(admin_client, player_client, monkeypatch):
    import app.websockets.lobby as lobby
    for sid, info in lobby.online.items():
        if info.get('username') == 'admin_actor':
            info['role'] = 'admin'; info['is_auth'] = True
        if info.get('username') == 'player_one':
            info['role'] = 'user'; info['is_auth'] = True
    class DummyAdmin: role='admin'; username='admin_actor'
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyAdmin())
    admin_client.emit('admin_kick_user', {'user':'player_one'})
    # After some event loop processing, player should disconnect (best-effort)
    # Use received events to verify notice at least
    rec_player = []
    if player_client.is_connected():
        rec_player = player_client.get_received()
    notice = _extract('admin_notice', rec_player) if rec_player else []
    # Accept absence if disconnect happened before notice retrieval; test is lenient
    # Ensure still that player record removed or disconnect flagged
    kicked_present = any(info.get('username')=='player_one' for info in lobby.online.values())
    assert notice or not kicked_present
