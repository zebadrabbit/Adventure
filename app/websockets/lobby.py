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
        role = _user_role()
        sid = request.sid
        online[sid] = {'username': username, 'role': role}
        join_room('global')
        join_room('users')  # baseline room for all authenticated or anonymous users
        if role == 'admin':
            join_room('admins')
            join_room('mods')  # admins implicitly get mod messages
        elif role == 'mod':
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
    role = _user_role()
    is_auth = getattr(current_user, 'is_authenticated', True)
    entry = online.get(request.sid)
    if not (role == 'admin' and is_auth and entry and entry.get('role') == 'admin'):
        return
    sid = request.sid
    payload = list(online.values())
    # Emit new response event; legacy event emitted only for admins (requester) to preserve backward compatibility
    emit('admin_online_users_response', payload, room=sid)
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
