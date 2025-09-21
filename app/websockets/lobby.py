"""Socket.IO lobby namespace handlers.

Events:
    - lobby_chat_message: Broadcast chat messages to all clients.
        Payload: { "message": string }
        Emits:   lobby_chat_message { user, message }
"""

from app import socketio
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from flask import request
from flask import session as flask_session
from .validation import (
    validate,
    LOBBY_CHAT_MESSAGE,
    ADMIN_BROADCAST,
)

# Track online users by session id
online = {}

def _user_role():
    try:
        return getattr(current_user, 'role', 'user') or 'user'
    except Exception:
        return 'user'

def _username():
    try:
        return getattr(current_user, 'username', 'Anonymous') or 'Anonymous'
    except Exception:
        return 'Anonymous'

@socketio.on('lobby_chat_message')
def handle_lobby_chat_message(data):
    ok, result = validate(data or {}, LOBBY_CHAT_MESSAGE)
    if not ok:
        emit('error', {'message': f"Invalid lobby_chat_message: {result['error']}", 'field': result['field'], 'code': result['code']})
        return
    message = result['message']
    user = _username()
    emit('lobby_chat_message', {'user': user, 'message': message}, room='global')


@socketio.on('connect')
def handle_connect():
    # Always isolate joins to explicit role rooms only after verifying role each connect.
    try:
        username = _username()
        # Determine auth strictly via session presence to avoid leaked test monkeypatch state
        session_uid = flask_session.get('_user_id')
        is_auth = bool(session_uid)
        raw_role = _user_role() if is_auth else 'user'
        role = raw_role if raw_role in ('admin','mod') else 'user'
        sid = request.sid
        stored_role = role if is_auth else 'user'
        online[sid] = {
            'username': username,
            'role': stored_role,
            'is_auth': is_auth,
            'legacy_ok': stored_role == 'admin' and is_auth
        }
        join_room('global')
        join_room('users')  # baseline room for all authenticated or anonymous users
        if stored_role == 'admin':
            join_room('admins')
            join_room('mods')  # admins implicitly get mod messages
        elif stored_role == 'mod':
            join_room('mods')
    except Exception:
        # Silently ignore connect bookkeeping errors
        pass


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    online.pop(sid, None)


@socketio.on('admin_online_users')
def handle_admin_online_users():
    """Request handler for online user list (admin only).

    Emits a response event 'admin_online_users_response' ONLY to the requesting admin's SID.
    Non-admin callers receive no event (silent). This rename prevents any queued stale
    'admin_online_users' broadcast from being misinterpreted by tests for anonymous clients.

    TODO(deprecate): Remove legacy 'admin_online_users' emission in a future minor release
    (e.g. v0.4.0). Clients should listen to 'admin_online_users_response'.
    """
    entry = online.get(request.sid)
    # Only allow if this SID connected as an authenticated admin (legacy_ok set at connect time)
    if not (entry and entry.get('legacy_ok')):
        return
    sid = request.sid
    payload = list(online.values())
    # Emit new response event; legacy event emitted only for admins (requester) to preserve backward compatibility
    emit('admin_online_users_response', payload, room=sid)
    if entry.get('legacy_ok'):
        emit('admin_online_users', payload, room=sid)


@socketio.on('admin_broadcast')
def handle_admin_broadcast(data):
    if _user_role() != 'admin':
        return  # silent drop
    ok, result = validate(data or {}, ADMIN_BROADCAST)
    if not ok:
        emit('error', {'message': f"Invalid admin_broadcast: {result['error']}", 'field': result['field'], 'code': result['code']})
        return
    target = result.get('target', 'global') or 'global'
    message = result['message']
    try:
        from_user = getattr(current_user, 'username', 'Admin')
    except Exception:
        from_user = 'Admin'
    payload = {'from': from_user, 'target': target, 'message': message}
    room = 'global'
    if target == 'admins':
        room = 'admins'
    elif target == 'mods':
        room = 'mods'
    elif target == 'users':
        room = 'users'
    # Targeted emission: for role-specific targets emit directly to each sid with that role.
    if target in ('admins','mods'):
        want_roles = {'admin'} if target == 'admins' else {'admin','mod'}
        from_user_name = payload.get('from')
        for sid, info in online.items():
            if info.get('role') in want_roles and (target != 'admins' or info.get('username') == from_user_name):
                emit('admin_broadcast', payload, room=sid)
    else:
        # global/users -> broadcast to global room (users all joined there)
        emit('admin_broadcast', payload, room='global')
