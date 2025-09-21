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

# Track online users by session id
online = {}

@socketio.on('lobby_chat_message')
def handle_lobby_chat_message(data):
    message = (data or {}).get('message', '').strip()
    if not message:
        return
    try:
        user = getattr(current_user, 'username', 'Anonymous')
    except Exception:
        user = 'Anonymous'
    emit('lobby_chat_message', {'user': user, 'message': message}, broadcast=True)


@socketio.on('connect')
def handle_connect():
    try:
        try:
            username = getattr(current_user, 'username', 'Anonymous')
        except Exception:
            username = 'Anonymous'
        try:
            role = getattr(current_user, 'role', 'user')
        except Exception:
            role = 'user'
        sid = request.sid
        online[sid] = {'username': username, 'role': role}
        # join role rooms for targeted broadcasts
        join_room('global')
        if role == 'admin':
            join_room('admins')
        if role in ('admin', 'mod'):
            join_room('mods')
        join_room('users')
    except Exception:
        pass


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    online.pop(sid, None)


@socketio.on('admin_online_users')
def handle_admin_online_users():
    try:
        role = getattr(current_user, 'role', 'user')
    except Exception:
        role = 'user'
    if role != 'admin':
        return
    emit('admin_online_users', list(online.values()))


@socketio.on('admin_broadcast')
def handle_admin_broadcast(data):
    try:
        role = getattr(current_user, 'role', 'user')
    except Exception:
        role = 'user'
    if role != 'admin':
        return
    target = (data or {}).get('target', 'global')
    message = (data or {}).get('message', '').strip()
    if not message:
        return
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
    emit('admin_broadcast', payload, room=room)
