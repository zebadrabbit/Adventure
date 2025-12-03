"""Theme management API routes."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models.theme import Theme
from app.routes.admin import admin_required

bp_theme = Blueprint("theme", __name__, url_prefix="/api/admin/themes")


@bp_theme.route("", methods=["GET"])
@login_required
@admin_required
def list_themes():
    """Get all themes."""
    themes = Theme.query.order_by(Theme.is_active.desc(), Theme.name).all()
    return jsonify({"themes": [t.to_dict() for t in themes]})


@bp_theme.route("/<int:theme_id>", methods=["GET"])
@login_required
@admin_required
def get_theme(theme_id):
    """Get a single theme."""
    theme = db.session.get(Theme, theme_id)
    if not theme:
        return jsonify({"error": "Theme not found"}), 404
    return jsonify(theme.to_dict())


@bp_theme.route("", methods=["POST"])
@login_required
@admin_required
def create_theme():
    """Create a new theme."""
    data = request.get_json() or {}

    # Validate required fields
    if not data.get("name"):
        return jsonify({"error": "Theme name is required"}), 400

    # Check for duplicate name
    existing = Theme.query.filter_by(name=data["name"]).first()
    if existing:
        return jsonify({"error": "Theme name already exists"}), 400

    theme = Theme(
        name=data["name"],
        description=data.get("description"),
        primary=data.get("primary", "#6366f1"),
        secondary=data.get("secondary", "#8b5cf6"),
        success=data.get("success", "#22c55e"),
        danger=data.get("danger", "#ef4444"),
        warning=data.get("warning", "#f59e0b"),
        info=data.get("info", "#3b82f6"),
        light=data.get("light", "#f8f9fa"),
        dark=data.get("dark", "#212529"),
        body_bg=data.get("body_bg", "#0f172a"),
        body_color=data.get("body_color", "#f1f5f9"),
        link_color=data.get("link_color", "#6366f1"),
        link_hover_color=data.get("link_hover_color", "#8b5cf6"),
        border_color=data.get("border_color", "#334155"),
        card_bg=data.get("card_bg", "#1e293b"),
        created_by=current_user.id,
    )

    db.session.add(theme)
    db.session.commit()

    return jsonify(theme.to_dict()), 201


@bp_theme.route("/<int:theme_id>", methods=["PUT"])
@login_required
@admin_required
def update_theme(theme_id):
    """Update a theme."""
    theme = db.session.get(Theme, theme_id)
    if not theme:
        return jsonify({"error": "Theme not found"}), 404

    data = request.get_json() or {}

    # Check for duplicate name if changing
    if data.get("name") and data["name"] != theme.name:
        existing = Theme.query.filter_by(name=data["name"]).first()
        if existing:
            return jsonify({"error": "Theme name already exists"}), 400
        theme.name = data["name"]

    # Update fields
    if "description" in data:
        theme.description = data["description"]
    if "primary" in data:
        theme.primary = data["primary"]
    if "secondary" in data:
        theme.secondary = data["secondary"]
    if "success" in data:
        theme.success = data["success"]
    if "danger" in data:
        theme.danger = data["danger"]
    if "warning" in data:
        theme.warning = data["warning"]
    if "info" in data:
        theme.info = data["info"]
    if "light" in data:
        theme.light = data["light"]
    if "dark" in data:
        theme.dark = data["dark"]
    if "body_bg" in data:
        theme.body_bg = data["body_bg"]
    if "body_color" in data:
        theme.body_color = data["body_color"]
    if "link_color" in data:
        theme.link_color = data["link_color"]
    if "link_hover_color" in data:
        theme.link_hover_color = data["link_hover_color"]
    if "border_color" in data:
        theme.border_color = data["border_color"]
    if "card_bg" in data:
        theme.card_bg = data["card_bg"]

    db.session.commit()

    return jsonify(theme.to_dict())


@bp_theme.route("/<int:theme_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_theme(theme_id):
    """Delete a theme."""
    theme = db.session.get(Theme, theme_id)
    if not theme:
        return jsonify({"error": "Theme not found"}), 404

    if theme.is_active:
        return jsonify({"error": "Cannot delete active theme"}), 400

    db.session.delete(theme)
    db.session.commit()

    return jsonify({"success": True}), 200


@bp_theme.route("/<int:theme_id>/activate", methods=["POST"])
@login_required
@admin_required
def activate_theme(theme_id):
    """Activate a theme (deactivates all others)."""
    theme = db.session.get(Theme, theme_id)
    if not theme:
        return jsonify({"error": "Theme not found"}), 404

    # Deactivate all themes
    Theme.query.update({"is_active": False})

    # Activate this theme
    theme.is_active = True
    db.session.commit()

    return jsonify(theme.to_dict())


@bp_theme.route("/active", methods=["GET"])
def get_active_theme():
    """Get the currently active theme (public endpoint)."""
    theme = Theme.query.filter_by(is_active=True).first()
    if not theme:
        # Return default theme if none active
        return jsonify(
            {
                "name": "Default",
                "primary": "#6366f1",
                "secondary": "#8b5cf6",
                "success": "#22c55e",
                "danger": "#ef4444",
                "warning": "#f59e0b",
                "info": "#3b82f6",
                "light": "#f8f9fa",
                "dark": "#212529",
                "body_bg": "#0f172a",
                "body_color": "#f1f5f9",
                "link_color": "#6366f1",
                "link_hover_color": "#8b5cf6",
                "border_color": "#334155",
                "card_bg": "#1e293b",
            }
        )

    return jsonify(theme.to_dict())


@bp_theme.route("/active/css", methods=["GET"])
def get_active_theme_css():
    """Get CSS variables for the active theme (public endpoint)."""
    theme = Theme.query.filter_by(is_active=True).first()
    if not theme:
        # Return default CSS
        css = """
:root {
    --bs-primary: #6366f1;
    --bs-secondary: #8b5cf6;
    --bs-success: #22c55e;
    --bs-danger: #ef4444;
    --bs-warning: #f59e0b;
    --bs-info: #3b82f6;
    --bs-light: #f8f9fa;
    --bs-dark: #212529;
    --bs-body-bg: #0f172a;
    --bs-body-color: #f1f5f9;
    --bs-link-color: #6366f1;
    --bs-link-hover-color: #8b5cf6;
    --bs-border-color: #334155;
    --bs-card-bg: #1e293b;
}
"""
        return css, 200, {"Content-Type": "text/css"}

    return theme.to_css_variables(), 200, {"Content-Type": "text/css"}
