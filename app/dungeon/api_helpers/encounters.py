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
from app.models.models import Character, GameClock
from app.services import spawn_service

__all__ = ["maybe_spawn_encounter", "run_monster_patrols"]


def _load_spawn_config():
    """Load encounter spawn pacing config.

    Reads from admin panel setting 'game_rules.encounter_spawn_rate' for base chance.
    Falls back to legacy 'encounter_spawn' JSON config if present.

    Structure:
      {
        "base": float   # base per-move spawn probability (default 0.05, admin-configurable)
        "streak_bonus_max": float  # cap for streak-based bonus added progressively
        "streak_unit": int  # multiplier for miss streak -> bonus scaling
      }
    Missing / invalid keys use defaults. Allows live tuning via admin panel.
    """
    import json as _json_cfg

    from app.models import GameConfig as _GC

    base_cfg = {"base": 0.05, "streak_bonus_max": 0.035, "streak_unit": 2}

    # First, try to load from admin panel game_rules.encounter_spawn_rate
    admin_rate = _GC.get("game_rules.encounter_spawn_rate")
    if admin_rate:
        try:
            base_cfg["base"] = float(_json_cfg.loads(admin_rate) if isinstance(admin_rate, str) else admin_rate)
        except Exception:
            pass

    # Legacy support: check for old encounter_spawn JSON config
    raw = _GC.get("encounter_spawn")
    if raw:
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


def maybe_spawn_encounter(instance, action_triggered: bool, resp: dict):
    """Attempt to spawn an encounter for any world-advancing player action.

    The previous implementation gated on actual movement; we now allow searches,
    treasure claims, cache openings, etc. to also roll encounters so long as they
    advance non-combat time (handled by caller). The action_triggered flag is kept
    for potential future conditional logic (e.g., actions explicitly opting out).
    """
    if not action_triggered:
        return
    try:
        clock = GameClock.get()
        last_tick_key = "_encounter_last_tick"
        miss_key = "_encounter_miss_streak"
        last_tick = session.get(last_tick_key)
        miss_streak = session.get(miss_key, 0)
        if last_tick is not None:
            # Add additional virtual misses based on ticks elapsed since last movement-involving action
            try:
                gap = max(0, int(clock.tick) - int(last_tick))
                if gap > 1:
                    miss_streak += gap - 1
            except Exception:
                pass
        cfg = _load_spawn_config()
        # Only apply streak bonuses if base rate is above 10%, otherwise respect the low spawn rate
        if cfg["base"] >= 0.10:
            base_chance = cfg["base"] + min(cfg["streak_bonus_max"], 0.01 * miss_streak * cfg.get("streak_unit", 2))
        else:
            # For low spawn rates, use base rate without bonuses to respect admin settings
            base_chance = cfg["base"]
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
            session[last_tick_key] = int(clock.tick)
            session[miss_key] = 0
            if _debug_flag():
                resp["encounter_chance"] = base_chance
                resp["encounter_roll"] = roll_val
        else:
            session[last_tick_key] = int(clock.tick)
            session[miss_key] = miss_streak + 1
            if _debug_flag():
                resp["encounter_chance"] = base_chance
                resp["encounter_roll"] = roll_val
    except Exception:
        pass


def run_monster_patrols(dungeon, instance, resp: dict, *, tick_amount: int = 1):
    """Update monster positions based on game clock using new spawn system.

    Args:
        dungeon: Dungeon layout object
        instance: DungeonInstance context
        resp: Response dict (reserved for future use)
        tick_amount: Number of ticks elapsed
    """
    try:
        from app.dungeon.spawn_integration import load_spawns_from_db
        from app.dungeon.spawn_manager import SpawnManager
        from app.models.entities import DungeonEntity as _DE
        from app.models.models import GameClock

        clock = GameClock.get()

        # Load spawn manager for this instance
        spawn_manager = SpawnManager(dungeon, instance)
        spawns = load_spawns_from_db(instance, spawn_manager)

        if not spawns:
            # No spawns loaded, skip patrol
            return

        # Update spawn positions based on game clock
        moved_spawns = spawn_manager.update_spawns(clock.tick)

        # Persist changes to database
        if moved_spawns:
            try:
                # Update entity positions for moved spawns
                for spawn in moved_spawns:
                    # Find entity by slug and original position
                    entity = _DE.query.filter_by(instance_id=instance.id, type="monster", slug=spawn.slug).first()

                    if entity:
                        entity.x = spawn.x
                        entity.y = spawn.y
                        # Update data with movement state
                        if entity.data:
                            import json as _json_patrol

                            try:
                                data = _json_patrol.loads(entity.data)
                                data["last_move_tick"] = spawn.last_move_tick
                                data["behavior"] = spawn.behavior.value
                                entity.data = _json_patrol.dumps(data)
                            except Exception:
                                pass

                db.session.commit()

                # Broadcast movement via websocket
                try:
                    from app import socketio

                    # Build full monster list for client update
                    monster_list = []
                    for spawn in spawn_manager.spawns:
                        monster_list.append({"slug": spawn.slug, "x": spawn.x, "y": spawn.y, "name": spawn.name})

                    socketio.emit(
                        "entities_update", {"monsters": monster_list, "instance_id": instance.id}, namespace="/game"
                    )
                except Exception:
                    pass

            except Exception:
                db.session.rollback()

    except Exception:
        # Swallow exceptions to avoid blocking player actions
        pass
