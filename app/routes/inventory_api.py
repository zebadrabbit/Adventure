"""Inventory & Equipment API.

Endpoints for managing character inventory, equipping items, and consuming potions.
Uses existing Character JSON columns: `items` (bag list of slugs) and `gear` (JSON mapping slot->slug).
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.inventory.utils import (
    apply_encumbrance_penalty,
    dump_inventory,
    encumbrance_state,
    load_inventory,
    remove_one,
)
from app.models import CharacterStatusEffect
from app.models.models import Character, Item
from app.models.xp import xp_for_level
from app.services.progression import progression_config
from app.services.time_service import advance_for

bp_inventory = Blueprint("inventory", __name__)


# ----------------------- Helpers -----------------------

_SLOTS = (
    "head",
    "chest",
    "legs",
    "boots",
    "gloves",
    "weapon",
    "offhand",
    "ring1",
    "ring2",
    "amulet",
    # canonical 8-slot gear slots (procedural items)
    "hands",
    "feet",
    "ring",
)


def _safe_json_load(s: str, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def _safe_json_dump(obj) -> str:
    try:
        return json.dumps(obj)
    except Exception:
        return "[]" if isinstance(obj, list) else "{}"


def _char_owned(cid: int) -> Character | None:
    # Robust user id extraction to avoid DetachedInstance errors
    uid = None
    try:
        uid = getattr(current_user, "id", None)
    except Exception:
        uid = None
    if uid is None:
        sid = session.get("_user_id") or session.get("user_id")
        try:
            uid = int(sid) if sid is not None else None
        except Exception:
            uid = None
    ch = db.session.get(Character, cid)
    if not ch or uid is None or ch.user_id != uid:
        return None
    return ch


def _normalize_gear(gear_raw) -> dict:
    """Coerce legacy gear values into a mapping.

    Older saves may store gear as a JSON list (e.g., []). Our equipment system
    expects a dict mapping slot->slug. If a list or other non-dict is found,
    normalize to an empty dict.
    """
    return gear_raw if isinstance(gear_raw, dict) else {}


def _slot_for_item(item: Item, gear: dict) -> str | None:
    """Infer target slot for an item based on item.type and slug keywords.
    Returns a slot string or None if not equippable.
    """
    t = (item.type or "").lower()
    slug = (item.slug or "").lower()
    name = (item.name or "").lower()
    if t == "weapon":
        return "weapon"
    if t == "armor":
        if "shield" in slug or "shield" in name:
            return "offhand"
        if any(k in slug or k in name for k in ("helm", "helmet", "hood", "cap")):
            return "head"
        if any(k in slug or k in name for k in ("boots", "greaves")):
            return "boots"
        if any(k in slug or k in name for k in ("glove", "gauntlet")):
            return "gloves"
        if any(k in slug or k in name for k in ("legging", "pants", "trousers", "legs")):
            return "legs"
        return "chest"
    if t == "ring":
        # pick first free ring slot
        return "ring1" if not gear.get("ring1") else "ring2"
    if t in ("amulet", "necklace", "talisman"):
        return "amulet"
    # tools, potions, scrolls not equippable
    return None


def _item_effects(item: Item) -> dict:
    """Return stat deltas for equippable items (simple defaults)."""
    slug = (item.slug or "").lower()
    t = (item.type or "").lower()
    # Coarse defaults
    if t == "weapon":
        # Specific weapons
        if "bow" in slug:
            return {"dex": +1}
        if "staff" in slug:
            return {"int": +1}
        if "dagger" in slug:
            return {"dex": +1}
        return {"str": +1}
    if t == "armor":
        if "shield" in slug:
            return {"con": +1}
        if "leather" in slug:
            return {"con": +1}
        return {"con": +1}
    if t == "ring":
        return {"wis": +1}
    if t in ("amulet", "necklace", "talisman"):
        return {"cha": +1}
    return {}


def _apply_effects(stats: dict, effects: dict) -> dict:
    out = dict(stats)
    for k, v in effects.items():
        try:
            out[k] = int(out.get(k, 0)) + int(v)
        except Exception:
            pass
    return out


def _computed_stats(base_stats: dict, gear: dict, items_lookup: dict[str, Item]) -> dict:
    cur = dict(base_stats)
    for slot, slug in (gear or {}).items():
        if not slug or not isinstance(slug, str):
            # Procedural gear instances are stored as dicts, not slugs; their
            # affixes aren't folded into displayed computed stats (separate,
            # known gap), but they must not crash this lookup.
            continue
        it = items_lookup.get(slug)
        if it:
            cur = _apply_effects(cur, _item_effects(it))
    return cur


def _progression_fields(ch: Character) -> dict:
    """Stat points + XP thresholds for the progression UI (read-only, derived)."""
    mod = float(progression_config().get("xp_difficulty_mod", 1.0))
    level = ch.level or 1
    return {
        "stat_points": ch.stat_points or 0,
        "xp_for_current_level": xp_for_level(level, mod),
        "xp_for_next_level": xp_for_level(level + 1, mod),
    }


def _serialize_item(item: Item) -> dict:
    return {
        "slug": item.slug,
        "name": item.name,
        "type": item.type,
        "rarity": getattr(item, "rarity", "common"),
        "level": getattr(item, "level", 0),
        "description": item.description,
        "value_copper": item.value_copper,
        "weight": getattr(item, "weight", 1.0),
        "effects": _item_effects(item),
    }


def _gear_instances_from_items(raw_json: str | None) -> list[dict]:
    """Extract procedural gear instances (dicts with uid) from the raw items JSON.

    These are skipped by load_inventory (which only handles slug/qty dicts) but
    must be included in the bag payload so the UI can render and equip them.
    """
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("uid")]


def _serialize_gear_slot(slot_value, items_map: dict) -> dict | None:
    """Serialize a gear slot value — either a legacy slug string or a gear instance dict."""
    if isinstance(slot_value, dict) and slot_value.get("uid"):
        return slot_value  # already a serializable instance
    if isinstance(slot_value, str) and slot_value in items_map:
        return _serialize_item(items_map[slot_value])
    return None


# ----------------------- Endpoints -----------------------


@bp_inventory.route("/api/characters/state")
@login_required
def list_characters_state():
    """Return state for current user's characters including equipment and bag items.
    Shape: { characters: [ { id, name, stats: {base, computed}, gear: {slot: item|None}, bag: [item,..] } ] }
    """
    # Robust current user id
    uid = None
    try:
        uid = getattr(current_user, "id", None)
    except Exception:
        uid = None
    if uid is None:
        sid = session.get("_user_id") or session.get("user_id")
        try:
            uid = int(sid) if sid is not None else None
        except Exception:
            uid = None
    if uid is None:
        return jsonify({"error": "unauthorized"}), 401
    chars = Character.query.filter_by(user_id=uid).all()
    out = []
    # Preload all items used by these characters for efficient lookups
    slugs_needed = set()
    for ch in chars:
        inv_objs = load_inventory(ch.items)
        # gather slugs with multiplicity irrelevant for prefetch
        for obj in inv_objs:
            if "slug" in obj:
                slugs_needed.add(obj["slug"])
        gear = _normalize_gear(_safe_json_load(ch.gear, {}))
        slugs_needed.update([s for s in gear.values() if isinstance(s, str) and s])
    items_map = {it.slug: it for it in Item.query.filter(Item.slug.in_(slugs_needed)).all()} if slugs_needed else {}
    for ch in chars:
        try:
            base_stats = _safe_json_load(ch.stats, {})
            gear = _normalize_gear(_safe_json_load(ch.gear, {}))
            inv_objs = load_inventory(ch.items)
            gear_instances = _gear_instances_from_items(ch.items)
            # Compute encumbrance BEFORE penalty application (but penalty affects exposed computed base dex)
            str_score = int(base_stats.get("str", 10)) if isinstance(base_stats, dict) else 10
            enc_state = encumbrance_state(str_score, inv_objs)
            penalized_base = apply_encumbrance_penalty(base_stats, enc_state)
            computed = _computed_stats(penalized_base, gear, items_map)
            bag_payload = []
            for obj in inv_objs:
                slug = obj.get("slug")
                if not slug:
                    continue
                it = items_map.get(slug)
                if not it:
                    continue
                ser = _serialize_item(it)
                ser["qty"] = obj.get("qty", 1)
                bag_payload.append(ser)
            # Append procedural gear instances after legacy consumables
            bag_payload.extend(gear_instances)
            out.append(
                {
                    "id": ch.id,
                    "name": ch.name,
                    "level": ch.level,
                    "stats": {"base": penalized_base, "computed": computed},
                    "gear": {slot: _serialize_gear_slot(val, items_map) for slot, val in (gear or {}).items()},
                    "bag": bag_payload,
                    "encumbrance": enc_state,
                    **_progression_fields(ch),
                }
            )
            # Persist migrated format if legacy list was detected (length mismatch between slugs list and objects)
            try:
                # Detect if original was legacy by comparing raw JSON parse result type
                raw = _safe_json_load(ch.items, [])
                if raw and isinstance(raw, list) and (not raw or isinstance(raw[0], str)):
                    ch.items = dump_inventory(inv_objs)
                    db.session.flush()
            except Exception:
                pass
        except Exception:
            out.append(
                {
                    "id": ch.id,
                    "name": ch.name,
                    "level": getattr(ch, "level", 1),
                    "stats": {"base": {}, "computed": {}},
                    "gear": {},
                    "bag": [],
                    "warning": "character_state_unavailable",
                }
            )
    return jsonify({"characters": out, "slots": list(_SLOTS)})


@bp_inventory.route("/api/characters/<int:cid>", methods=["GET"])
@login_required
def get_character_state(cid: int):
    """Return state for a single character including equipment and bag items."""
    ch = _char_owned(cid)
    if not ch:
        return jsonify({"error": "not found"}), 404

    # Load inventory and gear
    inv_objs = load_inventory(ch.items)
    gear_instances = _gear_instances_from_items(ch.items)
    gear = _normalize_gear(_safe_json_load(ch.gear, {}))

    # Gather all slugs for item lookup (skip instance dicts in gear values)
    slugs_needed = set()
    for obj in inv_objs:
        if "slug" in obj:
            slugs_needed.add(obj["slug"])
    slugs_needed.update([s for s in gear.values() if isinstance(s, str) and s])

    items_map = {it.slug: it for it in Item.query.filter(Item.slug.in_(slugs_needed)).all()} if slugs_needed else {}

    # Load and compute stats
    base_stats = _safe_json_load(ch.stats, {})
    str_score = int(base_stats.get("str", 10)) if isinstance(base_stats, dict) else 10
    enc_state = encumbrance_state(str_score, inv_objs)
    penalized_base = apply_encumbrance_penalty(base_stats, enc_state)
    computed = _computed_stats(penalized_base, gear, items_map)

    # Build bag payload: legacy consumables first, then gear instances
    bag_payload = []
    for obj in inv_objs:
        slug = obj.get("slug")
        if not slug:
            continue
        it = items_map.get(slug)
        if not it:
            continue
        ser = _serialize_item(it)
        ser["qty"] = obj.get("qty", 1)
        bag_payload.append(ser)
    bag_payload.extend(gear_instances)

    # Build gear payload — handles both legacy slugs and instance dicts
    gear_payload = {slot: _serialize_gear_slot(val, items_map) for slot, val in (gear or {}).items()}

    return jsonify(
        {
            "id": ch.id,
            "name": ch.name,
            "level": ch.level,
            "xp": ch.xp or 0,
            "stats": {"base": penalized_base, "computed": computed},
            "gear": gear_payload,
            "bag": bag_payload,
            "encumbrance": enc_state,
            **_progression_fields(ch),
        }
    )


@bp_inventory.route("/api/characters/<int:cid>/equip", methods=["POST"])
@login_required
def equip_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}

    # --- Gear-instance path: uid-based equip for procedural items ---
    uid = (data.get("uid") or "").strip()
    if uid:
        from app.loot.data.archetypes import SLOTS as GEAR_SLOTS

        items_raw = json.loads(ch.items) if ch.items else []
        if not isinstance(items_raw, list):
            items_raw = []
        gear_raw = json.loads(ch.gear) if ch.gear else {}
        if not isinstance(gear_raw, dict):
            gear_raw = {}
        inst = next((i for i in items_raw if isinstance(i, dict) and i.get("uid") == uid), None)
        if not inst:
            return jsonify({"error": "not_in_inventory"}), 400
        slot = inst.get("slot")
        if slot not in GEAR_SLOTS:
            return jsonify({"error": "bad_slot"}), 400
        # Swap any currently-equipped item in that slot back into items
        if gear_raw.get(slot):
            items_raw.append(gear_raw[slot])
        gear_raw[slot] = inst
        items_raw = [i for i in items_raw if not (isinstance(i, dict) and i.get("uid") == uid)]
        ch.gear = json.dumps(gear_raw)
        ch.items = json.dumps(items_raw)
        db.session.commit()
        return jsonify({"ok": True, "slot": slot, "gear": gear_raw})

    # --- Legacy slug-based equip path ---
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify({"error": "missing slug"}), 400
    item = Item.query.filter_by(slug=slug).first()
    if not item:
        return jsonify({"error": "item not found"}), 404
    inv = load_inventory(ch.items)
    gear = _normalize_gear(_safe_json_load(ch.gear, {}))
    # Require at least one instance
    if not any(o["slug"] == slug for o in inv):
        return jsonify({"error": "item not in bag"}), 400
    slot = data.get("slot") or _slot_for_item(item, gear)
    if slot not in _SLOTS:
        return jsonify({"error": "invalid slot"}), 400
    # Enforce compatibility
    inferred = _slot_for_item(item, gear)
    if inferred and inferred != slot:
        slot = inferred  # prefer inferred slot
    if _slot_for_item(item, gear) is None:
        return jsonify({"error": "item not equippable"}), 400
    # Perform equip: remove from bag, move current slot (if any) back to bag
    removed = remove_one(inv, slug)
    if not removed:
        return jsonify({"error": "item not in bag"}), 400
    existing = gear.get(slot)
    if existing:
        # return existing to inventory
        from app.inventory.utils import add_item

        add_item(inv, existing, 1)
    gear[slot] = slug
    ch.items = dump_inventory(inv)
    ch.gear = _safe_json_dump(gear)
    db.session.commit()
    try:
        advance_for("equip", character_ids=[ch.id])
    except Exception:
        pass
    return jsonify({"ok": True, "slot": slot, "equipped": slug})


@bp_inventory.route("/api/characters/<int:cid>/unequip", methods=["POST"])
@login_required
def unequip_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    slot = (data.get("slot") or "").strip()
    if slot not in _SLOTS:
        return jsonify({"error": "invalid slot"}), 400
    gear = _normalize_gear(_safe_json_load(ch.gear, {}))
    equipped = gear.get(slot)
    if not equipped:
        return jsonify({"error": "empty slot"}), 400

    # Gear-instance path: equipped value is a dict with uid
    if isinstance(equipped, dict) and equipped.get("uid"):
        items_raw = json.loads(ch.items) if ch.items else []
        if not isinstance(items_raw, list):
            items_raw = []
        items_raw.append(equipped)
        del gear[slot]
        ch.gear = json.dumps(gear)
        ch.items = json.dumps(items_raw)
        db.session.commit()
        return jsonify({"ok": True, "gear": gear})

    # Legacy slug-based path
    slug = equipped
    inv = load_inventory(ch.items)
    from app.inventory.utils import add_item

    add_item(inv, slug, 1)
    gear[slot] = None
    ch.items = dump_inventory(inv)
    ch.gear = _safe_json_dump(gear)
    db.session.commit()
    try:
        advance_for("unequip", character_ids=[ch.id])
    except Exception:
        pass
    return jsonify({"ok": True, "slot": slot, "unequipped": slug})


@bp_inventory.route("/api/characters/<int:cid>/consume", methods=["POST"])
@login_required
def consume_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify({"error": "missing slug"}), 400
    item = Item.query.filter_by(slug=slug).first()
    if not item:
        return jsonify({"error": "item not found"}), 404
    inv = load_inventory(ch.items)
    if not any(o["slug"] == slug for o in inv):
        return jsonify({"error": "item not in bag"}), 400
    # Only allow potions for now
    if (item.type or "").lower() != "potion":
        return jsonify({"error": "not consumable"}), 400
    base_stats = _safe_json_load(ch.stats, {})
    # Simple effects
    heal = 0
    mana = 0
    applied_regen_buff = False
    sl = (item.slug or "").lower()
    if "regen" in sl:
        applied_regen_buff = True
    elif "healing" in sl:
        heal = 5
    elif "mana" in sl:
        mana = 5
    # Apply
    if heal:
        base_stats["hp"] = int(base_stats.get("hp", 0)) + heal
    if mana:
        base_stats["mana"] = int(base_stats.get("mana", 0)) + mana
    # Remove potion from bag
    removed = remove_one(inv, slug)
    if removed:
        ch.items = dump_inventory(inv)
    ch.stats = _safe_json_dump(base_stats)
    db.session.commit()
    try:
        advance_for("consume", character_ids=[ch.id])
    except Exception:
        pass
    if applied_regen_buff:
        # Apply the persisted regen_buff after the tick-decay call above so the
        # freshly-granted buff starts at its full duration (matching the
        # combat-side regen_buff convention) instead of being immediately
        # decremented by the same action's own time advancement.
        CharacterStatusEffect.query.filter_by(character_id=ch.id, name="regen_buff").delete()
        db.session.add(
            CharacterStatusEffect(
                character_id=ch.id,
                name="regen_buff",
                remaining=5,
                data=json.dumps({"hp_mult": 3.0, "mp_mult": 3.0}),
            )
        )
        db.session.commit()
    return jsonify(
        {
            "ok": True,
            "consumed": slug,
            "effects": {"hp": heal, "mana": mana, "regen_buff": applied_regen_buff},
        }
    )


@bp_inventory.route("/api/characters/<int:cid>/level-up", methods=["POST"])
@login_required
def level_up_character(cid: int):
    """Confirm level-up and apply stat point allocations."""
    ch = _char_owned(cid)
    if not ch:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    allocations = data.get("stat_allocations", {})

    # Validate allocations against earned, unspent stat points (no free stats).
    valid_keys = ("str", "dex", "int", "con", "wis", "cha")
    try:
        requested = {k: int(v) for k, v in allocations.items() if k in valid_keys}
    except (TypeError, ValueError):
        return jsonify({"error": "invalid allocations"}), 400
    if any(v < 0 for v in requested.values()):
        return jsonify({"error": "allocations must be non-negative"}), 400
    total_requested = sum(requested.values())
    available = int(ch.stat_points or 0)
    if total_requested > available:
        return jsonify({"error": "not enough stat points", "available": available, "requested": total_requested}), 400

    # Load current stats
    stats = _safe_json_load(ch.stats, {})

    # Apply stat allocations
    for stat_key, points in requested.items():
        current = stats.get(stat_key, 10)
        stats[stat_key] = current + points
    ch.stat_points = available - total_requested

    # Update HP/Mana based on level (simple formula)
    level = ch.level or 1
    stats["max_hp"] = 20 + (level * 10)
    stats["max_mana"] = 10 + (level * 5)
    stats["hp"] = stats["max_hp"]  # Heal to full on level up
    stats["mana"] = stats["max_mana"]

    ch.stats = _safe_json_dump(stats)
    db.session.commit()

    return jsonify({"ok": True, "level": ch.level, "stats": stats, "stat_points": ch.stat_points})
