"""A party past the catalogue's top band still meets real monsters.

The monster catalogue tops out at level 20; characters reach 50
(`progression._MAX_LEVEL`). `_eligible_monsters` filtered on
`level_min <= level <= level_max`, so above 20 it returned nothing,
`choose_monster` raised, and `populate_spawn_stats` swallowed the error into a
bare "Trash Monster" stub with no name, family, loot table or resistances.

Every spawn for a high-level party degraded silently. The fix falls back to the
deepest band that exists rather than returning nothing: archetype and tier
scaling already adjust the stats, so a level-40 party fights a scaled-up version
of the nastiest thing in the book instead of a nameless placeholder.

These tests seed their own monsters -- db_isolation rebuilds leave only a
minimal catalogue, so depending on the real one makes tests order-dependent
(see docs/TESTING.md).
"""

import pytest

from app import db
from app.models.models import MonsterCatalog
from app.services import spawn_service


@pytest.fixture(autouse=True)
def _catalogue():
    """A tiny catalogue with a known ceiling."""
    spawn_service.clear_cache()
    specs = [
        ("_ceil_rat", "beast", 1, 3, False, "common"),
        ("_ceil_wolf", "beast", 4, 9, False, "common"),
        ("_ceil_wyrm", "beast", 10, 14, False, "uncommon"),
        ("_ceil_titan", "beast", 15, 18, False, "rare"),
        ("_ceil_overlord", "beast", 18, 18, True, "boss"),
    ]
    for slug, family, lmin, lmax, boss, rarity in specs:
        if not MonsterCatalog.query.filter_by(slug=slug).first():
            db.session.add(
                MonsterCatalog(
                    slug=slug,
                    name=slug.replace("_ceil_", "").title(),
                    level_min=lmin,
                    level_max=lmax,
                    base_hp=20 * lmax,
                    base_damage=4 * lmax,
                    armor=1,
                    speed=10,
                    rarity=rarity,
                    family=family,
                    loot_table="beast_basic",
                    xp_base=10 * lmax,
                    boss=boss,
                )
            )
    db.session.commit()
    spawn_service.clear_cache()
    yield
    spawn_service.clear_cache()


def test_within_the_catalogue_is_unchanged():
    pool = spawn_service._eligible_monsters(5, family="beast")
    assert {m.slug for m in pool} == {"_ceil_wolf"}


def test_above_the_ceiling_falls_back_to_the_deepest_band():
    """The regression: this used to be empty."""
    pool = spawn_service._eligible_monsters(40, family="beast", include_boss=True)
    assert pool, "no monsters available above the catalogue ceiling"
    assert max(int(m.level_max) for m in pool) == 18


def test_choosing_a_monster_far_above_the_ceiling_succeeds():
    monster = spawn_service.choose_monster(45, family="beast")
    assert monster["slug"].startswith("_ceil_")
    assert monster["name"], "a high-level spawn must still have a real name"


def test_the_fallback_scales_to_the_requested_level():
    """A level-45 encounter should not have level-18 stats."""
    low = spawn_service.choose_monster(18, family="beast")
    spawn_service.clear_cache()
    high = spawn_service.choose_monster(45, family="beast")
    assert high["hp"] >= low["hp"], "scaling collapsed above the ceiling"


def test_the_fallback_does_not_fire_inside_the_catalogue():
    """A gap mid-catalogue must not silently promote deep monsters."""
    pool = spawn_service._eligible_monsters(12, family="beast")
    assert {m.slug for m in pool} == {"_ceil_wyrm"}


def test_an_empty_family_still_raises_rather_than_inventing():
    """Fallback is for the ceiling, not for a family that does not exist."""
    with pytest.raises(ValueError):
        spawn_service.choose_monster(5, family="_no_such_family")
