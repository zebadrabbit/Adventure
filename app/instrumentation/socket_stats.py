"""Runtime Socket.IO instrumentation utilities.

Provides a lightweight, thread-safe in‑memory tracker for active Socket.IO
connections keyed by user id (or "anon" for unauthenticated visitors) and
namespace. This is intended for local diagnostics and the /api/debug/sockets
endpoint – NOT for authoritative security decisions (process memory resets
on deploy and does not aggregate across multiple workers).

Public object: ``socket_stats``
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Set


class SocketStats:
    """Track active sockets and provide point‑in‑time snapshots.

    Data model (all in memory / best‑effort):
      user_sids: { user_key: {sid, ...} }
      sid_meta:  { sid: { 'user': user_key, 'namespace': str, 'connected_at': ts } }
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.user_sids: Dict[str, Set[str]] = defaultdict(set)
        self.sid_meta: Dict[str, Dict[str, Any]] = {}
        self._connect_count = 0
        self._disconnect_count = 0

    # ---- Event hooks --------------------------------------------------
    def on_connect(self, *, user_id: int | None, username: str | None, sid: str, namespace: str) -> None:
        user_key = f"user:{user_id}" if user_id else "anon"
        with self._lock:
            self.user_sids[user_key].add(sid)
            self.sid_meta[sid] = {
                "user": user_key,
                "username": username or "Anonymous",
                "namespace": namespace,
                "connected_at": int(time.time()),
            }
            self._connect_count += 1

    def on_disconnect(self, sid: str) -> None:
        with self._lock:
            meta = self.sid_meta.pop(sid, None)
            if meta:
                user_key = meta.get("user")
                bucket = self.user_sids.get(user_key)
                if bucket and sid in bucket:
                    bucket.discard(sid)
                    if not bucket:
                        self.user_sids.pop(user_key, None)
            self._disconnect_count += 1

    # ---- Snapshot / serialization ------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            users: List[dict] = []
            for user_key, sids in sorted(self.user_sids.items()):
                users.append(
                    {
                        "user": user_key,
                        "connections": len(sids),
                    }
                )
            meta = {
                "total_active_sids": len(self.sid_meta),
                "unique_users": len(self.user_sids),
                "connect_events": self._connect_count,
                "disconnect_events": self._disconnect_count,
            }
            namespaces = {}
            for sd, m in self.sid_meta.items():
                ns = m.get("namespace") or "/"
                namespaces[ns] = namespaces.get(ns, 0) + 1
            return {
                "meta": meta,
                "users": users,
                "namespaces": namespaces,
                "sids": self._redacted_sid_list(),
            }

    def _redacted_sid_list(self) -> List[dict]:
        # Provide minimal per-sid info (avoid leaking raw sids in logs if copied)
        out: List[dict] = []
        for sid, m in self.sid_meta.items():
            out.append(
                {
                    "sid_tail": sid[-6:],
                    "user": m.get("user"),
                    "namespace": m.get("namespace"),
                    "age_s": int(time.time()) - int(m.get("connected_at", 0)),
                }
            )
        return out


socket_stats = SocketStats()
