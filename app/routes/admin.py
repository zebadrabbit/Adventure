"""Admin routes: protected management views & CSV import endpoints.

Provides a small, opinionated admin surface for:
  * Users (list / promote / ban) – pending
  * Game configuration key/values – pending
  * Item catalog listing & CSV import – pending
  * Monster catalog listing & CSV import – pending

Security model:
  * All routes require an authenticated user with role == 'admin'.
  * A lightweight decorator enforces this and returns 403 JSON for API style
    requests (Accept: application/json) or redirects to login/dashboard for
    normal browser navigation.

CSV Import Philosophy:
  Endpoints will accept a single text/csv upload (UTF-8). The server will:
    1. Parse headers, ensure required columns present.
    2. Validate each row (non-empty slug/name/type/etc.).
    3. Accumulate validation errors; if any, show a structured report and do
       NOT write partial rows.
    4. On success, perform an upsert style insert (existing rows matched by
       slug updated, new rows inserted) inside a single transaction.

This file currently only establishes the blueprint & dashboard shell; feature
routes will be added in subsequent patches.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models.models import GameConfig, Item, MonsterCatalog, User

bp_admin = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(fn: Callable):
    """Decorator enforcing that current_user is authenticated admin.

    Behavior:
      * If user not logged in -> redirect to login (HTML) or 401 JSON.
      * If user not admin -> 403 (HTML or JSON) to avoid leaking existence.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        if not current_user.is_authenticated:
            if wants_json:
                return {"error": "unauthorized"}, 401
            return redirect(url_for("auth.login"))
        if getattr(current_user, "role", "user") != "admin":
            if wants_json:
                return {"error": "forbidden"}, 403
            abort(403)
        return fn(*args, **kwargs)

    return login_required(wrapper)  # also stacks login_required for session refresh


@bp_admin.route("/")
@admin_required
def dashboard():
    """Admin landing page.

    Provides quick links to user management, config, items & monsters. Will
    later display recent import activity & basic stats.
    """

    return render_template("admin_dashboard.html")


# ----------------------------- Items --------------------------------------

REQUIRED_ITEM_COLUMNS = [
    "slug",
    "name",
    "type",
    "description",
    "value_copper",
    "level",
    "rarity",
]


def _parse_csv(stream, required_cols):
    """Parse a CSV file-like object into list[dict].

    Returns (rows, errors:list[str]). Ensures headers contain required columns.
    """
    import csv
    import io

    errors = []
    # Read raw bytes, decode as utf-8 with replacement to avoid hard failure
    raw = stream.read()
    MAX_CSV_BYTES = 500_000  # ~500 KB safety guard
    if isinstance(raw, (bytes, bytearray)) and len(raw) > MAX_CSV_BYTES:
        errors.append(f"File too large ({len(raw)} bytes > {MAX_CSV_BYTES} byte limit)")
        return [], errors
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", "replace")
        except Exception:
            text = raw.decode("utf-8", "ignore")
    else:
        text = raw
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sio = io.StringIO(text)
    # Sniff dialect optionally (fallback to excel)
    try:
        sample = text[:1024]
        dialect = csv.Sniffer().sniff(sample)
    except Exception:
        dialect = csv.excel
    reader = csv.DictReader(sio, dialect=dialect)
    headers = [h.strip() for h in (reader.fieldnames or []) if h]
    missing = [c for c in required_cols if c not in headers]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return [], errors
    rows = []
    for idx, row in enumerate(reader, start=2):  # header line = 1
        # Skip empty row (all values blank)
        if not any((v or "").strip() for v in row.values()):
            continue
        norm = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        norm["__line__"] = idx
        rows.append(norm)
        if len(rows) > 5000:  # hard cap to prevent accidental huge imports
            errors.append("Row limit exceeded (5000). Trim file and retry.")
            break
    if not rows:
        errors.append("No data rows found in CSV")
    return rows, errors


def _validate_item_rows(rows):
    """Return list[str] of validation errors for item rows."""
    errors = []
    seen_slugs = set()
    allowed_rarity = {"common", "uncommon", "rare", "epic", "legendary", "mythic"}
    for r in rows:
        line = r.get("__line__", "?")
        slug = r.get("slug") or ""
        name = r.get("name") or ""
        itype = r.get("type") or ""
        rarity = (r.get("rarity") or "").lower()
        # Required basics
        if not slug:
            errors.append(f"Line {line}: slug is required")
        else:
            if " " in slug:
                errors.append(f"Line {line}: slug must not contain spaces")
            if slug in seen_slugs:
                errors.append(f"Line {line}: duplicate slug '{slug}' in file")
            seen_slugs.add(slug)
        if not name:
            errors.append(f"Line {line}: name is required")
        if not itype:
            errors.append(f"Line {line}: type is required")
        # Numeric fields
        for fld in ("value_copper", "level"):
            raw = r.get(fld)
            if raw in (None, ""):
                errors.append(f"Line {line}: {fld} is required")
                continue
            try:
                val = int(raw)
            except Exception:
                errors.append(f"Line {line}: {fld} must be integer (got '{raw}')")
                continue
            if val < 0:
                errors.append(f"Line {line}: {fld} must be >= 0")
        if rarity not in allowed_rarity:
            errors.append(f"Line {line}: rarity '{rarity}' not in {sorted(allowed_rarity)}")
        # Optional weight
        w_raw = r.get("weight")
        if w_raw not in (None, ""):
            try:
                float(w_raw)
            except Exception:
                errors.append(f"Line {line}: weight must be numeric if provided")
    return errors


