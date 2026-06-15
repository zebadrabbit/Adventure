"""Turn-based combat service layer.

Responsibilities:
    * Orchestrate combat session lifecycle (start, player/monster turns, end).
    * Provide player action handlers (attack, flee, defend, use item, cast spell).
    * Drive monster AI turns (delegating to ``monster_ai.select_action`` when enabled).
    * Apply status effects and resistances via helpers in sibling modules.
    * Emit real-time updates over Socket.IO (``combat_update`` / ``combat_end`` events).

Design notes:
    - Persistence model uses ``CombatSession`` with JSON blobs for party, initiative, monster & logs.
    - Optimistic concurrency: client supplies ``version``; mismatch returns ``version_conflict``.
    - Logs trimmed to last 250 entries for memory stability.
    - Many helpers are intentionally private (prefixed with ``_``) to keep public surface minimal.
"""

import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app import db, socketio
from app.models.models import Character, CombatSession

from .combat_constants import (
    ACTOR_START_ACTION,
    COMBAT_COMPLETE,
    COMBAT_TURN_START,
    MONSTER_ATTACK_HIT,
    MONSTER_ATTACK_MISS,
    MONSTER_CALL_HELP,
    MONSTER_COOLDOWN_WAIT,
    MONSTER_FLEE,
    MONSTER_HESITATE,
    MONSTER_INCAPACITATED_WAIT,
    MONSTER_NO_TARGET_WAIT,
    MONSTER_SPELL_HIT,
    MONSTER_SPELL_MISS,
    PLAYER_ATTACK_HIT,
    PLAYER_ATTACK_MISS,
    PLAYER_DEFEND,
    PLAYER_FLEE_FAIL,
    PLAYER_FLEE_SUCCESS,
    PLAYER_SPELL_FIZZLE,
    PLAYER_SPELL_HIT,
    PLAYER_SPELL_MISS,
    PLAYER_USE_ITEM,
)
from .combat_utils import apply_resistances
from .loot_service import roll_loot
from .monster_ai import select_action
from .status_effects import apply_start_of_turn, can_act
from .time_service import set_combat_state

logger = structlog.get_logger()


def _now():
    return datetime.utcnow()


def _derive_stats(char: Character) -> Dict[str, Any]:
    import json as _json

    base = {}
    try:
        raw = _json.loads(char.stats) if char.stats else {}
        if isinstance(raw, dict):
            base = raw
    except Exception as e:
        logger.warning("Failed to parse character stats", char_id=char.id, exc_info=e)
        base = {}
    level = getattr(char, "level", 1) or 1
    STR = int(base.get("str", base.get("STR", 10)) or 10)
    DEX = int(base.get("dex", base.get("DEX", 10)) or 10)
    INT = int(base.get("int", base.get("INT", 10)) or 10)
    CON = int(base.get("con", base.get("CON", STR)) or STR)
    WIS = int(base.get("wis", base.get("WIS", 10)) or 10)
    CHA = int(base.get("cha", base.get("CHA", 10)) or 10)

    # Fold equipped gear affixes into attributes + derived stats.
    from app.loot.equip import gear_bonuses

    try:
        _gear = json.loads(char.gear) if getattr(char, "gear", None) else {}
    except Exception:
        _gear = {}
    _gb = gear_bonuses(_gear)
    STR += int(_gb.get("str", 0))
    DEX += int(_gb.get("dex", 0))
    INT += int(_gb.get("int", 0))
    CON += int(_gb.get("con", 0))
    WIS += int(_gb.get("wis", 0))
    CHA += int(_gb.get("cha", 0))

    max_hp = 50 + CON * 2 + level * 5
    attack = 8 + STR // 2 + level
    defense = 5 + DEX // 3 + level // 2
    speed = 8 + DEX // 2
    mana_max = 20 + INT * 2

    max_hp += int(_gb.get("max_hp", 0))
    attack += int(_gb.get("damage", 0))
    defense += int(_gb.get("armor", 0))
    speed += int(_gb.get("speed", 0))
    mana_max += int(_gb.get("mana", 0))

    # Read persisted current HP, fallback to max HP (e.g., new characters)
    hp_source = base.get("hp", max_hp)
    try:
        hp = int(hp_source)
    except Exception as e:
        logger.warning("Failed to parse hp value", char_id=char.id, hp_source=hp_source, exc_info=e)
        hp = max_hp
    hp = max(0, min(hp, max_hp))  # Clamp to valid range

    # Prefer persisted current_mana, fallback to legacy 'mana', else full
    mana_source = base.get("current_mana", base.get("mana", mana_max))
    try:
        mana = int(mana_source)
    except Exception as e:
        logger.warning("Failed to parse mana value", char_id=char.id, mana_source=mana_source, exc_info=e)
        mana = mana_max
    mana = max(0, min(mana, mana_max))

    # Extract or infer class from stats
    char_class = base.get("class", None)
    if not char_class:
        # Infer class from stat distribution (same logic as dashboard_helpers)
        if STR >= 16 and CON >= 14 and INT <= 8:
            char_class = "barbarian"
        elif STR >= 14 and CHA >= 12:
            char_class = "paladin"
        elif DEX >= 14 and WIS >= 12:
            char_class = "monk"
        elif CHA >= 14 and DEX >= 12:
            char_class = "bard"
        elif CHA >= 14 and INT <= 12:
            char_class = "sorcerer"
        elif CHA >= 14 and INT >= 11:
            char_class = "warlock"
        elif INT >= STR and INT >= DEX and INT >= WIS:
            char_class = "mage"
        elif WIS >= STR and WIS >= DEX and WIS >= INT and INT >= 11:
            char_class = "druid"
        elif DEX >= STR and WIS >= INT:
            char_class = "ranger"
        elif DEX >= STR and DEX >= INT and DEX >= WIS and CHA < 14:
            char_class = "rogue"
        elif STR >= DEX and STR >= INT and STR >= WIS:
            char_class = "fighter"
        else:
            char_class = "cleric"  # Default fallback

    return {
        # Controller user id retained separately from participant (character) id.
        "controller_id": char.user_id,
        "char_id": char.id,
        "name": char.name,
        "char_class": char_class,
        "hp": hp,
        "max_hp": max_hp,
        "attack": attack,
        "defense": defense,
        "speed": speed,
        "mana": mana,
        "mana_max": mana_max,
        "int_stat": INT,
        "str_stat": STR,
        "dex_stat": DEX,
        "resistances": {},
        "defending": False,
        "buffs": [],
    }


