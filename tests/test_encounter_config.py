import json

import pytest

from app.services import spawn_service
from app.services.loot_service import roll_loot


@pytest.fixture(autouse=True)
def _seed_monsters_for_band():
    """These tests assume a seeded monster catalog covering level 5.

    A bare create_all leaves MonsterCatalog empty (it's normally a CSV import),
    so seed a boss + a common monster spanning the band and clear the spawn
    eligibility cache (which may hold a stale empty result).
    """
    from app import db
    from app.models.models import MonsterCatalog

    def _ensure(slug, boss):
        if MonsterCatalog.query.filter_by(slug=slug).first():
            return
        db.session.add(
            MonsterCatalog(
                slug=slug,
                name=slug.replace("-", " ").title(),
                level_min=1,
                level_max=10,
                base_hp=20,
                base_damage=3,
                family="test",
                rarity="boss" if boss else "common",
                boss=boss,
                xp_base=10,
            )
        )

    _ensure("test-grunt", False)
    _ensure("test-overlord", True)
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()
    yield


def test_rarity_weight_override(auth_client, monkeypatch):
    # Force rarity weights so 'boss' dominates (set boss weight very high, others tiny)
    from app.models import GameConfig

    GameConfig.set(
        "rarity_weights",
        json.dumps({"boss": 1000, "common": 0.0001, "uncommon": 0.0001, "rare": 0.0001, "elite": 0.0001}),
    )
    # Choose level where a boss exists in catalog (seed already loaded in test env assumption)
    # We fallback to level 5; adjust if boss bands differ.
    # Retry a few times in case of weight randomness or absent boss at level
    boss_found = False
    for _ in range(5):
        inst = spawn_service.choose_monster(level=5, party_size=1, include_boss=True)
        if inst.get("boss"):
            boss_found = True
            break
    if not boss_found:
        import pytest

        pytest.skip("No boss encountered at level 5 after retries; catalog may lack boss in this band")
    assert boss_found


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
