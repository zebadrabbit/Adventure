"""Monster AI action selection (initial scaffold).

The goal is to keep legacy deterministic behavior unless specific feature flags are enabled.
This module exposes a single function select_action(monster, party, session_ctx) returning a dict:
{
  'type': 'attack' | 'spell' | 'flee' | 'help',
  'spell': 'firebolt',        # when type == 'spell'
  'target_index': 0,          # index into party['members']
}

Initial implementation always returns {'type': 'attack', 'target_index': 0}.
Future logic will incorporate:
- Spell casting if monster.get('spells') and config flag enable_monster_spells.
- Flee attempt if low HP and flag enable_monster_flee.
- Help call if conditions met and flag enable_monster_help.
- Ambush handled outside (encounter start) not here.
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict

from app.models import GameConfig

Action = Dict[str, Any]


def _cfg() -> Dict[str, Any]:
    try:
        raw = GameConfig.get("monster_ai")
        if raw:
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def select_action(monster: Dict[str, Any], party: Dict[str, Any], session_ctx: Dict[str, Any]) -> Action:
    members = party.get("members", [])
    if not members:
        return {"type": "idle"}
    cfg = _cfg()
    flee_threshold = float(cfg.get("flee_threshold", 0.2))
    flee_chance = float(cfg.get("flee_chance", 0.3))
    help_threshold = float(cfg.get("help_threshold", 0.5))
    help_chance = float(cfg.get("help_chance", 0.2))
    spell_chance = float(cfg.get("spell_chance", 0.4))
    # Low HP flee logic
    if monster.get("enable_monster_flee"):
        hp = monster.get("hp_current", monster.get("hp")) or session_ctx.get("monster_hp")
        max_hp = monster.get("hp", hp) or 1
        if hp is not None and max_hp and max_hp > 0 and hp / max_hp < flee_threshold:
            if random.random() < flee_chance:
                return {"type": "flee"}
    # Help call (does not change combat state yet, just logs) when below 50%
    if monster.get("enable_monster_help"):
        hp = monster.get("hp_current", monster.get("hp")) or session_ctx.get("monster_hp")
        max_hp = monster.get("hp", hp) or 1
        if hp is not None and max_hp and max_hp > 0 and hp / max_hp < help_threshold and random.random() < help_chance:
            return {"type": "help"}
    # If monster has spells and flag enable_monster_spells, 40% chance to cast firebolt equivalent
    spells = monster.get("spells") or []
    if monster.get("enable_monster_spells") and "firebolt" in spells:
        if random.random() < spell_chance:
            # target weakest (lowest hp) member
            target_index = min(range(len(members)), key=lambda i: members[i].get("hp", 9999))
            return {"type": "spell", "spell": "firebolt", "target_index": target_index}
    # Default basic attack first living member
    for idx, m in enumerate(members):
        if m.get("hp", 0) > 0:
            return {"type": "attack", "target_index": idx}
    return {"type": "idle"}


__all__ = ["select_action"]
