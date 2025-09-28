"""Time / tick advancement service.

Advances the global non-combat game clock for actions like movement, search,
item use, and spell casting. Future combat integration can gate advancement
via an in_combat() predicate.
"""

from __future__ import annotations

from typing import Optional, Dict

from app import db, socketio
from app.models import GameClock, GameConfig

# Placeholder combat state checker (can be replaced with real logic later)


def in_combat() -> bool:
    """Return True if the game is currently in a combat encounter.

    For now, we inspect a transient flag on the GameClock row (added later) or
    return False if unsupported. This will evolve once the combat system lands.
    """
    try:
        clock = GameClock.get()
        return bool(getattr(clock, "combat", False))
    except Exception:
        return False


# Default per-action tick costs (can be overridden via GameConfig row 'tick_costs')
DEFAULT_ACTION_TICK_COSTS: Dict[str, int] = {
    "move": 1,
    "search": 2,
    "use_item": 1,
    "cast_spell": 1,
    "equip": 0,  # equipment changes might be free (adjust later)
    "unequip": 0,
    "consume": 1,
    "loot_claim": 0,  # claiming loot itself may not consume time
}


def _load_action_costs() -> Dict[str, int]:
    try:
        cfg = GameConfig.get("tick_costs")
        if not cfg:
            return DEFAULT_ACTION_TICK_COSTS
        import json as _json

        data = _json.loads(cfg)
        if not isinstance(data, dict):  # defensive
            return DEFAULT_ACTION_TICK_COSTS
        # Merge defaults so missing keys fall back
        merged = dict(DEFAULT_ACTION_TICK_COSTS)
        for k, v in data.items():
            try:
                iv = int(v)
            except Exception:
                continue
            if iv < 0:
                iv = 0
            merged[k] = iv
        return merged
    except Exception:
        return DEFAULT_ACTION_TICK_COSTS


def advance_for(action: str, actor_id: Optional[int] = None) -> int:
    """Advance time based on an action key using the configured cost table.

    Returns the new tick value (or current if no advancement applied).
    """
    costs = _load_action_costs()
    delta = int(costs.get(action, 0))
    if delta <= 0:
        return GameClock.get().tick
    return advance_time(delta, reason=action, actor_id=actor_id)


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


def set_combat_state(on: bool) -> bool:
    """Set the global combat state flag on the GameClock row.

    Returns the new state (True/False). Emits 'combat_state' Socket.IO event if changed.
    Safe to call repeatedly. Swallows DB/emit errors.
    """
    try:
        clock = GameClock.get()
    except Exception:
        return False
    new_val = bool(on)
    if bool(getattr(clock, "combat", False)) == new_val:
        return new_val
    try:
        clock.combat = new_val  # type: ignore[attr-defined]
        db.session.add(clock)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return bool(getattr(clock, "combat", False))
    # Emit event so clients can react (e.g., pause local timers/UI)
    try:
        socketio.emit("combat_state", {"combat": new_val}, namespace="/adventure")
    except Exception:
        pass
    return new_val
