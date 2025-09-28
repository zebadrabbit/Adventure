from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models.models import UserPref

bp_user_prefs = Blueprint("user_prefs", __name__)


@bp_user_prefs.route("/api/prefs/tooltip_mode", methods=["GET"])
@login_required
def get_tooltip_mode():
    val = UserPref.get(current_user.id, "tooltip_mode", "rich")
    return jsonify({"key": "tooltip_mode", "value": val})


@bp_user_prefs.route("/api/prefs/tooltip_mode", methods=["POST"])
@login_required
def set_tooltip_mode():
    data = request.get_json(silent=True) or {}
    mode = (data.get("value") or "").lower()
    if mode not in ("rich", "plain", "off"):
        return jsonify({"error": "invalid mode"}), 400
    UserPref.set(current_user.id, "tooltip_mode", mode)
    return jsonify({"ok": True, "key": "tooltip_mode", "value": mode})
