"""
project: Adventure MUD
module: dashboard.py
https://github.com/zebadrabbit/Adventure
License: MIT

Dashboard and character management routes for Adventure MUD.

This module provides the dashboard view, character creation, party selection,
autofill, and character deletion logic. All routes require authentication.
"""

import json

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models.models import Character, User
from app.models.xp import xp_for_level

bp_dashboard = Blueprint("dashboard", __name__)


# Ensure authentication is rehydrated from session IDs for this blueprint to avoid
# intermittent AnonymousUser during test client context switches.
@bp_dashboard.before_request
def _rehydrate_login_from_session():
    try:
        if not current_user.is_authenticated:
            uid = session.get("_user_id") or session.get("user_id")
            if uid is not None:
                try:
                    uid_int = int(uid)
                except (TypeError, ValueError):
                    uid_int = None
                if uid_int is not None:
                    user = db.session.get(User, uid_int)
                    if user is not None:
                        from flask_login import login_user

                        login_user(user, remember=False)
    except Exception:
        # Non-fatal; fall through to normal @login_required handling
        pass


@bp_dashboard.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """
    Display the user's characters and handle character creation and party selection.

    GET: Show all characters for the current user, with class, stats, and inventory.
    POST: Handle character creation, party selection, email/password update, and adventure start.
    """
    import random

    # POST: handle form submissions
    if request.method == "POST":
        # Defensive: capture a stable user id even if the underlying SQLAlchemy instance
        # becomes detached between test requests. Instead of force-logging the user out
        # (which caused a regression where subsequent API calls received 302 redirects),
        # fall back to the session stored _user_id / user_id value when possible.
        current_user_id = None
        try:  # happy path: attached user object
            current_user_id = getattr(current_user, "id", None)
        except Exception:  # detached or other access error
            current_user_id = None
        if current_user_id is None:
            # Fallback to session keys used by flask-login / our tests
            sid = session.get("_user_id") or session.get("user_id")
            if sid is not None:
                try:
                    current_user_id = int(sid)
                except (TypeError, ValueError):
                    current_user_id = None
        if current_user_id is None:
            # As a last resort, redirect to login (rare)
            from flask_login import logout_user

            logout_user()
            return redirect(url_for("auth.login"))
        form_type = request.form.get("form")
        if form_type == "update_email":
            new_email = request.form.get("email", "").strip() or None
            if new_email and ("@" not in new_email or "." not in new_email):
                flash("Please enter a valid email address.", "warning")
            else:
                user = db.session.get(User, current_user_id)
                user.email = new_email
                db.session.commit()
                flash("Email updated." if new_email else "Email cleared.")
            return redirect(url_for("dashboard.dashboard"))
        elif form_type == "change_password":
            from werkzeug.security import check_password_hash, generate_password_hash

            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not new_pw or len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "warning")
                return redirect(url_for("dashboard.dashboard"))
            if new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "warning")
                return redirect(url_for("dashboard.dashboard"))
            user = db.session.get(User, current_user_id)
            if not check_password_hash(user.password, current_pw):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("dashboard.dashboard"))
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            flash("Password changed successfully.")
            return redirect(url_for("dashboard.dashboard"))
        elif form_type == "start_adventure":
            # Preserve existing dungeon seed & instance if already set via /api/dungeon/seed.
            # Only clear transient non-persistent structures.
            session.pop("party", None)
            session.pop("dungeon", None)
            session.pop("dungeon_pos", None)
            ids = request.form.getlist("party_ids")
            try:
                party_ids = list({int(i) for i in ids})
            except ValueError:
                party_ids = []
            if not (1 <= len(party_ids) <= 4):
                msg = "Select between 1 and 4 characters"
                flash(msg, "warning")
                # Inline render the dashboard so the validation text is present in this response
                characters = Character.query.filter_by(user_id=current_user_id).all()
                char_list = []
                for c in characters:
                    stats = json.loads(c.stats)
                    coins = {k: stats.get(k, 0) for k in ("gold", "silver", "copper")}
                    class_name = (stats.get("class") or "unknown").capitalize()
                    # Minimal inventory expansion for inline path
                    try:
                        raw_items = json.loads(c.items) if c.items else []
                    except Exception:
                        raw_items = []
                    inventory = []
                    if raw_items and isinstance(raw_items, list):
                        from app.models.models import Item

                        if raw_items and isinstance(raw_items[0], dict):
                            slugs = [o.get("slug") for o in raw_items if isinstance(o, dict)]
                        else:
                            slugs = [s for s in raw_items if isinstance(s, str)]
                        if slugs:
                            db_items = Item.query.filter(Item.slug.in_(slugs)).all()
                            by_slug = {i.slug: i for i in db_items}
                            for slug in slugs:
                                it = by_slug.get(slug)
                                if it:
                                    inventory.append(
                                        {
                                            "slug": it.slug,
                                            "name": it.name,
                                            "type": it.type,
                                            "qty": 1,
                                        }
                                    )
                    stats_copy = {k: v for k, v in stats.items() if k not in ("gold", "silver", "copper", "class")}
                    char_list.append(
                        {
                            "id": c.id,
                            "name": c.name,
                            "stats": stats_copy,
                            "coins": coins,
                            "inventory": inventory,
                            "class_name": class_name,
                            "xp": getattr(c, "xp", 0),
                            "level": getattr(c, "level", 1),
                            "xp_next": xp_for_level(getattr(c, "level", 1) + 1),
                        }
                    )
                dungeon_seed = session.get("dungeon_seed", "")
                user_email = (
                    db.session.get(User, current_user_id).email if db.session.get(User, current_user_id) else None
                )
                return render_template(
                    "dashboard.html",
                    characters=char_list,
                    user_email=user_email,
                    dungeon_seed=dungeon_seed,
                    validation_error=msg,
                )
            chars = Character.query.filter(Character.id.in_(party_ids), Character.user_id == current_user_id).all()
            if len(chars) != len(party_ids):
                flash("One or more selected characters are invalid.", "danger")
                return redirect(url_for("dashboard.dashboard"))
            party = []
            for c in chars:
                s = json.loads(c.stats)
                cls = s.get("class") or "unknown"
                party.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "class": cls.capitalize(),
                        "hp": s.get("hp", 0),
                        "mana": s.get("mana", 0),
                    }
                )
            session["party"] = party
            from app.models.dungeon_instance import DungeonInstance

            seed = session.get("dungeon_seed")
            dungeon_instance_id = session.get("dungeon_instance_id")
            instance = None
            if dungeon_instance_id:
                instance = db.session.get(DungeonInstance, dungeon_instance_id)
            if instance is None:
                # If no existing instance (user never touched seed widget/API), fallback to random seed here.
                import random

                seed = seed or random.randint(1, 1_000_000)
                instance = DungeonInstance(user_id=current_user_id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
                db.session.add(instance)
                db.session.commit()
                session["dungeon_instance_id"] = instance.id
                session["dungeon_seed"] = instance.seed
            return redirect(url_for("dungeon.adventure"))
        # Default: character creation form
        name = request.form["name"]
        char_class = request.form["char_class"]
        from app.routes.main import BASE_STATS, STARTER_ITEMS

        stats = BASE_STATS.get(char_class, BASE_STATS["fighter"])
        coins = {"gold": 5, "silver": 20, "copper": 50}
        items = STARTER_ITEMS.get(char_class, STARTER_ITEMS["fighter"])
        character = Character(
            user_id=current_user_id,
            name=name,
            stats=json.dumps({**stats, **coins, "class": char_class}),
            gear=json.dumps({}),
            items=json.dumps(items),
            xp=0,
            level=1,
        )
        db.session.add(character)
        db.session.commit()
        flash(f"Character {name} the {char_class} created!")
        return redirect(url_for("dashboard.dashboard"))
    # GET: show dashboard
    # Robust user id resolution (mirrors POST path) to avoid losing flash messages
    uid = None
    try:
        uid = getattr(current_user, "id", None)
    except Exception:
        uid = None
    if uid is None:
        sid = session.get("_user_id") or session.get("user_id")
        try:
            uid = int(sid) if sid is not None else None
        except (TypeError, ValueError):
            uid = None
    if uid is None:
        from flask_login import logout_user

        logout_user()
        return redirect(url_for("auth.login"))
    characters = Character.query.filter_by(user_id=uid).all()
    # Provide a resilient classification map that tolerates legacy / partial stat dicts.
    # Missing keys are treated as 0 via .get(). This prevents KeyError after server restarts
    # when a user directly refreshes /dashboard with characters created under older schemas
    # or manually modified rows.
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
    char_list = []
    _backfilled = False
    for c in characters:
        stats = json.loads(c.stats)
        # Normalize missing primary stats to 0 to avoid KeyError during classification.
        # This does not mutate DB unless we backfill class below; it's purely defensive.
        for _k in ("str", "dex", "int", "wis", "con", "cha", "hp", "mana"):
            stats.setdefault(_k, 0)
        stats_class = stats.pop("class", None)
        coins = {
            "gold": stats.pop("gold", 0),
            "silver": stats.pop("silver", 0),
            "copper": stats.pop("copper", 0),
        }
        # Inventory (supports legacy list-of-slugs & new stacked list-of-objects)
        from app.models.models import Item

        try:
            raw_items = json.loads(c.items) if c.items else []
        except Exception:
            raw_items = []
        # Determine representation
        stacked = []
        if raw_items and isinstance(raw_items, list) and raw_items and isinstance(raw_items[0], dict):
            # Already stacked format
            stacked = raw_items
        elif isinstance(raw_items, list):
            # Legacy list of slugs -> aggregate
            agg = {}
            for slug in raw_items:
                if isinstance(slug, str):
                    agg[slug] = agg.get(slug, 0) + 1
            stacked = [{"slug": s, "qty": q} for s, q in agg.items()]
            if stacked:
                try:
                    c.items = json.dumps(stacked)
                    _backfilled = True
                except Exception:
                    pass
        slugs_needed = [o["slug"] for o in stacked]
        db_items = Item.query.filter(Item.slug.in_(slugs_needed)).all() if slugs_needed else []
        by_slug = {i.slug: i for i in db_items}
        inventory = []
        for obj in stacked:
            it = by_slug.get(obj["slug"])
            if not it:
                continue
            inventory.append(
                {
                    "slug": it.slug,
                    "name": it.name,
                    "type": it.type,
                    "qty": obj.get("qty", 1),
                }
            )
        if stats_class:
            class_name = stats_class.capitalize()
        else:
            # Use current inventory slugs (from stacked representation) for heuristic class inference
            inv_slugs = {obj["slug"] for obj in stacked}
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
            _backfilled = True
        char_list.append(
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
    if _backfilled:
        db.session.commit()
    user_email = None
    try:
        user_obj = db.session.get(User, current_user.id)
        user_email = getattr(user_obj, "email", None)
    except Exception:
        user_email = None
    # Pre-fill dungeon seed if present in session
    dungeon_seed = session.get("dungeon_seed", "")
    return render_template(
        "dashboard.html",
        characters=char_list,
        user_email=user_email,
        dungeon_seed=dungeon_seed,
    )


@bp_dashboard.route("/delete_character/<int:char_id>", methods=["POST"])
def delete_character(char_id):
    """Delete a character by id and redirect to dashboard."""
    from flask_login import current_user

    from app.models.models import Character

    c = Character.query.filter_by(id=char_id, user_id=current_user.id).first()
    if c:
        from app import db

        db.session.delete(c)
        db.session.commit()
        from flask import flash

        flash(f"Character {c.name} deleted.", "info")
    else:
        from flask import flash

        flash("Character not found or not yours.", "warning")
    from flask import redirect, url_for

    return redirect(url_for("dashboard.dashboard"))


# Route to autofill party with random characters if user has fewer than 4
# POST /autofill_characters
# Returns: {"created": <number>}
@bp_dashboard.route("/autofill_characters", methods=["POST"])
@login_required
def autofill_characters():
    """Autofill the user's roster up to 4 characters with random class/name.

    Response JSON:
        { "created": <int>, "total": <int>, "characters": [ {id,name,class,level}, ... ] }
    Status Codes:
        201 when one or more characters were created
        200 when no creation was necessary (already had 4)
    """
    # Explicit guard (in addition to @login_required) to defend against any test that toggles LOGIN_DISABLED
    if not current_user.is_authenticated or not session.get("_user_id"):
        # If this looks like an AJAX/fetch request prefer JSON 401, else redirect
        wants_json = request.headers.get("X-Requested-With") == "fetch" or "application/json" in (
            request.headers.get("Accept") or ""
        )
        if wants_json:
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("auth.login"))
    current_user_id = current_user.id

    import json as _json
    import random

    from app.routes.main import BASE_STATS, NAME_POOLS, STARTER_ITEMS

    existing = Character.query.filter_by(user_id=current_user_id).all()
    needed = max(0, 4 - len(existing))
    created = []
    if needed:
        classes = list(BASE_STATS.keys())
        for _ in range(needed):
            cls = random.choice(classes)
            # Pick a name from pool; if exhausted or missing, synthesize one
            pool = NAME_POOLS.get(cls, [])
            base_name = random.choice(pool) if pool else cls.capitalize()
            # Add a short randomized suffix to avoid accidental duplicates
            suffix = random.randint(100, 999)
            name = f"{base_name}{suffix}"
            # Ensure uniqueness for this user (retry a few times if collision)
            attempts = 0
            while attempts < 5 and (any(c.name == name for c in existing) or any(c.name == name for c in created)):
                suffix = random.randint(100, 999)
                name = f"{base_name}{suffix}"
                attempts += 1
            stats = BASE_STATS.get(cls, BASE_STATS["fighter"])
            coins = {"gold": 5, "silver": 20, "copper": 50}
            # Normalize starter items: may be list of slugs OR list of {slug, qty}
            raw_items = STARTER_ITEMS.get(cls, STARTER_ITEMS["fighter"])
            norm = []  # list of {'slug': str, 'qty': int}
            if isinstance(raw_items, list):
                for ent in raw_items:
                    if isinstance(ent, str):
                        norm.append({"slug": ent, "qty": 1})
                    elif isinstance(ent, dict):
                        slug = ent.get("slug") or ent.get("name") or ent.get("id")
                        if slug:
                            try:
                                qty = int(ent.get("qty", 1))
                            except Exception:
                                qty = 1
                            if qty < 1:
                                qty = 1
                            norm.append({"slug": slug, "qty": qty})
            # Store as simple list of slugs (expanded) for backward compatibility with legacy code/tests
            expanded_slugs = []
            for obj in norm:
                expanded_slugs.extend([obj["slug"]] * obj["qty"])
            items = expanded_slugs
            character = Character(
                user_id=current_user_id,
                name=name,
                stats=_json.dumps({**stats, **coins, "class": cls}),
                gear=_json.dumps({}),
                items=_json.dumps(items),
                xp=0,
                level=1,
            )
            db.session.add(character)
            created.append(character)
        db.session.commit()
        existing.extend(created)

    # Prepare response payload
    payload_chars = []
    from app.models.models import Item

    for c in existing:
        try:
            s = json.loads(c.stats)
        except Exception:
            s = {}
        coins = {k: s.get(k, 0) for k in ("gold", "silver", "copper")}
        cls_name = (s.get("class") or "unknown").capitalize()
        # Inventory expansion
        try:
            raw_inv = json.loads(c.items) if c.items else []
        except Exception:
            raw_inv = []
        # Flatten any structured entries back into pure slug list
        item_slugs = []
        if isinstance(raw_inv, list):
            for ent in raw_inv:
                if isinstance(ent, str):
                    item_slugs.append(ent)
                elif isinstance(ent, dict):
                    slug = ent.get("slug") or ent.get("name") or ent.get("id")
                    if slug:
                        try:
                            qty = int(ent.get("qty", 1))
                        except Exception:
                            qty = 1
                        if qty < 1:
                            qty = 1
                        item_slugs.extend([slug] * qty)
        items = []
        if item_slugs:
            db_items = Item.query.filter(Item.slug.in_(item_slugs)).all()
            by_slug = {i.slug: i for i in db_items}
            for slug in item_slugs:
                it = by_slug.get(slug)
                if it:
                    items.append({"slug": it.slug, "name": it.name, "type": it.type})
        # Remove coin/class keys from stats copy for clarity
        stats_copy = {k: v for k, v in s.items() if k not in ("gold", "silver", "copper", "class")}
        payload_chars.append(
            {
                "id": c.id,
                "name": c.name,
                "class": cls_name,
                "level": getattr(c, "level", 1),
                "coins": coins,
                "stats": stats_copy,
                "inventory": items,
            }
        )
    status = 201 if created else 200
    return (
        jsonify(
            {
                "created": len(created),
                "total": len(existing),
                "characters": payload_chars,
            }
        ),
        status,
    )


# Route to delete a character by id (POST)
# POST /delete_character/<int:char_id>
# Redirects to dashboard after deletion

# Add other dashboard/character management routes here

# Add other dashboard/character management routes here
