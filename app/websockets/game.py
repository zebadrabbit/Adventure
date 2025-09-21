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

@socketio.on('join_game')
def handle_join_game(data):
    room = (data or {}).get('room')
    if not room:
        return
    join_room(room)
    try:
        user = getattr(current_user, 'username', 'Anonymous')
    except Exception:
        user = 'Anonymous'
    emit('status', {'msg': f'{user} has joined the game.'}, room=room)

@socketio.on('leave_game')
def handle_leave_game(data):
    room = (data or {}).get('room')
    if not room:
        return
    leave_room(room)
    try:
        user = getattr(current_user, 'username', 'Anonymous')
    except Exception:
        user = 'Anonymous'
    emit('status', {'msg': f'{user} has left the game.'}, room=room)

@socketio.on('game_action')
def handle_game_action(data):
    payload = data or {}
    room = payload.get('room')
    action = payload.get('action')
    if not room or not action:
        return
    # Process action here
    emit('game_update', {'msg': f'Action processed: {action}'}, room=room)
