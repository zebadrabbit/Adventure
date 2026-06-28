"""Test suite for GET /api/dungeon/affixes endpoint."""

import pytest

from app import db
from app.models.dungeon_tier import DungeonAffix


@pytest.fixture
def seeded_affixes():
    """Seed DungeonAffix data for testing."""
    affixes = [
        {
            "affix_id": "swarming",
            "name": "Swarming",
            "threat_weight": 2,
            "monster_count_multiplier": 1.2,
            "xp_multiplier": 1.1,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "color": "#e74c3c",
            "description": "+20% more monsters, +10% XP.",
        },
        {
            "affix_id": "bulwark",
            "name": "Bulwark",
            "threat_weight": 2,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.3,
            "monster_damage_multiplier": 1.0,
            "color": "#3498db",
            "description": "Monsters have +30% HP.",
        },
        {
            "affix_id": "savage",
            "name": "Savage",
            "threat_weight": 2,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.2,
            "color": "#e67e22",
            "description": "Monsters deal +20% damage.",
        },
        {
            "affix_id": "thinned",
            "name": "Thinned Ranks",
            "threat_weight": 1,
            "monster_count_multiplier": 0.9,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.1,
            "monster_damage_multiplier": 1.1,
            "color": "#95a5a6",
            "description": "-10% monsters, but each is +10% stronger.",
        },
        {
            "affix_id": "bloodthirsty",
            "name": "Bloodthirsty",
            "threat_weight": 3,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "color": "#c0392b",
            "description": "Monsters regenerate 2% HP per round.",
            "special_effect": '{"regen_pct": 0.02}',
        },
        {
            "affix_id": "cursed",
            "name": "Cursed",
            "threat_weight": 3,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "color": "#8e44ad",
            "description": "Players take +15% damage.",
            "special_effect": '{"player_damage_taken_multiplier": 1.15}',
        },
        {
            "affix_id": "gilded",
            "name": "Gilded",
            "threat_weight": 1,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.15,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "color": "#f1c40f",
            "description": "+15% XP, -10% loot quality.",
            "special_effect": '{"loot_quality_bonus": -0.10}',
        },
        {
            "affix_id": "fortified",
            "name": "Fortified",
            "threat_weight": 2,
            "monster_count_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "monster_hp_multiplier": 1.0,
            "monster_damage_multiplier": 1.0,
            "color": "#1abc9c",
            "description": "Bosses have +50% HP.",
            "special_effect": '{"boss_hp_multiplier": 1.5}',
        },
    ]

    for spec in affixes:
        affix = DungeonAffix(**spec)
        db.session.add(affix)

    db.session.commit()
    return affixes


@pytest.mark.db_isolation
def test_get_affixes_returns_list(client, logged_in_user, seeded_affixes):
    """Test that GET /api/dungeon/affixes returns a list of affixes."""
    resp = client.get("/api/dungeon/affixes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 8
    assert all("affix_id" in a and "threat_weight" in a for a in data)


@pytest.mark.db_isolation
def test_get_affixes_unauthenticated(client):
    """Test that GET /api/dungeon/affixes requires authentication."""
    resp = client.get("/api/dungeon/affixes")
    assert resp.status_code in (401, 302)
