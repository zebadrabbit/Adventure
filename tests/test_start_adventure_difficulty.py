"""Tests that start_adventure reads difficulty_tier and affix_ids from the form."""

import pytest


@pytest.fixture(autouse=True)
def seed_affixes(client):
    """Ensure DungeonAffix rows exist in the test database."""
    from app import db
    from app.models.dungeon_tier import DungeonAffix

    with client.application.app_context():
        if DungeonAffix.query.count() == 0:
            for affix_id in [
                "swarming",
                "bulwark",
                "savage",
                "thinned",
                "bloodthirsty",
                "cursed",
                "gilded",
                "fortified",
            ]:
                db.session.add(DungeonAffix(affix_id=affix_id, name=affix_id.capitalize()))
            db.session.commit()


@pytest.fixture()
def party_ready(client, logged_in_user):
    """Create a character and return a list with its id (ready to pass as party_ids)."""
    import uuid
    from tests.factories import create_character

    char = create_character(logged_in_user, name="DungeonHero_" + uuid.uuid4().hex[:8], items=[])
    return [str(char.id)]


def test_start_adventure_sets_tier(client, logged_in_user, party_ready):
    char_ids = party_ready
    resp = client.post(
        "/dashboard",
        data={
            "form": "start_adventure",
            "party_ids": char_ids,
            "difficulty_tier": "2",
            "affix_ids": '["swarming"]',
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 200)

    with client.session_transaction() as sess:
        instance_id = sess.get("dungeon_instance_id")
    assert instance_id is not None

    from app.models.dungeon_instance import DungeonInstance
    from app import db

    with client.application.app_context():
        instance = db.session.get(DungeonInstance, instance_id)
        assert instance.tier == 2
        assert "swarming" in instance.get_affixes()


def test_start_adventure_invalid_affix_dropped(client, logged_in_user, party_ready):
    char_ids = party_ready
    client.post(
        "/dashboard",
        data={
            "form": "start_adventure",
            "party_ids": char_ids,
            "difficulty_tier": "1",
            "affix_ids": '["nonexistent-affix"]',
        },
        follow_redirects=False,
    )
    with client.session_transaction() as sess:
        instance_id = sess.get("dungeon_instance_id")
    from app.models.dungeon_instance import DungeonInstance
    from app import db

    with client.application.app_context():
        instance = db.session.get(DungeonInstance, instance_id)
        assert instance.get_affixes() == []


def test_start_adventure_tier_clamped(client, logged_in_user, party_ready):
    """Tier values outside 1-3 should be clamped silently."""
    char_ids = party_ready
    client.post(
        "/dashboard",
        data={
            "form": "start_adventure",
            "party_ids": char_ids,
            "difficulty_tier": "99",
            "affix_ids": "[]",
        },
        follow_redirects=False,
    )
    with client.session_transaction() as sess:
        instance_id = sess.get("dungeon_instance_id")
    from app.models.dungeon_instance import DungeonInstance
    from app import db

    with client.application.app_context():
        instance = db.session.get(DungeonInstance, instance_id)
        assert instance.tier == 3
