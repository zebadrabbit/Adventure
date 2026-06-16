"""Test extraction mechanics.

Tests for extraction service, permadeath, and locked-in-dungeon states.
"""

import json

import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User
from app.services import extraction_service


@pytest.fixture(scope="function", autouse=True)
def setup_database(test_app):
    """Setup and teardown database for each test."""
    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        yield
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def test_user(test_app):
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def test_dungeon(test_app, test_user):
    """Create a test dungeon instance."""
    instance = DungeonInstance(user_id=test_user.id, seed=12345, tier=1, bosses_defeated=0, extraction_available=False)
    db.session.add(instance)
    db.session.commit()
    return instance


@pytest.fixture
def test_characters(test_app, test_user, test_dungeon):
    """Create test characters locked in dungeon."""
    chars = []
    for i in range(3):
        stats = {"str": 10, "dex": 10, "int": 10, "hp": 100, "HP": 100, "hp_max": 100, "mana": 50, "mana_max": 50}
        char = Character(
            user_id=test_user.id,
            name=f"Hero{i+1}",
            stats=json.dumps(stats),
            level=5,
            xp=500,
            locked_in_dungeon=True,
            locked_dungeon_id=test_dungeon.id,
        )
        db.session.add(char)
        chars.append(char)
    db.session.commit()
    return chars


def test_check_extraction_available_early(test_app, test_dungeon):
    """Test extraction availability check for early extraction."""
    available, reason = extraction_service.check_extraction_available(test_dungeon)
    assert available is True
    assert "Early extraction" in reason


def test_check_extraction_available_complete(test_app, test_dungeon):
    """Test extraction availability after all bosses defeated."""
    test_dungeon.extraction_available = True
    db.session.commit()

    available, reason = extraction_service.check_extraction_available(test_dungeon)
    assert available is True
    assert "Hearthstone Portal" in reason


def test_calculate_extraction_penalties_early(test_app, test_dungeon):
    """Test early extraction penalties."""
    penalties = extraction_service.calculate_extraction_penalties(test_dungeon, early=True)

    assert penalties["xp_multiplier"] == 0.7  # 30% loss
    assert penalties["loot_quality_multiplier"] == 0.8  # 20% reduction


def test_calculate_extraction_penalties_complete(test_app, test_dungeon):
    """Test no penalties when all bosses defeated."""
    test_dungeon.extraction_available = True
    penalties = extraction_service.calculate_extraction_penalties(test_dungeon, early=False)

    assert penalties["xp_multiplier"] == 1.0  # No penalty
    assert penalties["loot_quality_multiplier"] == 1.0  # No penalty


def test_extract_all_characters(test_app, test_user, test_dungeon, test_characters):
    """Test extracting all characters successfully."""
    char_ids = [c.id for c in test_characters]

    success, message, result = extraction_service.extract_party(test_dungeon, char_ids, test_user.id)

    assert success is True
    assert "Extracted 3 character(s)" in message
    assert len(result["extracted"]) == 3
    assert len(result["left_behind"]) == 0
    assert result["early_extraction"] is True

    # Verify characters unlocked
    for char in test_characters:
        db.session.refresh(char)
        assert char.locked_in_dungeon is False
        assert char.locked_dungeon_id is None
        assert char.permadeath is False


def test_extract_with_left_behind(test_app, test_user, test_dungeon, test_characters):
    """Test extraction leaving one character behind (permadeath)."""
    # Extract only first two characters
    char_ids = [test_characters[0].id, test_characters[1].id]

    success, message, result = extraction_service.extract_party(test_dungeon, char_ids, test_user.id)

    assert success is True
    assert "1 left behind (PERMADEATH)" in message
    assert len(result["extracted"]) == 2
    assert len(result["left_behind"]) == 1
    assert result["left_behind"][0] == test_characters[2].name

    # Verify permadeath for left behind character
    db.session.refresh(test_characters[2])
    assert test_characters[2].permadeath is True
    assert test_characters[2].locked_in_dungeon is False

    # Verify extracted characters safe
    for char in test_characters[:2]:
        db.session.refresh(char)
        assert char.permadeath is False
        assert char.locked_in_dungeon is False


