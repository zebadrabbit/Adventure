"""Socket.IO game namespace handlers.

Events:
    - join_game: Join a game room; payload { room }
    - leave_game: Leave a game room; payload { room }
    - game_action: Submit an action; payload { room, action }

Emits:
    - status: Room status updates (join/leave)
    - game_update: Acknowledgement of actions (placeholder for game logic)
"""

from app import socketio
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from .validation import (
    validate,
    JOIN_GAME,
    LEAVE_GAME,
    GAME_ACTION,
)

@socketio.on('join_game')
def handle_join_game(data):
    ok, result = validate(data or {}, JOIN_GAME)
    if not ok:
        emit('error', {'message': f"Invalid join_game: {result['error']}", 'field': result['field'], 'code': result['code']})
        return
    room = result['room']
    join_room(room)
    try:
        user = getattr(current_user, 'username', 'Anonymous')
    except Exception:
        user = 'Anonymous'
    emit('status', {'msg': f'{user} has joined the game.'}, room=room)

@socketio.on('leave_game')
def handle_leave_game(data):
    ok, result = validate(data or {}, LEAVE_GAME)
    if not ok:
        emit('error', {'message': f"Invalid leave_game: {result['error']}", 'field': result['field'], 'code': result['code']})
        return
    room = result['room']
    leave_room(room)
    try:
        user = getattr(current_user, 'username', 'Anonymous')
    except Exception:
        user = 'Anonymous'
    emit('status', {'msg': f'{user} has left the game.'}, room=room)

@socketio.on('game_action')
def handle_game_action(data):
    ok, result = validate(data or {}, GAME_ACTION)
    if not ok:
        emit('error', {'message': f"Invalid game_action: {result['error']}", 'field': result['field'], 'code': result['code']})
        return
    room = result['room']
    action = result['action']
    # Placeholder for future game logic
    emit('game_update', {'msg': f'Action processed: {action}'}, room=room)
