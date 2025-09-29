"""Perception and loot noticing helpers for dungeon API.

This module centralizes logic formerly in routes.dungeon_api:
  * Party perception roll aggregation
  * Loot row lookup & filtering
  * Session-based tracking of noticed coordinates
  * Perception-based revealing / failing logic (with loot deletion of scattered loot)
  * Search action resolution (revealing concrete item list)

Public functions kept intentionally small to keep the route layer thin.

Contract summary:
- roll_perception_for_user() -> dict describing the best party perception roll
- maybe_perceive_and_mark_loot(instance, x, y) -> (noticed: bool, message: str, roll_info: dict|None)
- get_noticed_coords(instance) -> list[[x,y]] for still valid, unclaimed loot locations
- search_current_tile(instance) -> (success: bool, response_dict: dict) where response_dict is ready for jsonify

All DB interactions are best-effort; failures fall back gracefully to avoid blocking core movement.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from flask import session
from flask_login import current_user

from app import db
from app.models.loot import DungeonLoot
from app.models.models import Character, Item
from app.services.time_service import advance_for

__all__ = [
    "roll_perception_for_user",
    "maybe_perceive_and_mark_loot",
    "get_noticed_coords",
    "search_current_tile",
]

# -------------------- Internal small utilities --------------------


def _get_party_for_current_user():
    party_meta = session.get("party") or []
    names = {(m.get("name") or "").strip() for m in party_meta if isinstance(m, dict)}
    names.discard("")
    q = Character.query.filter_by(user_id=current_user.id)
    if names:
        rows = q.filter(Character.name.in_(list(names))).all()
        if rows:
            return rows
    return q.all()


def _perception_mod_from_stats(stats_json: str) -> int:
    if not stats_json:
        return 0
    try:
        data = json.loads(stats_json)
        if isinstance(data, dict):
            if "perception" in data and isinstance(data["perception"], (int, float)):
                return int(data["perception"])
            wis = data.get("wis") or data.get("WIS") or data.get("wisdom")
            if isinstance(wis, (int, float)):
                return int((wis - 10) // 2)
    except Exception:
        return 0
    return 0


def _loot_rows_at(seed: int, x: int, y: int) -> List[DungeonLoot]:
    return DungeonLoot.query.filter_by(seed=seed, x=x, y=y, z=0, claimed=False).all()


def _session_noticed_key(seed: int) -> str:
    return f"noticed:{seed}"


def _coord_key(x: int, y: int) -> str:
    return f"{x},{y}"


def _is_container_item(item: Item) -> bool:
    t = (item.type or "").lower().strip() if item and getattr(item, "type", None) else ""
    return t in ("container", "chest", "lockbox")


# -------------------- Public helpers --------------------


def roll_perception_for_user():
    import random as _random

    rows = _get_party_for_current_user()
    best_mod = 1
    best_char = None
    if rows:
        top_mod = None
        for c in rows:
            try:
                eff = _perception_mod_from_stats(c.stats) + max(0, int(c.level) // 2)
            except Exception:
                eff = _perception_mod_from_stats(getattr(c, "stats", None))
            if top_mod is None or eff > top_mod:
                top_mod = int(eff)
                best_char = c
        if top_mod is not None:
            best_mod = int(top_mod)
    die_roll = _random.randint(1, 20)
    total = die_roll + best_mod
    return {
        "skill": "perception",
        "die": "d20",
        "roll": die_roll,
        "mod": best_mod,
        "total": total,
        "expr": f"1d20+{best_mod}",
        "character": ({"id": int(best_char.id), "name": best_char.name} if best_char else None),
    }


def maybe_perceive_and_mark_loot(instance, x: int, y: int) -> Tuple[bool, str, dict | None]:
    seed = instance.seed
    rows = _loot_rows_at(seed, x, y)
    if not rows:
        return False, "", None
    key = _session_noticed_key(seed)
    noticed_map = session.get(key) or {}
    ck = _coord_key(x, y)
    if noticed_map.get(ck):
        return True, "You recall a suspicious spot here.", None
    roll_info = roll_perception_for_user()
    total = roll_info["total"]
    DC = 13
    if total >= DC:
        noticed_map[ck] = True
        session[key] = noticed_map
        try:
            session.modified = True
        except Exception:
            pass
        return True, "You notice a glint of something hidden. You can Search this area.", roll_info
    # Failure path: remove scattered loot (non-container)
    removed = 0
    for r in list(rows):
        item = db.session.get(Item, r.item_id)
        if not _is_container_item(item):
            try:
                db.session.delete(r)
                removed += 1
            except Exception:
                pass
    if removed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return False, "You find nothing of interest. Whatever was here is lost to the dark.", roll_info


def get_noticed_coords(instance) -> List[List[int]]:
    key = _session_noticed_key(instance.seed)
    noticed_map = session.get(key) or {}
    coords: List[List[int]] = []
    for ck, val in noticed_map.items():
        if not val:
            continue
        try:
            xs, ys = ck.split(",")
            x = int(xs)
            y = int(ys)
        except Exception:
            continue
        rows = _loot_rows_at(instance.seed, x, y)
        if rows:
            coords.append([x, y])
    return coords


def search_current_tile(instance):
    x, y, _ = instance.pos_x, instance.pos_y, instance.pos_z
    key = _session_noticed_key(instance.seed)
    noticed_map = session.get(key) or {}
    ck = _coord_key(x, y)
    if not noticed_map.get(ck):
        return False, {"found": False, "message": "You see nothing here to search."}, 403
    rows = _loot_rows_at(instance.seed, x, y)
    if not rows:
        return False, {"found": False, "message": "There is nothing here."}, 404
    items = []
    for r in rows:
        item = db.session.get(Item, r.item_id)
        if not item:
            continue
        items.append(
            {
                "id": r.id,
                "name": item.name,
                "slug": item.slug,
                "rarity": getattr(item, "rarity", "common"),
                "level": getattr(item, "level", 0),
                "type": getattr(item, "type", ""),
                "value_copper": getattr(item, "value_copper", 0),
                "description": getattr(item, "description", "") or "",
            }
        )
    if not items:
        return False, {"found": False, "message": "There is nothing here."}, 404
    names = ", ".join(i["name"] for i in items)
    msg = f"You search the area and discover: {names}."
    try:
        advance_for("search", actor_id=None)
    except Exception:
        pass
    return True, {"found": True, "items": items, "message": msg}, 200