def test_extract_with_xp_penalty(test_app, test_user, test_dungeon, test_characters):
    """Test XP penalty applied on early extraction."""
    from app.models.models import GameConfig

    # Isolate the penalty mechanic from the Spec-5 extraction XP bonus.
    GameConfig.set("progression", '{"extraction_xp": 0}')
    original_xp = test_characters[0].xp

    success, message, result = extraction_service.extract_party(test_dungeon, [test_characters[0].id], test_user.id)

    assert success is True
    db.session.refresh(test_characters[0])

    # Verify XP reduced by 30%
    expected_xp = int(original_xp * 0.7)
    assert test_characters[0].xp == expected_xp


def test_extract_no_penalty_when_bosses_defeated(test_app, test_user, test_dungeon, test_characters):
    """Test no XP penalty when all bosses defeated."""
    from app.models.models import GameConfig

    # Isolate the penalty mechanic from the Spec-5 extraction XP bonus.
    GameConfig.set("progression", '{"extraction_xp": 0}')
    test_dungeon.extraction_available = True
    db.session.commit()

    original_xp = test_characters[0].xp

    success, message, result = extraction_service.extract_party(test_dungeon, [test_characters[0].id], test_user.id)

    assert success is True
    db.session.refresh(test_characters[0])

    # Verify XP unchanged
    assert test_characters[0].xp == original_xp
    assert result["early_extraction"] is False


def test_handle_character_death(test_app, test_user, test_dungeon):
    """Test character death handling."""
    stats = {"str": 10, "hp": 100, "HP": 100, "hp_max": 100}
    char = Character(
        user_id=test_user.id, name="TestHero", stats=json.dumps(stats), level=5, locked_dungeon_id=test_dungeon.id
    )
    db.session.add(char)
    db.session.commit()

    extraction_service.handle_character_death(char, test_dungeon)

    db.session.refresh(char)
    assert char.is_dead is True
    assert char.death_count == 1
    assert char.locked_in_dungeon is True
    assert char.locked_dungeon_id == test_dungeon.id


def test_revive_character(test_app, test_user):
    """Test character resurrection."""
    stats = {"str": 10, "hp": 0, "HP": 0, "hp_max": 100}
    char = Character(user_id=test_user.id, name="DeadHero", stats=json.dumps(stats), level=5, is_dead=True)
    db.session.add(char)
    db.session.commit()

    success, message = extraction_service.revive_character(char)

    assert success is True
    assert "revived" in message.lower()

    db.session.refresh(char)
    assert char.is_dead is False

    # Verify HP restored to 25%
    stats = json.loads(char.stats)
    assert stats["hp"] == 25  # 25% of 100


def test_revive_permadeath_character(test_app, test_user):
    """Test that permadeath characters cannot be revived."""
    char = Character(user_id=test_user.id, name="PermaDeadHero", stats="{}", level=5, is_dead=True, permadeath=True)
    db.session.add(char)
    db.session.commit()

    success, message = extraction_service.revive_character(char)

    assert success is False
    assert "permadeath" in message.lower()


def test_get_extraction_status(test_app, test_user, test_dungeon, test_characters):
    """Test extraction status retrieval."""
    status = extraction_service.get_extraction_status(test_dungeon, test_user.id)

    assert status["extraction_available"] is True
    assert status["all_bosses_defeated"] is False
    assert status["bosses_defeated"] == 0
    assert len(status["characters"]) == 3
    assert status["penalties"]["xp_multiplier"] == 0.7

    # Verify character info
    char_info = status["characters"][0]
    assert "id" in char_info
    assert "name" in char_info
    assert "level" in char_info
    assert "is_dead" in char_info


def test_extract_dead_character_revives(test_app, test_user, test_dungeon, test_characters):
    """Test that dead characters are revived on successful extraction."""
    test_characters[0].is_dead = True
    db.session.commit()

    success, message, result = extraction_service.extract_party(test_dungeon, [test_characters[0].id], test_user.id)

    assert success is True

    db.session.refresh(test_characters[0])
    assert test_characters[0].is_dead is False

    # Verify HP restored
    stats = json.loads(test_characters[0].stats)
    assert stats["hp"] == stats["hp_max"]
