"""Admin settings pages must change the game, not just their own JSON blob.

Each page persists a "<page>_settings" GameConfig row that no gameplay module
reads; the engine reads a different, smaller set of keys. Every knob that is
supposed to do something is mirrored across in admin_new._mirror_to_engine, and
these tests assert the mirror by reading back through the *gameplay* accessor —
not by inspecting the row the admin page just wrote.
"""

import json
import uuid

import pytest

from app import db
from app.models.models import GameConfig, User
from app.routes import admin_new


@pytest.fixture()
def admin_client(client):
    from werkzeug.security import generate_password_hash

    user = User(
        username="cfgadmin_" + uuid.uuid4().hex[:8],
        password=generate_password_hash("pass"),
        role="admin",
    )
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return client


def test_dungeon_page_sets_the_early_extraction_penalty(admin_client):
    from app.services import progression

    payload = dict(admin_new.DEFAULT_DUNGEON_CONFIG)
    payload["early_exit_xp_penalty"] = 35

    r = admin_client.post("/admin/v2/settings/dungeon/save", json=payload)
    assert r.status_code == 200, r.get_json()

    assert progression.progression_config()["early_extraction_xp_penalty"] == 0.35


def test_combat_page_sets_monster_ai_behaviour(admin_client):
    payload = dict(admin_new.DEFAULT_COMBAT_CONFIG)
    payload.update(
        {
            "ambush_chance": 10,
            "monster_spell_chance": 25,
            "monster_flee_hp_threshold": 40,
            "monster_help_chance": 5,
        }
    )

    r = admin_client.post("/admin/v2/settings/combat/save", json=payload)
    assert r.status_code == 200, r.get_json()

    # Read through the key the AI actually consults.
    cfg = json.loads(GameConfig.get("monster_ai"))
    assert cfg["ambush_chance"] == 0.10
    assert cfg["spell_chance"] == 0.25
    assert cfg["flee_threshold"] == 0.40
    assert cfg["help_chance"] == 0.05


def test_combat_mirror_preserves_unrelated_monster_ai_keys(admin_client):
    """Patrol settings live under the same key and are not on this page."""
    GameConfig.set("monster_ai", json.dumps({"patrol_enabled": True, "patrol_radius": 9}))

    payload = dict(admin_new.DEFAULT_COMBAT_CONFIG)
    payload["ambush_chance"] = 15
    assert admin_client.post("/admin/v2/settings/combat/save", json=payload).status_code == 200

    cfg = json.loads(GameConfig.get("monster_ai"))
    assert cfg["ambush_chance"] == 0.15
    assert cfg["patrol_enabled"] is True, "mirroring one page must not clear the rest of the key"
    assert cfg["patrol_radius"] == 9


def test_loot_page_sets_floor_loot_weights_not_monster_weights(admin_client):
    """The two rarity_weights are different things despite the shared name."""
    weights = {"common": 10, "uncommon": 5, "rare": 1}
    payload = dict(admin_new.DEFAULT_LOOT_CONFIG)
    payload["rarity_weights"] = weights

    r = admin_client.post("/admin/v2/settings/loot/save", json=payload)
    assert r.status_code == 200, r.get_json()

    assert json.loads(GameConfig.get("floor_loot"))["rarity_weights"] == weights
    assert GameConfig.get("rarity_weights") is None, "item weights must not reweight monster spawns"


def test_saving_the_page_untouched_does_not_change_behaviour(admin_client):
    """The page's defaults match the engine's own (app/server.py seeds these).

    Without that alignment, an admin opening the page and hitting Save — the
    most likely thing they will ever do — would silently retune monster AI.
    """
    engine_defaults = {"ambush_chance": 0.5, "spell_chance": 0.4, "flee_threshold": 0.2, "help_chance": 0.2}

    r = admin_client.post("/admin/v2/settings/combat/save", json=dict(admin_new.DEFAULT_COMBAT_CONFIG))
    assert r.status_code == 200, r.get_json()

    cfg = json.loads(GameConfig.get("monster_ai"))
    for field, expected in engine_defaults.items():
        assert cfg[field] == expected, field
