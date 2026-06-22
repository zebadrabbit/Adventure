import json
from app import db
from app.models.models import Character, User
from app.services.combat_service import _derive_stats


def test_equipped_dex_raises_derived_dex(test_app):
    with test_app.app_context():
        u = User.query.filter_by(username="geartester").first()
        if not u:
            u = User(username="geartester", password="x")
            db.session.add(u)
            db.session.commit()
        gear = {"weapon": {"slot": "weapon", "affixes": [{"stat": "dex", "val": 10}]}}
        c = Character(
            user_id=u.id,
            name="GearHero",
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
            gear=json.dumps(gear),
            items="[]",
        )
        db.session.add(c)
        db.session.commit()
        derived = _derive_stats(c)
        assert derived["dex_stat"] == 20  # 10 base + 10 from gear


def test_derive_stats_includes_effects_display_for_known_effect(test_app):
    with test_app.app_context():
        from app.models import CharacterStatusEffect
        from app.models.models import Character, User

        user = User(username="combat-effects-display-checker", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="EffectsDisplayChecker",
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=3, data='{"damage": 5}'))
        db.session.commit()

        derived = _derive_stats(char)

        assert len(derived["effects_display"]) == 1
        eff = derived["effects_display"][0]
        assert eff["icon"] == "☠"
        assert eff["label"] == "Poison"
        assert eff["css_class"] == "effect-debuff"
        assert eff["remaining"] == 3


def test_derive_stats_effects_display_empty_when_no_effects(test_app):
    with test_app.app_context():
        from app.models.models import Character, User

        user = User(username="combat-no-effects-checker", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="NoEffectsChecker",
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()

        derived = _derive_stats(char)

        assert derived["effects_display"] == []
