"""Socket.IO lobby namespace handlers.

Events:
    - lobby_chat_message: Broadcast chat messages to all clients.
        Payload: { "message": string }
        Emits:   lobby_chat_message { user, message }
"""

from app import socketio
from flask_socketio import emit
from flask_login import current_user

@socketio.on('lobby_chat_message')
def handle_lobby_chat_message(data):
    message = (data or {}).get('message', '').strip()
    if not message:
        return
    user = getattr(current_user, 'username', 'Anonymous')
    emit('lobby_chat_message', {'user': user, 'message': message}, broadcast=True)
