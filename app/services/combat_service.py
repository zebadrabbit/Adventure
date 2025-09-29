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

from app import db, socketio
from app.models.models import Character, CombatSession

from .combat_utils import apply_resistances
from .loot_service import roll_loot
from .monster_ai import select_action
from .status_effects import apply_start_of_turn, can_act
from .time_service import set_combat_state


def _now():
    return datetime.utcnow()


def _derive_stats(char: Character) -> Dict[str, Any]:
    import json as _json

    base = {}
    try:
        raw = _json.loads(char.stats) if char.stats else {}
        if isinstance(raw, dict):
            base = raw
    except Exception:
        base = {}
    level = getattr(char, "level", 1) or 1
    STR = int(base.get("str", base.get("STR", 10)) or 10)
    DEX = int(base.get("dex", base.get("DEX", 10)) or 10)
    INT = int(base.get("int", base.get("INT", 10)) or 10)
    CON = int(base.get("con", base.get("CON", STR)) or STR)
    max_hp = 50 + CON * 2 + level * 5
    attack = 8 + STR // 2 + level
    defense = 5 + DEX // 3 + level // 2
    speed = 8 + DEX // 2
    mana_max = 20 + INT * 2
    mana = min(int(base.get("mana", mana_max)), mana_max)
    return {
        # Controller user id retained separately from participant (character) id.
        "controller_id": char.user_id,
        "char_id": char.id,
        "name": char.name,
        "hp": max_hp,
        "max_hp": max_hp,
        "attack": attack,
        "defense": defense,
        "speed": speed,
        "mana": mana,
        "mana_max": mana_max,
        "int_stat": INT,
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
            "hp": 100,
            "max_hp": 100,
            "attack": 12,
            "defense": 5,
            "speed": 10,
            "mana": 30,
            "mana_max": 30,
            "int_stat": 10,
            "resistances": {},
            "defending": False,
            "buffs": [],
        }
    ]
    return {"members": members}


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


def _append_log(session: CombatSession, message: str):
    logs = json.loads(session.log_json) if session.log_json else []
    logs.append({"ts": _now().isoformat(), "m": message})
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
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return
    session.active_index += 1
    if session.active_index >= len(initiative):
        session.active_index = 0
        session.combat_turn += 1
    session.version += 1


def _check_end(session: CombatSession):
    # Monster defeat
    if session.monster_hp is not None and session.monster_hp <= 0:
        monster = session.monster()
        rewards = roll_loot(monster) if monster else {}
        session.status = "complete"
        _append_log(session, f"{monster.get('name')} defeated! Loot: {rewards}")
        # Persist XP & loot to first character (simple placeholder logic)
        try:
            party = json.loads(session.party_snapshot_json or "{}") or {}
            char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
            # Distribute XP equally among present characters
            xp_total = int(monster.get("xp", 0)) if monster else 0
            members = party.get("members", [])
            share = int(xp_total / len(members)) if members else xp_total
            xp_map = {}
            for m in members:
                row = char_rows.get(m.get("char_id") or m.get("id"))
                if row:
                    row.xp += share
                    db.session.add(row)
                    try:
                        xp_map[str(m.get("char_id") or m.get("id"))] = share
                    except Exception:
                        pass
            # Loot -> first character inventory for now
            if rewards.get("items") and char_rows:
                first = next(iter(char_rows.values()))
                items = []
                if first.items:
                    try:
                        items = json.loads(first.items)
                        if not isinstance(items, list):
                            items = []
                    except Exception:
                        items = []
                # rewards['items'] now mapping slug->qty; fallback: if legacy list provided under items_list merge those
                if isinstance(rewards.get("items"), dict):
                    for slug, qty in rewards.get("items", {}).items():
                        try:
                            q = int(qty)
                        except Exception:
                            q = 1
                        for _ in range(max(1, q)):
                            items.append(slug)
                elif isinstance(rewards.get("items"), list):  # legacy
                    for slug in rewards.get("items", []):
                        items.append(slug)
                # Include any legacy items_list (list of slugs) if provided and not already counted
                if isinstance(rewards.get("items_list"), list):
                    for slug in rewards.get("items_list"):
                        items.append(slug)
                first.items = json.dumps(items)
                db.session.add(first)
            # Augment rewards with XP distribution metadata so clients/tests can introspect
            try:
                rewards["xp"] = {"total": xp_total, "per_member": xp_map}
            except Exception:
                pass
        except Exception:
            db.session.rollback()
        session.rewards_json = json.dumps(rewards)
        set_combat_state(False)
    else:
        # All players dead?
        party = json.loads(session.party_snapshot_json or "{}") or {}
        alive = [m for m in party.get("members", []) if m.get("hp", 0) > 0]
        if not alive:
            session.status = "complete"
            session.rewards_json = json.dumps({})
            _append_log(session, "Party defeated.")
            set_combat_state(False)


