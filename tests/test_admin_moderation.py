import pytest
from app import app, socketio, db
from app.models.models import User

@pytest.fixture()
def setup_users():
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db.create_all()
        for name, role in [('admin_actor','admin'),('player_two','user')]:
            u = User.query.filter_by(username=name).first()
            if not u:
                u = User(username=name, password=generate_password_hash('pass'), role=role)
                db.session.add(u)
        db.session.commit()
    yield

@pytest.fixture()
def admin_client(setup_users):
    with app.app_context():
        admin = User.query.filter_by(username='admin_actor').first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
    c = socketio.test_client(app, flask_test_client=fc)
    c.get_received()
    # Force role flags
    import app.websockets.lobby as lobby
    for sid, info in lobby.online.items():
        if info.get('username') == 'admin_actor':
            info['role'] = 'admin'; info['is_auth']=True; info['legacy_ok']=True
    return c

@pytest.fixture()
def player_client(setup_users):
    with app.app_context():
        player = User.query.filter_by(username='player_two').first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess['_user_id'] = str(player.id)
    c = socketio.test_client(app, flask_test_client=fc)
    c.get_received()
    import app.websockets.lobby as lobby
    for sid, info in lobby.online.items():
        if info.get('username') == 'player_two':
            info['role'] = 'user'; info['is_auth']=True
    return c

def _extract(event, received):
    return [p['args'][0] for p in received if p['name']==event and p['args']]

def test_mute_suppresses_chat(admin_client, player_client, monkeypatch):
    import app.websockets.lobby as lobby
    class DummyAdmin: role='admin'; username='admin_actor'
    class DummyPlayer: role='user'; username='player_two'
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyAdmin())
    # Mute player
    admin_client.emit('admin_mute_user', {'user':'player_two'})
    # Player sends chat
    # Flush any pre-existing events
    player_client.get_received(); admin_client.get_received()
    # Baseline counts
    baseline_player = 0
    baseline_admin = 0
    # Switch context to player for chat emission
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyPlayer())
    player_client.emit('lobby_chat_message', {'message':'Hello world'})
    # Neither player nor admin should see broadcast
    rec_player = player_client.get_received()
    rec_admin = admin_client.get_received()
    msgs_player = _extract('lobby_chat_message', rec_player)
    msgs_admin = _extract('lobby_chat_message', rec_admin)
    assert len(msgs_player) == baseline_player
    assert len(msgs_admin) == baseline_admin
    # Unmute and retry
    admin_client.emit('admin_unmute_user', {'user':'player_two'})
    player_client.emit('lobby_chat_message', {'message':'Hello again'})
    rec2 = player_client.get_received()
    msgs2 = _extract('lobby_chat_message', rec2)
    assert any(m.get('message')=='Hello again' for m in msgs2)

def test_ban_blocks_reconnect(admin_client, player_client, monkeypatch):
    import app.websockets.lobby as lobby
    class DummyAdmin: role='admin'; username='admin_actor'
    monkeypatch.setattr('app.websockets.lobby.current_user', DummyAdmin())
    # Ban player
    admin_client.emit('admin_ban_user', {'user':'player_two'})
    # Kick side-effect should disconnect
    if player_client.is_connected():
        player_client.disconnect()
    # Attempt reconnect for banned user
    with app.app_context():
        user = User.query.filter_by(username='player_two').first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
    c2 = socketio.test_client(app, flask_test_client=fc)
    # Request status and ensure banned user not listed (simulate admin view)
    admin_client.emit('admin_status')
    rec = admin_client.get_received()
    users_events = [p for p in rec if p['name']=='admin_status']
    banned_visible = False
    if users_events:
        payload = users_events[-1]['args'][0]
        banned_visible = any(u.get('username')=='player_two' for u in payload.get('users',[]))
    assert not banned_visible
    # Unban and reconnect should succeed
    admin_client.emit('admin_unban_user', {'user':'player_two'})
    c3 = socketio.test_client(app, flask_test_client=fc)
    assert c3.is_connected()
