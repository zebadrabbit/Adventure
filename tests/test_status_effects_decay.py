from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User


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
