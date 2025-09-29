"""Minimal status effects framework.

Effects structure (attached to combat participants in-memory snapshots):

Each participant (player or monster dict) may have a list under key 'effects' each entry:
{
  'name': 'poison',            # identifier
  'remaining': 3,              # turns remaining (decrement each time owner starts turn)
  'data': {...},               # optional custom payload
}

Supported baseline effects:
- poison: deals flat or scaled damage at start of owner's turn.
- stun: prevents action this turn (consumes turn, then decrements).

Extension points: add new effect handlers to EFFECT_START and EFFECT_PRE_ACTION maps.
All calculations are intentionally simple and deterministic aside from random already in combat.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Type aliases
Effect = Dict[str, Any]
Participant = Dict[str, Any]

# Registry of per-turn start handlers: signature (participant, effect)-> log messages list


def _poison_start(target: Participant, effect: Effect) -> List[str]:
    dmg = int(effect.get("data", {}).get("damage", 5))
    # Apply damage but not below zero
    prev = target.get("hp", 0)
    target["hp"] = max(0, prev - dmg)
    return [f"{target.get('name','?')} suffers {dmg} poison damage ({target.get('hp')})"]


# stun has no start damage; handled in pre-action check


def _noop(target: Participant, effect: Effect) -> List[str]:
    return []


EFFECT_START = {
    "poison": _poison_start,
}

# Registry for pre-action veto: return (can_act: bool, optional log message)


def _stun_pre(target: Participant, effect: Effect) -> Tuple[bool, List[str]]:
    # Stun prevents action for the turn it triggers.
    return False, [f"{target.get('name','?')} is stunned and cannot act!"]


EFFECT_PRE_ACTION = {
    "stun": _stun_pre,
}


def _decrement_and_prune(effects: List[Effect]) -> List[Effect]:
    remaining = []
    for eff in effects:
        eff["remaining"] = int(eff.get("remaining", 0)) - 1
        if eff["remaining"] > 0:
            remaining.append(eff)
    return remaining


def apply_start_of_turn(participant: Participant) -> List[str]:
    """Apply start-of-turn effects (damage over time, regen, etc.).

    Returns list of log message strings produced by effects.
    """
    logs: List[str] = []
    effects: List[Effect] = participant.get("effects", []) or []
    for eff in list(effects):  # iterate snapshot
        handler = EFFECT_START.get(eff.get("name"))
        if handler:
            logs.extend(handler(participant, eff))
    # Decrement durations after processing start effects
    participant["effects"] = _decrement_and_prune(effects)
    return logs


def can_act(participant: Participant) -> Tuple[bool, List[str]]:
    """Check pre-action veto effects (e.g., stun). Returns (can_act, logs)."""
    logs: List[str] = []
    for eff in participant.get("effects", []) or []:
        handler = EFFECT_PRE_ACTION.get(eff.get("name"))
        if handler:
            ok, eff_logs = handler(participant, eff)
            if eff_logs:
                logs.extend(eff_logs)
            if not ok:
                return False, logs
    return True, logs


def add_effect(participant: Participant, name: str, turns: int, **data: Any):
    effs: List[Effect] = participant.setdefault("effects", [])
    effs.append({"name": name, "remaining": int(turns), "data": data})


__all__ = [
    "apply_start_of_turn",
    "can_act",
    "add_effect",
]
