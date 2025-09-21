# WebSocket Event Contracts

This document describes the current (alpha) WebSocket namespaces, events, and payload schemas used by Adventure. It is meant to stabilize expectations for client & future tooling. All events use JSON payloads.

Namespaces:
- `/lobby` – Session lobby, chat, presence, and (future) party coordination.
- `/game` – In-dungeon gameplay events (movement, combat, state sync – future expansion).

## Common Conventions
- Server → client events use snake_case names.
- Client → server emits may use the same event name unless noted.
- Authentication: Current prototype relies on the Flask session cookie. Future enhancement may add a signed auth token passed during connection.
- Errors: When validation fails, the server emits an `error` event with `{ "message": str, "code": optional_int }` on the same namespace.

---
## Lobby Namespace `/lobby`

### Events (Client → Server)
| Event | Payload | Description |
|-------|---------|-------------|
| `join` | `{ "username": string }` | (Planned) Explicitly announce lobby presence (currently implicit on connect). |
| `chat_message` | `{ "message": string }` | Send a chat line to all connected lobby clients. Empty/whitespace-only messages rejected. |
| `admin_broadcast` | `{ "message": string }` | (Admin only) Broadcast a system / announcement message. Non-admins ignored (no error to reduce spam probing). |

### Events (Server → Client)
| Event | Payload | Description |
|-------|---------|-------------|
| `chat_message` | `{ "username": string, "message": string, "timestamp": iso8601 }` | Normal user chat line. |
| `system_message` | `{ "message": string, "level": "info"|"warning"|"error", "timestamp": iso8601 }` | System / admin broadcast or server notice. |
| `user_joined` | `{ "username": string }` | (Planned) User presence notification. |
| `user_left` | `{ "username": string }` | (Planned) User disconnect notification. |

### Validation Rules
- `chat_message.message`: trimmed length > 0 and <= 500 chars (target cap; enforce once implemented). Future: rate limiting & spam filters.
- `admin_broadcast.message`: same base rules; silently ignored if sender lacks admin role.

---
## Game Namespace `/game`
(Current implementation minimal; foundation for future expansion.)

### Events (Client → Server)
| Event | Payload | Description |
|-------|---------|-------------|
| `join_game` | `{ "character_ids": [int, ...] }` | (Planned) Join game session with selected party. |
| `game_action` | `{ "action": string, "data": object }` | Generic action envelope (movement, ability, interaction). Currently used as a pass-through test hook. |

### Events (Server → Client)
| Event | Payload | Description |
|-------|---------|-------------|
| `game_state` | `{ "dungeon_instance_id": int, "pos": [x,y,z], "exits": [string,...], "desc": string }` | (Planned) Snapshot of current cell state. |
| `action_result` | `{ "action": string, "result": object }` | Outcome of a generic `game_action`. |
| `error` | `{ "message": string, "code"?: int }` | Validation / processing error. |

### Planned Movement Event Split
Future movement may shift to a dedicated event (`move`) with payload `{ "dir": "N|S|E|W" }` returning `{ "pos": [x,y,z], "exits": [...], "desc": str }` for clarity vs generic action envelope.

---
## Versioning & Stability
- This contract is pre-1.0 and may evolve; breaking changes will be documented in `docs/CHANGELOG.md` under “Changed”.
- Consider adding automated schema validation & TypeScript definitions once event set solidifies.

## Roadmap Ideas
- Presence roster event (`roster`) listing active users.
- Room / channel partitioning in lobby for topic-based chat.
- Combat events: `attack`, `damage_event`, `status_update`.
- Party sync: `party_update` broadcasting composition & ready state.
- Heartbeat / latency metrics event.

---
## Client Examples

### JavaScript (Browser) – Lobby Chat
```js
import { io } from 'https://cdn.socket.io/4.7.2/socket.io.esm.min.js';

// Reuses Flask session cookie; no extra auth token yet
const lobby = io('/lobby', { transports: ['websocket'] });

lobby.on('connect', () => {
	console.log('Connected to lobby');
	lobby.emit('lobby_chat_message', { message: 'Hello dungeon!' });
});

lobby.on('lobby_chat_message', (payload) => {
	console.log(`${payload.user}: ${payload.message}`);
});

lobby.on('error', (err) => {
	console.warn('Lobby error', err);
});
```

### JavaScript – Game Namespace
```js
const game = io('/game', { transports: ['websocket'] });

game.on('connect', () => {
	game.emit('join_game', { room: 'seed-42' });
	game.emit('game_action', { room: 'seed-42', action: 'look' });
});

game.on('status', (s) => console.log('[status]', s.msg));
game.on('game_update', (u) => console.log('[update]', u.msg));
game.on('error', (e) => console.warn('[game error]', e));
```

### Python (socketio-client)
```py
import socketio

sio = socketio.Client()

@sio.event(namespace='/lobby')
def connect():
		print('Connected to lobby')
		sio.emit('lobby_chat_message', {'message': 'Hi from Python'}, namespace='/lobby')

@sio.on('lobby_chat_message', namespace='/lobby')
def on_chat(data):
		print('Chat:', data)

@sio.on('error', namespace='/lobby')
def on_error(err):
		print('Error:', err)

sio.connect('http://localhost:5000/lobby', transports=['websocket'])
sio.wait()
```

Notes:
- Error events follow `{ message, field?, code? }` shape.
- The current auth model depends on the Flask session cookie; cross-origin clients may need proper CORS & cookie settings.

---
_Last updated: 2025-09-21_