@bp_admin.route("/items", methods=["GET", "POST"])
@admin_required
def items():
    """List items; on POST handle CSV upload with validation & atomic upsert."""
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return render_template("admin_items.html", errors=["No file uploaded"], imported=None, rows=[])
        rows, parse_errors = _parse_csv(file, REQUIRED_ITEM_COLUMNS)
        if parse_errors:
            return render_template("admin_items.html", errors=parse_errors, imported=None, rows=[])
        val_errors = _validate_item_rows(rows)
        if val_errors:
            return render_template("admin_items.html", errors=val_errors, imported=None, rows=rows)
        # Apply transaction
        changed = 0
        try:
            for r in rows:
                slug = r["slug"]
                obj = Item.query.filter_by(slug=slug).first()
                if not obj:
                    obj = Item(slug=slug)
                    db.session.add(obj)
                obj.name = r["name"]
                obj.type = r["type"]
                obj.description = r.get("description") or ""
                obj.value_copper = int(r["value_copper"])
                obj.level = int(r["level"])
                obj.rarity = (r.get("rarity") or "common").lower()
                w_raw = r.get("weight")
                if w_raw not in (None, ""):
                    try:
                        obj.weight = float(w_raw)
                    except Exception:
                        pass
                changed += 1
            db.session.commit()
            return render_template("admin_items.html", errors=[], imported=changed, rows=[])
        except Exception as e:  # pragma: no cover - defensive
            db.session.rollback()
            return render_template("admin_items.html", errors=[f"Database error: {e}"], imported=None, rows=rows)
    # GET
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    items_query = Item.query.order_by(Item.id.asc())
    total = items_query.count()
    rows = items_query.offset((page - 1) * per_page).limit(per_page).all()
    return render_template(
        "admin_items.html",
        errors=[],
        imported=None,
        rows=[],  # only show preview rows after failed validation; normal listing separate var
        items=rows,
        page=page,
        per_page=per_page,
        total=total,
    )


# ----------------------------- Monsters -----------------------------------

REQUIRED_MONSTER_COLUMNS = [
    "slug",
    "name",
    "level_min",
    "level_max",
    "base_hp",
    "base_damage",
    "armor",
    "speed",
    "rarity",
    "family",
    "xp_base",
]


def _validate_monster_rows(rows):
    errors = []
    seen = set()
    allowed_rarity = {"common", "uncommon", "rare", "elite", "boss", "epic", "legendary", "mythic"}
    for r in rows:
        line = r.get("__line__", "?")
        slug = r.get("slug") or ""
        if not slug:
            errors.append(f"Line {line}: slug required")
        else:
            if slug in seen:
                errors.append(f"Line {line}: duplicate slug '{slug}' in file")
            seen.add(slug)
        name = r.get("name") or ""
        if not name:
            errors.append(f"Line {line}: name required")
        rarity = (r.get("rarity") or "").lower()
        if rarity not in allowed_rarity:
            errors.append(f"Line {line}: rarity '{rarity}' invalid (allowed {sorted(allowed_rarity)})")
        fam = r.get("family") or ""
        if not fam:
            errors.append(f"Line {line}: family required")
        # Numeric ints
        for fld in ("level_min", "level_max", "base_hp", "base_damage", "armor", "speed", "xp_base"):
            raw = r.get(fld)
            if raw in (None, ""):
                errors.append(f"Line {line}: {fld} required")
                continue
            try:
                val = int(raw)
            except Exception:
                errors.append(f"Line {line}: {fld} must be integer (got '{raw}')")
                continue
            if val < 0:
                errors.append(f"Line {line}: {fld} must be >= 0")
        try:
            lmin = int(r.get("level_min", 1))
            lmax = int(r.get("level_max", 1))
            if lmax < lmin:
                errors.append(f"Line {line}: level_max < level_min")
        except Exception:
            pass
        # Optional boolean boss
        b_raw = (r.get("boss") or "").strip().lower()
        if b_raw and b_raw not in ("0", "1", "true", "false", "yes", "no"):
            errors.append(f"Line {line}: boss must be boolean-ish (0/1/true/false/yes/no)")
    return errors


