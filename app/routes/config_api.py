"""
project: Adventure MUD
module: config_api.py
https://github.com/zebadrabbit/Adventure
License: MIT

Game configuration API endpoints for Adventure MUD (name pools, starter items, base stats, class map).

This module provides endpoints to fetch game configuration data for use by the frontend
and dashboard. All routes require authentication.
"""

from flask import Blueprint, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required

bp_config = Blueprint("config", __name__)

# Example: These could be loaded from DB or config file in the future
NAME_POOLS = {
    "fighter": [
        "Brakus",
        "Durgan",
        "Freya",
        "Gunnar",
        "Hilda",
        "Korrin",
        "Magda",
        "Roderic",
        "Sable",
        "Thrain",
        "Viggo",
        "Wulfric",
    ],
    "rogue": [
        "Ash",
        "Briar",
        "Cipher",
        "Dax",
        "Eve",
        "Fable",
        "Gale",
        "Hex",
        "Iris",
        "Jinx",
        "Kestrel",
        "Lark",
    ],
    "mage": [
        "Aelwyn",
        "Belisar",
        "Cyrene",
        "Daelon",
        "Eldrin",
        "Faelith",
        "Galen",
        "Hypatia",
        "Ilyria",
        "Jorahm",
        "Kaelis",
        "Lunara",
    ],
    "cleric": [
        "Ansel",
        "Benedict",
        "Cyril",
        "Delphine",
        "Elias",
        "Fiora",
        "Gideon",
        "Honora",
        "Isidore",
        "Jorah",
        "Lucien",
        "Mariel",
    ],
    "ranger": [
        "Arden",
        "Briar",
        "Cedar",
        "Dawn",
        "Ember",
        "Flint",
        "Grove",
        "Hawk",
        "Ivy",
        "Jasper",
        "Kieran",
        "Linden",
    ],
    "druid": [
        "Alder",
        "Birch",
        "Clover",
        "Dew",
        "Elder",
        "Fern",
        "Gale",
        "Hazel",
        "Iris",
        "Juniper",
        "Kestrel",
        "Laurel",
    ],
}
STARTER_ITEMS = {
    "fighter": ["short-sword", "wooden-shield", "potion-healing"],
    "rogue": ["dagger", "lockpicks", "potion-healing"],
    "mage": ["oak-staff", "potion-mana", "potion-mana"],
    "cleric": ["oak-staff", "potion-healing", "potion-mana"],
    "ranger": ["hunting-bow", "dagger", "potion-healing"],
    "druid": ["oak-staff", "herbal-pouch", "potion-healing", "potion-mana"],
    "barbarian": ["iron-axe", "potion-healing", "potion-healing"],
    "bard": ["dagger", "potion-healing", "potion-mana"],
    "monk": ["potion-healing", "potion-mana"],
    "paladin": ["short-sword", "wooden-shield", "potion-healing"],
    "sorcerer": ["oak-staff", "potion-mana", "potion-mana"],
    "warlock": ["oak-staff", "potion-mana", "potion-healing"],
}
BASE_STATS = {
    "fighter": {
        "str": 16,
        "con": 15,
        "dex": 10,
        "cha": 8,
        "int": 8,
        "wis": 8,
        "mana": 5,
        "hp": 20,
    },
    "rogue": {
        "str": 10,
        "con": 10,
        "dex": 16,
        "cha": 14,
        "int": 10,
        "wis": 8,
        "mana": 8,
        "hp": 14,
    },
    "mage": {
        "str": 8,
        "con": 10,
        "dex": 10,
        "cha": 10,
        "int": 16,
        "wis": 15,
        "mana": 20,
        "hp": 10,
    },
    "cleric": {
        "str": 12,
        "con": 12,
        "dex": 8,
        "cha": 10,
        "int": 10,
        "wis": 16,
        "mana": 12,
        "hp": 16,
    },
    "ranger": {
        "str": 12,
        "con": 12,
        "dex": 16,
        "cha": 10,
        "int": 10,
        "wis": 14,
        "mana": 8,
        "hp": 16,
    },
    "druid": {
        "str": 10,
        "con": 12,
        "dex": 10,
        "cha": 10,
        "int": 12,
        "wis": 16,
        "mana": 16,
        "hp": 14,
    },
    "barbarian": {
        "str": 18,
        "con": 16,
        "dex": 12,
        "cha": 8,
        "int": 6,
        "wis": 10,
        "mana": 0,
        "hp": 24,
    },
    "bard": {
        "str": 8,
        "con": 10,
        "dex": 14,
        "cha": 16,
        "int": 12,
        "wis": 10,
        "mana": 14,
        "hp": 12,
    },
    "monk": {
        "str": 10,
        "con": 12,
        "dex": 16,
        "cha": 8,
        "int": 10,
        "wis": 14,
        "mana": 10,
        "hp": 14,
    },
    "paladin": {
        "str": 16,
        "con": 14,
        "dex": 10,
        "cha": 14,
        "int": 8,
        "wis": 12,
        "mana": 10,
        "hp": 18,
    },
    "sorcerer": {
        "str": 6,
        "con": 10,
        "dex": 12,
        "cha": 16,
        "int": 10,
        "wis": 8,
        "mana": 20,
        "hp": 10,
    },
    "warlock": {
        "str": 8,
        "con": 12,
        "dex": 10,
        "cha": 16,
        "int": 12,
        "wis": 10,
        "mana": 18,
        "hp": 12,
    },
}
CLASS_MAP = {
    "fighter": "Fighter",
    "rogue": "Rogue",
    "mage": "Mage",
    "cleric": "Cleric",
    "ranger": "Ranger",
    "druid": "Druid",
    "barbarian": "Barbarian",
    "bard": "Bard",
    "monk": "Monk",
    "paladin": "Paladin",
    "sorcerer": "Sorcerer",
    "warlock": "Warlock",
}

