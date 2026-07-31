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
from app.models.models import Character, CombatSession, Item
from app.models.dungeon_instance import DungeonInstance
from app.services import extraction_service

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
    PLAYER_SKILL,
    PLAYER_SPELL_FIZZLE,
    PLAYER_SPELL_HIT,
    PLAYER_SPELL_MISS,
    PLAYER_USE_ITEM,
)
from .combat_utils import apply_resistances
from .item_effects import REFUSAL_ITEM_REMOVAL_FAILED, REFUSAL_NO_EFFECT, resolve_potion_effect
from .loot_service import _item_display_name, _loot_summary, roll_loot
from .monster_ai import select_action
from .status_effects import apply_start_of_turn, can_act, replace_effect
from .time_service import set_combat_state

logger = structlog.get_logger()

# Player-facing refusal when the acting character's own pack doesn't hold the
# named potion -- same register as item_effects.REFUSAL_NO_EFFECT (prose, not
# a machine code). Ownership is checked before an effect is ever applied, so
# this is what an exploited "use an item you don't have" attempt now gets.
_REFUSAL_NOT_CARRIED = "No such potion turns up among your provisions."

# The remaining refusals player_use_item can return. The item panel shows the
# player whatever comes back, so every branch of that one function needs prose
# -- no_effect and not_carried arriving as sentences while their immediate
# neighbours still answered with machine codes is how "cannot_use" ended up on
# screen. (The item-removal failure shares its wording with the out-of-combat
# path, so it lives in item_effects alongside REFUSAL_NO_EFFECT.)
_REFUSAL_ITEM_REQUIRED = "Name the draught you mean to drink."
_REFUSAL_CANNOT_USE = "No such hero stands with the party in this fight."
_REFUSAL_NOT_YOUR_TURN = "It is not your turn to act."
_REFUSAL_VERSION_CONFLICT = "The fight has moved on since you last looked. Take stock and try again."


def _now():
    return datetime.utcnow()


# The damage types the pipeline actually emits: monster and player attacks tag
# "physical", and the three offensive spells tag fire / ice / lightning. Note it
# is "ice", not "cold" -- the monster catalogue's trait vocabulary disagrees, and
# the traits are decoration, so this list follows the code that runs.
RESISTABLE_ELEMENTS = ("physical", "fire", "ice", "lightning")

# One resist point = one percent off, floored so a stacked set cannot reach
# immunity. 25 resist is a quarter off; the floor bites past 60 points.
_RESIST_FLOOR = 0.4


def _resist_map(resist_all: int) -> Dict[str, float]:
    if not resist_all:
        return {}
    mult = max(_RESIST_FLOOR, 1.0 - (int(resist_all) / 100.0))
    return {element: mult for element in RESISTABLE_ELEMENTS}


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
    from app.services.loot_service import gear_bonuses

    try:
        _gear = json.loads(char.gear) if getattr(char, "gear", None) else {}
    except Exception:
        _gear = {}
    _gb = gear_bonuses(_gear)
    # Fold unlocked passive skill effects in alongside gear (same stat vocabulary).
    try:
        from app.services.skill_effects import passive_bonuses

        for _k, _v in passive_bonuses(char.id).items():
            _gb[_k] = _gb.get(_k, 0) + _v
    except Exception:
        logger.debug("suppressed_exception", where="_derive_stats", exc_info=True)
    STR += int(_gb.get("str", 0))
    DEX += int(_gb.get("dex", 0))
    INT += int(_gb.get("int", 0))
    CON += int(_gb.get("con", 0))
    WIS += int(_gb.get("wis", 0))
    CHA += int(_gb.get("cha", 0))

    # Cap formulas match character_stats.compute_hp_mana_max, but this pass
    # stays inline deliberately: it derives attack/defense/speed from the
    # same folded attributes, and its CON default falls back to STR (not 10)
    # for legacy rows — folding onto the shared helper would change combat
    # HP for characters missing a con stat.
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

    # crit / lifesteal / resist were rolled onto gear, named in the item, shown
    # in the tooltip -- and read by nothing. 11.4% of every affix point a player
    # earned went into a stat with no consumer, and on rings and amulets it was
    # 100% of the prefix weight. They are carried through now; see the crit roll
    # in player_attack and apply_resistances for where each lands.
    crit_bonus = int(_gb.get("crit", 0))
    lifesteal = int(_gb.get("lifesteal", 0))
    resist_all = int(_gb.get("resist", 0))

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

    from app.models import CharacterStatusEffect

    PERSISTED_EFFECT_NAMES = ("poison", "regen_buff")

    try:
        effects = [
            {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
            for row in CharacterStatusEffect.query.filter(
                CharacterStatusEffect.character_id == char.id,
                CharacterStatusEffect.name.in_(PERSISTED_EFFECT_NAMES),
            ).all()
        ]
    except Exception:
        effects = []

    from app.services.status_effects import describe_status_effect

    effects_display = [describe_status_effect(e) for e in effects]

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
        "level": level,
        "int_stat": INT,
        "str_stat": STR,
        "dex_stat": DEX,
        # Gear resist is an all-element value. apply_resistances takes
        # MULTIPLIERS (0.5 halves the damage), not flat points, so it is
        # converted here -- one resist point is one percent off, floored at a
        # 60% reduction so stacking cannot make a character immune. This was
        # hardcoded {}, which is why apply_resistances was live code that
        # always no-opped and "of Warding" was an entirely inert suffix.
        "resistances": _resist_map(resist_all),
        "crit_bonus": crit_bonus,
        "lifesteal": lifesteal,
        "defending": False,
        "buffs": [],
        "effects": effects,
        "effects_display": effects_display,
    }


def _party_characters(user_id: int) -> List[Character]:
    """The up to 4 characters that make up ``user_id``'s combat party -- the
    same scope _base_player_snapshot uses to build ``members``.

    Every item_counts call site must query this exact set, not just "all of
    this user's characters": a character outside the active party can never
    be ``actor_id`` in this session, so counting their potions produces
    entries no combat action can ever touch, and (worse) a user with 5+
    characters would otherwise get a session-start item_counts that omits
    characters 5+ while every later recompute (reward grant, item use,
    backfill) silently includes them.
    """
    return Character.query.filter_by(user_id=user_id).order_by(Character.id.asc()).limit(4).all()


def _base_player_snapshot(user_id: int) -> Dict[str, Any]:
    # Build party from user's characters (up to 4)
    chars = _party_characters(user_id)
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
            "level": 1,
            "int_stat": 10,
            "str_stat": 10,
            "dex_stat": 10,
            "resistances": {},
            "defending": False,
            "buffs": [],
        }
    ]
    # Per-character inventory counts (plus kind/name metadata) surfaced for UI
    # gating and grouping — each character's potions are their own, not a
    # shared pool. Every slug the resolver recognises is counted, not just
    # the two legacy ones, so tiered potions show up too.
    try:
        item_payload = _party_item_payload(chars)
    except Exception as e:
        logger.warning("Failed to parse inventory", exc_info=e)
        item_payload = {"item_counts": {}, "item_meta": {}}
    return {
        "members": members,
        **item_payload,
    }