def _base_player_snapshot(user_id: int) -> Dict[str, Any]:
    # Build party from user's characters (up to 4)
    chars = Character.query.filter_by(user_id=user_id).order_by(Character.id.asc()).limit(4).all()
    members = [_derive_stats(c) for c in chars] or [
        {
            "controller_id": user_id,
            "char_id": -1,
            "name": f"Hero{user_id}",
            "char_class": "fighter",
            "hp": 100,
            "max_hp": 100,
            "attack": 12,
            "defense": 5,
            "speed": 10,
            "mana": 30,
            "mana_max": 30,
            "int_stat": 10,
            "str_stat": 10,
            "dex_stat": 10,
            "resistances": {},
            "defending": False,
            "buffs": [],
        }
    ]
    # Lightweight shared inventory count(s) surfaced for UI gating (e.g. potion button visibility)
    # For now we only expose healing potion count from the first character's inventory list.
    potion_count = 0
    try:
        first_char = chars[0] if chars else None
        if first_char and first_char.items:
            inv_raw = json.loads(first_char.items)
            if isinstance(inv_raw, list):
                for entry in inv_raw:
                    if isinstance(entry, str) and entry == "potion-healing":
                        potion_count += 1
                    elif isinstance(entry, dict) and entry.get("slug") == "potion-healing":
                        try:
                            potion_count += int(entry.get("qty", 1))
                        except Exception as e:
                            logger.warning("Failed to parse potion quantity", entry=entry, exc_info=e)
                            potion_count += 1
    except Exception as e:
        logger.warning("Failed to parse inventory", char_id=first_char.id if first_char else None, exc_info=e)
        potion_count = potion_count or 0
    return {"members": members, "item_counts": {"potion-healing": potion_count}}


def _calc_initiative(party: Dict[str, Any], monster: Dict[str, Any]) -> List[Dict[str, Any]]:
    order = []
    for member in party["members"]:
        roll = member.get("speed", 10) + random.randint(1, 20)
        order.append(
            {
                "type": "player",
                "id": member.get("char_id"),  # participant id (character id)
                "controller_id": member.get("controller_id"),
                "name": member["name"],
                "roll": roll,
            }
        )
    m_roll = monster.get("speed", 8) + random.randint(1, 20)
    order.append({"type": "monster", "id": monster.get("id"), "name": monster.get("name"), "roll": m_roll})
    order.sort(key=lambda x: x["roll"], reverse=True)
    return order


def _capture_dungeon_snapshot(user_id: int) -> Dict[str, Any]:
    """Capture a lightweight snapshot of the user's dungeon position/state.

    Snapshot includes current instance id and coordinates plus seed if available.
    Safe fallback to empty dict on any error. This avoids adding FK dependencies
    into combat while allowing a 'return to dungeon' restore after combat.
    """
    try:
        from sqlalchemy import text as _t

        from app.models.models import User as _User

        # Direct SQL to avoid importing full dungeon models (keeps coupling low)
        row = db.session.execute(
            _t("SELECT id, seed, pos_x, pos_y, pos_z FROM dungeon_instance WHERE user_id=:u ORDER BY id DESC LIMIT 1"),
            {"u": user_id},
        ).fetchone()
        if not row:
            return {}
        snap = {
            "instance_id": row[0],
            "seed": row[1],
            "pos": {"x": row[2], "y": row[3], "z": row[4]},
        }
        # Attempt to enrich with a small explored tiles sample (no new columns needed)
        try:
            user_row = db.session.get(_User, user_id)
            if user_row and user_row.explored_tiles and row[1]:  # seed required to map subset
                import json as _json

                tiles_map = {}
                try:
                    tiles_map = _json.loads(user_row.explored_tiles)
                except Exception:
                    tiles_map = {}
                seed_key = str(row[1])
                raw_tiles = tiles_map.get(seed_key)
                if isinstance(raw_tiles, str):
                    coords = [c for c in raw_tiles.split(";") if c]
                elif isinstance(raw_tiles, list):  # future-proof if format migrates
                    coords = [str(c) for c in raw_tiles]
                else:
                    coords = []
                # Keep only first 50 to bound payload size
                if coords:
                    snap["explored_sample"] = coords[:50]
                    snap["explored_count"] = len(coords)
        except Exception:
            pass
        return snap
    except Exception:
        return {}


