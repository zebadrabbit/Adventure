"""
project: Adventure MUD
module: main.py
https://github.com/zebadrabbit/Adventure
License: MIT

Core application routes: legal/info pages and blueprint registration.
"""

from flask import Blueprint, render_template

bp = Blueprint("main", __name__)

# --- Configurable Game Data API Endpoints ---

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
    "druid": ["herbal-pouch", "potion-healing", "potion-mana"],
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
}
CLASS_MAP = {
    "fighter": "Fighter",
    "rogue": "Rogue",
    "mage": "Mage",
    "cleric": "Cleric",
    "ranger": "Ranger",
    "druid": "Druid",
}

# --- Legal and Info Pages ---


@bp.route("/licenses", endpoint="licenses")
def licenses():
    return render_template("licenses.html")


@bp.route("/privacy", endpoint="privacy")
def privacy():
    return render_template("privacy.html")


@bp.route("/terms", endpoint="terms")
def terms():
    return render_template("terms.html")


@bp.route("/conduct", endpoint="conduct")
def conduct():
    return render_template("conduct.html")


# --- Home Page ---


@bp.route("/")
def index():
    return render_template("index.html")