# Centralized class color configuration (background & text plus optional border accent)
CLASS_COLORS = {
    "fighter": {"bg": "#301d0b", "fg": "#f2e2d8", "border": "#271504"},
    "rogue": {"bg": "#6F7A16", "fg": "#e5e5d1", "border": "#6d740f"},
    "mage": {"bg": "#189bca", "fg": "#d2f2ff", "border": "#196e89"},
    "cleric": {"bg": "#c3ccd1", "fg": "#f5f5f5", "border": "#9aa1a5"},
    "druid": {"bg": "#FF7B00", "fg": "#d8f2dc", "border": "#574a2f"},
    "ranger": {"bg": "#1a940a", "fg": "#d8eef5", "border": "#337d2c"},
    "barbarian": {"bg": "#8b2e2e", "fg": "#ffd8d8", "border": "#6d1f1f"},
    "bard": {"bg": "#9b59b6", "fg": "#f5e6ff", "border": "#7d3c98"},
    "monk": {"bg": "#d4a574", "fg": "#2d2419", "border": "#a67c52"},
    "paladin": {"bg": "#f39c12", "fg": "#2d1f0a", "border": "#c87f0a"},
    "sorcerer": {"bg": "#e74c3c", "fg": "#fff5f5", "border": "#c0392b"},
    "warlock": {"bg": "#2c3e50", "fg": "#ecf0f1", "border": "#1a252f"},
}


@bp_config.route("/api/config/name_pools")
@login_required
def api_name_pools():
    """
    Return the name pools for all classes.
    Response: { 'fighter': [...], 'rogue': [...], ... }
    """
    if not current_user.is_authenticated or not session.get("_user_id"):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        return (jsonify({"error": "unauthorized"}), 401) if wants_json else redirect(url_for("auth.login"))
    return jsonify(NAME_POOLS)


@bp_config.route("/api/config/starter_items")
@login_required
def api_starter_items():
    """
    Return the starter items for all classes.
    Response: { 'fighter': [...], 'rogue': [...], ... }
    """
    if not current_user.is_authenticated or not session.get("_user_id"):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        return (jsonify({"error": "unauthorized"}), 401) if wants_json else redirect(url_for("auth.login"))
    return jsonify(STARTER_ITEMS)


@bp_config.route("/api/config/base_stats")
@login_required
def api_base_stats():
    """
    Return the base stats for all classes.
    Response: { 'fighter': {...}, 'rogue': {...}, ... }
    """
    if not current_user.is_authenticated or not session.get("_user_id"):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        return (jsonify({"error": "unauthorized"}), 401) if wants_json else redirect(url_for("auth.login"))
    return jsonify(BASE_STATS)


@bp_config.route("/api/config/class_map")
@login_required
def api_class_map():
    """
    Return the class map (slug to display name).
    Response: { 'fighter': 'Fighter', ... }
    """
    if not current_user.is_authenticated or not session.get("_user_id"):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        return (jsonify({"error": "unauthorized"}), 401) if wants_json else redirect(url_for("auth.login"))
    return jsonify(CLASS_MAP)


@bp_config.route("/api/config/class_colors")
@login_required
def api_class_colors():
    """Return centralized class color mapping.
    Response: { 'fighter': { 'bg': '#xxxxxx', 'fg': '#yyyyyy', 'border': '#zzzzzz' }, ... }
    """
    if not current_user.is_authenticated or not session.get("_user_id"):
        wants_json = "application/json" in (request.headers.get("Accept") or "")
        return (jsonify({"error": "unauthorized"}), 401) if wants_json else redirect(url_for("auth.login"))
    return jsonify(CLASS_COLORS)