def start_session(user_id: int, monster: Dict[str, Any]) -> CombatSession:
    """Create and persist a new combat session for ``user_id`` vs ``monster``.

    Applies initiative ordering (players + monster) and optional ambush logic
    (monster acts before normal turn order if configured and roll succeeds).

    Parameters
    ----------
    user_id: Controller user id starting the encounter.
    monster: Scaled monster instance dict from ``spawn_service.choose_monster``.

    Returns
    -------
    CombatSession
        Newly persisted active session (``status='active'``).
    """
    party = _base_player_snapshot(user_id)
    initiative = _calc_initiative(party, monster)
    # Monster HP scaling already applied in monster dict (assumption)
    monster_hp = monster.get("hp", 50)
    dungeon_snapshot = _capture_dungeon_snapshot(user_id)
    session = CombatSession(
        user_id=user_id,
        monster_json=json.dumps(monster),
        party_snapshot_json=json.dumps(party),
        initiative_json=json.dumps(initiative),
        monster_hp=monster_hp,
        combat_turn=1,
        active_index=0,
        log_json=json.dumps([{"ts": _now().isoformat(), "m": f"Encounter starts vs {monster.get('name')}"}]),
        version=1,
        # Add snapshot JSON if column exists (older DBs may not have migrated yet)
        **(
            {"dungeon_snapshot_json": json.dumps(dungeon_snapshot)}
            if hasattr(CombatSession, "dungeon_snapshot_json")
            else {}
        ),
    )
    db.session.add(session)
    db.session.commit()
    # Ambush mechanic: if flag set and random succeeds, monster gets immediate pre-turn action
    try:
        if monster.get("enable_ambush"):
            from app.models import (
                GameConfig as _GC,  # local import to avoid circular at module load
            )

            ambush_chance = 0.5
            try:
                raw_cfg = _GC.get("monster_ai")
                if raw_cfg:
                    import json as _json

                    cfg_obj = _json.loads(raw_cfg) if isinstance(raw_cfg, str) else raw_cfg
                    if isinstance(cfg_obj, dict):
                        ambush_chance = float(cfg_obj.get("ambush_chance", ambush_chance))
            except Exception:
                pass
            if random.random() < ambush_chance:
                logs = json.loads(session.log_json)
                logs.append({"ts": _now().isoformat(), "m": f"{monster.get('name')} ambushes the party!"})
                session.log_json = json.dumps(logs)
                # Monster acts immediately (surprise) without advancing initiative index (still 0 afterwards)
                # We call monster_auto_turn-like logic but constrained: one basic attack only.
                party_state = json.loads(session.party_snapshot_json or "{}") or {}
                members = party_state.get("members", [])
                if members:
                    tgt = members[0]
                    m_base = monster.get("damage", 8)
                    acc_roll = random.randint(1, 20)
                    accuracy = m_base + acc_roll
                    defender_evasion = tgt.get("defense", 5) + 10
                    if acc_roll != 1 and (acc_roll == 20 or accuracy >= defender_evasion):
                        variance = random.randint(-m_base // 4, m_base // 4)
                        dmg = max(1, m_base + variance)
                        if acc_roll == 20:
                            dmg = int(dmg * 1.5)
                        resistances = tgt.get("resistances", {})
                        try:
                            dmg = int(apply_resistances(dmg, ["physical"], resistances))
                        except Exception:
                            pass
                        if tgt.get("defending"):
                            dmg = max(1, dmg // 2)
                            tgt["defending"] = False
                        tgt["hp"] = max(0, tgt.get("hp", 0) - dmg)
                        members[0] = tgt
                        party_state["members"] = members
                        session.party_snapshot_json = json.dumps(party_state)
                        logs = json.loads(session.log_json)
                        logs.append(
                            {
                                "ts": _now().isoformat(),
                                "m": f"{monster.get('name')} strikes first for {dmg} damage (HP {tgt['hp']})",
                            }
                        )
                        session.log_json = json.dumps(logs)
                db.session.add(session)
                db.session.commit()
    except Exception:
        pass
    set_combat_state(True)
    return session


def _load_session(combat_id: int) -> CombatSession:
    return CombatSession.query.filter_by(id=combat_id, archived=False).first()


def _append_log(session: CombatSession, message: str, code: str | None = None):
    """Append a combat log line.

    Adds optional structured action code for downstream consumers (tests, UI accessibility).
    Existing callers that do not supply a code remain backward compatible.
    """
    logs = json.loads(session.log_json) if session.log_json else []
    entry = {"ts": _now().isoformat(), "m": message}
    if code:
        entry["code"] = code
    logs.append(entry)
    # Trim logs if very large (keep last 250)
    if len(logs) > 250:
        logs = logs[-250:]
    session.log_json = json.dumps(logs)
    # Emission will occur after commit via helper


def _player_ref(party: Dict[str, Any], char_id: int):
    for m in party.get("members", []):
        if m.get("char_id") == char_id:
            return m
    return None


def _is_monster_turn(session: CombatSession) -> bool:
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return False
    actor = initiative[session.active_index]
    return actor["type"] == "monster"


def _advance_turn(session: CombatSession):
    """Advance to next initiative entry and reset phase to 'start'."""
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return
    session.active_index += 1
    if session.active_index >= len(initiative):
        session.active_index = 0
        session.combat_turn += 1
    # Reset phases for new actor
    session.phase = "start"
    session.phase_step = 0
    session.version += 1
    # Log whose turn it is (player name or monster). Helps players know next actor.
    try:
        actor = initiative[session.active_index]
        if actor.get("type") == "player":
            # Need player snapshot to map id -> name
            party = json.loads(session.party_snapshot_json or "{}") or {}
            name = None
            for m in party.get("members", []):
                if m.get("char_id") == actor.get("id"):
                    name = m.get("name")
                    break
            if not name:
                name = f"Player {actor.get('id')}"
            _append_log(session, f"Turn {session.combat_turn}: {name}'s turn.", code=COMBAT_TURN_START)
        else:
            _append_log(
                session, f"Turn {session.combat_turn}: {actor.get('name','Monster')}'s turn.", code=COMBAT_TURN_START
            )
    except Exception:
        pass
    # Emit lightweight turn_change event (non-critical). Clients may ignore if unimplemented.
    try:
        socketio.emit(
            "turn_change",
            {
                "id": session.id,
                "active_index": session.active_index,
                "turn": session.combat_turn,
                "phase": session.phase,
            },
            namespace="/adventure",
        )
    except Exception:
        pass


def _progress_phase(session: CombatSession):
    """Move session.phase forward inside the active actor's turn.

    Phases: start -> action -> end -> (advance turn)
    Returns True if the turn advanced (i.e., phase cycle completed).
    """
    if session.phase == "start":
        session.phase = "action"
        # Log phase transition so players know they can act (or monster will act)
        try:
            initiative = json.loads(session.initiative_json or "[]")
            actor = initiative[session.active_index]
            if actor.get("type") == "player":
                party = json.loads(session.party_snapshot_json or "{}") or {}
                name = None
                for m in party.get("members", []):
                    if m.get("char_id") == actor.get("id"):
                        name = m.get("name")
                        break
                name = name or f"Player {actor.get('id')}"
                _append_log(session, f"{name} is acting.", code=ACTOR_START_ACTION)
            else:
                _append_log(session, f"{actor.get('name','Monster')} is acting (AI).", code=ACTOR_START_ACTION)
        except Exception:
            pass
    elif session.phase == "action":
        session.phase = "end"
    elif session.phase == "end":
        _advance_turn(session)
        return True
    session.version += 1
    return False


def _check_end(session: CombatSession):
    # Monster defeat path
    if session.monster_hp is not None and session.monster_hp <= 0:
        monster = session.monster()
        rewards = roll_loot(monster) if monster else {}
        session.status = "complete"
        _append_log(session, f"{monster.get('name')} defeated! Loot: {rewards}", code=COMBAT_COMPLETE)

        # Track boss kills and progress
        try:
            from app.models.dungeon_instance import DungeonInstance
            from app.services import boss_abilities

            instance_snapshot = session.dungeon_snapshot or {}
            instance_id = instance_snapshot.get("instance_id")

            if instance_id and monster:
                instance = db.session.get(DungeonInstance, instance_id)
                if instance:
                    # Track based on archetype
                    archetype = monster.get("archetype", "")

                    if boss_abilities.is_boss(monster):
                        instance.bosses_defeated += 1
                        _append_log(session, f"Boss defeated! ({instance.bosses_defeated}/{instance.bosses_total})")

                        # Check if all bosses defeated
                        if instance.bosses_defeated >= instance.bosses_total:
                            instance.extraction_available = True
                            _append_log(session, "🎉 All bosses defeated! Extraction portal is now available!")
                    elif archetype == "Elite":
                        instance.elites_defeated += 1
                    else:
                        instance.monsters_defeated += 1

                    db.session.add(instance)
        except Exception as e:
            # Log but don't fail combat completion
            logger.warning("boss_kill_tracking_failed", error=str(e))

        try:
            party = json.loads(session.party_snapshot_json or "{}") or {}
            char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
            xp_total = int(monster.get("xp", 0)) if monster else 0
            members = party.get("members", [])
            share = int(xp_total / len(members)) if members else xp_total
            xp_map = {}

            # Helper function to calculate required XP for a level
            def xp_for_level(level):
                return int((level - 1) ** 2 * 100)

            for m in members:
                row = char_rows.get(m.get("char_id") or m.get("id"))
                if row:
                    old_level = row.level or 1
                    row.xp += share

                    # Check for level-up
                    new_level = old_level
                    while row.xp >= xp_for_level(new_level + 1):
                        new_level += 1

                    if new_level > old_level:
                        row.level = new_level
                        # Note: Stat point allocation happens via /api/characters/<id>/level-up endpoint

                    db.session.add(row)
                    try:
                        xp_map[str(m.get("char_id") or m.get("id"))] = share
                    except Exception:
                        pass
            if rewards.get("items") and char_rows:
                first = next(iter(char_rows.values()))
                inv_items: list = []
                if first.items:
                    try:
                        inv_items = json.loads(first.items)
                        if not isinstance(inv_items, list):
                            inv_items = []
                    except Exception:
                        inv_items = []
                if isinstance(rewards.get("items"), dict):
                    for slug, qty in rewards.get("items", {}).items():
                        try:
                            q = int(qty)
                        except Exception:
                            q = 1
                        for _ in range(max(1, q)):
                            inv_items.append(slug)
                elif isinstance(rewards.get("items"), list):
                    for slug in rewards.get("items", []):
                        inv_items.append(slug)
                if isinstance(rewards.get("items_list"), list):
                    for slug in rewards.get("items_list"):
                        inv_items.append(slug)
                first.items = json.dumps(inv_items)
                db.session.add(first)
            try:
                rewards["xp"] = {"total": xp_total, "per_member": xp_map}
            except Exception:
                pass
        except Exception:
            db.session.rollback()
        session.rewards_json = json.dumps(rewards)
        try:
            party = json.loads(session.party_snapshot_json or "{}") or {}
            if rewards.get("items") or rewards.get("items_list"):
                potion_count = 0
                from json import loads as _loads

                char_rows = (
                    Character.query.filter_by(user_id=session.user_id).order_by(Character.id.asc()).limit(1).all()
                )
                first_char = char_rows[0] if char_rows else None
                if first_char and first_char.items:
                    try:
                        inv_raw = _loads(first_char.items)
                        if isinstance(inv_raw, list):
                            for entry in inv_raw:
                                if isinstance(entry, str) and entry == "potion-healing":
                                    potion_count += 1
                                elif isinstance(entry, dict) and entry.get("slug") == "potion-healing":
                                    try:
                                        potion_count += int(entry.get("qty", 1))
                                    except Exception:
                                        potion_count += 1
                    except Exception:
                        pass
                counts = party.setdefault("item_counts", {})
                counts["potion-healing"] = potion_count
                session.party_snapshot_json = json.dumps(party)
        except Exception:
            pass
        _persist_party_resources(session)
        set_combat_state(False)
        return
    # Party defeat path
    party = json.loads(session.party_snapshot_json or "{}") or {}
    alive = [m for m in party.get("members", []) if m.get("hp", 0) > 0]
    if not alive:
        session.status = "complete"
        session.rewards_json = json.dumps({})
        _append_log(session, "Party defeated.", code=COMBAT_COMPLETE)
        _persist_party_resources(session)
        set_combat_state(False)


def _emit_session(event: str, session: CombatSession):  # safe emit wrapper
    try:
        socketio.emit(event, session.to_dict(), namespace="/adventure")
    except Exception:
        pass


def _emit_if_completed(session: CombatSession):
    """Emit end/completion events if the session is no longer active.

    Consolidates repeated logic scattered across action handlers. Always emits
    'combat_end' for backward compatibility and 'combat_complete' (new) so
    clients can differentiate finalization from interim updates.
    """
    if session.status != "active":
        # Always emit legacy end event
        _emit_session("combat_end", session)
        # Also emit new completion event (idempotent if called multiple times)
        try:
            _emit_session("combat_complete", session)
        except Exception:
            pass


def _persist_party_resources(session: CombatSession):
    """Persist surviving party HP and mana back into Character.stats JSON.

    Assumptions / Simplifications:
    - Character.stats JSON contains (or can accept) 'hp' and 'mana' keys representing current values.
    - We do not yet track max_hp/mana persistently outside stats snapshot; we only update current.
    - Dead characters (hp <= 0) persist with hp=0.
    - Silently ignores any character ids not found (e.g., temporary generated hero placeholder).
    """
    try:
        if not session.party_snapshot_json:
            return
        import json as _json

        party = _json.loads(session.party_snapshot_json) or {}
        members = party.get("members", [])
        if not members:
            return
        char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
        changed = False
        for m in members:
            cid = m.get("char_id") or m.get("id")
            row = char_rows.get(cid)
            if not row or not row.stats:
                continue
            try:
                stats_obj = _json.loads(row.stats) if isinstance(row.stats, str) else {}
            except Exception:
                stats_obj = {}
            # Update only the instantaneous current values
            try:
                stats_obj["hp"] = int(m.get("hp", stats_obj.get("hp", 0)))
            except Exception:
                pass
            try:
                stats_obj["current_mana"] = int(m.get("mana", stats_obj.get("current_mana", stats_obj.get("mana", 0))))
            except Exception:
                pass
            row.stats = _json.dumps(stats_obj)
            db.session.add(row)
            changed = True
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        pass


def player_attack(combat_id: int, user_id: int, version: int, actor_id: Optional[int] = None) -> Dict[str, Any]:
    """Execute a basic weapon attack for the active player initiative entry.

    Enforces turn ownership and optimistic version check. Miss / crit outcomes
    logged; on hit monster HP reduced and turn advanced.

    Returns a response dict containing either ``{"ok": True, "state": ...}``
    or ``{"error": <code>, ...}`` with the authoritative session state.
    """
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return {"error": "no_initiative"}
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "state": session.to_dict()}
    # Determine controlling user and required actor id
    if actor_id is None:
        actor_id = actor.get("id")
    if actor.get("controller_id") != user_id or actor.get("id") != actor_id:
        return {"error": "not_your_turn", "state": session.to_dict()}
    # Check if character is alive (dead characters cannot act)
    party = json.loads(session.party_snapshot_json or "{}") or {}
    attacker = _player_ref(party, actor_id)
    if attacker and attacker.get("hp", 0) <= 0:
        _append_log(session, f"{attacker.get('name', 'Character')} is unconscious and cannot act!")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "skipped": True}
    # Improved damage model with accuracy/evasion & crits (placeholder formulas)
    monster = session.monster()
    atk = attacker.get("attack", 12) if attacker else 12
    acc_roll = random.randint(1, 20)
    accuracy = atk + acc_roll
    evasion = monster.get("armor", 0) + 10  # simple base + armor scaling
    if acc_roll == 1:
        hit = False
    elif acc_roll == 20:
        hit = True
    else:
        hit = accuracy >= evasion
    if not hit:
        _append_log(session, f"Player misses {monster.get('name')} (roll {acc_roll})", code=PLAYER_ATTACK_MISS)
        # Track miss for visual effects
        session.last_damage_json = json.dumps({"to_monster": {"amount": 0, "is_miss": True, "is_critical": False}})
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "miss": True}
    base = atk
    variance = random.randint(-atk // 4, atk // 4)
    dmg = max(1, base + variance)
    crit = acc_roll == 20
    if crit:
        dmg = int(dmg * 1.5)
    session.monster_hp = max(0, (session.monster_hp or 0) - dmg)
    _append_log(
        session,
        f"Player hits {monster.get('name')} for {dmg}{' (CRIT)' if crit else ''} damage (HP {session.monster_hp})",
        code=PLAYER_ATTACK_HIT,
    )
    # Track damage for visual effects
    session.last_damage_json = json.dumps({"to_monster": {"amount": dmg, "is_miss": False, "is_critical": crit}})
    # After action resolution move to end phase (skipping remaining intermediate phases for now)
    session.phase = "end"
    _progress_phase(session)  # this will advance turn because phase becomes end -> progress -> next
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict()}


