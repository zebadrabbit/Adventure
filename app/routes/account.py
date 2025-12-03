"""Account and profile routes."""

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.models import Character

bp_account = Blueprint("account", __name__, url_prefix="/account")


@bp_account.route("/profile")
@login_required
def profile():
    """User profile page with stats and history."""

    # Get all user's characters
    characters = Character.query.filter_by(user_id=current_user.id).all()

    # Parse character stats and augment character objects for template
    characters_enriched = []
    active_characters = 0

    for c in characters:
        try:
            stats = json.loads(c.stats) if c.stats else {}
            # Create a dict with character data plus parsed stats
            char_data = {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "xp": c.xp,
                "current_hp": stats.get("hp", 0),
                "max_hp": stats.get("hp_max", 0),
                "current_mana": stats.get("mana", 0),
                "max_mana": stats.get("mana_max", 0),
                "char_class": stats.get("class", "Unknown"),
            }
            characters_enriched.append(char_data)

            if char_data["current_hp"] > 0:
                active_characters += 1
        except (json.JSONDecodeError, AttributeError):
            # If stats can't be parsed, create minimal character data
            char_data = {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "xp": c.xp,
                "current_hp": 0,
                "max_hp": 0,
                "current_mana": 0,
                "max_mana": 0,
                "char_class": "Unknown",
            }
            characters_enriched.append(char_data)

    # Calculate aggregate stats
    total_characters = len(characters)
    lost_characters = total_characters - active_characters

    # Character stats
    highest_level = max([c.level for c in characters]) if characters else 0
    total_xp = sum([c.xp for c in characters])

    # For now, set combat/loot stats to 0 since the data model is different than expected
    # TODO: Implement proper combat/loot history tracking
    stats = {
        "total_characters": total_characters,
        "active_characters": active_characters,
        "lost_characters": lost_characters,
        "total_kills": 0,  # TODO: Track via CombatSession status='won'
        "total_deaths": 0,  # TODO: Track via CombatSession status='lost'
        "total_gold": 0,  # TODO: Sum from character inventories or loot tables
        "total_items_looted": 0,  # TODO: Count items in character inventories
        "highest_level": highest_level,
        "total_xp": total_xp,
    }

    return render_template(
        "account/profile.html",
        characters=characters_enriched,
        stats=stats,
        recent_combats=[],  # TODO: Query CombatSession
        recent_loot=[],  # TODO: Query DungeonLoot
    )


@bp_account.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Account settings page."""

    if request.method == "POST":
        if "new_email" in request.form:
            new_email = request.form.get("new_email", "").strip()
            confirm_email = request.form.get("confirm_email", "").strip()

            if not new_email or not confirm_email:
                flash("All email fields are required.", "danger")
            elif new_email != confirm_email:
                flash("Email addresses do not match.", "danger")
            elif "@" not in new_email:
                flash("Invalid email address.", "danger")
            else:
                current_user.email = new_email
                db.session.commit()
                flash("Email updated successfully!", "success")
                return redirect(url_for("account.settings"))

        elif "new_password" in request.form:
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not all([current_password, new_password, confirm_password]):
                flash("All password fields are required.", "danger")
            elif not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "danger")
            elif len(new_password) < 6:
                flash("Password must be at least 6 characters.", "danger")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password changed successfully!", "success")
                return redirect(url_for("account.settings"))

    return render_template("account/settings.html")
