"""
New modular admin panel routes
"""

import json
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db

# Single admin blueprint (formerly split across bp_admin `/admin` and this one).
# No url_prefix: each route carries its full path so both the legacy `/admin/*`
# paths (hit by JS with hardcoded URLs) and the modular `/admin/v2/*` paths live
# under one blueprint.
bp_admin_new = Blueprint("admin_new", __name__)


def admin_required(f):
    """Decorator to require admin role"""

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated_function


# Default fog configuration
DEFAULT_FOG_CONFIG = {
    "inner_radius": 8,
    "full_radius": 26,
    "min_opacity": 0.18,
    "max_opacity": 0.92,
    "noise": 0.08,
    "memory_opacity": 0.35,
}

# Default dungeon configuration
DEFAULT_DUNGEON_CONFIG = {
    "map_size": 75,
    "room_density": 0.25,
    "monster_density": 0.15,
    "elite_spawn_rate": 0.05,
    "boss_count": 2,
    "loot_density": 0.1,
    "hp_mult_per_tier": 1.15,
    "dmg_mult_per_tier": 1.1,
    "xp_mult_per_tier": 1.25,
    "loot_mult_per_tier": 1.2,
    "early_exit_xp_penalty": 30,
    "early_exit_loot_penalty": 20,
    "full_clear_bonus": 25,
    "flawless_xp_bonus": 25,
    "speed_clear_time": 30,
    "speed_clear_bonus": 50,
    "affixes": {
        "frenzied": True,
        "bolstered": True,
        "volcanic": True,
        "necrotic": True,
        "arcane": True,
        "cursed": True,
    },
}

# Default loot configuration
DEFAULT_LOOT_CONFIG = {
    "base_drop_rate": 0.6,
    "magic_find_mult": 1.0,
    "gold_multiplier": 1.0,
    "rarity_weights": {"common": 600, "uncommon": 250, "rare": 100, "epic": 35, "legendary": 13, "mythic": 2},
    "category_weights": {"weapons": 40, "armor": 30, "consumables": 20, "jewelry": 10},
    "elite_loot_mult": 2.5,
    "boss_loot_mult": 4.0,
    "boss_min_rarity": "rare",
    "boss_cache_size": 3,
    "smart_loot": True,
    "unique_protection": True,
    "level_scaling": True,
}

# Default progression configuration
DEFAULT_PROGRESSION_CONFIG = {
    "max_level": 50,
    "xp_curve_type": "custom",
    "base_xp_mult": 1.0,
    "death_xp_penalty": 10,
    "xp_sources": {"monster_kills": 1.0, "exploration": 1.0, "quests": 1.0, "skill_usage": 1.0, "dungeon_clear": 1.0},
    "talent_frequency": 2,
    "starting_talent_points": 0,
    "respec_cost": 1000,
    "stat_points_per_level": 0,
    "starting_stat_total": 72,
    "max_stat": 20,
    "tier_bonuses": {"early_loot": 1.0, "mid_loot": 1.2, "late_loot": 1.5},
    "level_scaling_enemies": False,
    "party_xp_sharing": True,
    "rest_xp_bonus": False,
    "allow_deleveling": False,
}

# Default combat configuration
DEFAULT_COMBAT_CONFIG = {
    "crit_multiplier": 1.5,
    "base_evasion": 10,
    "damage_variance_pct": 25,
    "min_damage": 1,
    "defend_reduction_pct": 50,
    "flee_base_chance": 60,
    "spell_costs": {"firebolt": 5, "ice_shard": 6, "lightning": 8},
    "spell_int_scaling": 0.6,
    "initiative_bonus": 0,
    "ambush_chance": 20,
    "monster_spell_chance": 30,
    "monster_flee_hp_threshold": 20,
    "monster_help_chance": 15,
    "victory_xp_mult": 1.0,
    "flee_xp_penalty_pct": 50,
    "party_xp_split": "equal",
    "allow_friendly_fire": False,
    "death_saves": False,
    "auto_monster_turns": True,
    "resistance_system": True,
}