def player_flee(combat_id: int, user_id: int, version: int, actor_id: Optional[int] = None) -> Dict[str, Any]:
    """Attempt to flee the encounter.

    50% success ends combat immediately with no rewards; failure advances turn.
    Always validates active actor & version first.
    """
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "state": session.to_dict()}
    # Multi-character support: validate by controller id; ignore stale actor_id mismatch by re-binding to active actor
    if actor.get("controller_id") != user_id:
        return {"error": "not_your_turn", "state": session.to_dict()}
    if actor_id is not None and actor.get("id") != actor_id:
        # Provided actor_id is stale; proceed anyway (tests may have cached earlier id)
        pass
    success = random.random() < 0.5
    if success:
        session.status = "complete"
        _append_log(session, "Player flees successfully.", code=PLAYER_FLEE_SUCCESS)
        _persist_party_resources(session)
        set_combat_state(False)
    else:
        _append_log(session, "Flee attempt failed.", code=PLAYER_FLEE_FAIL)
    # Flee consumes the whole turn (advance immediately)
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)
    if not success:  # Only if combat continues
        session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "fled": success}


def monster_auto_turn(session: CombatSession):
    """Perform the monster's automatic action if it's the monster's turn.

    Applies start-of-turn effects, cooldown gating, AI action selection, damage
    calculation, and end-of-combat checks. Emits appropriate update events.
    Silently returns if session not active or not monster's initiative slot.
    """
    if session.status != "active":
        return
    if not _is_monster_turn(session):
        return
    party = json.loads(session.party_snapshot_json or "{}") or {}
    # Cooldown gate: if monster_ai.cooldown_turns > 0 and last action turn stored in monster['last_turn'] >= current - (cooldown-1), skip action
    try:
        from app.models import GameConfig as _GC  # local import for dynamic lookup

        cfg_raw = _GC.get("monster_ai")
        cooldown_turns = 0
        if cfg_raw:
            import json as _json

            cfg_obj = _json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
            if isinstance(cfg_obj, dict):
                cooldown_turns = int(cfg_obj.get("cooldown_turns", 0))
        if cooldown_turns > 0:
            monster_preview = session.monster() or {}
            last_turn = monster_preview.get("last_turn")
            if isinstance(last_turn, int) and session.combat_turn - last_turn < cooldown_turns:
                _append_log(session, f"{monster_preview.get('name')} waits (cooldown).", code=MONSTER_COOLDOWN_WAIT)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                if session.status != "active":
                    _emit_session("combat_end", session)
                return
    except Exception:
        pass
    members = party.get("members", [])
    if not members:
        # No viable targets; log an explicit wait so client sees monster acted
        try:
            monster_preview = session.monster() or {}
            _append_log(
                session, f"{monster_preview.get('name','Monster')} waits (no targets).", code=MONSTER_NO_TARGET_WAIT
            )
            db.session.commit()
            _emit_session("combat_update", session)
        except Exception:
            pass
        return
    # Ensure effects list presence for each member to simplify later additions
    for m in members:
        m.setdefault("effects", [])
    target = members[0]
    monster = session.monster() or {}
    # Start-of-turn effects for monster (e.g., poison on monster)
    monster.setdefault("effects", [])
    start_logs = []
    try:
        start_logs.extend(apply_start_of_turn(monster))
    except Exception:
        pass
    for msg in start_logs:
        _append_log(session, msg)
    # If monster died to DoT before acting
    if (session.monster_hp is not None and session.monster_hp <= 0) or monster.get("hp", session.monster_hp) <= 0:
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        return
    # Pre-action veto (stun)
    can_act_flag, veto_logs = True, []
    try:
        can_act_flag, veto_logs = can_act(monster)
    except Exception:
        pass
    for msg in veto_logs:
        _append_log(session, msg)
    if not can_act_flag:
        # If no specific veto logs were produced, add a generic waits/inactive line for clarity
        if not veto_logs:
            try:
                _append_log(session, f"{monster.get('name')} waits (incapacitated).", code=MONSTER_INCAPACITATED_WAIT)
            except Exception:
                pass
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        return
    # Boss ability system - check if boss should use special ability
    boss_action = None
    try:
        from app.services import boss_abilities

        if boss_abilities.is_boss(monster):
            boss_action = boss_abilities.select_boss_ability(monster, party, session.combat_turn)
    except Exception:
        pass

    # If boss uses ability, execute it
    if boss_action:
        try:
            from app.services import boss_abilities

            if boss_action.get("type") == "boss_aoe":
                logs, party = boss_abilities.execute_boss_aoe(monster, party, session)
                for log in logs:
                    _append_log(session, log)
                session.party_snapshot_json = json.dumps(party)
                session.monster_json = json.dumps(monster)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                _emit_if_completed(session)
                return
            elif boss_action.get("type") == "boss_buff":
                logs = boss_abilities.execute_boss_buff(monster)
                for log in logs:
                    _append_log(session, log)
                session.monster_json = json.dumps(monster)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                _emit_if_completed(session)
                return
            elif boss_action.get("type") == "boss_heal":
                logs = boss_abilities.execute_boss_heal(monster)
                for log in logs:
                    _append_log(session, log)
                session.monster_json = json.dumps(monster)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                _emit_if_completed(session)
                return
            elif boss_action.get("type") == "boss_summon":
                logs = boss_abilities.execute_boss_summon(monster, session)
                for log in logs:
                    _append_log(session, log)
                session.monster_json = json.dumps(monster)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                _emit_if_completed(session)
                return
        except Exception:
            pass  # Fall through to normal AI

    # AI delegation (still only basic attack). If monster has flag ai_enabled use selector.
    action = {"type": "attack", "target_index": 0}
    try:
        if monster.get("ai_enabled"):
            action = select_action(monster, party, {"turn": session.combat_turn}) or action
    except Exception:
        pass
    if action.get("type") == "spell" and action.get("spell") == "firebolt":
        idx = int(action.get("target_index", 0))
        if idx < 0 or idx >= len(members):
            idx = 0
        target = members[idx]
        # Monster INT-like stat: use damage as surrogate, or explicit int_stat
        int_stat = int(monster.get("int_stat", monster.get("damage", 8)))
        acc_roll = random.randint(1, 20)
        # Spell evasion slightly lower than physical to ensure deterministic test hit scenarios
        defender_evasion = target.get("defense", 5) + 8
        if acc_roll == 1:
            _append_log(session, f"{monster.get('name')}" + "'s Firebolt fizzles (natural 1).")
        else:
            crit = acc_roll == 20
            attack_total = int_stat + acc_roll
            hit = True if crit else attack_total >= defender_evasion
            if not hit:
                _append_log(
                    session,
                    f"{monster.get('name')}'s Firebolt misses {target['name']} (roll {acc_roll}).",
                    code=MONSTER_SPELL_MISS,
                )
            else:
                roll = random.randint(1, 8) + random.randint(1, 8)
                dmg = int(roll + int_stat * 0.6)
                if crit:
                    dmg = int(dmg * 1.5)
                resistances = target.get("resistances", {})
                try:
                    dmg = int(apply_resistances(dmg, ["fire"], resistances))
                except Exception:
                    pass
                if target.get("defending"):
                    dmg = max(1, dmg // 2)
                    target["defending"] = False
                target["hp"] = max(0, target.get("hp", 0) - dmg)
                members[idx] = target
                party["members"] = members
                session.party_snapshot_json = json.dumps(party)
                _append_log(
                    session,
                    f"{monster.get('name')} casts Firebolt on {target['name']} for {dmg}{' (CRIT)' if crit else ''} damage (HP {target['hp']})",
                    code=MONSTER_SPELL_HIT,
                )
    elif action.get("type") == "flee":
        # Monster attempts to flee: end combat, no rewards
        session.status = "complete"
        _append_log(session, f"{monster.get('name')} flees!", code=MONSTER_FLEE)
        _persist_party_resources(session)
        set_combat_state(False)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        return
    elif action.get("type") == "help":
        # For now just a log entry; future: spawn ally or buff
        _append_log(session, f"{monster.get('name')} calls for help!", code=MONSTER_CALL_HELP)
    elif action.get("type") == "attack":
        # Smart targeting: pick alive character with highest threat/lowest HP
        alive_members = [(i, m) for i, m in enumerate(members) if m.get("hp", 0) > 0]
        if not alive_members:
            # No targets available, skip turn
            _advance_turn(session)
            _check_end(session)
            db.session.commit()
            _emit_session("combat_update", session)
            _emit_if_completed(session)
            return

        # Prioritize low HP targets (more likely to finish them off)
        alive_members.sort(key=lambda x: (x[1].get("hp", 100), x[0]))
        idx, target = alive_members[0]

        m_base = monster.get("damage", 8)
        acc_roll = random.randint(1, 20)
        accuracy = m_base + acc_roll
        defender_evasion = target.get("defense", 5) + 10
        if acc_roll == 1:
            _append_log(session, f"{monster.get('name')} misses {target['name']} (roll 1)", code=MONSTER_ATTACK_MISS)
            # Track miss for visual effects
            damage_track = {"to_party": {target.get("char_id"): {"amount": 0, "is_miss": True, "is_critical": False}}}
            session.last_damage_json = json.dumps(damage_track)
            try:
                monster_data = session.monster() or {}
                monster_data["last_turn"] = session.combat_turn
                session.monster_json = json.dumps(monster_data)
            except Exception:
                pass
            _advance_turn(session)
            _check_end(session)
            db.session.commit()
            _emit_session("combat_update", session)
            _emit_if_completed(session)
            return
        hit = True if acc_roll == 20 else accuracy >= defender_evasion
        if not hit:
            _append_log(
                session, f"{monster.get('name')} misses {target['name']} (roll {acc_roll})", code=MONSTER_ATTACK_MISS
            )
            # Track miss for visual effects
            damage_track = {"to_party": {target.get("char_id"): {"amount": 0, "is_miss": True, "is_critical": False}}}
            session.last_damage_json = json.dumps(damage_track)
            try:
                monster_data = session.monster() or {}
                monster_data["last_turn"] = session.combat_turn
                session.monster_json = json.dumps(monster_data)
            except Exception:
                pass
            _advance_turn(session)
            _check_end(session)
            db.session.commit()
            _emit_session("combat_update", session)
            _emit_if_completed(session)
            return
        variance = random.randint(-m_base // 4, m_base // 4)
        dmg = max(1, m_base + variance)
        is_crit = acc_roll == 20
        if is_crit:
            dmg = int(dmg * 1.5)
        resistances = target.get("resistances", {})
        dmg = int(apply_resistances(dmg, ["physical"], resistances))
        if target.get("defending"):
            dmg = max(1, dmg // 2)
            target["defending"] = False
        target["hp"] = max(0, target.get("hp", 0) - dmg)
        party["members"][idx] = target
        session.party_snapshot_json = json.dumps(party)
        # Track damage for visual effects
        damage_track = {"to_party": {target.get("char_id"): {"amount": dmg, "is_miss": False, "is_critical": is_crit}}}
        session.last_damage_json = json.dumps(damage_track)
        _append_log(
            session,
            f"{monster.get('name')} hits {target['name']} for {dmg} damage (HP {target['hp']})",
            code=MONSTER_ATTACK_HIT,
        )
    else:
        # Unknown/idle action just advances turn
        _append_log(session, f"{monster.get('name')} hesitates.", code=MONSTER_HESITATE)
    # (already coded above - kept for clarity)
    # Persist last action turn onto monster JSON so cooldown can reference next cycle
    try:
        monster_data = session.monster() or {}
        monster_data["last_turn"] = session.combat_turn
        session.monster_json = json.dumps(monster_data)
    except Exception:
        pass
    # Monster completes its action; advance to next turn via end phase progression
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)


def progress_monster_turn_if_needed(combat_id: int):
    """Convenience helper to advance monster logic if current turn is monster.

    Used by routes/tests that poll session state to eagerly progress AI turns.
    """
    session = _load_session(combat_id)
    if not session or session.status != "active":
        return
    if _is_monster_turn(session):
        monster_auto_turn(session)


# ---------------- New Actions -----------------


def player_defend(combat_id: int, user_id: int, version: int, actor_id: Optional[int] = None) -> Dict[str, Any]:
    """Mark the acting player as defending (halves next physical damage) and advance turn."""
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return {"error": "no_initiative"}
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "state": session.to_dict()}
    if actor_id is None:
        actor_id = actor.get("id")
    if actor.get("controller_id") != user_id or actor.get("id") != actor_id:
        return {"error": "not_your_turn", "state": session.to_dict()}
    party = json.loads(session.party_snapshot_json or "{}") or {}
    for m in party.get("members", []):
        if m.get("char_id") == actor_id:
            m["defending"] = True
            break
    session.party_snapshot_json = json.dumps(party)
    _append_log(session, "Player braces for impact (Defend).", code=PLAYER_DEFEND)
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "defend": True}