@bp_admin.route("/monsters", methods=["GET", "POST"])
@admin_required
def monsters():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return render_template("admin_monsters.html", errors=["No file uploaded"], imported=None, rows=[])
        rows, parse_errors = _parse_csv(file, REQUIRED_MONSTER_COLUMNS)
        if parse_errors:
            return render_template("admin_monsters.html", errors=parse_errors, imported=None, rows=[])
        val_errors = _validate_monster_rows(rows)
        if val_errors:
            return render_template("admin_monsters.html", errors=val_errors, imported=None, rows=rows)
        changed = 0
        try:
            for r in rows:
                slug = r["slug"]
                obj = MonsterCatalog.query.filter_by(slug=slug).first()
                if not obj:
                    obj = MonsterCatalog(slug=slug)
                    db.session.add(obj)
                obj.name = r["name"]
                obj.level_min = int(r["level_min"])
                obj.level_max = int(r["level_max"])
                obj.base_hp = int(r["base_hp"])
                obj.base_damage = int(r["base_damage"])
                obj.armor = int(r["armor"])
                obj.speed = int(r["speed"])
                obj.rarity = (r.get("rarity") or "common").lower()
                obj.family = r.get("family") or "neutral"
                obj.traits = r.get("traits") or None
                obj.loot_table = r.get("loot_table") or None
                obj.special_drop_slug = r.get("special_drop_slug") or None
                obj.xp_base = int(r["xp_base"])
                b_raw = (r.get("boss") or "").strip().lower()
                if b_raw in ("1", "true", "yes"):
                    obj.boss = True
                elif b_raw in ("0", "false", "no"):
                    obj.boss = False
                # Optional resistances/damage_types columns
                if r.get("resistances"):
                    obj.resistances = r.get("resistances")
                if r.get("damage_types"):
                    obj.damage_types = r.get("damage_types")
                changed += 1
            db.session.commit()
            return render_template("admin_monsters.html", errors=[], imported=changed, rows=[])
        except Exception as e:  # pragma: no cover
            db.session.rollback()
            return render_template("admin_monsters.html", errors=[f"Database error: {e}"], imported=None, rows=rows)
    # GET listing
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    q = MonsterCatalog.query.order_by(MonsterCatalog.id.asc())
    total = q.count()
    monsters = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template(
        "admin_monsters.html",
        errors=[],
        imported=None,
        rows=[],
        monsters=monsters,
        page=page,
        per_page=per_page,
        total=total,
    )


# Placeholder routes (to be implemented in follow-up patches):
# /admin/game-config (GET/POST)
# Additional user management endpoints below

# ----------------------------- Users --------------------------------------


@bp_admin.route("/users")
@admin_required
def users():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    q = User.query.order_by(User.id.asc())
    total = q.count()
    users = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("admin_users.html", users=users, page=page, per_page=per_page, total=total)


def _json_wants():
    return "application/json" in (request.headers.get("Accept") or "")


@bp_admin.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_user_role(user_id):
    if user_id == current_user.id:
        return ({"error": "cannot change own role"}, 400) if _json_wants() else (redirect(url_for("admin.users")))
    user = User.query.get_or_404(user_id)
    new_role = (request.form.get("role") or request.json.get("role") if request.is_json else None) or ""
    new_role = new_role.lower()
    if new_role not in ("user", "mod", "admin"):
        return ({"error": "invalid role"}, 400) if _json_wants() else (redirect(url_for("admin.users")))
    user.role = new_role
    db.session.commit()
    if _json_wants():
        return {"status": "ok", "id": user.id, "role": user.role}
    return redirect(url_for("admin.users"))


# ----------------------------- Game Config --------------------------------


@bp_admin.route("/game-config", methods=["GET", "POST"])
@admin_required
def game_config():
    if request.method == "POST":
        key = (request.form.get("key") or "").strip()
        value = (request.form.get("value") or "").strip()
        if key and value:
            # Store raw string (caller should ensure JSON shape if JSON semantics expected)
            row = GameConfig.query.filter_by(key=key).first()
            if not row:
                row = GameConfig(key=key, value=value)
                db.session.add(row)
            else:
                row.value = value
            db.session.commit()
        return redirect(url_for("admin.game_config"))
    rows = GameConfig.query.order_by(GameConfig.key.asc()).all()
    return render_template("admin_game_config.html", rows=rows)


@bp_admin.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    if user_id == current_user.id:
        return ({"error": "cannot ban self"}, 400) if _json_wants() else (redirect(url_for("admin.users")))
    user = User.query.get_or_404(user_id)
    action = (request.form.get("action") or request.json.get("action") if request.is_json else "") or "ban"
    action = action.lower()
    if action == "ban":
        user.banned = True
        user.ban_reason = request.form.get("reason") or (request.json.get("reason") if request.is_json else None)
    elif action == "unban":
        user.banned = False
        user.ban_reason = None
    else:
        return ({"error": "invalid action"}, 400) if _json_wants() else (redirect(url_for("admin.users")))
    db.session.commit()
    if _json_wants():
        return {"status": "ok", "id": user.id, "banned": user.banned, "ban_reason": user.ban_reason}
    return redirect(url_for("admin.users"))
