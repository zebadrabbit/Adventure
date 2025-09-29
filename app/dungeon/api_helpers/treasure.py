"""Treasure claiming helper.

Extracted from dungeon_api.claim_treasure route. Provides a single function
`claim_treasure_entity(entity_id, instance)` which returns a tuple
(status_code:int, response:dict) ready for jsonify().

Behavior preserved:
  * Validates entity & proximity
  * Optional hidden perception gate (simple threshold) using local roll logic
  * Loot roll via loot_service with faux monster/table override
  * Deletes entity row on success
"""

from __future__ import annotations

import json
from random import randint
from typing import Tuple

from flask_login import current_user

from app import db
from app.models import DungeonEntity
from app.models.models import Character

__all__ = ["claim_treasure_entity"]


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


def _get_party_for_current_user():
    from flask import session

    party_meta = session.get("party") or []
    names = {(m.get("name") or "").strip() for m in party_meta if isinstance(m, dict)}
    names.discard("")
    q = Character.query.filter_by(user_id=current_user.id)
    if names:
        rows = q.filter(Character.name.in_(list(names))).all()
        if rows:
            return rows
    return q.all()


def claim_treasure_entity(entity_id: int, instance) -> Tuple[int, dict]:
    row = DungeonEntity.query.filter_by(id=entity_id, instance_id=instance.id).first()
    if not row:
        return 404, {"error": "not_found"}
    if row.type != "treasure":
        return 400, {"error": "wrong_type"}
    dist_xy = abs(int(instance.pos_x) - int(row.x)) + abs(int(instance.pos_y) - int(row.y))
    if getattr(instance, "pos_z", 0) != getattr(row, "z", 0):
        dist_xy = 999
    if dist_xy > 1:
        return 400, {"error": "too_far", "required": 1, "distance": dist_xy}
    hidden_flag = False
    loot_table_override = None
    meta = {}
    try:
        if row.data:
            meta = json.loads(row.data)
            if isinstance(meta, dict):
                hidden_flag = bool(meta.get("hidden", False))
                loot_table_override = meta.get("loot_table") or None
    except Exception:
        pass
    if hidden_flag:
        tier = 1
        try:
            tier = max(1, int(meta.get("tier", 1)))  # type: ignore
        except Exception:
            tier = 1
        rows_party = _get_party_for_current_user()
        best_mod = 1
        for c in rows_party:
            try:
                eff = _perception_mod_from_stats(c.stats) + max(0, int(c.level) // 2)
            except Exception:
                eff = _perception_mod_from_stats(getattr(c, "stats", None))
            if eff > best_mod:
                best_mod = eff
        roll = randint(1, 20)
        total = roll + best_mod
        threshold = 10 + tier
        if total < threshold:
            return 400, {
                "error": "perception_failed",
                "roll": roll,
                "mod": best_mod,
                "total": total,
                "threshold": threshold,
            }
    try:
        from app.services.loot_service import roll_loot

        table = loot_table_override or "potion-healing, dagger, short-sword, leather-armor"
        faux = {
            "slug": "treasure-cache",
            "name": "Treasure Cache",
            "level": 1,
            "hp": 1,
            "damage": 0,
            "armor": 0,
            "speed": 0,
            "rarity": "common",
            "family": "cache",
            "traits": [],
            "resistances": {},
            "damage_types": [],
            "loot_table": table,
            "special_drop_slug": None,
            "xp": 0,
            "boss": False,
        }
        loot = roll_loot(faux)
        items = loot.get("items_list") or list((loot.get("items") or {}).keys())
    except Exception:
        items = []
    try:
        db.session.delete(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 500, {"error": "persist_fail"}
    return 200, {"claimed": True, "items": items, "count": len(items)}