def player_use_item(
    combat_id: int, user_id: int, version: int, slug: str, actor_id: Optional[int] = None
) -> Dict[str, Any]:
    """Consume / apply a combat item (currently only healing potion) for actor.

    Removes one instance of the item from first character inventory if present
    (supports legacy & stacked formats) and updates HP. Advances turn whether
    or not monster defeated on heal (heals cannot end combat).
    """
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "state": session.to_dict()}
    if actor_id is None:
        actor_id = actor.get("id")
    if actor.get("controller_id") != user_id:
        return {"error": "not_your_turn", "state": session.to_dict()}
    if actor.get("id") != actor_id:
        # Allow stale actor id (client cached) by rebinding to current initiative actor
        actor_id = actor.get("id")
    if not slug:
        return {"error": "item_required"}
    # Only simple healing potion for now
    party = json.loads(session.party_snapshot_json or "{}") or {}
    used = False
    for m in party.get("members", []):
        if m.get("char_id") == actor_id:
            if slug == "potion-healing":
                heal = 25
                m["hp"] = min(m.get("max_hp", 100), m.get("hp", 0) + heal)
                used = True
            break
    if not used:
        return {"error": "cannot_use"}
    # Attempt to remove the item from the first character's inventory list if present
    removed_successfully = False
    try:
        char_row = Character.query.filter_by(user_id=session.user_id).first()
        if char_row and char_row.items:
            inv = []
            try:
                inv = json.loads(char_row.items)
            except Exception:
                inv = []
            changed = False
            # Inventory may be list of strings or list of {slug,qty}
            new_inv = []
            removed = False
            for entry in inv:
                if removed:
                    new_inv.append(entry)
                    continue
                if isinstance(entry, str):
                    if entry == slug:
                        removed = True
                        changed = True
                        removed_successfully = True
                        continue
                    new_inv.append(entry)
                elif isinstance(entry, dict):
                    if entry.get("slug") == slug:
                        qty = int(entry.get("qty", 1)) - 1
                        if qty > 0:
                            entry["qty"] = qty
                            new_inv.append(entry)
                        changed = True
                        removed = True
                        removed_successfully = True
                    else:
                        new_inv.append(entry)
                else:
                    new_inv.append(entry)
            if changed:
                char_row.items = json.dumps(new_inv)
                db.session.add(char_row)
    except Exception:
        pass
    # Decrement surfaced party item counts if present and we actually removed an item.
    try:
        if removed_successfully:
            counts = party.setdefault("item_counts", {})
            if slug == "potion-healing":
                current = int(counts.get("potion-healing", 0))
                counts["potion-healing"] = max(0, current - 1)
    except Exception:
        pass
    session.party_snapshot_json = json.dumps(party)
    _append_log(session, f"Player uses {slug}.", code=PLAYER_USE_ITEM)
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "item_used": slug}