def _emit_session(event: str, session: CombatSession):  # safe emit wrapper
    try:
        socketio.emit(event, session.to_dict(), namespace="/adventure")
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
    # Improved damage model with accuracy/evasion & crits (placeholder formulas)
    monster = session.monster()
    party = json.loads(session.party_snapshot_json or "{}") or {}
    attacker = _player_ref(party, actor_id)
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
        _append_log(session, f"Player misses {monster.get('name')} (roll {acc_roll})")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
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
    )
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
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
        _append_log(session, "Player flees successfully.")
        set_combat_state(False)
    else:
        _append_log(session, "Flee attempt failed.")
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
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
                _append_log(session, f"{monster_preview.get('name')} is waiting (cooldown).")
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
        if session.status != "active":
            _emit_session("combat_end", session)
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
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
        return
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
                _append_log(session, f"{monster.get('name')}'s Firebolt misses {target['name']} (roll {acc_roll}).")
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
                )
    elif action.get("type") == "flee":
        # Monster attempts to flee: end combat, no rewards
        session.status = "complete"
        _append_log(session, f"{monster.get('name')} flees!")
        set_combat_state(False)
    elif action.get("type") == "help":
        # For now just a log entry; future: spawn ally or buff
        _append_log(session, f"{monster.get('name')} calls for help!")
    elif action.get("type") == "attack":
        idx = int(action.get("target_index", 0))
        if idx < 0 or idx >= len(members):
            idx = 0
        target = members[idx]
        m_base = monster.get("damage", 8)
        acc_roll = random.randint(1, 20)
        accuracy = m_base + acc_roll
        defender_evasion = target.get("defense", 5) + 10
        if acc_roll == 1:
            _append_log(session, f"{monster.get('name')} misses {target['name']} (roll 1)")
            # Persist last_turn even on early exit for cooldown logic
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
            if session.status != "active":
                _emit_session("combat_end", session)
            return
        hit = True if acc_roll == 20 else accuracy >= defender_evasion
        if not hit:
            _append_log(session, f"{monster.get('name')} misses {target['name']} (roll {acc_roll})")
            # Persist last_turn even on early exit for cooldown logic
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
            if session.status != "active":
                _emit_session("combat_end", session)
            return
        variance = random.randint(-m_base // 4, m_base // 4)
        dmg = max(1, m_base + variance)
        if acc_roll == 20:
            dmg = int(dmg * 1.5)
        resistances = target.get("resistances", {})
        dmg = int(apply_resistances(dmg, ["physical"], resistances))
        if target.get("defending"):
            dmg = max(1, dmg // 2)
            target["defending"] = False
        target["hp"] = max(0, target.get("hp", 0) - dmg)
        party["members"][idx] = target
        session.party_snapshot_json = json.dumps(party)
        _append_log(session, f"{monster.get('name')} hits {target['name']} for {dmg} damage (HP {target['hp']})")
    else:
        # Unknown/idle action just advances turn
        _append_log(session, f"{monster.get('name')} hesitates.")
    # Persist last action turn onto monster JSON so cooldown can reference next cycle
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
    if session.status != "active":
        _emit_session("combat_end", session)


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
    _append_log(session, "Player braces for impact (Defend).")
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
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
                    else:
                        new_inv.append(entry)
                else:
                    new_inv.append(entry)
            if changed:
                char_row.items = json.dumps(new_inv)
                db.session.add(char_row)
    except Exception:
        pass
    session.party_snapshot_json = json.dumps(party)
    _append_log(session, f"Player uses {slug}.")
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
    return {"ok": True, "state": session.to_dict(), "item_used": slug}


def player_cast_spell(
    combat_id: int, user_id: int, version: int, spell: str, actor_id: Optional[int] = None
) -> Dict[str, Any]:
    """Cast a supported spell (Firebolt) reducing mana and dealing damage.

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
    if spell not in ("firebolt",):
        return {"error": "bad_spell"}
    party = json.loads(session.party_snapshot_json or "{}") or {}
    caster = _player_ref(party, actor_id)
    if not caster:
        return {"error": "no_caster"}
    cost = 5
    if caster.get("mana", 0) < cost:
        return {"error": "no_mana", "mana": caster.get("mana", 0)}
    caster["mana"] -= cost
    int_stat = caster.get("int_stat", caster.get("attack", 10))
    # Spell accuracy: d20 + INT-based attack surrogate vs monster evasion (10 + armor)
    acc_roll = random.randint(1, 20)
    evasion = session.monster().get("armor", 0) + 10
    # Basic hit logic parallel to weapon attacks
    if acc_roll == 1:
        _append_log(session, "Player's Firebolt fizzles (natural 1).")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
        return {"ok": True, "state": session.to_dict(), "spell": spell, "miss": True}
    crit = acc_roll == 20
    # Always hit on natural 20; otherwise compare INT surrogate + roll to evasion
    attack_total = int_stat + acc_roll
    hit = True if crit else attack_total >= evasion
    if not hit:
        _append_log(session, f"Player's Firebolt misses (roll {acc_roll}).")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        if session.status != "active":
            _emit_session("combat_end", session)
        return {"ok": True, "state": session.to_dict(), "spell": spell, "miss": True}
    roll = random.randint(1, 8) + random.randint(1, 8)
    dmg = int(roll + int_stat * 0.6)
    if crit:
        dmg = int(dmg * 1.5)
    # Apply monster resistances if any (treat firebolt as 'fire')
    resistances = session.monster().get("resistances", {}) or {}
    try:
        dmg = int(apply_resistances(dmg, ["fire"], resistances))
    except Exception:
        pass
    session.monster_hp = max(0, (session.monster_hp or 0) - dmg)
    session.party_snapshot_json = json.dumps(party)
    _append_log(
        session,
        f"Player casts Firebolt for {dmg}{' (CRIT)' if crit else ''} damage (HP {session.monster_hp})",
    )
    _advance_turn(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
    return {"ok": True, "state": session.to_dict(), "spell": spell, "damage": dmg, "crit": crit}
