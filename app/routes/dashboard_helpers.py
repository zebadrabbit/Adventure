"""Helper functions extracted from `dashboard.py` to reduce route size.

These utilities encapsulate form handling, character/inventory serialization, and
auto-fill logic. They are intentionally kept framework-light: Flask request/session
objects are passed in explicitly where needed to simplify future unit testing.
"""

from __future__ import annotations

import json
import random
from typing import Any, Sequence

from flask import redirect, render_template, session, url_for
from flask_login import current_user

from app import db
from app.models import GameClock
from app.models.models import Character, User
from app.models.xp import xp_for_level


def _stable_current_user_id() -> int | None:
    """Return a resilient current user id (handles detached SQLAlchemy instance)."""
    try:
        uid = getattr(current_user, "id", None)
    except Exception:  # pragma: no cover - defensive
        uid = None
    if uid is not None:
        return uid
    sid = session.get("_user_id") or session.get("user_id")
    if sid is None:
        return None
    try:
        return int(sid)
    except (TypeError, ValueError):  # pragma: no cover - invalid session state
        return None


def serialize_character_list(user_id: int) -> list[dict[str, Any]]:
    """Serialize all characters for a user for dashboard display.

    Performs legacy data normalization (inventory stacking, class backfill) and commits
    any backfilled rows in a single batch at end.
    """
    characters = Character.query.filter_by(user_id=user_id).all()
    class_map = {
        "fighter": lambda s: s.get("str", 0) >= s.get("dex", 0)
        and s.get("str", 0) >= s.get("int", 0)
        and s.get("str", 0) >= s.get("wis", 0),
        "mage": lambda s: s.get("int", 0) >= s.get("str", 0)
        and s.get("int", 0) >= s.get("dex", 0)
        and s.get("int", 0) >= s.get("wis", 0),
        "druid": lambda s: s.get("wis", 0) >= s.get("str", 0)
        and s.get("wis", 0) >= s.get("dex", 0)
        and s.get("wis", 0) >= s.get("int", 0),
        "ranger": lambda s: s.get("dex", 0) >= s.get("str", 0) and s.get("wis", 0) >= s.get("int", 0),
        "rogue": lambda s: s.get("dex", 0) >= s.get("str", 0)
        and s.get("dex", 0) >= s.get("int", 0)
        and s.get("dex", 0) >= s.get("wis", 0),
        "cleric": lambda s: True,
    }
    out: list[dict[str, Any]] = []
    backfilled = False
    from app.models.models import Item

    for c in characters:
        stats = json.loads(c.stats)
        for key in ("str", "dex", "int", "wis", "con", "cha", "hp", "mana"):
            stats.setdefault(key, 0)
        stats_class = stats.pop("class", None)
        coins = {k: stats.pop(k, 0) for k in ("gold", "silver", "copper")}
        try:
            raw_items = json.loads(c.items) if c.items else []
        except Exception:
            raw_items = []
        stacked: list[dict[str, Any]] = []
        if raw_items and isinstance(raw_items, list) and raw_items and isinstance(raw_items[0], dict):
            stacked = raw_items
        elif isinstance(raw_items, list):
            agg: dict[str, int] = {}
            for slug in raw_items:
                if isinstance(slug, str):
                    agg[slug] = agg.get(slug, 0) + 1
            stacked = [{"slug": s, "qty": q} for s, q in agg.items()]
            if stacked:
                try:
                    c.items = json.dumps(stacked)
                    backfilled = True
                except Exception:  # pragma: no cover
                    pass
        # Normalize stacked entries
        norm: list[dict[str, Any]] = []
        for ent in stacked:
            if isinstance(ent, dict) and ent.get("slug"):
                try:
                    qty = int(ent.get("qty", 1))
                except Exception:
                    qty = 1
                if qty < 1:
                    qty = 1
                norm.append({"slug": ent["slug"], "qty": qty})
        stacked = norm
        slugs_needed = [o["slug"] for o in stacked]
        db_items = Item.query.filter(Item.slug.in_(slugs_needed)).all() if slugs_needed else []
        # by_slug not needed in simplified inventory construction
        inventory = [
            {
                "slug": it.slug,
                "name": it.name,
                "type": it.type,
                "qty": next((o["qty"] for o in stacked if o["slug"] == it.slug), 1),
            }
            for it in db_items
        ]
        if stats_class:
            class_name = stats_class.capitalize()
        else:
            inv_slugs = {o["slug"] for o in stacked}
            if "herbal-pouch" in inv_slugs:
                class_name = "Druid"
            elif "hunting-bow" in inv_slugs:
                class_name = "Ranger"
            else:
                if class_map["fighter"](stats):
                    class_name = "Fighter"
                elif class_map["mage"](stats):
                    class_name = "Mage"
                elif class_map["druid"](stats):
                    class_name = "Druid"
                elif class_map["ranger"](stats):
                    class_name = "Ranger"
                elif class_map["rogue"](stats):
                    class_name = "Rogue"
                else:
                    class_name = "Cleric"
            new_stats = dict(stats)
            new_stats.update(coins)
            new_stats["class"] = class_name.lower()
            c.stats = json.dumps(new_stats)
            backfilled = True
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "stats": stats,
                "coins": coins,
                "inventory": inventory,
                "class_name": class_name,
                "xp": getattr(c, "xp", 0),
                "level": getattr(c, "level", 1),
                "xp_next": xp_for_level(getattr(c, "level", 1) + 1),
            }
        )
    if backfilled:
        db.session.commit()
    return out


