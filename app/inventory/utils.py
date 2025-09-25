"""Inventory utilities for stacking and encumbrance.

This module centralizes logic for migrating legacy inventories (list of slugs)
to a structured format with quantities, calculating carry weights, and
enforcing encumbrance rules driven by database-backed configuration.

Inventory canonical format (bag stored in Character.items JSON string):
    [ {"slug": "potion-healing", "qty": 3}, {"slug": "dagger", "qty": 1} ]

Legacy format support:
    ["potion-healing", "potion-healing", "dagger"]
will be converted automatically on load.

Encumbrance configuration row (GameConfig key='encumbrance'):
    {
      "base_capacity": 10,
      "per_str": 5,
      "warn_pct": 1.0,
      "hard_cap_pct": 1.10,
      "dex_penalty": 2
    }

Weight calculation: each item weight taken from Item.weight (default 1.0).
Total carried weight = sum(item.weight * qty).
Capacity = base_capacity + STR * per_str.
State categories:
  weight <= capacity -> normal
  capacity < weight <= capacity * hard_cap_pct -> over_encumbered (DEX penalty)
  weight > capacity * hard_cap_pct -> cannot add more (reject additions)
"""
from __future__ import annotations
from typing import List, Dict, Any, Tuple
import json
from app import db
from app.models.models import Item, GameConfig, Character


def load_inventory(raw_json: str | None) -> List[Dict[str, Any]]:
    """Deserialize inventory JSON into canonical list of {slug, qty} dicts.

    Accepts legacy list-of-slugs and consolidates to stacked representation.
    Malformed JSON returns an empty list.
    """
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
    except Exception:
        return []
    if isinstance(data, list) and (not data or isinstance(data[0], str)):
        # Legacy list of slugs -> aggregate
        agg = {}
        for slug in data:
            if not isinstance(slug, str):
                continue
            agg[slug] = agg.get(slug, 0) + 1
        return [{"slug": s, "qty": q} for s, q in agg.items()]
    # Already canonical? Validate shape
    out = []
    if isinstance(data, list):
        for obj in data:
            if not isinstance(obj, dict):
                continue
            slug = obj.get('slug')
            qty = obj.get('qty', 1)
            if isinstance(slug, str):
                try:
                    qty_i = int(qty)
                except Exception:
                    qty_i = 1
                if qty_i > 0:
                    out.append({'slug': slug, 'qty': qty_i})
    return out


def dump_inventory(inv: List[Dict[str, Any]]) -> str:
    """Serialize inventory to JSON string."""
    try:
        return json.dumps(inv)
    except Exception:
        return '[]'


def add_item(inv: List[Dict[str, Any]], slug: str, qty: int = 1) -> List[Dict[str, Any]]:
    """Add quantity of an item to inventory (in-place update)."""
    if qty <= 0:
        return inv
    for obj in inv:
        if obj['slug'] == slug:
            obj['qty'] += qty
            break
    else:  # not found
        inv.append({'slug': slug, 'qty': qty})
    return inv


def remove_one(inv: List[Dict[str, Any]], slug: str) -> bool:
    """Remove a single instance of slug if present; return True if removed."""
    for obj in inv:
        if obj['slug'] == slug:
            obj['qty'] -= 1
            if obj['qty'] <= 0:
                inv.remove(obj)
            return True
    return False


def fetch_encumbrance_config() -> dict:
    row = GameConfig.query.filter_by(key='encumbrance').first()
    if not row:
        # Provide hardcoded fallback if seeding failed
        return {'base_capacity': 10, 'per_str': 5, 'warn_pct': 1.0, 'hard_cap_pct': 1.10, 'dex_penalty': 2}
    try:
        return json.loads(row.value)
    except Exception:
        return {'base_capacity': 10, 'per_str': 5, 'warn_pct': 1.0, 'hard_cap_pct': 1.10, 'dex_penalty': 2}


def compute_capacity(str_score: int, cfg: dict) -> int:
    base = int(cfg.get('base_capacity', 10))
    per = int(cfg.get('per_str', 5))
    return base + max(0, int(str_score)) * per


def compute_weight(inv: List[Dict[str, Any]]) -> float:
    if not inv:
        return 0.0
    slugs = [o['slug'] for o in inv]
    items = Item.query.filter(Item.slug.in_(slugs)).all()
    weight_by_slug = {i.slug: (getattr(i, 'weight', 1.0) or 1.0) for i in items}
    total = 0.0
    for obj in inv:
        total += weight_by_slug.get(obj['slug'], 1.0) * obj.get('qty', 1)
    return float(total)


def encumbrance_state(str_score: int, inv: List[Dict[str, Any]]) -> dict:
    cfg = fetch_encumbrance_config()
    cap = compute_capacity(str_score, cfg)
    w = compute_weight(inv)
    warn_pct = float(cfg.get('warn_pct', 1.0))
    hard_pct = float(cfg.get('hard_cap_pct', 1.10))
    penalty = int(cfg.get('dex_penalty', 2))
    status = 'normal'
    dex_pen = 0
    if w > cap * hard_pct:
        status = 'blocked'
        dex_pen = penalty
    elif w > cap * warn_pct:
        status = 'encumbered'
        dex_pen = penalty
    return {
        'weight': w,
        'capacity': cap,
        'status': status,
        'dex_penalty': dex_pen,
        'hard_cap_pct': hard_pct,
    }


def can_add_item(str_score: int, inv: List[Dict[str, Any]], slug: str, qty: int = 1) -> Tuple[bool, dict]:
    """Predict whether adding qty of slug would exceed hard cap.

    Returns (allowed, resulting_state) where resulting_state is encumbrance state AFTER
    the hypothetical addition (if allowed) or current state if not allowed.
    """
    # Quick evaluation using current state and projected weight delta
    cfg = fetch_encumbrance_config()
    cap = compute_capacity(str_score, cfg)
    hard_pct = float(cfg.get('hard_cap_pct', 1.10))
    penalty = int(cfg.get('dex_penalty', 2))
    # Pull item weight
    item = Item.query.filter_by(slug=slug).first()
    item_w = getattr(item, 'weight', 1.0) if item else 1.0
    cur_weight = compute_weight(inv)
    new_weight = cur_weight + item_w * qty
    if new_weight > cap * hard_pct:
        # Not allowed; report current state
        return False, encumbrance_state(str_score, inv)
    # Allowed; compute new state
    # Temporarily adjust inventory for state computation
    temp_inv = [dict(o) for o in inv]
    add_item(temp_inv, slug, qty)
    return True, encumbrance_state(str_score, temp_inv)


def apply_encumbrance_penalty(base_stats: dict, enc_state: dict) -> dict:
    if enc_state.get('status') in ('encumbered', 'blocked'):
        pen = int(enc_state.get('dex_penalty', 0))
        if pen:
            try:
                base_stats = dict(base_stats)
                base_stats['dex'] = max(0, int(base_stats.get('dex', 0)) - pen)
            except Exception:
                pass
    return base_stats
