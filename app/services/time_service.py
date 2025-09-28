"""Time / tick advancement service.

Advances the global non-combat game clock for actions like movement, search,
item use, and spell casting. Future combat integration can gate advancement
via an in_combat() predicate.
"""

from __future__ import annotations

from typing import Optional

from app import db, socketio
from app.models import GameClock

# Placeholder combat state checker (can be replaced with real logic later)


def in_combat() -> bool:
    # TODO: integrate with combat encounter state when implemented
    return False


def advance_time(delta: int, reason: str, actor_id: Optional[int] = None) -> int:
    """Advance the global clock by delta ticks if not in combat.

    Emits a 'time_update' Socket.IO event on namespace '/adventure'.
    Returns the new tick count.
    """
    if delta <= 0:
        return GameClock.get().tick
    if in_combat():  # Pause ticking during combat
        return GameClock.get().tick
    clock = GameClock.get()
    clock.tick += delta
    try:
        db.session.add(clock)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return clock.tick  # return last known even if failed
    payload = {"tick": clock.tick, "delta": delta, "reason": reason, "actor_id": actor_id}
    try:
        socketio.emit("time_update", payload, namespace="/adventure")
    except Exception:
        # Emission failure should not rollback time advancement
        pass
    return clock.tick