def _calc_initiative(party: Dict[str, Any], monsters: Any) -> List[Dict[str, Any]]:
    """Initiative across every combatant, one entry per monster.

    Still accepts a bare monster dict: ``encounters.py`` and ~50 test call sites
    pass one, and this spends a ``random.randint`` per combatant -- about a dozen
    test files feed a finite ``iter([...])`` to ``random.randint`` and depend on
    the exact roll ordering, so the single-monster path must consume exactly the
    rolls it always did.
    """
    if not isinstance(monsters, list):
        monsters = [monsters]
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
    for monster in monsters:
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
            logger.debug("suppressed_exception", where="_capture_dungeon_snapshot", exc_info=True)
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
    # One monster or a pack: callers still pass a bare dict (encounters.py and
    # every existing test), so normalise here rather than at each call site.
    monsters = [dict(m) for m in monster] if isinstance(monster, list) else [dict(monster)]
    # Session-local ids, assigned once and never reused or compacted -- dead
    # monsters are tombstoned, so an id must not be inferable from a position.
    # The spawn payload's own "id" is the *catalog* id: usually None, and
    # identical for every member of a same-slug pack, so it cannot be a target
    # key. hp is current from here on; hp_max keeps the spawn value, which is
    # what to_dict has always reported as monster_max_hp.
    for i, m in enumerate(monsters):
        m["id"] = i
        m.setdefault("hp_max", m.get("hp", 50))
        m["hp"] = m.get("hp", 50)
    monster = monsters[0]

    party = _base_player_snapshot(user_id)
    initiative = _calc_initiative(party, monsters)
    # Monster HP scaling already applied in monster dict (assumption)
    monster_hp = monster.get("hp", 50)
    dungeon_snapshot = _capture_dungeon_snapshot(user_id)
    session = CombatSession(
        user_id=user_id,
        monster_json=json.dumps(monster),
        monsters_json=json.dumps(monsters),
        party_snapshot_json=json.dumps(party),
        initiative_json=json.dumps(initiative),
        monster_hp=monster_hp,
        combat_turn=1,
        active_index=0,
        log_json=json.dumps([{"ts": _now().isoformat(), "m": f"Encounter starts vs {_describe_pack(monsters)}"}]),
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
                logger.debug("suppressed_exception", where="start_session", exc_info=True)
            if random.random() < ambush_chance:
                logs = json.loads(session.log_json)
                logs.append({"ts": _now().isoformat(), "m": f"{monster.get('name')} ambushes the party!"})
                session.log_json = json.dumps(logs)
                # Monster acts immediately (surprise) without advancing initiative index (still 0 afterwards)
                # We call monster_auto_turn-like logic but constrained: one basic attack only.
                party_state = json.loads(session.party_snapshot_json or "{}") or {}
                members = party_state.get("members", [])
                if members:
                    _amb_idx, _amb_tgt = _pick_monster_target(members)
                    tgt = _amb_tgt if _amb_tgt is not None else members[0]
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
                            logger.debug("suppressed_exception", where="start_session", exc_info=True)
                        if tgt.get("defending"):
                            dmg = max(1, dmg // 2)
                            tgt["defending"] = False
                        tgt["hp"] = max(0, tgt.get("hp", 0) - dmg)
                        members[_amb_idx] = tgt
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
        logger.debug("suppressed_exception", where="start_session", exc_info=True)
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


# --- The monster list -------------------------------------------------------
# ``monsters_json`` is the source of truth: one entry per monster, each an
# ordinary spawn payload plus a session-local ``id``, a current ``hp`` and an
# ``hp_max``. Everything below goes through these three helpers so there is one
# reader, one lookup and one writer.


def _damage_monster(session: CombatSession, dmg: int, target_id: Any = None) -> Dict[str, Any]:
    """Apply damage to one monster, persist the list, return the monster hit.

    Every path that hurts a monster must come through here. ``monsters_json`` is
    the source of truth that ``_check_end`` reads, so a path that decrements only
    the denormalised ``session.monster_hp`` leaves the list holding the monster's
    old HP -- and the "all monsters down" test then never becomes true, so the
    fight cannot end.

    ``target_id`` of None means the first living monster, which is what every
    caller wanted back when there was only ever one.
    """
    monsters = _monsters(session)
    target = _monster_ref(monsters, target_id) if target_id is not None else None
    if target is None or int(target.get("hp", 0) or 0) <= 0:
        target = next((m for m in monsters if int(m.get("hp", 0) or 0) > 0), None)
    if target is None:
        return {}
    was_alive = int(target.get("hp", 0) or 0) > 0
    target["hp"] = max(0, int(target.get("hp", 0) or 0) - int(dmg))
    # Announce the kill where it happens. _check_end names the pack as a whole
    # when the fight ends, which with several monsters would tell the player
    # about every death at once, after the fact.
    if was_alive and target["hp"] <= 0 and len(monsters) > 1:
        _append_log(session, f"{target.get('name', 'The monster')} falls!")
    _save_monsters(session, monsters)
    return target


def _merge_rewards(rolls) -> Dict[str, Any]:
    """Fold one roll_loot() result per monster into a single rewards dict.

    roll_loot returns the same drops twice -- ``items`` as a {slug: qty} map and
    ``items_list`` as a flat mirror -- and the grant in _check_end is an
    if/elif chain that must consume exactly one of them (iterating both is what
    granted every drop twice until it was fixed). So a key is only created here
    when at least one roll actually supplied it: synthesising ``items`` from an
    ``items_list``-only roll would make the fallback branch unreachable again,
    and that branch is pinned by tests/test_combat_reward_inventory_shape.py.
    """
    merged: Dict[str, Any] = {}
    for r in rolls:
        if not isinstance(r, dict):
            continue
        if "items" in r and isinstance(r.get("items"), dict):
            bucket = merged.setdefault("items", {})
            for slug, qty in r["items"].items():
                bucket[slug] = bucket.get(slug, 0) + int(qty or 0)
        if "items_list" in r and isinstance(r.get("items_list"), list):
            merged.setdefault("items_list", []).extend(r["items_list"])
        if r.get("gear"):
            merged.setdefault("gear", []).extend(r["gear"])
        if "rolls" in r:
            merged.setdefault("rolls", []).append(r["rolls"])
    return merged


def _describe_pack(monsters: List[Dict[str, Any]]) -> str:
    """ "a Goblin", "2 Goblins", "a Goblin and an Orc" -- for log lines.

    Single-monster encounters must read exactly as they always did, so the
    one-entry case returns the bare name.
    """
    names = [str(m.get("name") or "something") for m in monsters]
    if len(names) == 1:
        return names[0]
    counts: Dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    parts = [(f"{c} {n}s" if c > 1 else n) for n, c in counts.items()]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def _monsters(session: CombatSession) -> List[Dict[str, Any]]:
    """Every monster in the encounter, oldest sessions included.

    Rows written before ``monsters_json`` existed -- including any session live
    at the moment the app upgraded -- have it NULL. Wrapping the legacy
    ``monster_json``/``monster_hp`` pair here is what let the migration skip a
    backfill: a data migration could not have covered a fight that started
    between the migration and the deploy, and this does.
    """
    try:
        raw = json.loads(session.monsters_json) if session.monsters_json else None
    except Exception:
        raw = None
    if isinstance(raw, list) and raw:
        # Reconcile the denormalised column into the first entry. _save_monsters
        # keeps the two in step, so a divergence means something wrote
        # session.monster_hp directly -- which stays a supported way to say "the
        # first monster took damage" for the compat period, and is what the
        # reward tests and any un-migrated caller still do. Trusting the column
        # here is what stops such a write being silently ignored, which would
        # leave the fight unable to end.
        if session.monster_hp is not None and int(raw[0].get("hp", 0) or 0) != int(session.monster_hp):
            raw[0] = {**raw[0], "hp": int(session.monster_hp)}
        return raw
    legacy = session.monster() or {}
    hp = session.monster_hp if session.monster_hp is not None else legacy.get("hp", 0)
    return [{**legacy, "id": 0, "hp": hp, "hp_max": legacy.get("hp", hp)}]


def _monster_ref(monsters: List[Dict[str, Any]], mid: Any) -> Optional[Dict[str, Any]]:
    """The monster with this id.

    By id, never by list position: dead monsters are tombstoned rather than
    removed, so position and id stay equal only by accident, and a boss summon
    would append with a fresh id rather than at its own index. ``None`` reads as
    0 because legacy initiative entries carry ``"id": None`` -- ``_calc_initiative``
    wrote ``monster.get("id")`` and the spawn payload has never had one. Without
    that, every combat in flight at deploy time hangs on a monster turn nobody
    can resolve.
    """
    key = 0 if mid is None else mid
    for m in monsters:
        if (0 if m.get("id") is None else m.get("id")) == key:
            return m
    return None


def _save_monsters(session: CombatSession, monsters: List[Dict[str, Any]]) -> None:
    """Persist the list, and mirror the first entry into the legacy columns.

    ``monster_json``/``monster_hp`` are kept as a denormalised view rather than
    dropped, so readers that predate multi-enemy keep working. This is the only
    writer that keeps the two in step.
    """
    session.monsters_json = json.dumps(monsters)
    if monsters:
        first = monsters[0]
        session.monster_json = json.dumps(first)
        session.monster_hp = int(first.get("hp", 0) or 0)


def _living_monsters(session: CombatSession) -> List[Dict[str, Any]]:
    return [m for m in _monsters(session) if int(m.get("hp", 0) or 0) > 0]


def _dead_monster_ids(session: CombatSession) -> set:
    """Monster ids in this session at or below 0 HP. Mirrors _downed_player_ids."""
    return {(0 if m.get("id") is None else m.get("id")) for m in _monsters(session) if int(m.get("hp", 0) or 0) <= 0}


def _active_actor(session: CombatSession) -> Optional[Dict[str, Any]]:
    """The initiative entry whose turn it is, or None if the list is unusable."""
    try:
        initiative = json.loads(session.initiative_json or "[]")
    except Exception:
        return None
    if not initiative:
        return None
    idx = session.active_index
    if idx < 0 or idx >= len(initiative):
        return None
    return initiative[idx]


def _active_monster(session: CombatSession) -> Optional[Dict[str, Any]]:
    """The monster acting right now, or None when it is a player's turn."""
    actor = _active_actor(session)
    if not actor or actor.get("type") != "monster":
        return None
    return _monster_ref(_monsters(session), actor.get("id"))


def _entry_qty(entry: Any) -> int:
    """Parse the ``qty`` of a stacked ``{"slug", "qty"}`` inventory entry.

    Defaults to 1 for a missing qty, and to 1 for an unparseable one (never
    raises) -- the one place that parse happens, so a malformed qty can't
    make ownership and decrement disagree about how many units an entry
    represents (ownership would see it as present, decrement would raise).
    """
    try:
        return int(entry.get("qty", 1))
    except Exception:
        return 1


def _entry_matches_slug(entry: Any, slug: str) -> bool:
    """True if a single inventory entry -- bare string (legacy, one unit) or
    ``{"slug", "qty"}`` dict (stacked) -- represents at least one unit of
    ``slug``. The one predicate both "does this character hold this item"
    (ownership) and "remove one unit of this item" (decrement) are built on,
    so those two checks cannot disagree about what counts as holding it."""
    if isinstance(entry, str):
        return entry == slug
    if isinstance(entry, dict):
        return entry.get("slug") == slug and _entry_qty(entry) > 0
    return False


def _character_holds_slug(character, slug: str) -> bool:
    """True if this character's own inventory currently holds at least one
    unit of ``slug``. Ownership must be verified with this *before* a potion's
    effect is applied, not after -- see player_use_item."""
    if not character or not character.items:
        return False
    try:
        inv = json.loads(character.items)
    except Exception:
        return False
    if not isinstance(inv, list):
        return False
    return any(_entry_matches_slug(entry, slug) for entry in inv)


def _decrement_character_slug(character, slug: str) -> bool:
    """Remove one unit of ``slug`` from this character's own inventory.

    Handles both inventory entry formats (see _entry_matches_slug). Returns
    True and mutates ``character.items`` if a unit was found and removed;
    returns False and leaves the character untouched otherwise.
    """
    if not character or not character.items:
        return False
    try:
        inv = json.loads(character.items)
    except Exception:
        return False
    if not isinstance(inv, list):
        return False
    new_inv = []
    removed = False
    for entry in inv:
        if not removed and _entry_matches_slug(entry, slug):
            removed = True
            if isinstance(entry, dict):
                qty = _entry_qty(entry) - 1
                if qty > 0:
                    new_inv.append(dict(entry, qty=qty))
            continue
        new_inv.append(entry)
    if not removed:
        return False
    character.items = json.dumps(new_inv)
    return True


def _grant_slug_to_inventory(inv: List[Any], slug: str, qty: int = 1) -> None:
    """Add ``qty`` units of ``slug`` to a raw inventory list *in the shape that
    list is already in*, mutating it in place.

    The bag is stored in one of two shapes and inventory.utils.load_inventory
    picks its branch by sniffing ``data[0]`` alone -- then discards every entry
    of the other kind. So the shape of the existing list is not cosmetic:
    appending a bare string to a list of dicts (which is what combat rewards
    used to do) means load_inventory takes the canonical branch and drops the
    reward, leaving a potion that combat's own parser can see and spend but
    that never appears in the bag grid, and that the next load/dump round-trip
    deletes outright. Appending a dict to a legacy list of strings is the same
    bug pointed the other way, and it would take procedural gear instances with
    it, so neither shape may simply be imposed on the other.

    Legacy lists therefore get bare strings and canonical lists get a merged
    ``{"slug", "qty"}`` stack. An empty list is canonical: the first entry it
    gets decides the branch for good, and canonical is the format everything
    else writes. Gear instances (dicts with a ``uid`` and no ``slug``) are never
    merged into -- they are not stacks and hold no qty.
    """
    if qty <= 0:
        return
    if inv and isinstance(inv[0], str):
        inv.extend([slug] * qty)
        return
    for entry in inv:
        if isinstance(entry, dict) and not entry.get("uid") and entry.get("slug") == slug:
            entry["qty"] = _entry_qty(entry) + qty
            return
    inv.append({"slug": slug, "qty": qty})


def _item_counts_by_character(chars) -> Dict[str, Dict[str, int]]:
    """Per-character counts of every potion the resolver recognises, keyed
    ``{slug: {char_id: count}}``. Each character's potions are their own --
    there is no shared/party-wide potion pool.

    The single place the counts get built. All four sites that used to call
    this directly -- session start (_base_player_snapshot), reward grants
    (_check_end), the use_item decrement, and the old-session backfill
    (combat_api.combat_state) -- now go through _party_item_payload instead,
    which calls this and pairs it with item_meta (kind/name) built from the
    same counts, so the two can never drift apart. Keeping this function
    itself narrow (counts only, no catalogue lookup) is what let
    potion-regen end up counted at session start but never decremented when
    spent, once upon a time -- that drift is now impossible because there is
    exactly one place ("which slugs count") both the count and the metadata
    are derived from.
    """
    counts: Dict[str, Dict[str, int]] = {}
    for c in chars:
        if not c.items:
            continue
        try:
            inv = json.loads(c.items)
        except Exception:
            continue
        if not isinstance(inv, list):
            continue
        for entry in inv:
            if isinstance(entry, str):
                slug, qty = entry, 1
            elif isinstance(entry, dict):
                slug = entry.get("slug")
                qty = _entry_qty(entry)
            else:
                continue
            if not slug or qty <= 0 or resolve_potion_effect(slug) is None:
                continue
            per_char = counts.setdefault(slug, {})
            per_char[str(c.id)] = per_char.get(str(c.id), 0) + qty
    return counts


def _party_item_payload(chars) -> Dict[str, Any]:
    """``item_counts`` plus the display metadata (kind, name) the combat UI
    needs to group and label potions -- built together so the two can never
    disagree about which slugs are recognised.

    _item_counts_by_character already calls resolve_potion_effect(slug) to
    decide what counts, so the kind is known at the exact moment the map is
    built. Nothing downstream should have to re-derive it: item_effects.py's
    own contract is that adding a family is one table entry, no other file
    needs to change -- the combat UI matching a potion's *name* against a
    regex to guess its kind (an earlier version of this panel) had quietly
    become that second file.

    ``item_counts`` keeps its original flat shape ({slug: {char_id: count}})
    unchanged -- tests/test_potions_per_character.py asserts that shape
    directly -- so item_meta is a sibling map, not a nested addition.

    A slug can be counted here (resolve_potion_effect recognises it) with no
    matching Item catalogue row: bag_payload (inventory_api._serialize_item)
    silently drops those, since _item_counts_by_character is a pure slug
    parse with no catalogue lookup of its own. item_meta's name falls back
    to the slug itself for exactly that case, rather than the client finding
    out the hard way.
    """
    counts = _item_counts_by_character(chars)
    names: Dict[str, str] = {}
    if counts:
        try:
            names = {i.slug: i.name for i in Item.query.filter(Item.slug.in_(counts)).all()}
        except Exception:
            names = {}
    return {
        "item_counts": counts,
        "item_meta": {
            slug: {"kind": resolve_potion_effect(slug)["kind"], "name": names.get(slug, slug)} for slug in counts
        },
    }


def _spell_power(caster: Dict[str, Any]) -> float:
    """Magical counterpart to a weapon user's ``attack`` stat.

    ``attack`` is 8 + STR/2 + level + gear, so a fighter's output grows with
    every level. Spells and skills previously scaled with INT alone (or, for
    skills, with nothing at all), which is why a level-20 firebolt hit for the
    same ~17 as a level-1 one while a plain attack had doubled to ~32. Both
    inputs are folded in here so every offensive action grows together.
    """
    int_stat = int(caster.get("int_stat", caster.get("attack", 10)) or 10)
    level = int(caster.get("level", 1) or 1)
    return int_stat * 0.6 + level


def _pick_monster_target(members: List[Dict[str, Any]], rng=None) -> tuple[int, Optional[Dict[str, Any]]]:
    """Choose which party member a monster swings at.

    Returns (index, member) or (0, None) when everyone is down.

    Weighted random among the living, biased toward the wounded rather than
    locked onto them. The old behaviour sorted by HP and always hit the lowest,
    so every monster in the dungeon focused the same character until they
    dropped -- from the player's seat it looks like only one party member is
    ever in danger, and the other three are spectators.
    """
    rng = rng or random
    alive = [(i, m) for i, m in enumerate(members) if m.get("hp", 0) > 0]
    if not alive:
        return 0, None
    weights = []
    for _, m in alive:
        hp = max(0, int(m.get("hp", 0)))
        max_hp = max(1, int(m.get("max_hp", hp) or hp or 1))
        # 1.0 at full health, up to 2.0 at death's door.
        weights.append(1.0 + (1.0 - min(1.0, hp / max_hp)))
    pivot = rng.random() * sum(weights)
    acc = 0.0
    for (idx, member), w in zip(alive, weights):
        acc += w
        if pivot <= acc:
            return idx, member
    return alive[-1]


def _skip_if_unconscious(session: CombatSession, party: Dict[str, Any], char_id: int) -> Optional[Dict[str, Any]]:
    """Apply start-of-turn effects (e.g. poison) to the acting character, then
    if they're downed (hp<=0), log it, skip their turn, and return the
    response dict the caller should return immediately.

    Returns None if the actor is conscious and the caller should proceed
    with its normal action handling.
    """
    actor_ref = _player_ref(party, char_id)
    if actor_ref:
        effect_logs = apply_start_of_turn(actor_ref)
        if effect_logs:
            for line in effect_logs:
                _append_log(session, line)
        session.party_snapshot_json = json.dumps(party)
    if actor_ref and actor_ref.get("hp", 0) <= 0:
        _append_log(session, f"{actor_ref.get('name', 'Character')} is unconscious and cannot act!")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "skipped": True}
    return None


def _is_monster_turn(session: CombatSession) -> bool:
    """Whether a monster is acting. Which one is _active_monster's job."""
    actor = _active_actor(session)
    return bool(actor) and actor.get("type") == "monster"


def _downed_player_ids(session: CombatSession) -> set:
    """Character ids in this session currently at 0 HP."""
    try:
        party = json.loads(session.party_snapshot_json or "{}") or {}
    except Exception:
        return set()
    return {
        m.get("char_id") or m.get("id")
        for m in party.get("members", [])
        if int(m.get("hp", 0) or 0) <= 0 and (m.get("char_id") or m.get("id")) is not None
    }


def _advance_turn(session: CombatSession):
    """Advance to next initiative entry and reset phase to 'start'."""
    initiative = json.loads(session.initiative_json or "[]")
    if not initiative:
        return
    session.active_index += 1
    if session.active_index >= len(initiative):
        session.active_index = 0
        session.combat_turn += 1

    # Step over combatants who cannot act instead of stopping on them.
    #
    # Downed party members: each action handler already refuses to act while
    # unconscious, but landing on a downed character still made their turn the
    # *active* turn -- the client offered their buttons and the player had to
    # spend a click to burn it, which reads as "dead characters still take
    # turns".
    #
    # Dead monsters: corpses are tombstoned in the initiative list rather than
    # removed, because active_index is persisted, echoed to the client and used
    # as the turn-ownership key on three server paths -- filtering the list
    # would silently change what a stale index means. So the same loop has to
    # skip them, or the engine stops on a corpse's turn and nobody can drive it.
    #
    # Bounded by the initiative length: "at most one lap". If every entry is
    # skippable it exits on an arbitrary index and _check_end resolves the
    # encounter -- which is why this must not become a `while True`.
    downed = _downed_player_ids(session)
    dead = _dead_monster_ids(session)
    for _ in range(len(initiative)):
        actor = initiative[session.active_index]
        kind = actor.get("type")
        aid = actor.get("id")
        if kind == "player" and aid in downed:
            pass
        elif kind == "monster" and (0 if aid is None else aid) in dead:
            pass
        else:
            break
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
        logger.debug("suppressed_exception", where="_advance_turn", exc_info=True)
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
        logger.debug("suppressed_exception", where="_advance_turn", exc_info=True)


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
            logger.debug("suppressed_exception", where="_progress_phase", exc_info=True)
    elif session.phase == "action":
        session.phase = "end"
    elif session.phase == "end":
        _advance_turn(session)
        return True
    session.version += 1
    return False


def _check_end(session: CombatSession):
    # A completed session is never re-resolved. Neither end_turn endpoint
    # refuses one, and after a win active_index has already stepped onto a
    # player of the same user -- so a second end_turn used to re-enter here with
    # the monster still at 0 HP and roll and grant the loot a second time. This
    # guard also stops the pack path below re-rolling once per surviving check.
    if session.status != "active":
        return
    # Monster defeat path: every monster down, not just the first. `monsters and`
    # matters -- an empty list must never read as "all dead".
    monsters = _monsters(session)
    if monsters and all(int(m.get("hp", 0) or 0) <= 0 for m in monsters):
        monster = monsters[0]
        rewards = _merge_rewards(roll_loot(m) or {} for m in monsters)
        session.status = "complete"
        loot_text = _loot_summary(rewards)
        _append_log(session, f"{_describe_pack(monsters)} defeated! Loot: {loot_text}", code=COMBAT_COMPLETE)

        # Track boss kills and progress
        try:
            from app.models.dungeon_instance import DungeonInstance
            from app.services import boss_abilities

            instance_snapshot = json.loads(getattr(session, "dungeon_snapshot_json", None) or "{}") or {}
            instance_id = instance_snapshot.get("instance_id")

            if instance_id and monster:
                instance = db.session.get(DungeonInstance, instance_id)
                if instance:
                    # Every corpse counts, not just the first.
                    killed_a_boss = False
                    for dead_monster in monsters:
                        archetype = dead_monster.get("archetype", "")

                        if boss_abilities.is_boss(dead_monster):
                            killed_a_boss = True
                            instance.bosses_defeated += 1
                            _append_log(session, f"Boss defeated! ({instance.bosses_defeated}/{instance.bosses_total})")
                        elif archetype == "Elite":
                            instance.elites_defeated += 1
                            try:
                                from app.services import quest_progress_service

                                quest_progress_service.record_kill(session.user_id, is_elite=True)
                            except Exception:
                                logger.debug("suppressed_exception", where="_check_end", exc_info=True)
                        else:
                            instance.monsters_defeated += 1
                            try:
                                from app.services import quest_progress_service

                                quest_progress_service.record_kill(session.user_id, is_elite=False)
                            except Exception:
                                logger.debug("suppressed_exception", where="_check_end", exc_info=True)

                    # Outside the loop deliberately: a pack holding two bosses
                    # would otherwise announce the unlock once per boss. Still
                    # gated on a boss having died this encounter -- unguarded,
                    # an instance with bosses_total 0 satisfies 0 >= 0 and every
                    # ordinary kill would unlock extraction.
                    if killed_a_boss and instance.bosses_defeated >= instance.bosses_total:
                        instance.extraction_available = True
                        _append_log(session, "🎉 All bosses defeated! Extraction portal is now available!")

                    db.session.add(instance)
        except Exception as e:
            # Log but don't fail combat completion
            logger.warning("boss_kill_tracking_failed", error=str(e))

        try:
            party = json.loads(session.party_snapshot_json or "{}") or {}
            char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
            xp_total = sum(int(m.get("xp", 0) or 0) for m in monsters)
            members = party.get("members", [])
            share = int(xp_total / len(members)) if members else xp_total
            xp_map = {}

            from app.services import durability, progression

            for m in members:
                row = char_rows.get(m.get("char_id") or m.get("id"))
                if row:
                    # Unified progression: grant_xp uses the canonical XP table
                    # (app/models/xp.py) and applies level-ups + talent points.
                    progression.grant_xp(row, share)
                    # Gentle gear wear for survivors on a win (config-driven, no-op
                    # if durability disabled).
                    if m.get("hp", 0) > 0:
                        durability.degrade_gear(row)
                    db.session.add(row)
                    try:
                        xp_map[str(m.get("char_id") or m.get("id"))] = share
                    except Exception:
                        logger.debug("suppressed_exception", where="_check_end", exc_info=True)
            if (rewards.get("items") or rewards.get("items_list")) and char_rows:
                first = next(iter(char_rows.values()))
                inv_items: list = []
                if first.items:
                    try:
                        inv_items = json.loads(first.items)
                        if not isinstance(inv_items, list):
                            inv_items = []
                    except Exception:
                        inv_items = []
                # Every append goes through _grant_slug_to_inventory, which
                # matches the shape the bag is already in. These three loops
                # used to append bare strings unconditionally, so a reward
                # dropped into a canonical bag (any character who has ever
                # equipped or consumed anything) was visible to combat's own
                # parser and invisible to load_inventory: in the item panel and
                # drinkable mid-fight, absent from the bag grid and the
                # dashboard, and destroyed by the next load/dump round-trip.
                # Exactly one of these branches may run. roll_loot returns the
                # same drops twice -- `items` as a quantity map and `items_list`
                # as a flat mirror "for legacy compatibility"
                # (loot_service.py:182) -- and this used to read both, in two
                # independent `if`s, so every real combat drop was granted
                # twice: one potion landed at qty 2, two at qty 4. The outer
                # guard also required `items`, so `items_list` could never
                # actually serve as the fallback it exists to be; it was
                # reachable only as a duplicate.
                if isinstance(rewards.get("items"), dict):
                    for slug, qty in rewards.get("items", {}).items():
                        try:
                            q = int(qty)
                        except Exception:
                            q = 1
                        _grant_slug_to_inventory(inv_items, slug, max(1, q))
                elif isinstance(rewards.get("items"), list):
                    for slug in rewards.get("items", []):
                        _grant_slug_to_inventory(inv_items, slug)
                elif isinstance(rewards.get("items_list"), list):
                    for slug in rewards.get("items_list"):
                        _grant_slug_to_inventory(inv_items, slug)
                first.items = json.dumps(inv_items)
                db.session.add(first)
            if rewards.get("gear"):
                try:
                    from app.services.loot_service import add_gear_to_character

                    first = next(iter(char_rows.values()))
                    add_gear_to_character(first, rewards["gear"])
                    db.session.add(first)
                except Exception:
                    logger.debug("suppressed_exception", where="_check_end", exc_info=True)
            try:
                rewards["xp"] = {"total": xp_total, "per_member": xp_map}
            except Exception:
                logger.debug("suppressed_exception", where="_check_end", exc_info=True)
        except Exception as e:
            # This rollback also discards the kill-tracking increments above, so
            # never let it fail silently.
            logger.warning("combat_reward_grant_failed", error=str(e), exc_info=True)
            db.session.rollback()
        session.rewards_json = json.dumps(rewards)
        try:
            party = json.loads(session.party_snapshot_json or "{}") or {}
            if rewards.get("items") or rewards.get("items_list"):
                # Recompute per-character (not just whichever character happened to
                # receive the loot) — each character's potions are their own. Same
                # party scope _base_player_snapshot used at session start (up to 4
                # characters), not every character this user owns.
                reward_chars = _party_characters(session.user_id)
                party.update(_party_item_payload(reward_chars))
                session.party_snapshot_json = json.dumps(party)
        except Exception:
            logger.debug("suppressed_exception", where="_check_end", exc_info=True)
        sync_member_death_states(session)
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
        resolve_party_defeat_if_any(session)
        _persist_party_resources(session)
        set_combat_state(False)


def _current_instance_for_user(user_id: int):
    """Resolve the dungeon instance the user is actually in.

    Prefers session['dungeon_instance_id'] — the canonical "current instance"
    pointer every dungeon route (dungeon_api.py) reads/writes — over guessing
    via "most recent DungeonInstance row for this user." A user can accumulate
    multiple instance rows (e.g. an older, abandoned run), so "most recent by
    id" can diverge from where they actually are. Falls back to the most
    recent row when there's no request context or no session value (e.g.
    direct service-level calls outside an HTTP request).
    """
    try:
        from flask import session as _session

        inst_id = _session.get("dungeon_instance_id")
        if inst_id:
            instance = db.session.get(DungeonInstance, inst_id)
            if instance is not None and instance.user_id == user_id:
                return instance
    except RuntimeError:
        logger.debug("suppressed_exception", where="_current_instance_for_user", exc_info=True)
    return DungeonInstance.query.filter_by(user_id=user_id).order_by(DungeonInstance.id.desc()).first()


def sync_member_death_states(session) -> None:
    """Persist per-member downed state to Character rows after a resolution.

    Any member at hp<=0 becomes is_dead + locked to the current instance (downed,
    recoverable). Does NOT set permadeath here — that is decided at extraction or
    on a wipe.
    """
    party = json.loads(session.party_snapshot_json or "{}") or {}
    members = party.get("members", [])
    if not members:
        return
    instance = _current_instance_for_user(session.user_id)
    char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
    changed = False
    for m in members:
        cid = m.get("char_id") or m.get("id")
        char = char_rows.get(cid)
        if not char:
            continue
        if m.get("hp", 0) <= 0 and not char.is_dead:
            if instance is not None:
                extraction_service.handle_character_death(char, instance)
            else:
                char.is_dead = True
                char.death_count = (char.death_count or 0) + 1
            changed = True
    if changed:
        db.session.commit()


def party_is_wiped(user_id: int) -> bool:
    """True if the user has a tracked current party and every member of it
    is dead. Used to stop dungeon movement/exploration after a full wipe —
    combat already marks each member is_dead=True via
    resolve_party_defeat_if_any, but nothing outside combat checked it."""
    from flask import session as _session

    party_ids = _session.get("last_party_ids") or []
    if not party_ids:
        return False
    chars = Character.query.filter(Character.id.in_(party_ids), Character.user_id == user_id).all()
    if not chars:
        return False
    return all(c.is_dead for c in chars)


def resolve_party_defeat_if_any(session) -> bool:
    """If every party member is at 0 HP, permadeath the run.

    Marks each member's Character dead + permadeath (a wipe loses the run: the haul
    is simply never pooled into the hoard, and whatever they carried in dies with
    them) and resets the dungeon: the instance is deleted and the session pointer
    cleared, so the player starts a fresh run once they have new characters.
    Returns True if a wipe occurred.
    """
    party = json.loads(session.party_snapshot_json or "{}") or {}
    members = party.get("members", [])
    alive = [m for m in members if m.get("hp", 0) > 0]
    if members and not alive:
        instance = _current_instance_for_user(session.user_id)
        char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
        for m in members:
            cid = m.get("char_id") or m.get("id")
            char = char_rows.get(cid)
            if not char:
                continue
            if instance is not None:
                extraction_service.handle_character_death(char, instance)
            else:
                char.is_dead = True
                char.death_count = (char.death_count or 0) + 1
            char.permadeath = True
            # The run is over and the instance is about to go: leave no lock
            # pointing at a dungeon that no longer exists.
            char.locked_in_dungeon = False
            char.locked_dungeon_id = None
        if instance is not None:
            db.session.delete(instance)
        db.session.commit()
        _clear_session_instance()
        return True
    return False


def _clear_session_instance():
    """Drop the current-instance pointer from the flask session, if there is one."""
    try:
        from flask import has_request_context
        from flask import session as _session

        if has_request_context():
            _session.pop("dungeon_instance_id", None)
    except Exception:
        logger.debug("suppressed_exception", where="_clear_session_instance", exc_info=True)


def _emit_session(event: str, session: CombatSession):  # safe emit wrapper
    try:
        socketio.emit(event, session.to_dict(), namespace="/adventure")
    except Exception:
        logger.debug("suppressed_exception", where="_emit_session", exc_info=True)


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
            logger.debug("suppressed_exception", where="_emit_if_completed", exc_info=True)


def _persist_party_resources(session: CombatSession):
    """Persist surviving party HP and mana back into Character.stats JSON,
    and write back any remaining poison effects to CharacterStatusEffect.

    Assumptions / Simplifications:
    - Character.stats JSON contains (or can accept) 'hp' and 'mana' keys representing current values.
    - We do not yet track max_hp/mana persistently outside stats snapshot; we only update current.
    - Dead characters (hp <= 0) persist with hp=0 and do not get their effects written back
      (a dead character's status effects are moot -- unrelated death/revival handling applies).
    - Silently ignores any character ids not found (e.g., temporary generated hero placeholder).
    """
    try:
        if not session.party_snapshot_json:
            return
        import json as _json

        from app.models import CharacterStatusEffect

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
                logger.debug("suppressed_exception", where="_persist_party_resources", exc_info=True)
            try:
                stats_obj["current_mana"] = int(m.get("mana", stats_obj.get("current_mana", stats_obj.get("mana", 0))))
            except Exception:
                logger.debug("suppressed_exception", where="_persist_party_resources", exc_info=True)
            row.stats = _json.dumps(stats_obj)
            db.session.add(row)
            changed = True

            # Write back remaining poison/regen_buff -- delete-then-recreate is
            # simplest and avoids diffing old vs new rows. Dead characters
            # (hp<=0) don't get effects written back.
            try:
                PERSISTED_EFFECT_NAMES = ("poison", "regen_buff")
                CharacterStatusEffect.query.filter(
                    CharacterStatusEffect.character_id == cid,
                    CharacterStatusEffect.name.in_(PERSISTED_EFFECT_NAMES),
                ).delete(synchronize_session=False)
                if int(m.get("hp", 0)) > 0:
                    for eff in m.get("effects", []) or []:
                        if eff.get("name") in PERSISTED_EFFECT_NAMES and int(eff.get("remaining", 0)) > 0:
                            db.session.add(
                                CharacterStatusEffect(
                                    character_id=cid,
                                    name=eff["name"],
                                    remaining=int(eff["remaining"]),
                                    data=_json.dumps(eff.get("data", {})),
                                )
                            )
            except Exception:
                logger.debug("suppressed_exception", where="_persist_party_resources", exc_info=True)
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        logger.debug("suppressed_exception", where="_persist_party_resources", exc_info=True)


def player_attack(
    combat_id: int, user_id: int, version: int, actor_id: Optional[int] = None, target_id: Optional[int] = None
) -> Dict[str, Any]:
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
    skip_result = _skip_if_unconscious(session, party, actor_id)
    if skip_result is not None:
        return skip_result
    attacker = _player_ref(party, actor_id)
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
    attacker_name = attacker.get("name", "Player") if attacker else "Player"
    if not hit:
        _append_log(session, f"{attacker_name} misses {monster.get('name')} (roll {acc_roll})", code=PLAYER_ATTACK_MISS)
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
    # A natural 20 always crits; gear crit adds a percentage chance on top.
    # Before this, `crit` was purely the nat-20 and every point of crit an
    # affix granted did nothing at all.
    _crit_bonus = int((attacker or {}).get("crit_bonus", 0) or 0)
    # Short-circuit deliberately: with no crit gear this consumes no random
    # draw at all, so it cannot shift any other roll in the turn. A dozen tests
    # feed a finite iter([...]) to random.randint and depend on the exact
    # sequence -- an unconditional roll here made three of them StopIteration.
    crit = acc_roll == 20 or (_crit_bonus > 0 and random.randint(1, 100) <= _crit_bonus)
    if crit:
        dmg = int(dmg * 1.5)
    hit = _damage_monster(session, dmg, target_id)
    monster = hit or monster
    # Lifesteal returns a percentage of damage dealt, capped by the attacker's
    # own max HP. Also previously rolled, named ("Vampiric"), and inert.
    _steal = int((attacker or {}).get("lifesteal", 0) or 0)
    if attacker and _steal > 0 and dmg > 0:
        healed = max(1, int(dmg * _steal / 100.0))
        before = int(attacker.get("hp", 0) or 0)
        attacker["hp"] = min(int(attacker.get("max_hp", before) or before), before + healed)
        gained = attacker["hp"] - before
        if gained > 0:
            _append_log(session, f"{attacker_name} drains {gained} health.")
    _append_log(
        session,
        f"{attacker_name} hits {monster.get('name')} for {dmg}{' (CRIT)' if crit else ''} damage "
        f"(HP {monster.get('hp', 0)})",
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
    party = json.loads(session.party_snapshot_json or "{}") or {}
    skip_result = _skip_if_unconscious(session, party, actor.get("id"))
    if skip_result is not None:
        return skip_result
    fleeing = _player_ref(party, actor.get("id"))
    fleeing_name = fleeing.get("name", "Player") if fleeing else "Player"
    success = random.random() < 0.5
    if success:
        session.status = "complete"
        _append_log(session, f"{fleeing_name} flees successfully.", code=PLAYER_FLEE_SUCCESS)
        _persist_party_resources(session)
        set_combat_state(False)
    else:
        _append_log(session, f"{fleeing_name}'s flee attempt failed.", code=PLAYER_FLEE_FAIL)
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
    # Whichever monster holds this initiative slot -- not monsters[0]. `acting`
    # is an element of `monsters`, so mutating it and calling _save_monsters
    # persists; that is why the list is fetched once here rather than per write.
    monsters = _monsters(session)
    _actor = _active_actor(session)
    acting = _monster_ref(monsters, _actor.get("id")) if _actor else None
    if acting is None:
        # The initiative slot names a monster this session no longer has.
        # Advance rather than stall, or nobody can drive the turn.
        _advance_turn(session)
        db.session.commit()
        _emit_session("combat_update", session)
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
            monster_preview = acting
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
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
    members = party.get("members", [])
    if not members:
        # No viable targets; log an explicit wait so client sees monster acted
        try:
            monster_preview = acting
            _append_log(
                session, f"{monster_preview.get('name','Monster')} waits (no targets).", code=MONSTER_NO_TARGET_WAIT
            )
            db.session.commit()
            _emit_session("combat_update", session)
        except Exception:
            logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
        return
    # Ensure effects list presence for each member to simplify later additions
    for m in members:
        m.setdefault("effects", [])
    _default_idx, _default_target = _pick_monster_target(members)
    target = _default_target if _default_target is not None else members[0]
    monster = acting
    # Start-of-turn effects for monster (e.g., poison on monster)
    monster.setdefault("effects", [])
    start_logs = []
    try:
        start_logs.extend(apply_start_of_turn(monster))
    except Exception:
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
    for msg in start_logs:
        _append_log(session, msg)
    # If monster died to DoT before acting
    if int(monster.get("hp", 0) or 0) <= 0:
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
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
    for msg in veto_logs:
        _append_log(session, msg)
    if not can_act_flag:
        # If no specific veto logs were produced, add a generic waits/inactive line for clarity
        if not veto_logs:
            try:
                _append_log(session, f"{monster.get('name')} waits (incapacitated).", code=MONSTER_INCAPACITATED_WAIT)
            except Exception:
                logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)

    # If boss uses ability, execute it
    if boss_action:
        try:
            from app.services import boss_abilities

            if boss_action.get("type") == "boss_aoe":
                logs, party = boss_abilities.execute_boss_aoe(monster, party, session)
                for log in logs:
                    _append_log(session, log)
                session.party_snapshot_json = json.dumps(party)
                _save_monsters(session, monsters)
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
                _save_monsters(session, monsters)
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
                _save_monsters(session, monsters)
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
                _save_monsters(session, monsters)
                _advance_turn(session)
                _check_end(session)
                db.session.commit()
                _emit_session("combat_update", session)
                _emit_if_completed(session)
                return
        except Exception:
            logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)  # Fall through to normal AI

    # AI delegation (still only basic attack). If monster has flag ai_enabled use selector.
    action = {"type": "attack", "target_index": _default_idx}
    try:
        if monster.get("ai_enabled"):
            action = select_action(monster, party, {"turn": session.combat_turn}) or action
    except Exception:
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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
                    logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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

        # Weighted toward the wounded, but not locked onto them -- see
        # _pick_monster_target for why focusing the lowest HP every turn made
        # combat feel like a one-character fight.
        idx, target = _pick_monster_target(members)
        if target is None:
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
                acting["last_turn"] = session.combat_turn
                _save_monsters(session, monsters)
            except Exception:
                logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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
                acting["last_turn"] = session.combat_turn
                _save_monsters(session, monsters)
            except Exception:
                logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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
        acting["last_turn"] = session.combat_turn
        _save_monsters(session, monsters)
    except Exception:
        logger.debug("suppressed_exception", where="monster_auto_turn", exc_info=True)
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
    skip_result = _skip_if_unconscious(session, party, actor_id)
    if skip_result is not None:
        return skip_result
    defender_name = "Player"
    for m in party.get("members", []):
        if m.get("char_id") == actor_id:
            m["defending"] = True
            defender_name = m.get("name", "Player")
            break
    session.party_snapshot_json = json.dumps(party)
    _append_log(session, f"{defender_name} braces for impact (Defend).", code=PLAYER_DEFEND)
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
    """Consume / apply a combat item (healing potion, mana potion, regen potion, ...) for actor.

    The slug is resolved through item_effects.resolve_potion_effect -- the one
    place a slug becomes an effect -- before anything else happens. Ownership
    of the item is verified against the acting character's own inventory
    *before* the effect is applied, and the item is only removed *after* the
    effect has actually been applied: a potion is never consumed unless an
    effect was applied, and no effect is applied unless the acting character
    genuinely holds it (checking client-side only let an empty bag heal
    repeatably). Advances turn whether or not monster defeated on heal (heals
    cannot end combat). A refusal (no_effect / not_carried / cannot_use)
    leaves the item, the party snapshot, and the turn untouched.
    """
    session = _load_session(combat_id)
    if not session:
        return {"error": "not_found"}
    if session.status != "active":
        return {"error": "inactive", "state": session.to_dict()}
    if session.version != version:
        return {"error": "version_conflict", "message": _REFUSAL_VERSION_CONFLICT, "state": session.to_dict()}
    initiative = json.loads(session.initiative_json or "[]")
    actor = initiative[session.active_index]
    if actor["type"] != "player":
        return {"error": "not_your_turn", "message": _REFUSAL_NOT_YOUR_TURN, "state": session.to_dict()}
    if actor_id is None:
        actor_id = actor.get("id")
    if actor.get("controller_id") != user_id:
        return {"error": "not_your_turn", "message": _REFUSAL_NOT_YOUR_TURN, "state": session.to_dict()}
    if actor.get("id") != actor_id:
        # Allow stale actor id (client cached) by rebinding to current initiative actor
        actor_id = actor.get("id")
    if not slug:
        return {"error": "item_required", "message": _REFUSAL_ITEM_REQUIRED}
    party = json.loads(session.party_snapshot_json or "{}") or {}
    skip_result = _skip_if_unconscious(session, party, actor_id)
    if skip_result is not None:
        return skip_result

    # 1. Resolve the effect from the slug before touching any state at all.
    effect = resolve_potion_effect(slug)
    if effect is None:
        return {"error": "no_effect", "message": REFUSAL_NO_EFFECT}

    member = _player_ref(party, actor_id)
    if member is None:
        # Actor isn't part of this session's party snapshot -- nothing to
        # apply an effect to. Distinct from "not carried"; shouldn't happen
        # via the real callers, all of which derive actor_id from initiative.
        return {"error": "cannot_use", "message": _REFUSAL_CANNOT_USE}

    # 2. Ownership: ONLY the acting character's own bag counts, checked
    # before the effect is applied -- this is the gate that was missing.
    char_row = db.session.get(Character, actor_id)
    if not _character_holds_slug(char_row, slug):
        return {"error": "not_carried", "message": _REFUSAL_NOT_CARRIED}

    # 3. Apply the descriptor to the party-snapshot member. `or <fallback>`,
    # not `.get(key, <fallback>)`: a present-but-falsy (0/None) cap must not
    # win over the fallback either, or a snapshot member missing its cap
    # clamps healing down to 0 -- a healing potion that kills. Unreachable
    # today (_derive_stats and the no-characters fallback below both always
    # set these), but the clamp itself must not depend on that holding.
    # Fallbacks match the synthetic "no characters" member's own values.
    kind = effect.get("kind")
    if kind == "restore_hp":
        max_hp = member.get("max_hp") or 100
        member["hp"] = min(max_hp, member.get("hp", 0) + effect.get("amount", 0))
    elif kind == "restore_mp":
        mana_max = member.get("mana_max") or 30
        member["mana"] = min(mana_max, member.get("mana", 0) + effect.get("amount", 0))
    elif kind == "status":
        member["effects"] = replace_effect(
            member.get("effects", []) or [], effect["name"], effect["ticks"], **effect.get("data", {})
        )
    else:
        # The resolver's contract only emits the three kinds above; an
        # unrecognised kind is a resolver/combat mismatch, not a player
        # mistake. Refuse rather than silently doing nothing while still
        # spending the potion and the turn.
        return {"error": "no_effect", "message": REFUSAL_NO_EFFECT}

    # 4. Only now decrement inventory -- and stop swallowing failure. Having
    # just verified ownership against the same row, this should never miss;
    # if it does, that's a real bug (e.g. a lost race), not something to log
    # at debug and move on from while the effect above has already applied.
    if not _decrement_character_slug(char_row, slug):
        logger.error(
            "potion_decrement_failed_after_effect_applied",
            char_id=actor_id,
            slug=slug,
            combat_id=combat_id,
        )
        return {"error": "item_removal_failed", "message": REFUSAL_ITEM_REMOVAL_FAILED}
    db.session.add(char_row)

    # item_counts/item_meta are rebuilt from the acting character's party
    # roster (same scope _base_player_snapshot/_check_end use -- up to 4
    # characters, not every character this user owns) so it can never drift
    # from what the party actually carries now that the inventory just
    # changed. Guarded like the other three item_counts call sites: the
    # effect and the decrement have already succeeded and nothing has been
    # persisted yet, so a failure here should leave item_counts stale rather
    # than turn an otherwise-successful item use into a 500.
    try:
        party.update(_party_item_payload(_party_characters(user_id)))
    except Exception as e:
        logger.warning("item_counts_recompute_failed", char_id=actor_id, slug=slug, exc_info=e)

    session.party_snapshot_json = json.dumps(party)
    user_name = member.get("name", "Player")
    # The catalogue name, never the raw slug: before the tiered catalogue only
    # two legacy hyphenated slugs could reach this line, and now forty
    # underscore-and-tier machine strings can, which made "Hero uses
    # potion_heal_l4." ordinary play. _item_display_name is the same lookup
    # (and the same title-cased fallback for a slug with no catalogue row) that
    # _loot_summary uses two lines up the very same log.
    _append_log(session, f"{user_name} drinks {_item_display_name(slug)}.", code=PLAYER_USE_ITEM)
    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    _emit_if_completed(session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "item_used": slug}


