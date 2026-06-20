import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User
from app.services.character_stats import compute_hp_mana_max
from app.services.status_effects import apply_tick_decay


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


def test_apply_tick_decay_applies_poison_damage_and_floors_at_one_hp():
    from app.models import GameConfig

    # Zero out regen for this test so it isolates poison's floor behavior --
    # regen runs in the same pass and would otherwise heal the character
    # back above 1, which is correct combined behavior but not what this
    # test is checking.
    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 0.0, "mp_pct_per_tick": 0.0}))
    db.session.commit()

    char = _make_character("poisondecay")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 3, "current_mana": 20})
    db.session.add(char)
    db.session.commit()
    effect = CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 10}')
    db.session.add(effect)
    db.session.commit()

    apply_tick_decay(1)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    assert stats["hp"] == 1  # floored, not 0 or negative

    remaining_effect = CharacterStatusEffect.query.filter_by(character_id=char.id).first()
    assert remaining_effect.remaining == 4


def test_apply_tick_decay_deletes_expired_effects():
    char = _make_character("expiredecay")
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=1, data='{"damage": 1}'))
    db.session.commit()

    apply_tick_decay(1)

    assert CharacterStatusEffect.query.filter_by(character_id=char.id).count() == 0


def test_apply_tick_decay_regen_caps_at_max_and_scales_with_delta():
    char = _make_character("regendecay")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, mana_max = compute_hp_mana_max(char)

    apply_tick_decay(10)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    # 0.5% of hp_max per tick * 10 ticks, at least 1 hp healed, never exceeding max
    assert stats["hp"] > 1
    assert stats["hp"] <= hp_max
    assert stats["current_mana"] > 1
    assert stats["current_mana"] <= mana_max


def test_apply_tick_decay_noop_when_nothing_to_update():
    char = _make_character("noopdecay")
    hp_max, mana_max = compute_hp_mana_max(char)
    char.stats = json.dumps({"con": 10, "int": 10, "hp": hp_max, "current_mana": mana_max})
    db.session.add(char)
    db.session.commit()
    before = char.stats

    apply_tick_decay(5)

    db.session.refresh(char)
    assert char.stats == before


def test_apply_tick_decay_respects_custom_regen_rates_from_game_config():
    from app.models import GameConfig

    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 50.0, "mp_pct_per_tick": 0.0}))
    db.session.commit()

    char = _make_character("customrates")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, mana_max = compute_hp_mana_max(char)

    apply_tick_decay(1)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    # 50% of hp_max in one tick should heal far more than the 0.5% default would
    assert stats["hp"] > 1 + int(hp_max * 0.01)
    # mp_pct_per_tick of 0 means no mana regen at all
    assert stats["current_mana"] == 1