def get_fog_config():
    """Get current fog configuration from database or defaults"""
    # For now, return defaults - will implement DB storage next
    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="fog_settings").first()
    if config:
        import json

        return json.loads(config.value)
    return DEFAULT_FOG_CONFIG.copy()


def save_fog_config(config_data):
    """Save fog configuration to database"""
    import json

    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="fog_settings").first()
    if not config:
        config = GameConfig(key="fog_settings", value="")

    config.value = json.dumps(config_data)
    db.session.add(config)
    db.session.commit()


def get_dungeon_config():
    """Get current dungeon configuration from database or defaults"""
    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="dungeon_settings").first()
    if config:
        import json

        return json.loads(config.value)
    return DEFAULT_DUNGEON_CONFIG.copy()


def save_dungeon_config(config_data):
    """Save dungeon configuration to database"""
    import json

    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="dungeon_settings").first()
    if not config:
        config = GameConfig(key="dungeon_settings", value="")

    config.value = json.dumps(config_data)
    db.session.add(config)
    db.session.commit()


def get_loot_config():
    """Get current loot configuration from database or defaults"""
    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="loot_settings").first()
    if config:
        import json

        return json.loads(config.value)
    return DEFAULT_LOOT_CONFIG.copy()


def save_loot_config(config_data):
    """Save loot configuration to database"""
    import json

    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="loot_settings").first()
    if not config:
        config = GameConfig(key="loot_settings", value="")

    config.value = json.dumps(config_data)
    db.session.add(config)
    db.session.commit()


def get_progression_config():
    """Get current progression configuration from database or defaults"""
    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="progression_settings").first()
    if config:
        import json

        return json.loads(config.value)
    return DEFAULT_PROGRESSION_CONFIG.copy()


def save_progression_config(config_data):
    """Save progression configuration to database"""
    import json

    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="progression_settings").first()
    if not config:
        config = GameConfig(key="progression_settings", value="")

    config.value = json.dumps(config_data)
    db.session.add(config)
    db.session.commit()


def get_combat_config():
    """Get current combat configuration from database or defaults"""
    import json

    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key="combat_settings").first()
    if config:
        return json.loads(config.value)
    return DEFAULT_COMBAT_CONFIG.copy()


def save_combat_config(config_data):
    """Save combat configuration to database"""
    import json

    from app.models.models import GameConfig

    # Validate required fields
    required = [
        "crit_multiplier",
        "base_evasion",
        "damage_variance_pct",
        "min_damage",
        "defend_reduction_pct",
        "flee_base_chance",
        "spell_int_scaling",
        "party_xp_split",
    ]
    for field in required:
        if field not in config_data:
            raise ValueError(f"Missing required field: {field}")

    # Validate nested spell_costs
    if "spell_costs" not in config_data or not isinstance(config_data["spell_costs"], dict):
        raise ValueError("spell_costs must be a dictionary")

    config = GameConfig.query.filter_by(key="combat_settings").first()
    if not config:
        config = GameConfig(key="combat_settings", value=json.dumps(config_data))
        db.session.add(config)
    else:
        config.value = json.dumps(config_data)
    db.session.commit()
    return True


# ============================================================================
# GAME SETTINGS ROUTES
# ============================================================================


@bp_admin_new.route("/admin/v2/settings/fog")
@admin_required
def fog_settings():
    """Fog & visibility settings page"""
    fog_config = get_fog_config()
    return render_template("admin/fog_settings.html", fog_config=fog_config)