def player_cast_spell(
    combat_id: int,
    user_id: int,
    version: int,
    spell: str,
    actor_id: Optional[int] = None,
    target_id: Optional[int] = None,
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
    skip_result = _skip_if_unconscious(session, party, actor_id)
    if skip_result is not None:
        return skip_result
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
    # Persist the spend immediately. The fizzle and miss paths below commit and
    # return without re-serialising the party, so the deduction -- which only
    # mutates the in-memory dict -- used to be discarded: a spell that missed
    # was free, and casting looked like it cost no mana at all.
    session.party_snapshot_json = json.dumps(party)
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
    dmg = int(roll + _spell_power(caster))
    if crit:
        dmg = int(dmg * 1.5)
    # Apply monster resistances if any
    resistances = session.monster().get("resistances", {}) or {}
    try:
        dmg = int(apply_resistances(dmg, [config["element"]], resistances))
    except Exception:
        logger.debug("suppressed_exception", where="player_cast_spell", exc_info=True)
    hit = _damage_monster(session, dmg, target_id)
    session.party_snapshot_json = json.dumps(party)
    # Track damage for visual effects
    session.last_damage_json = json.dumps({"to_monster": {"amount": dmg, "is_miss": False, "is_critical": crit}})
    caster_name = caster.get("name", "Player")
    _append_log(
        session,
        f"{caster_name} casts {config['name']} for {dmg}{' (CRIT)' if crit else ''} damage "
        f"(HP {(hit or {}).get('hp', session.monster_hp)})",
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


def player_cast_skill(
    combat_id: int,
    user_id: int,
    version: int,
    skill_id: int,
    actor_id: Optional[int] = None,
    target_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Use an unlocked *active* skill in combat.

    Applies the skill's effect_json: 'damage'/'spell_damage' -> monster, 'heal' ->
    caster (capped at max_hp). Respects turn order, version, cooldown, and ownership.
    Skills auto-hit (no accuracy roll) to keep them distinct from weapon/spell attacks.
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

    party = json.loads(session.party_snapshot_json or "{}") or {}
    skip_result = _skip_if_unconscious(session, party, actor_id)
    if skip_result is not None:
        return skip_result

    from app.models.skill import CharacterSkill, Skill

    cs = CharacterSkill.query.filter_by(character_id=actor_id, skill_id=skill_id).first()
    if not cs:
        return {"error": "skill_not_unlocked"}
    skill = db.session.get(Skill, skill_id)
    if not skill or skill.skill_type != "active":
        return {"error": "not_active_skill"}
    # Cooldown (seconds) parallels skill_api.use_skill.
    if cs.last_used and skill.cooldown:
        elapsed = (_now() - cs.last_used).total_seconds()
        if elapsed < skill.cooldown:
            return {"error": "on_cooldown", "remaining_seconds": int(skill.cooldown - elapsed)}

    try:
        eff = json.loads(skill.effect_json or "{}")
    except Exception:
        eff = {}
    if not isinstance(eff, dict):
        eff = {}

    caster = _player_ref(party, actor_id)
    if not caster:
        return {"error": "no_caster"}

    # Mana cost (parallels skill_api / spell casting). Reject before applying
    # effects if the caster can't afford it; deduct otherwise.
    mana_cost = int(skill.mana_cost or 0)
    mana_available = caster.get("mana") if "mana" in caster else caster.get("current_mana", 0)
    if mana_cost > 0 and mana_available < mana_cost:
        return {"error": "not_enough_mana", "mana": mana_available, "required": mana_cost}

    # effect_json carries a flat base (5..22 in seed_skills). On its own that
    # never scaled with anything, so a tier-3 skill costing mana and a cooldown
    # was worth less than a free swing from level ~5 onward. The base now rides
    # on top of the caster's power, keyed to the effect's own flavour:
    # spell_damage scales with _spell_power, damage with the weapon `attack`
    # stat -- so a skill is always worth more than the basic attack it replaces.
    phys_base = int(eff.get("damage", 0) or 0)
    magic_base = int(eff.get("spell_damage", 0) or 0)
    heal = int(eff.get("heal", 0) or 0)
    dmg = 0
    if phys_base > 0:
        dmg += phys_base + int(caster.get("attack", 10) or 10)
    if magic_base > 0:
        dmg += magic_base + int(_spell_power(caster))
    if dmg <= 0 and heal <= 0:
        return {"error": "no_effect"}

    mana_suffix = f" (-{mana_cost} mana)" if mana_cost > 0 else ""
    extra: Dict[str, Any] = {}
    if dmg > 0:
        hit = _damage_monster(session, dmg, target_id)
        session.last_damage_json = json.dumps({"to_monster": {"amount": dmg, "is_miss": False, "is_critical": False}})
        _append_log(
            session,
            f"{caster.get('name', 'Player')} uses {skill.name} for {dmg} damage "
            f"(HP {(hit or {}).get('hp', session.monster_hp)}){mana_suffix}",
            code=PLAYER_SKILL,
        )
        extra["damage"] = dmg
    if heal > 0:
        # Same reasoning as damage: a flat heal stops mattering as max HP grows.
        heal += int(_spell_power(caster) * 0.5)
        cur_hp = int(caster.get("hp", 0))
        max_hp = int(caster.get("max_hp", cur_hp))
        new_hp = min(max_hp, cur_hp + heal)
        healed = new_hp - cur_hp
        caster["hp"] = new_hp
        _append_log(
            session,
            f"{caster.get('name', 'Player')} uses {skill.name}, healing {healed} (HP {new_hp}){mana_suffix}",
            code=PLAYER_SKILL,
        )
        extra["heal"] = healed

    if mana_cost > 0:
        remaining_mana = mana_available - mana_cost
        # Normalize back into both keys for backward compatibility (matches spell casting).
        caster["mana"] = remaining_mana
        caster["current_mana"] = remaining_mana
        extra["mana"] = remaining_mana

    session.party_snapshot_json = json.dumps(party)
    cs.times_used = (cs.times_used or 0) + 1
    cs.last_used = _now()

    session.phase = "end"
    _progress_phase(session)
    _check_end(session)
    db.session.commit()
    _emit_session("combat_update", session)
    if session.status != "active":
        _emit_session("combat_end", session)
    session = _auto_progress_monster_after_player(session)
    return {"ok": True, "state": session.to_dict(), "skill": skill.name, **extra}


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
        # Loop, don't run one: with a pack, two monsters can hold adjacent
        # initiative slots, and running only the first leaves the client waiting
        # on a turn nobody drives. Bounded by the initiative length -- a monster
        # path that failed to advance would otherwise make this an infinite
        # HTTP request, which is worse than a stalled turn.
        try:
            rounds = len(json.loads(session.initiative_json or "[]")) or 1
        except Exception:
            rounds = 1
        for _ in range(rounds):
            if session.status != "active" or not _is_monster_turn(session):
                break
            monster_auto_turn(session)  # commits & emits internally
            refreshed = _load_session(session.id)
            if not refreshed:
                break
            session = refreshed
    except Exception:
        logger.debug("suppressed_exception", where="_auto_progress_monster_after_player", exc_info=True)
    return session
