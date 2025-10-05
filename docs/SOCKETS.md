# Socket Architecture

This document summarizes the current real-time socket design and instrumentation in Adventure MUD.

## Overview

Adventure uses a single primary Socket.IO namespace (`/adventure`) for in-dungeon realtime events plus the default namespace (root) for lobby/chat/admin lightweight events. The consolidation from multiple namespaces reduced duplicate connection overhead and eliminated a burst of parallel Engine.IO ping sessions previously observed.

## Namespaces

- `root` ("/") – Lobby chat, lightweight status pings, optional admin instrumentation.
- `/adventure` – Dungeon movement, encounters, combat event streaming (planned richer delta snapshots).

## Connection Lifecycle Instrumentation

`app/instrumentation/socket_stats.py` exports a `SocketStats` singleton that tracks:
- Total connects/disconnects per namespace
- Active connection IDs grouped by user id
- Per-user counts

Endpoint: `GET /api/debug/sockets` (admin only) returns a JSON snapshot:
```json
{
  "namespaces": {"/": 2, "/adventure": 1},
  "users": {"42": {"/": 1, "/adventure": 1}},
  "totals": {"connections": 3}
}
```

## Client Strategy

All game JS modules reuse a single lazy-initialized socket instance. Avoid multiple `io()` calls—import and share the created socket. This prevents connection fan-out and reduces server heartbeat traffic.

## Planned Evolution

1. Entity Snapshot Bootstrap – Initial dungeon load fetches a full state snapshot once.
2. Delta Event Stream – Subsequent updates delivered via small diffs over `/adventure`.
3. Backpressure Handling – Queue & coalesce high-frequency movement events server-side.

## Debugging Tips

- Use `/api/debug/sockets` while loading pages to confirm one connection per namespace per tab.
- Open browser devtools -> Network -> WS to ensure only expected sockets.
- Instrument client with simple counters (already present in debug builds) to watch reconnection patterns.

## Adding New Realtime Features

1. Decide if it belongs to lobby (`/`) or gameplay (`/adventure`).
2. Extend existing socket module; do not create a new namespace without a strong isolation motive.
3. Emit structured events: `{type: 'monster.spawn', payload: {...}}` to allow future generic handlers.

## Security & Limits

- Authentication enforced at Flask level before serving pages that initialize sockets.
- Consider adding per-user rate limiting for chat and movement events (not yet implemented).

## Glossary

- Namespace: Logical channel for grouping events in Socket.IO.
- Engine Connection: Underlying WebSocket/long-poll transport session.
- Delta: Incremental update representing changes since last client-applied state.

---
Last updated: 2025-10-05
