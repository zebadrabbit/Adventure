"""Inventory & Equipment API.

Endpoints for managing character inventory, equipping items, and consuming potions.
Uses existing Character JSON columns: `items` (bag list of slugs) and `gear` (JSON mapping slot->slug).
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user
from app import db
from app.models.models import Character, Item
import json

bp_inventory = Blueprint('inventory', __name__)


# ----------------------- Helpers -----------------------

_SLOTS = (
    'head', 'chest', 'legs', 'boots', 'gloves', 'weapon', 'offhand', 'ring1', 'ring2', 'amulet'
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
        return '[]' if isinstance(obj, list) else '{}'

def _char_owned(cid: int) -> Character | None:
    # Robust user id extraction to avoid DetachedInstance errors
    uid = None
    try:
        uid = getattr(current_user, 'id', None)
    except Exception:
        uid = None
    if uid is None:
        sid = session.get('_user_id') or session.get('user_id')
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
    t = (item.type or '').lower()
    slug = (item.slug or '').lower()
    name = (item.name or '').lower()
    if t == 'weapon':
        return 'weapon'
    if t == 'armor':
        if 'shield' in slug or 'shield' in name:
            return 'offhand'
        if any(k in slug or k in name for k in ('helm','helmet','hood','cap')):
            return 'head'
        if any(k in slug or k in name for k in ('boots','greaves')):
            return 'boots'
        if any(k in slug or k in name for k in ('glove','gauntlet')):
            return 'gloves'
        if any(k in slug or k in name for k in ('legging','pants','trousers','legs')):
            return 'legs'
        return 'chest'
    if t == 'ring':
        # pick first free ring slot
        return 'ring1' if not gear.get('ring1') else 'ring2'
    if t in ('amulet','necklace','talisman'):
        return 'amulet'
    # tools, potions, scrolls not equippable
    return None

def _item_effects(item: Item) -> dict:
    """Return stat deltas for equippable items (simple defaults)."""
    slug = (item.slug or '').lower()
    t = (item.type or '').lower()
    # Coarse defaults
    if t == 'weapon':
        # Specific weapons
        if 'bow' in slug:
            return {'dex': +1}
        if 'staff' in slug:
            return {'int': +1}
        if 'dagger' in slug:
            return {'dex': +1}
        return {'str': +1}
    if t == 'armor':
        if 'shield' in slug:
            return {'con': +1}
        if 'leather' in slug:
            return {'con': +1}
        return {'con': +1}
    if t == 'ring':
        return {'wis': +1}
    if t in ('amulet','necklace','talisman'):
        return {'cha': +1}
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
        if not slug:
            continue
        it = items_lookup.get(slug)
        if it:
            cur = _apply_effects(cur, _item_effects(it))
    return cur

def _serialize_item(item: Item) -> dict:
    return {
        'slug': item.slug,
        'name': item.name,
        'type': item.type,
        'rarity': getattr(item, 'rarity', 'common'),
        'level': getattr(item, 'level', 0),
        'description': item.description,
        'value_copper': item.value_copper,
    }


# ----------------------- Endpoints -----------------------

@bp_inventory.route('/api/characters/state')
@login_required
def list_characters_state():
    """Return state for current user's characters including equipment and bag items.
    Shape: { characters: [ { id, name, stats: {base, computed}, gear: {slot: item|None}, bag: [item,..] } ] }
    """
    # Robust current user id
    uid = None
    try:
        uid = getattr(current_user, 'id', None)
    except Exception:
        uid = None
    if uid is None:
        sid = session.get('_user_id') or session.get('user_id')
        try:
            uid = int(sid) if sid is not None else None
        except Exception:
            uid = None
    if uid is None:
        return jsonify({'error': 'unauthorized'}), 401
    chars = Character.query.filter_by(user_id=uid).all()
    out = []
    # Preload all items used by these characters for efficient lookups
    slugs_needed = set()
    for ch in chars:
        bag = _safe_json_load(ch.items, [])
        gear = _normalize_gear(_safe_json_load(ch.gear, {}))
        slugs_needed.update(bag)
        slugs_needed.update([s for s in gear.values() if s])
    items_map = {it.slug: it for it in Item.query.filter(Item.slug.in_(slugs_needed)).all()} if slugs_needed else {}
    for ch in chars:
        try:
            base_stats = _safe_json_load(ch.stats, {})
            gear = _normalize_gear(_safe_json_load(ch.gear, {}))
            bag_slugs = _safe_json_load(ch.items, [])
            computed = _computed_stats(base_stats, gear, items_map)
            out.append({
                'id': ch.id,
                'name': ch.name,
                'level': ch.level,
                'stats': {'base': base_stats, 'computed': computed},
                'gear': {slot: (_serialize_item(items_map[slug]) if slug in items_map else None) for slot, slug in (gear or {}).items()},
                'bag': [ _serialize_item(items_map[s]) for s in bag_slugs if s in items_map ],
            })
        except Exception:
            # Best-effort fallback for malformed legacy data; prevents 500s breaking UI
            out.append({
                'id': ch.id,
                'name': ch.name,
                'level': getattr(ch, 'level', 1),
                'stats': {'base': {}, 'computed': {}},
                'gear': {},
                'bag': [],
                'warning': 'character_state_unavailable'
            })
    return jsonify({'characters': out, 'slots': list(_SLOTS)})


@bp_inventory.route('/api/characters/<int:cid>/equip', methods=['POST'])
@login_required
def equip_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    slug = (data.get('slug') or '').strip()
    if not slug:
        return jsonify({'error': 'missing slug'}), 400
    item = Item.query.filter_by(slug=slug).first()
    if not item:
        return jsonify({'error': 'item not found'}), 404
    bag = _safe_json_load(ch.items, [])
    gear = _normalize_gear(_safe_json_load(ch.gear, {}))
    if slug not in bag:
        return jsonify({'error': 'item not in bag'}), 400
    slot = data.get('slot') or _slot_for_item(item, gear)
    if slot not in _SLOTS:
        return jsonify({'error': 'invalid slot'}), 400
    # Enforce compatibility
    inferred = _slot_for_item(item, gear)
    if inferred and inferred != slot:
        slot = inferred  # prefer inferred slot
    if _slot_for_item(item, gear) is None:
        return jsonify({'error': 'item not equippable'}), 400
    # Perform equip: remove from bag, move current slot (if any) back to bag
    try:
        bag.remove(slug)
    except ValueError:
        pass
    existing = gear.get(slot)
    if existing:
        bag.append(existing)
    gear[slot] = slug
    ch.items = _safe_json_dump(bag)
    ch.gear = _safe_json_dump(gear)
    db.session.commit()
    return jsonify({'ok': True, 'slot': slot, 'equipped': slug})


@bp_inventory.route('/api/characters/<int:cid>/unequip', methods=['POST'])
@login_required
def unequip_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    slot = (data.get('slot') or '').strip()
    if slot not in _SLOTS:
        return jsonify({'error': 'invalid slot'}), 400
    gear = _normalize_gear(_safe_json_load(ch.gear, {}))
    bag = _safe_json_load(ch.items, [])
    slug = gear.get(slot)
    if not slug:
        return jsonify({'error': 'empty slot'}), 400
    bag.append(slug)
    gear[slot] = None
    ch.items = _safe_json_dump(bag)
    ch.gear = _safe_json_dump(gear)
    db.session.commit()
    return jsonify({'ok': True, 'slot': slot, 'unequipped': slug})


@bp_inventory.route('/api/characters/<int:cid>/consume', methods=['POST'])
@login_required
def consume_item(cid: int):
    ch = _char_owned(cid)
    if not ch:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    slug = (data.get('slug') or '').strip()
    if not slug:
        return jsonify({'error': 'missing slug'}), 400
    item = Item.query.filter_by(slug=slug).first()
    if not item:
        return jsonify({'error': 'item not found'}), 404
    bag = _safe_json_load(ch.items, [])
    if slug not in bag:
        return jsonify({'error': 'item not in bag'}), 400
    # Only allow potions for now
    if (item.type or '').lower() != 'potion':
        return jsonify({'error': 'not consumable'}), 400
    base_stats = _safe_json_load(ch.stats, {})
    # Simple effects
    heal = 0
    mana = 0
    sl = (item.slug or '').lower()
    if 'healing' in sl:
        heal = 5
    elif 'mana' in sl:
        mana = 5
    # Apply
    if heal:
        base_stats['hp'] = int(base_stats.get('hp', 0)) + heal
    if mana:
        base_stats['mana'] = int(base_stats.get('mana', 0)) + mana
    # Remove potion from bag
    bag.remove(slug)
    ch.items = _safe_json_dump(bag)
    ch.stats = _safe_json_dump(base_stats)
    db.session.commit()
    return jsonify({'ok': True, 'consumed': slug, 'effects': {'hp': heal, 'mana': mana}})
