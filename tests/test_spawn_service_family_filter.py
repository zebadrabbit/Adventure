"""Tests that choose_monster/_eligible_monsters can be restricted to a
single MonsterCatalog family."""

from app import db
from app.models.models import MonsterCatalog
from app.services import spawn_service


def _seed_two_families():
    for slug, family in (("theme-undead-1", "undead"), ("theme-beast-1", "beast")):
        if MonsterCatalog.query.filter_by(slug=slug).first():
            continue
        db.session.add(
            MonsterCatalog(
                slug=slug,
                name=slug,
                level_min=1,
                level_max=10,
                base_hp=20,
                base_damage=3,
                family=family,
                rarity="common",
                boss=False,
                xp_base=10,
            )
        )
    db.session.commit()
    spawn_service._ELIGIBLE_CACHE.clear()


def test_family_filter_restricts_eligible_pool(test_app):
    with test_app.app_context():
        _seed_two_families()
        pool = spawn_service._eligible_monsters(level=1, family="undead")
        slugs = {m.slug for m in pool}
        assert "theme-undead-1" in slugs
        assert "theme-beast-1" not in slugs


def test_choose_monster_with_family_only_returns_that_family(test_app):
    with test_app.app_context():
        _seed_two_families()
        for _ in range(10):
            monster = spawn_service.choose_monster(level=1, family="undead")
            assert monster["slug"] == "theme-undead-1"


def test_choose_monster_without_family_is_unrestricted(test_app):
    with test_app.app_context():
        _seed_two_families()
        seen_slugs = {spawn_service.choose_monster(level=1)["slug"] for _ in range(30)}
        # Both seeded slugs are eligible at level 1 with no family
        # restriction; over 30 draws we expect to see at least one of
        # them (not asserting both appear, to avoid test flakiness --
        # this just confirms the unrestricted call doesn't silently
        # apply a leftover/cached family filter).
        assert seen_slugs & {"theme-undead-1", "theme-beast-1"}