def render_dashboard():
    """Render the dashboard template with serialized characters and metadata."""
    uid = _stable_current_user_id()
    if uid is None:
        from flask_login import logout_user

        logout_user()
        return redirect(url_for("auth.login"))
    char_list = serialize_character_list(uid)
    try:
        user_obj = db.session.get(User, current_user.id)
        user_email = getattr(user_obj, "email", None)
    except Exception:  # pragma: no cover
        user_email = None
    dungeon_seed = session.get("dungeon_seed", "")
    try:
        clock = GameClock.get()
    except Exception:  # pragma: no cover
        clock = None
    return render_template(
        "dashboard.html",
        characters=char_list,
        user_email=user_email,
        dungeon_seed=dungeon_seed,
        game_clock=clock,
    )


def build_party_payload(chars: Sequence[Character]):
    party = []
    for c in chars:
        try:
            s = json.loads(c.stats)
        except Exception:
            s = {}
        party.append(
            {
                "id": c.id,
                "name": c.name,
                "class": (s.get("class") or "unknown").capitalize(),
                "hp": s.get("hp", 0),
                "mana": s.get("mana", 0),
            }
        )
    return party


def handle_autofill(existing: list[Character], current_user_id: int):
    """Create random characters up to 4 and return full roster list."""
    from app.routes.main import BASE_STATS, NAME_POOLS, STARTER_ITEMS
    from app.services.auto_equip import auto_equip_for

    needed = max(0, 4 - len(existing))
    created: list[Character] = []
    if needed:
        classes = list(BASE_STATS.keys())
        for _ in range(needed):
            cls = random.choice(classes)
            pool = NAME_POOLS.get(cls, [])
            base_name = random.choice(pool) if pool else cls.capitalize()
            suffix = random.randint(100, 999)
            name = f"{base_name}{suffix}"
            attempts = 0
            while attempts < 5 and (any(c.name == name for c in existing) or any(c.name == name for c in created)):
                suffix = random.randint(100, 999)
                name = f"{base_name}{suffix}"
                attempts += 1
            stats = BASE_STATS.get(cls, BASE_STATS["fighter"])
            coins = {"gold": 5, "silver": 20, "copper": 50}
            raw_items = STARTER_ITEMS.get(cls, STARTER_ITEMS["fighter"])
            # Expanded slug list for backward compatibility
            expanded: list[str] = []
            if isinstance(raw_items, list):
                for ent in raw_items:
                    if isinstance(ent, str):
                        expanded.append(ent)
                    elif isinstance(ent, dict):
                        slug = ent.get("slug") or ent.get("name") or ent.get("id")
                        if slug:
                            try:
                                qty = int(ent.get("qty", 1))
                            except Exception:
                                qty = 1
                            if qty < 1:
                                qty = 1
                            expanded.extend([slug] * qty)
            gear_map = auto_equip_for(cls, expanded)
            ch = Character(
                user_id=current_user_id,
                name=name,
                stats=json.dumps({**stats, **coins, "class": cls}),
                gear=json.dumps(gear_map),
                items=json.dumps(expanded),
                xp=0,
                level=1,
            )
            db.session.add(ch)
            created.append(ch)
        db.session.commit()
        existing.extend(created)
    return existing, created