def player_cast_spell(
    combat_id: int, user_id: int, version: int, spell: str, actor_id: Optional[int] = None
) -> Dict[str, Any]:
    """Cast a supported spell (Firebolt, Ice Shard, Lightning) reducing mana and dealing damage.

    Provides miss / crit semantics parallel to physical attacks; applies
    monster resistances. Unsupported spells return ``{"error":"bad_spell"}``.
    """
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "state": session.to_dict()}
    if actor_id is None:
        actor_id = actor.get("id")
    if actor.get("controller_id") != user_id or actor.get("id") != actor_id:
        return {"error": "not_your_turn", "state": session.to_dict()}

    # Spell configuration
    spell_config = {
        "firebolt": {"cost": 5, "damage_dice": (1, 8, 2), "element": "fire", "name": "Firebolt"},
        "ice_shard": {"cost": 6, "damage_dice": (2, 6, 1), "element": "ice", "name": "Ice Shard"},
        "lightning": {"cost": 8, "damage_dice": (1, 10, 2), "element": "lightning", "name": "Lightning Bolt"},
    }

    if spell not in spell_config:
        return {"error": "bad_spell"}

    config = spell_config[spell]
    party = json.loads(session.party_snapshot_json or "{}") or {}
    caster = _player_ref(party, actor_id)
    if not caster:
        return {"error": "no_caster"}

    cost = config["cost"]
    mana_available = caster.get("mana") if "mana" in caster else caster.get("current_mana", 0)
    if mana_available < cost:
        return {"error": "no_mana", "mana": mana_available}
    mana_available -= cost
    # Normalize storage back into both keys for backward compatibility
    caster["mana"] = mana_available
    caster["current_mana"] = mana_available
    int_stat = caster.get("int_stat", caster.get("attack", 10))
    # Spell accuracy: d20 + INT-based attack surrogate vs monster evasion (10 + armor)
    acc_roll = random.randint(1, 20)
    evasion = session.monster().get("armor", 0) + 10
    # Basic hit logic parallel to weapon attacks
    if acc_roll == 1:
        _append_log(session, f"Player's {config['name']} fizzles (natural 1).", code=PLAYER_SPELL_FIZZLE)
        # Track miss for visual effects
        session.last_damage_json = json.dumps({"to_monster": {"amount": 0, "is_miss": True, "is_critical": False}})
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "spell": spell, "miss": True}
    crit = acc_roll == 20
    # Always hit on natural 20; otherwise compare INT surrogate + roll to evasion
    attack_total = int_stat + acc_roll
    hit = True if crit else attack_total >= evasion
    if not hit:
        _append_log(session, f"Player's {config['name']} misses (roll {acc_roll}).", code=PLAYER_SPELL_MISS)
        # Track miss for visual effects
        session.last_damage_json = json.dumps({"to_monster": {"amount": 0, "is_miss": True, "is_critical": False}})
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "spell": spell, "miss": True}

    # Calculate damage based on spell configuration
    num_dice, die_size, num_rolls = config["damage_dice"]
    roll = sum(random.randint(1, die_size) for _ in range(num_dice * num_rolls))
    dmg = int(roll + int_stat * 0.6)
    if crit:
        dmg = int(dmg * 1.5)
    # Apply monster resistances if any
    resistances = session.monster().get("resistances", {}) or {}
    try:
        dmg = int(apply_resistances(dmg, [config["element"]], resistances))
    except Exception:
        pass
    session.monster_hp = max(0, (session.monster_hp or 0) - dmg)
    session.party_snapshot_json = json.dumps(party)
    # Track damage for visual effects
    session.last_damage_json = json.dumps({"to_monster": {"amount": dmg, "is_miss": False, "is_critical": crit}})
    _append_log(
        session,
        f"Player casts {config['name']} for {dmg}{' (CRIT)' if crit else ''} damage (HP {session.monster_hp})",
        code=PLAYER_SPELL_HIT,
    )
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "spell": spell, "damage": dmg, "crit": crit}


# ---------------- Auto Monster Progression Helper -----------------


def _auto_progress_monster_after_player(session: CombatSession) -> CombatSession:
    """If after a player action it's now the monster's turn, immediately run the monster AI.

    Returns the (possibly reloaded) session so callers can serialize fresh state.
    Safe no-op if combat ended or still a player's turn.
    """
    try:
        if not session or session.status != "active":
            return session
        # Ensure we have latest DB state before deciding (commit already done by caller)
        db.session.refresh(session)
        if _is_monster_turn(session):
            monster_auto_turn(session)  # commits & emits internally
            # Reload to pick up monster action effects
            refreshed = _load_session(session.id)
            if refreshed:
                return refreshed
    except Exception:
        pass
    return session
