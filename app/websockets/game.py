from app import socketio
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user

@socketio.on('join_game')
def handle_join_game(data):
    room = data.get('room')
    join_room(room)
    emit('status', {'msg': f'{current_user.username} has joined the game.'}, room=room)

@socketio.on('leave_game')
def handle_leave_game(data):
    room = data.get('room')
    leave_room(room)
    emit('status', {'msg': f'{current_user.username} has left the game.'}, room=room)

@socketio.on('game_action')
def handle_game_action(data):
    room = data.get('room')
    action = data.get('action')
    # Process action here
    emit('game_update', {'msg': f'Action processed: {action}'}, room=room)
