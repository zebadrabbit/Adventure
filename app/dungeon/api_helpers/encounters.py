"""Encounter spawning and patrol helpers.

Encapsulates logic previously inline in dungeon_api.dungeon_move:
  * Encounter spawn chance calculation with streak-based pacing
  * Monster selection & combat session start
  * Optional debug fields based on GameConfig flag
  * Passive monster patrol persistence and broadcast

Public functions:
- maybe_spawn_encounter(instance, moved: bool, resp: dict) -> None (mutates resp)
- run_monster_patrols(dungeon, instance, resp: dict) -> None (adds websocket side effects)

Design choices:
- Functions swallow exceptions to avoid blocking player movement
- Debug keys included only if debug_encounters flag truthy
"""

from __future__ import annotations

import random as _r

from flask import session
from flask_login import current_user

from app import db
from app.models.models import Character
from app.services import spawn_service

__all__ = ["maybe_spawn_encounter", "run_monster_patrols"]


def _load_spawn_config():
    import json as _json_cfg

    from app.models import GameConfig as _GC

    base_cfg = {"base": 0.18, "streak_bonus_max": 0.04, "streak_unit": 2}
    raw = _GC.get("encounter_spawn")
    if not raw:
        return base_cfg
    try:
        parsed = _json_cfg.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict):
            for k in ["base", "streak_bonus_max", "streak_unit"]:
                if k in parsed:
                    base_cfg[k] = parsed[k]
    except Exception:
        pass
    return base_cfg


def _debug_flag() -> bool:
    import json as _json_dbg

    from app.models import GameConfig as _GC_DEBUG

    try:
        raw = _GC_DEBUG.get("debug_encounters")
        if not raw:
            return False
        if isinstance(raw, str):
            try:
                val = _json_dbg.loads(raw)
            except Exception:
                val = None
            return bool(val)
        return bool(raw)
    except Exception:
        return False


def maybe_spawn_encounter(instance, moved: bool, resp: dict):
    if not moved:
        return
    try:
        pace_key = "_encounter_cooldown"
        miss_streak = session.get(pace_key, 0)
        cfg = _load_spawn_config()
        base_chance = cfg["base"] + min(cfg["streak_bonus_max"], 0.01 * miss_streak * cfg.get("streak_unit", 2))
        roll_val = _r.random()
        force_spawn = base_chance >= 0.9999
        if roll_val < base_chance or force_spawn:
            try:
                party_chars = (
                    Character.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
                )
            except Exception:
                party_chars = []
            party_size = max(1, len(party_chars) or 1)
            avg_level = 1
            if party_chars:
                avg_level = max(1, sum(c.level for c in party_chars) // len(party_chars))
            monster = spawn_service.choose_monster(level=avg_level, party_size=party_size)
            try:
                from app.services import combat_service as _combat

                session_row = _combat.start_session(current_user.id, monster)
                resp["encounter"] = {"monster": monster, "combat_id": session_row.id}
            except Exception:
                resp["encounter"] = {"monster": monster, "error": "combat_init_failed"}
            session[pace_key] = 0
            if _debug_flag():
                resp["encounter_chance"] = base_chance
                resp["encounter_roll"] = roll_val
        else:
            session[pace_key] = miss_streak + 1
            if _debug_flag():
                resp["encounter_chance"] = base_chance
                resp["encounter_roll"] = roll_val
    except Exception:
        pass


def run_monster_patrols(dungeon, instance, resp: dict):  # resp unused currently but reserved
    try:
        from app.models.entities import DungeonEntity as _DE
        from app.services.monster_patrol import maybe_patrol as _maybe_patrol

        if not (hasattr(dungeon, "spawn_manager") and getattr(dungeon.spawn_manager, "monsters", None)):
            return
        changed_positions = []
        for m in dungeon.spawn_manager.monsters:  # type: ignore[attr-defined]
            if not isinstance(m, dict) or "x" not in m or "y" not in m:
                continue
            if m.get("in_combat"):
                continue
            old_x, old_y = m.get("x"), m.get("y")
            if _maybe_patrol(m, dungeon):
                if m.get("slug") and (m.get("x") != old_x or m.get("y") != old_y):
                    changed_positions.append((m.get("slug"), int(m.get("x")), int(m.get("y"))))
        if changed_positions:
            try:
                for slug, mx, my in changed_positions:
                    q = _DE.query.filter_by(instance_id=instance.id, slug=slug, type="monster")
                    row = q.first()
                    if row:
                        row.x, row.y = mx, my
                db.session.commit()
            except Exception:
                db.session.rollback()
            try:
                persist = getattr(dungeon.spawn_manager, "persist", None)
                if callable(persist):
                    persist()
            except Exception:
                pass
            try:
                from app import socketio

                payload = [{"slug": slug, "x": mx, "y": my} for slug, mx, my in changed_positions]
                socketio.emit("entities_update", {"monsters": payload, "instance_id": instance.id}, namespace="/game")
            except Exception:
                pass
    except Exception:
        pass
