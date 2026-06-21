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
Also see apply_tick_decay for the persisted (DB-backed) counterpart that applies
poison decay and passive HP/MP regen outside of in-memory combat snapshots.
"""

from __future__ import annotations

import json
import math

from typing import Any, Dict, List, Tuple

DEFAULT_REGEN_RATES = {"hp_pct_per_tick": 0.5, "mp_pct_per_tick": 1.0}

# Type aliases
Effect = Dict[str, Any]
Participant = Dict[str, Any]

# Registry of per-turn start handlers: signature (participant, effect)-> log messages list


def _poison_start(target: Participant, effect: Effect) -> List[str]:
    dmg = int(effect.get("data", {}).get("damage", 5))
    # Floors at 0, unlike apply_tick_decay's out-of-combat floor of 1 --
    # poison can down a player mid-fight (same as any other damage source),
    # but should never be the cause of death while just exploring.
    prev = target.get("hp", 0)
    target["hp"] = max(0, prev - dmg)
    return [f"{target.get('name','?')} suffers {dmg} poison damage ({target.get('hp')})"]


def _regen_buff_start(target: Participant, effect: Effect) -> List[str]:
    """Heal a flat 2% of max HP/mana per turn, scaled by this effect's
    hp_mult/mp_mult -- e.g. hp_mult=3.0 heals 6% of max HP this turn.
    Capped at max, never overheals.
    """
    data = effect.get("data", {}) or {}
    try:
        hp_mult = float(data.get("hp_mult", 1.0))
    except Exception:
        hp_mult = 1.0
    try:
        mp_mult = float(data.get("mp_mult", 1.0))
    except Exception:
        mp_mult = 1.0
    max_hp = int(target.get("max_hp", 0))
    max_mana = int(target.get("mana_max", 0))
    hp_heal = math.ceil(max_hp * 0.02 * hp_mult)
    mp_heal = math.ceil(max_mana * 0.02 * mp_mult)
    target["hp"] = min(max_hp, int(target.get("hp", 0)) + hp_heal) if max_hp else target.get("hp", 0)
    target["mana"] = min(max_mana, int(target.get("mana", 0)) + mp_heal) if max_mana else target.get("mana", 0)
    return [f"{target.get('name', '?')} is well-rested, regenerating ({target.get('hp')} hp, {target.get('mana')} mp)"]


# stun has no start damage; handled in pre-action check


def _noop(target: Participant, effect: Effect) -> List[str]:
    return []


EFFECT_START = {
    "poison": _poison_start,
    "regen_buff": _regen_buff_start,
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


def replace_effect(effects: List[Effect], name: str, remaining: int, **data: Any) -> List[Effect]:
    """Return a new effects list with any existing entry named ``name``
    removed and a fresh one appended -- replace, not stack."""
    kept = [e for e in effects if e.get("name") != name]
    kept.append({"name": name, "remaining": int(remaining), "data": data})
    return kept


def _load_regen_rates() -> Dict[str, float]:
    from app.models import GameConfig

    try:
        raw = GameConfig.get("regen_rates")
        if not raw:
            return dict(DEFAULT_REGEN_RATES)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(DEFAULT_REGEN_RATES)
        merged = dict(DEFAULT_REGEN_RATES)
        for key in ("hp_pct_per_tick", "mp_pct_per_tick"):
            try:
                merged[key] = float(data.get(key, merged[key]))
            except Exception:
                continue
        return merged
    except Exception:
        return dict(DEFAULT_REGEN_RATES)


def apply_tick_decay(delta: int, character_ids) -> None:
    """Apply ``delta`` ticks worth of persisted effect decay and passive
    HP/MP regen to the characters in ``character_ids``.

    ``character_ids`` is required and must contain the specific
    character(s) the triggering action belongs to (e.g. the acting
    character for equip/consume, or the full party for movement/search) --
    callers must resolve this themselves. An earlier version scanned every
    Character in the database on every call, which meant one player moving
    silently applied regen/poison decay to every other user's characters
    too, including offline ones; that is not what "characters slowly heal
    while exploring" was meant to do, and the full-table scan does not
    scale with the player base.

    Safe to call frequently; no-ops cleanly (no DB writes) if a given
    character has nothing to update. Never raises -- failures roll back and
    are swallowed, matching the rest of time_service.py's error handling, so
    a decay/regen failure never blocks the action that triggered it.
    """
    if delta <= 0:
        return
    character_ids = list(character_ids)
    if not character_ids:
        return

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character
    from app.services.character_stats import compute_hp_mana_max

    try:
        rates = _load_regen_rates()
        all_chars = {c.id: c for c in Character.query.filter(Character.id.in_(character_ids)).all()}

        changed_any = False
        effects_touched = False
        for char in all_chars.values():
            try:
                stats = json.loads(char.stats) if char.stats else {}
                if not isinstance(stats, dict):
                    stats = {}
            except Exception:
                stats = {}

            hp_max, mana_max = compute_hp_mana_max(char)
            hp = int(stats.get("hp", hp_max))
            mana_key = "current_mana" if "current_mana" in stats else "mana"
            mana = int(stats.get(mana_key, mana_max))

            stats_changed = False

            effects = CharacterStatusEffect.query.filter_by(character_id=char.id).all()
            if effects:
                effects_touched = True
            hp_mult = 1.0
            mp_mult = 1.0
            for effect in effects:
                if effect.name == "poison":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                    except Exception:
                        payload = {}
                    damage = int(payload.get("damage", 0)) * delta
                    if damage > 0:
                        hp = max(1, hp - damage)
                        stats_changed = True
                elif effect.name == "regen_buff":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                        if not isinstance(payload, dict):
                            payload = {}
                    except Exception:
                        payload = {}
                    try:
                        hp_mult = float(payload.get("hp_mult", 1.0))
                    except Exception:
                        hp_mult = 1.0
                    try:
                        mp_mult = float(payload.get("mp_mult", 1.0))
                    except Exception:
                        mp_mult = 1.0
                effect.remaining -= delta
                if effect.remaining <= 0:
                    db.session.delete(effect)
                else:
                    db.session.add(effect)

            if hp < hp_max:
                hp = min(hp_max, hp + math.ceil(hp_max * rates["hp_pct_per_tick"] * hp_mult / 100 * delta))
                stats_changed = True
            if mana < mana_max:
                mana = min(mana_max, mana + math.ceil(mana_max * rates["mp_pct_per_tick"] * mp_mult / 100 * delta))
                stats_changed = True

            if stats_changed:
                stats["hp"] = hp
                stats[mana_key] = mana
                char.stats = json.dumps(stats)
                db.session.add(char)
                changed_any = True

        if changed_any or effects_touched:
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


__all__ = [
    "apply_start_of_turn",
    "can_act",
    "add_effect",
    "replace_effect",
    "apply_tick_decay",
]
