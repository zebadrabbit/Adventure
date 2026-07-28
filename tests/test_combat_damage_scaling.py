"""Every offensive action must grow with the character using it.

Playtest finding (2026-07-27): "spells and special attacks felt underwhelming
compared to just pressing attack". They were. A weapon swing scales with
STR *and level* (attack = 8 + STR/2 + level + gear), while spells scaled with
INT alone and skills were flat constants out of effect_json. Measured means
before the fix:

    level    attack   firebolt   skill
    1          15.2     17.4      5-22 (flat)
    20         31.8     17.8      5-22 (flat)

so a level-20 mage's firebolt cost mana to do half a free swing. The root cause
was structural: the combat party snapshot did not carry `level` at all, so
nothing downstream could scale by it.

These tests pin the relationships, not the exact numbers -- balance can move,
but a resource-costing action must never fall behind the free one again.
See scripts/audit_combat_damage.py to re-measure.
"""

import json

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service


@pytest.fixture()
def user(test_app):
    from werkzeug.security import generate_password_hash

    row = User.query.filter_by(username="scaling_user").first()
    if not row:
        row = User(username="scaling_user", password=generate_password_hash("pw"))
        db.session.add(row)
        db.session.commit()
    return row


def _caster(level, int_stat=14, attack=20):
    return {"level": level, "int_stat": int_stat, "attack": attack, "name": "T"}


# ----------------------------------------------------------------- spell power


def test_spell_power_grows_with_level():
    low = combat_service._spell_power(_caster(1))
    high = combat_service._spell_power(_caster(20))
    assert high > low
    # The level term must be worth roughly what it is worth to a weapon user,
    # or casters fall behind again as levels climb.
    assert high - low == pytest.approx(19, abs=1)


def test_spell_power_grows_with_int():
    dull = combat_service._spell_power(_caster(5, int_stat=10))
    bright = combat_service._spell_power(_caster(5, int_stat=20))
    assert bright > dull


def test_spell_power_tolerates_a_snapshot_without_level():
    """Combat sessions created before `level` was added must not crash."""
    legacy = {"int_stat": 12, "attack": 15}
    assert combat_service._spell_power(legacy) > 0


def test_party_snapshot_carries_level(user):
    """The bug underneath the bug: nothing could scale by a level it never saw."""
    char = Character.query.filter_by(user_id=user.id, name="Leveled").first()
    if not char:
        char = Character(
            user_id=user.id,
            name="Leveled",
            stats=json.dumps({"str": 12, "int": 12, "con": 10}),
            gear="{}",
            items="[]",
            level=7,
        )
        db.session.add(char)
        db.session.commit()

    snapshot = combat_service._base_player_snapshot(user.id)
    member = next(m for m in snapshot["members"] if m["char_id"] == char.id)
    assert member["level"] == 7


# ---------------------------------------------------------------- skill damage


def _skill_damage(caster, effect):
    """Mirror of the damage arithmetic in player_cast_skill.

    Kept deliberately small: the full path needs a session, an unlocked skill
    and a live turn, all of which scripts/audit_combat_damage.py exercises. What
    matters here is the relationship between base, stats and level.
    """
    phys = int(effect.get("damage", 0) or 0)
    magic = int(effect.get("spell_damage", 0) or 0)
    dmg = 0
    if phys > 0:
        dmg += phys + int(caster.get("attack", 10))
    if magic > 0:
        dmg += magic + int(combat_service._spell_power(caster))
    return dmg


def test_physical_skill_beats_the_free_attack_it_replaces():
    for level in (1, 5, 10, 20):
        caster = _caster(level, attack=8 + 14 // 2 + level)
        skill = _skill_damage(caster, {"damage": 5})
        assert skill > caster["attack"], f"level {level}: skill {skill} <= attack {caster['attack']}"


def test_caster_skill_beats_the_free_attack_at_every_level():
    for level in (1, 5, 10, 20):
        caster = _caster(level, attack=8 + 14 // 2 + level)
        skill = _skill_damage(caster, {"spell_damage": 8})
        assert skill > caster["attack"], f"level {level}: skill {skill} <= attack {caster['attack']}"


def test_skill_damage_scales_with_level():
    low = _skill_damage(_caster(1, attack=15), {"spell_damage": 8})
    high = _skill_damage(_caster(20, attack=35), {"spell_damage": 8})
    assert high > low * 1.5, "a tier-1 skill must not be a level-1 relic"


def test_flat_skills_are_no_longer_flat():
    """The exact regression: identical effect_json, different characters."""
    novice = _skill_damage(_caster(1, int_stat=10, attack=12), {"spell_damage": 22})
    veteran = _skill_damage(_caster(20, int_stat=20, attack=35), {"spell_damage": 22})
    assert veteran > novice
