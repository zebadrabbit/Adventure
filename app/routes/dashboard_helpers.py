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
from app.services.progression import progression_config
from app.services.status_effects import describe_status_effect


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
        "barbarian": lambda s: s.get("str", 0) >= 16 and s.get("con", 0) >= 14 and s.get("int", 0) <= 8,
        "paladin": lambda s: s.get("str", 0) >= 14 and s.get("cha", 0) >= 12,
        "fighter": lambda s: s.get("str", 0) >= s.get("dex", 0)
        and s.get("str", 0) >= s.get("int", 0)
        and s.get("str", 0) >= s.get("wis", 0),
        "monk": lambda s: s.get("dex", 0) >= 14 and s.get("wis", 0) >= 12,
        "rogue": lambda s: s.get("dex", 0) >= s.get("str", 0)
        and s.get("dex", 0) >= s.get("int", 0)
        and s.get("dex", 0) >= s.get("wis", 0)
        and s.get("cha", 0) < 14,
        "bard": lambda s: s.get("cha", 0) >= 14 and s.get("dex", 0) >= 12,
        "sorcerer": lambda s: s.get("cha", 0) >= 14 and s.get("int", 0) <= 12,
        "warlock": lambda s: s.get("cha", 0) >= 14 and s.get("int", 0) >= 11,
        "mage": lambda s: s.get("int", 0) >= s.get("str", 0)
        and s.get("int", 0) >= s.get("dex", 0)
        and s.get("int", 0) >= s.get("wis", 0),
        "druid": lambda s: s.get("wis", 0) >= s.get("str", 0)
        and s.get("wis", 0) >= s.get("dex", 0)
        and s.get("wis", 0) >= s.get("int", 0)
        and s.get("int", 0) >= 11,
        "ranger": lambda s: s.get("dex", 0) >= s.get("str", 0) and s.get("wis", 0) >= s.get("int", 0),
        "cleric": lambda s: True,
    }
    out: list[dict[str, Any]] = []
    backfilled = False
    from app.models.models import Item

    for c in characters:
        stats = json.loads(c.stats)
        for key in ("str", "dex", "int", "wis", "con", "cha"):
            stats.setdefault(key, 0)
        if "hp" not in stats or "mana" not in stats:
            from app.services.character_stats import compute_hp_mana_max

            hp_max, mana_max = compute_hp_mana_max(c)
            stats.setdefault("hp", hp_max)
            stats.setdefault("mana", mana_max)

        from app.services.character_stats import compute_hp_mana_max

        hp_max, mana_max = compute_hp_mana_max(c)

        try:
            from app.models import CharacterStatusEffect

            effects_display = [
                describe_status_effect(
                    {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
                )
                for row in CharacterStatusEffect.query.filter_by(character_id=c.id).all()
            ]
        except Exception:
            effects_display = []
        stats_class = stats.get("class", None)
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
        try:
            gear = json.loads(c.gear) if c.gear else {}
            if not isinstance(gear, dict):
                gear = {}
        except Exception:
            gear = {}
        mod = float(progression_config().get("xp_difficulty_mod", 1.0))
        level = getattr(c, "level", 1)
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "stats": stats,
                "coins": coins,
                "inventory": inventory,
                "gear": gear,
                "class_name": class_name,
                "xp": getattr(c, "xp", 0),
                "level": level,
                "xp_current": xp_for_level(level, mod),
                "xp_next": xp_for_level(level + 1, mod),
                "stat_points": getattr(c, "stat_points", 0) or 0,
                "hp_max": hp_max,
                "mana_max": mana_max,
                "effects_display": effects_display,
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
    # Build ordered party chars list for the Party and Dungeon tab slots
    party_ids_ordered = session.get("last_party_ids") or [p["id"] for p in session.get("party", [])]
    chars_by_id = {c["id"]: c for c in char_list}
    party_chars = [chars_by_id[pid] for pid in party_ids_ordered if pid in chars_by_id]
    return render_template(
        "dashboard.html",
        characters=char_list,
        party_chars=party_chars,
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

        # Calculate max HP and mana based on character stats and level
        level = getattr(c, "level", 1) or 1
        # Try lowercase first, then uppercase for stats (handle both formats)
        con = int(s.get("con", s.get("CON", 10)))
        intelligence = int(s.get("int", s.get("INT", 10)))

        # Max HP: base 50 + CON*2 + level*5 (matches combat_service.py)
        hp_max = 50 + con * 2 + level * 5
        # Max Mana: base 20 + INT*2 (matches combat_service.py)
        mana_max = 20 + intelligence * 2

        from app.loot.equip import gear_bonuses

        try:
            gear = json.loads(c.gear) if getattr(c, "gear", None) else {}
        except Exception:
            gear = {}
        gb = gear_bonuses(gear)
        # Fold unlocked passive skill effects in alongside gear (matches combat).
        try:
            from app.services.skill_effects import passive_bonuses

            for _k, _v in passive_bonuses(c.id).items():
                gb[_k] = gb.get(_k, 0) + _v
        except Exception:
            pass
        hp_max += int(gb.get("max_hp", 0)) + int(gb.get("con", 0)) * 2
        mana_max += int(gb.get("mana", 0)) + int(gb.get("int", 0)) * 2

        # Read actual current HP/MP from stats (persistent values)
        hp = int(s.get("hp", hp_max))  # Default to full if not set
        mana = int(s.get("current_mana", s.get("mana", mana_max)))  # Check both keys

        party.append(
            {
                "id": c.id,
                "name": c.name,
                "class": (s.get("class") or "unknown").capitalize(),
                "level": level,
                "hp": hp,
                "hp_max": hp_max,
                "mana": mana,
                "mana_max": mana_max,
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

        def _name_taken(candidate: str) -> bool:
            return any(c.name == candidate for c in existing) or any(c.name == candidate for c in created)

        for _ in range(needed):
            cls = random.choice(classes)
            pool = NAME_POOLS.get(cls, [])
            # Prefer an unsuffixed pool name — only fall back to a numeric
            # suffix once every pool name for this class is already taken.
            shuffled_pool = random.sample(pool, len(pool)) if pool else []
            name = next((candidate for candidate in shuffled_pool if not _name_taken(candidate)), None)
            if name is None:
                base_name = random.choice(pool) if pool else cls.capitalize()
                suffix = random.randint(100, 999)
                name = f"{base_name}{suffix}"
                attempts = 0
                while attempts < 5 and _name_taken(name):
                    suffix = random.randint(100, 999)
                    name = f"{base_name}{suffix}"
                    attempts += 1
            stats = dict(BASE_STATS.get(cls, BASE_STATS["fighter"]))
            # BASE_STATS["hp"]/["mana"] are legacy flat per-class baselines, not
            # a fresh character's current HP/MP — start at the same computed
            # max combat/the dashboard use everywhere else (50 + con*2 +
            # level*5 for HP, 20 + int*2 for mana, level 1).
            stats["hp"] = 50 + int(stats.get("con", 10)) * 2 + 1 * 5
            stats["mana"] = 20 + int(stats.get("int", 10)) * 2
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


def generate_candidate(current_user_id: int, cls: str | None = None) -> dict:
    """Return an unsaved level-1 character candidate dict."""
    import random as _random
    from app.routes.main import BASE_STATS, NAME_POOLS, STARTER_ITEMS
    from app.services.auto_equip import auto_equip_for

    classes = list(BASE_STATS.keys())
    if cls is None:
        cls = _random.choice(classes)

    pool = NAME_POOLS.get(cls, [])
    base_name = _random.choice(pool) if pool else cls.capitalize()
    name = f"{base_name}{_random.randint(100, 999)}"

    stats = dict(BASE_STATS.get(cls, BASE_STATS["fighter"]))
    stats["hp"] = 50 + int(stats.get("con", 10)) * 2 + 5
    stats["mana"] = 20 + int(stats.get("int", 10)) * 2
    coins = {"gold": 5, "silver": 20, "copper": 50}

    raw_items = STARTER_ITEMS.get(cls, STARTER_ITEMS["fighter"])
    expanded: list[str] = []
    if isinstance(raw_items, list):
        for ent in raw_items:
            if isinstance(ent, str):
                expanded.append(ent)
            elif isinstance(ent, dict):
                slug = ent.get("slug") or ent.get("name") or ent.get("id")
                if slug:
                    qty = max(1, int(ent.get("qty", 1)))
                    expanded.extend([slug] * qty)

    gear_map = auto_equip_for(cls, expanded)
    return {
        "name": name,
        "cls": cls,
        "stats": {**stats, **coins},
        "gear_slugs": expanded,
        "gear_map": gear_map,
    }
