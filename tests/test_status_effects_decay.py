import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User
from app.services.character_stats import compute_hp_mana_max


def _make_character(username_suffix):
    user = User(username=f"statuseffect_{username_suffix}")
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Hero",
        stats='{"con": 10, "int": 10, "hp": 50, "current_mana": 20}',
        gear="{}",
        items="[]",
    )
    db.session.add(char)
    db.session.commit()
    return char


def test_character_status_effect_round_trip():
    char = _make_character("model")
    effect = CharacterStatusEffect(
        character_id=char.id,
        name="poison",
        remaining=3,
        data='{"damage": 5}',
    )
    db.session.add(effect)
    db.session.commit()

    fetched = CharacterStatusEffect.query.filter_by(character_id=char.id).first()
    assert fetched is not None
    assert fetched.name == "poison"
    assert fetched.remaining == 3
    assert fetched.data == '{"damage": 5}'
    assert fetched.created_at is not None


def test_compute_hp_mana_max_uses_con_int_level_and_gear():
    char = _make_character("hpmax")
    char.stats = json.dumps({"con": 14, "int": 12})
    char.level = 3
    char.gear = "{}"
    db.session.add(char)
    db.session.commit()

    hp_max, mana_max = compute_hp_mana_max(char)

    # base 50 + CON*2 + level*5 = 50 + 28 + 15 = 93
    assert hp_max == 93
    # base 20 + INT*2 = 20 + 24 = 44
    assert mana_max == 44


def test_compute_hp_mana_max_defaults_when_stats_missing():
    char = _make_character("hpmaxdefault")
    char.stats = "{}"
    char.level = 1
    char.gear = "{}"
    db.session.add(char)
    db.session.commit()

    hp_max, mana_max = compute_hp_mana_max(char)

    # base 50 + CON(10)*2 + level(1)*5 = 75
    assert hp_max == 75
    # base 20 + INT(10)*2 = 40
    assert mana_max == 40
