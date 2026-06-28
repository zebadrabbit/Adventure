"""Tests for dungeon difficulty seeding."""


def test_seed_is_idempotent(test_app):
    from app.seed_dungeon_difficulty import seed_dungeon_difficulty
    from app.models.dungeon_tier import DungeonTier, DungeonAffix

    seed_dungeon_difficulty()
    seed_dungeon_difficulty()  # should not raise or duplicate
    assert DungeonTier.query.count() >= 3
    assert DungeonAffix.query.count() >= 8
    # No duplicate tier numbers
    tiers = [t.tier for t in DungeonTier.query.all()]
    assert len(tiers) == len(set(tiers))
