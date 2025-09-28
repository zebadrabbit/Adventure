import json

from app.services import spawn_service
from app.services.loot_service import roll_loot


def test_rarity_weight_override(auth_client, monkeypatch):
    # Force rarity weights so 'boss' dominates (set boss weight very high, others tiny)
    from app.models import GameConfig

    GameConfig.set(
        "rarity_weights",
        json.dumps({"boss": 1000, "common": 0.0001, "uncommon": 0.0001, "rare": 0.0001, "elite": 0.0001}),
    )
    # Choose level where a boss exists in catalog (seed already loaded in test env assumption)
    # We fallback to level 5; adjust if boss bands differ.
    inst = spawn_service.choose_monster(level=5, party_size=1, include_boss=True)
    assert inst["boss"] is True


def test_encounter_spawn_probability_config(auth_client, monkeypatch):
    # Set encounter_spawn base=1.0 to guarantee spawn on first move
    from app.models import GameConfig

    GameConfig.set("encounter_spawn", json.dumps({"base": 1.0, "streak_bonus_max": 0.0}))
    # Trigger movement
    auth_client.post("/api/dungeon/move", json={"dir": ""})
    resp = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    assert resp.status_code == 200
    assert "encounter" in resp.json
    assert "combat_id" in resp.json["encounter"]


def test_encounter_spawn_probability_zero(auth_client, monkeypatch):
    # Set encounter_spawn base=0.0 to prevent spawn
    from app.models import GameConfig

    GameConfig.set("encounter_spawn", json.dumps({"base": 0.0, "streak_bonus_max": 0.0}))
    auth_client.post("/api/dungeon/move", json={"dir": ""})
    resp = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    # Rare case: movement blocked; ensure absence of encounter key or empty
    assert resp.status_code == 200
    assert not resp.json.get("encounter")


def test_loot_service_special_drop(auth_client):
    monster = {
        "slug": "test-mob",
        "name": "Test Mob",
        "level": 1,
        "hp": 10,
        "damage": 2,
        "armor": 0,
        "speed": 10,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "potion-healing, dagger",
        "special_drop_slug": "goblin-ear",
        "xp": 5,
        "boss": False,
    }

    # Mock RNG to force special drop (roll 0.0) then to force picking first item
    class FakeRandom:
        seq = [0.0, 0.0]  # first for special, second for base table pivot

        def random(self):
            return self.seq.pop(0) if self.seq else 0.0

    result = roll_loot(monster, rng=FakeRandom())
    assert "goblin-ear" in result["items"]
    assert any(i in result["items"] for i in ["potion-healing", "dagger"])  # at least one base drop


def test_loot_service_no_special(auth_client):
    monster = {
        "slug": "test-mob",
        "name": "Test Mob",
        "level": 1,
        "hp": 10,
        "damage": 2,
        "armor": 0,
        "speed": 10,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "potion-healing, dagger",
        "special_drop_slug": None,
        "xp": 5,
        "boss": False,
    }

    class FakeRandom:
        def random(self):
            return 0.999  # never trigger special (none anyway)

    result = roll_loot(monster, rng=FakeRandom())
    assert result["rolls"]["special"] is None
    assert len(result["items"]) >= 1
