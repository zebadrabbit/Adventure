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

# Track active game rooms with simple membership counts for admin diagnostics
# Structure: { room_name: { 'members': set([sid,...]), 'created': timestamp } }
import time
try:
    from app.logging_utils import log as _log
except Exception:  # pragma: no cover
    class _NoLog:  # fallback
        def info(self, **k): pass
    _log = _NoLog()
active_games = {}

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
    # Track membership
    from flask import request
    sid = request.sid
    info = active_games.setdefault(room, {'members': set(), 'created': time.time()})
    info['members'].add(sid)
    emit('status', {'msg': f'{user} has joined the game.'}, room=room)
    _log.info(event="join_game", room=room, user=user, members=len(info['members']))

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
    from flask import request
    sid = request.sid
    info = active_games.get(room)
    if info:
        info['members'].discard(sid)
        if not info['members']:
            # prune empty room for cleanliness
            active_games.pop(room, None)
    emit('status', {'msg': f'{user} has left the game.'}, room=room)
    _log.info(event="leave_game", room=room, user=user, remaining=len(info['members']) if info else 0)

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
    _log.info(event="game_action", room=room, action=action)
