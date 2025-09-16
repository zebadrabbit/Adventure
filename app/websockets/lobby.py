from app import socketio
from flask_socketio import emit
from flask_login import current_user

@socketio.on('lobby_chat_message')
def handle_lobby_chat_message(data):
    message = data.get('message', '').strip()
    if not message:
        return
    user = getattr(current_user, 'username', 'Anonymous')
    emit('lobby_chat_message', {'user': user, 'message': message}, broadcast=True)
