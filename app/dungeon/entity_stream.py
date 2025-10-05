"""Entity delta streaming helpers.

Provides an in-memory per-instance ring buffer of recent entity deltas plus
simple snapshot construction for resync. Intended for single-process dev /
small deployment; for multi-process scaling a shared store (Redis) would be
needed.

Exports:
  record_delta(instance_id:int, tick:int, delta:dict) -> dict (final payload w/ seq)
  build_snapshot(instance_id:int) -> dict (full snapshot payload)
  fetch_missing(instance_id:int, since_seq:int) -> list[dict] | None

Delta schema (base):
  {
    'event': 'entities_delta',
    'instance_id': int,
    'seq': int,
    'tick': int,
    'monsters_changed': [ {id, slug, x, y, hp_current?} ],
    'monsters_removed': [ id ],
    'treasures_changed': [ {id, x, y} ],
    'treasures_removed': [ id ]
  }

Snapshot schema:
  {
    'event': 'entities_snapshot',
    'instance_id': int,
    'seq': int,        # current seq head AFTER assigning this snapshot (authoritative)
    'tick': int,
    'full': True,
    'monsters': [... full monster list ...],
    'treasures': [... full treasure list ...]
  }
"""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Deque, Dict, List, Optional

_BUFFER_SIZE = 100
_lock = RLock()
# instance_id -> {'seq': int, 'deltas': deque}
_state: Dict[int, Dict[str, object]] = {}


def _get_state(inst_id: int) -> Dict[str, object]:
    with _lock:
        st = _state.get(inst_id)
        if not st:
            st = {"seq": 0, "deltas": deque(maxlen=_BUFFER_SIZE)}
            _state[inst_id] = st
        return st


def record_delta(instance_id: int, tick: int, delta: dict) -> dict:
    """Assign sequence number, store delta, and return enriched payload.

    The provided delta dict should already contain the changed/removed lists.
    This function adds seq, tick, instance_id, and event='entities_delta'.
    """
    st = _get_state(instance_id)
    with _lock:
        seq = int(st["seq"]) + 1  # type: ignore
        st["seq"] = seq
        payload = {
            "event": "entities_delta",
            "instance_id": instance_id,
            "seq": seq,
            "tick": tick,
            "monsters_changed": delta.get("monsters_changed", []),
            "monsters_removed": delta.get("monsters_removed", []),
            "treasures_changed": delta.get("treasures_changed", []),
            "treasures_removed": delta.get("treasures_removed", []),
        }
        st["deltas"].append(payload)  # type: ignore
        return payload


def build_snapshot(instance_id: int, *, tick: int, monsters: List[dict], treasures: List[dict]) -> dict:
    """Return a full authoritative snapshot and advance seq.

    Snapshot increments the sequence (represents state edge) so subsequent deltas
    start after this number. Clients treat snapshot.seq as their new lastSeq.
    """
    st = _get_state(instance_id)
    with _lock:
        seq = int(st["seq"]) + 1  # type: ignore
        st["seq"] = seq
        snap = {
            "event": "entities_snapshot",
            "instance_id": instance_id,
            "seq": seq,
            "tick": tick,
            "full": True,
            "monsters": monsters,
            "treasures": treasures,
        }
        # We do NOT store snapshots inside delta ring; only deltas are replayed. A snapshot resets baseline.
        return snap


def fetch_missing(instance_id: int, since_seq: int) -> Optional[List[dict]]:
    """Return list of deltas with seq > since_seq if fully available; else None.

    If earliest stored seq is <= since_seq < latest seq and contiguous coverage exists,
    returns list filtered to those with seq greater than since_seq.
    If since_seq is too old (fallen off buffer) returns None (caller should send snapshot).
    If since_seq equals current head, returns empty list.
    """
    st = _get_state(instance_id)
    with _lock:
        deltas: Deque[dict] = st["deltas"]  # type: ignore
        if not deltas:
            # No deltas yet; caller should request snapshot instead
            return [] if since_seq == st["seq"] else None
        first_seq = deltas[0]["seq"]
        current_seq = st["seq"]  # type: ignore
        if since_seq == current_seq:
            return []
        if since_seq < first_seq - 1:
            # Gap too large; can't replay
            return None
        # Filter those strictly greater than since_seq
        missing = [d for d in deltas if d["seq"] > since_seq]
        # Basic contiguity check: expected last seq matches current_seq
        if not missing:
            return []
        if missing[-1]["seq"] != current_seq:
            # Race condition (new delta appended after initial copy); allow caller to retry
            return None
        return missing


__all__ = ["record_delta", "build_snapshot", "fetch_missing"]