@bp_admin_new.route("/admin/v2/settings/fog/save", methods=["POST"])
@admin_required
def save_fog_settings():
    """Save fog configuration"""
    try:
        data = request.get_json()

        # Validate data
        required_fields = ["inner_radius", "full_radius", "min_opacity", "max_opacity", "noise", "memory_opacity"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Save to database
        save_fog_config(data)

        return jsonify({"success": True, "message": "Fog settings saved successfully", "config": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/fog/reset", methods=["POST"])
@admin_required
def reset_fog_settings():
    """Reset fog configuration to defaults"""
    try:
        save_fog_config(DEFAULT_FOG_CONFIG.copy())
        return jsonify({"success": True, "message": "Fog settings reset to defaults", "config": DEFAULT_FOG_CONFIG})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/api/fog-config", methods=["GET"])
def get_fog_config_api():
    """Public API to get current fog configuration (no auth required)"""
    try:
        config = get_fog_config()
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/api/server-info", methods=["GET"])
@admin_required
def get_server_info():
    """Get server information (Python version, Flask version, uptime)"""
    import platform
    import sys
    import time

    import flask

    # Calculate uptime (approximation based on module load time)
    try:
        import psutil

        process = psutil.Process()
        uptime_seconds = time.time() - process.create_time()
    except ImportError:
        uptime_seconds = 0

    # Format uptime
    if uptime_seconds > 0:
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = "Unknown"

    return jsonify(
        {
            "success": True,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "flask_version": flask.__version__,
            "uptime": uptime_str,
            "platform": platform.system(),
        }
    )


@bp_admin_new.route("/admin/v2/settings/combat")
@admin_required
def combat_settings():
    """Combat rules settings page"""
    config = get_combat_config()
    return render_template("admin/combat_settings.html", config=config)


@bp_admin_new.route("/admin/v2/settings/combat/save", methods=["POST"])
@admin_required
def save_combat():
    """Save combat configuration"""
    try:
        config_data = request.get_json()
        save_combat_config(config_data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@bp_admin_new.route("/admin/v2/settings/combat/reset", methods=["POST"])
@admin_required
def reset_combat():
    """Reset combat configuration to defaults"""
    try:
        save_combat_config(DEFAULT_COMBAT_CONFIG.copy())
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@bp_admin_new.route("/admin/v2/settings/loot")
@admin_required
def loot_settings():
    """Loot & rewards settings page"""
    config = get_loot_config()
    return render_template("admin/loot_settings.html", config=config)


@bp_admin_new.route("/admin/v2/settings/loot/save", methods=["POST"])
@admin_required
def save_loot_settings():
    """Save loot configuration"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = [
            "base_drop_rate",
            "magic_find_mult",
            "gold_multiplier",
            "elite_loot_mult",
            "boss_loot_mult",
            "boss_min_rarity",
            "boss_cache_size",
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Validate nested objects
        if "rarity_weights" not in data or not isinstance(data["rarity_weights"], dict):
            return jsonify({"error": "Invalid rarity_weights"}), 400

        if "category_weights" not in data or not isinstance(data["category_weights"], dict):
            return jsonify({"error": "Invalid category_weights"}), 400

        # Save to database
        save_loot_config(data)

        return jsonify({"success": True, "message": "Loot settings saved successfully", "config": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/loot/reset", methods=["POST"])
@admin_required
def reset_loot_settings():
    """Reset loot configuration to defaults"""
    try:
        save_loot_config(DEFAULT_LOOT_CONFIG.copy())
        return jsonify({"success": True, "message": "Loot settings reset to defaults", "config": DEFAULT_LOOT_CONFIG})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/dungeon")
@admin_required
def dungeon_settings():
    """Dungeon generation settings page"""
    config = get_dungeon_config()
    return render_template("admin/dungeon_settings.html", config=config)


@bp_admin_new.route("/admin/v2/settings/dungeon/save", methods=["POST"])
@admin_required
def save_dungeon_settings():
    """Save dungeon configuration"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = [
            "map_size",
            "room_density",
            "monster_density",
            "elite_spawn_rate",
            "boss_count",
            "loot_density",
            "hp_mult_per_tier",
            "dmg_mult_per_tier",
            "xp_mult_per_tier",
            "loot_mult_per_tier",
            "early_exit_xp_penalty",
            "early_exit_loot_penalty",
            "full_clear_bonus",
            "flawless_xp_bonus",
            "speed_clear_time",
            "speed_clear_bonus",
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Validate affixes
        if "affixes" not in data or not isinstance(data["affixes"], dict):
            return jsonify({"error": "Invalid affixes"}), 400

        # Save to database
        save_dungeon_config(data)

        return jsonify({"success": True, "message": "Dungeon settings saved successfully", "config": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/dungeon/reset", methods=["POST"])
@admin_required
def reset_dungeon_settings():
    """Reset dungeon configuration to defaults"""
    try:
        save_dungeon_config(DEFAULT_DUNGEON_CONFIG.copy())
        return jsonify(
            {"success": True, "message": "Dungeon settings reset to defaults", "config": DEFAULT_DUNGEON_CONFIG}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/progression")
@admin_required
def progression_settings():
    """Progression & XP settings page"""
    config = get_progression_config()
    return render_template("admin/progression_settings.html", config=config)


@bp_admin_new.route("/admin/v2/settings/progression/save", methods=["POST"])
@admin_required
def save_progression_settings():
    """Save progression configuration"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = [
            "max_level",
            "xp_curve_type",
            "base_xp_mult",
            "death_xp_penalty",
            "talent_frequency",
            "starting_talent_points",
            "respec_cost",
            "stat_points_per_level",
            "starting_stat_total",
            "max_stat",
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Validate nested objects
        if "xp_sources" not in data or not isinstance(data["xp_sources"], dict):
            return jsonify({"error": "Invalid xp_sources"}), 400

        if "tier_bonuses" not in data or not isinstance(data["tier_bonuses"], dict):
            return jsonify({"error": "Invalid tier_bonuses"}), 400

        # Save to database
        save_progression_config(data)

        return jsonify({"success": True, "message": "Progression settings saved successfully", "config": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/settings/progression/reset", methods=["POST"])
@admin_required
def reset_progression_settings():
    """Reset progression configuration to defaults"""
    try:
        save_progression_config(DEFAULT_PROGRESSION_CONFIG.copy())
        return jsonify(
            {"success": True, "message": "Progression settings reset to defaults", "config": DEFAULT_PROGRESSION_CONFIG}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# SERVER MANAGEMENT ROUTES
# ============================================================================


@bp_admin_new.route("/admin/v2/server/status")
@admin_required
def server_status():
    """Server status page"""
    from app.models.dungeon_instance import DungeonInstance
    from app.models.models import (
        Character,
        CombatSession,
        Item,
        MonsterCatalog,
        User,
    )

    stats = {
        "total_users": User.query.count(),
        "total_characters": Character.query.count(),
        "active_sessions": CombatSession.query.filter_by(status="active").count(),
        "total_combats": CombatSession.query.count(),
        "total_items": Item.query.count(),
        "total_monsters": MonsterCatalog.query.count(),
        "dungeons_explored": DungeonInstance.query.count(),
    }
    return render_template("admin/server_status.html", stats=stats)


@bp_admin_new.route("/admin/v2/server/logs")
@admin_required
def logs():
    """Server logs page"""
    return render_template("admin/placeholder.html", page_title="Server Logs", page_description="application logs")


@bp_admin_new.route("/admin/v2/server/database")
@admin_required
def database():
    """Database management page"""
    from app.models.models import Character, GameConfig, Item, MonsterCatalog, User

    tables = {
        "users": User.query.count(),
        "characters": Character.query.count(),
        "items": Item.query.count(),
        "monsters": MonsterCatalog.query.count(),
    }
    configs = GameConfig.query.order_by(GameConfig.key.asc()).all()
    return render_template("admin/database.html", tables=tables, configs=configs)


@bp_admin_new.route("/admin/v2/database/config", methods=["POST"])
@admin_required
def save_config():
    """Save or update game configuration"""
    from app.models.models import GameConfig

    data = request.get_json()
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()

    if not key or not value:
        return jsonify({"error": "Key and value are required"}), 400

    config = GameConfig.query.filter_by(key=key).first()
    if not config:
        config = GameConfig(key=key, value=value)
        db.session.add(config)
    else:
        config.value = value

    db.session.commit()
    return jsonify({"success": True})


@bp_admin_new.route("/admin/v2/database/config/<key>", methods=["DELETE"])
@admin_required
def delete_config(key):
    """Delete game configuration"""
    from app.models.models import GameConfig

    config = GameConfig.query.filter_by(key=key).first()
    if config:
        db.session.delete(config)
        db.session.commit()

    return jsonify({"success": True})


# ============================================================================
# USER MANAGEMENT ROUTES
# ============================================================================


@bp_admin_new.route("/admin/v2/users")
@admin_required
def users():
    """User management page"""
    from app.models.models import User

    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    q = User.query.order_by(User.id.asc())
    total = q.count()
    users_list = q.offset((page - 1) * per_page).limit(per_page).all()
    return render_template("admin/users.html", users=users_list, page=page, per_page=per_page, total=total)


@bp_admin_new.route("/admin/v2/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_user_role(user_id):
    """Update user role"""
    from app.models.models import User

    if user_id == current_user.id:
        return jsonify({"error": "Cannot change your own role"}), 400

    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_role = (data.get("role") or "").lower()

    if new_role not in ("user", "mod", "admin"):
        return jsonify({"error": "Invalid role"}), 400

    user.role = new_role
    db.session.commit()

    return jsonify({"success": True, "id": user.id, "role": user.role})


@bp_admin_new.route("/admin/v2/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    """Ban or unban a user"""
    from app.models.models import User

    if user_id == current_user.id:
        return jsonify({"error": "Cannot ban yourself"}), 400

    user = User.query.get_or_404(user_id)
    data = request.get_json()
    action = (data.get("action") or "").lower()

    if action == "ban":
        user.banned = True
        user.ban_reason = data.get("reason")
    elif action == "unban":
        user.banned = False
        user.ban_reason = None
    else:
        return jsonify({"error": "Invalid action"}), 400

    db.session.commit()
    return jsonify({"success": True, "id": user.id, "banned": user.banned})


@bp_admin_new.route("/admin/v2/users/characters")
@admin_required
def characters():
    """Character management page"""
    return render_template(
        "admin/placeholder.html", page_title="Character Management", page_description="player characters"
    )


@bp_admin_new.route("/admin/v2/users/moderation")
@admin_required
def moderation():
    """Moderation tools page"""
    return render_template("admin/placeholder.html", page_title="Moderation Tools", page_description="user moderation")


# ============================================================================
# TOOLS ROUTES
# ============================================================================


@bp_admin_new.route("/admin/v2/tools/seed")
@admin_required
def seed_data():
    """Seed data tools page"""
    return render_template("admin/seed_data.html")


@bp_admin_new.route("/admin/v2/tools/seed/<seed_type>", methods=["POST"])
@admin_required
def run_seed(seed_type):
    """Run SQL seed scripts"""

    if seed_type not in ("items", "monsters"):
        return jsonify({"error": "Invalid seed type"}), 400

    try:
        # Map seed type to SQL file
        sql_files = {
            "items": ["items_potions.sql", "items_misc.sql"],
            "monsters": ["monsters_seed.sql"],
        }

        if seed_type not in sql_files:
            return jsonify({"error": "No SQL files for this seed type"}), 400

        results = []
        for sql_file in sql_files[seed_type]:
            sql_path = f"sql/{sql_file}"
            # This is a placeholder - actual implementation would run the SQL
            results.append(f"Would run: {sql_path}")

        return jsonify(
            {"success": True, "message": f"{seed_type.title()} seed completed", "details": {"results": results}}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp_admin_new.route("/admin/v2/tools/debug")
@admin_required
def debug():
    """Debug tools page"""
    return render_template("admin/placeholder.html", page_title="Debug Tools", page_description="debugging utilities")


# ============================================================================
# LEGACY ADMIN ROUTES (folded in from the former bp_admin `/admin` blueprint).
# Paths are preserved exactly (JS posts to /admin/items & /admin/monsters by
# hardcoded URL; templates use url_for with the new admin_new.* endpoint names).
# ============================================================================


@bp_admin_new.route("/admin/")
@admin_required
def dashboard():
    """Admin landing page - redirect to modular admin panel."""
    return redirect(url_for("admin_new.fog_settings"))


@bp_admin_new.route("/admin/themes")
@admin_required
def themes():
    """Theme management page."""
    return render_template("admin_themes.html")


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


@bp_admin_new.route("/admin/items", methods=["GET", "POST"])
@admin_required
def items():
    """List items; on POST handle CSV upload with validation & atomic upsert."""
    from app.models.models import Item

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


@bp_admin_new.route("/admin/monsters", methods=["GET", "POST"])
@admin_required
def monsters():
    from app.models.models import MonsterCatalog

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


# ----------------------------- Game Rules ---------------------------------


@bp_admin_new.route("/admin/game-rules", methods=["GET", "POST"])
@admin_required
def game_rules():
    """Manage gameplay modifiers and difficulty settings."""
    from app.models.models import GameConfig

    if request.method == "POST":
        # Define all the game rule parameters
        rules = {
            "xp_multiplier": float(request.form.get("xp_multiplier", 1.0)),
            "gold_multiplier": float(request.form.get("gold_multiplier", 1.0)),
            "loot_drop_multiplier": float(request.form.get("loot_drop_multiplier", 1.0)),
            "monster_hp_multiplier": float(request.form.get("monster_hp_multiplier", 1.0)),
            "monster_damage_multiplier": float(request.form.get("monster_damage_multiplier", 1.0)),
            "fog_density": float(request.form.get("fog_density", 0.0)),
            "vision_range": int(request.form.get("vision_range", 10)),
            "rest_heal_percent": float(request.form.get("rest_heal_percent", 50.0)),
            "skill_check_difficulty": int(request.form.get("skill_check_difficulty", 13)),
            "critical_hit_multiplier": float(request.form.get("critical_hit_multiplier", 2.0)),
            "death_penalty_percent": float(request.form.get("death_penalty_percent", 10.0)),
        }

        # Save to database
        for key, value in rules.items():
            row = GameConfig.query.filter_by(key=f"game_rules.{key}").first()
            if not row:
                row = GameConfig(key=f"game_rules.{key}", value=json.dumps(value))
                db.session.add(row)
            else:
                row.value = json.dumps(value)

        db.session.commit()
        flash("Game rules updated successfully!", "success")
        return redirect(url_for("admin_new.game_rules"))

    # Load current values from database
    def get_rule(key, default):
        row = GameConfig.query.filter_by(key=f"game_rules.{key}").first()
        if row:
            try:
                return json.loads(row.value)
            except (json.JSONDecodeError, ValueError):
                return default
        return default

    rules = {
        "xp_multiplier": get_rule("xp_multiplier", 1.0),
        "gold_multiplier": get_rule("gold_multiplier", 1.0),
        "loot_drop_multiplier": get_rule("loot_drop_multiplier", 1.0),
        "monster_hp_multiplier": get_rule("monster_hp_multiplier", 1.0),
        "monster_damage_multiplier": get_rule("monster_damage_multiplier", 1.0),
        "fog_density": get_rule("fog_density", 0.0),
        "vision_range": get_rule("vision_range", 10),
        "rest_heal_percent": get_rule("rest_heal_percent", 50.0),
        "skill_check_difficulty": get_rule("skill_check_difficulty", 13),
        "critical_hit_multiplier": get_rule("critical_hit_multiplier", 2.0),
        "death_penalty_percent": get_rule("death_penalty_percent", 10.0),
    }

    return render_template("admin_game_rules.html", rules=rules)
