import json
from app.routes.dashboard_helpers import build_party_payload, serialize_character_list
from app.models.models import db, User


class _C:
    def __init__(self, stats, gear):
        # Negative id: real Character rows are autoincrement-positive, so this can
        # never collide with a leftover row in the shared session-scoped test DB
        # (passive_bonuses(c.id) hits the real DB and would otherwise pick up
        # whatever skills a real character with the colliding id has unlocked).
        self.id = -1
        self.name = "P"
        self.level = 1
        self.stats = json.dumps(stats)
        self.gear = json.dumps(gear)


def test_payload_reflects_gear_hp(test_app):
    with test_app.app_context():
        c = _C(
            {"con": 10, "int": 10},
            {"chest": {"slot": "chest", "affixes": [{"stat": "max_hp", "val": 25}]}},
        )
        payload = build_party_payload([c])
        # base hp_max = 50 + con*2 + level*5 = 50+20+5 = 75; +25 gear = 100
        assert payload[0]["hp_max"] == 100


def test_serialize_character_list_exposes_stat_points_and_xp_current(test_app):
    with test_app.app_context():
        u = User(username="progression-dash-checker", email="pdc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="DashChecker",
            level=3,
            xp=1000,
            stat_points=4,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        from app.models.xp import xp_for_level

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["stat_points"] == 4
        assert match["xp_current"] == xp_for_level(3)
        assert match["xp_next"] == xp_for_level(4)


def test_serialize_character_list_backfills_missing_hp_to_computed_max(test_app):
    with test_app.app_context():
        u = User(username="hp-backfill-checker", email="hbc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character
        from app.services.character_stats import compute_hp_mana_max

        char = Character(
            user_id=u.id,
            name="HpBackfillChecker",
            level=3,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 14, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        hp_max, mana_max = compute_hp_mana_max(char)

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["stats"]["hp"] == hp_max
        assert match["stats"]["mana"] == mana_max


def test_serialize_character_list_exposes_hp_max_and_mana_max(test_app):
    with test_app.app_context():
        u = User(username="hpmax-dash-checker", email="hmdc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character
        from app.services.character_stats import compute_hp_mana_max

        char = Character(
            user_id=u.id,
            name="HpMaxChecker",
            level=2,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 12, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        hp_max, mana_max = compute_hp_mana_max(char)

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["hp_max"] == hp_max
        assert match["mana_max"] == mana_max


def test_serialize_character_list_exposes_known_effect_display(test_app):
    with test_app.app_context():
        u = User(username="effect-dash-checker", email="edc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models import CharacterStatusEffect
        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="EffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=3, data='{"damage": 5}'))
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert len(match["effects_display"]) == 1
        eff = match["effects_display"][0]
        assert eff["icon"] == "☠"
        assert eff["label"] == "Poison"
        assert eff["css_class"] == "effect-debuff"
        assert eff["remaining"] == 3


def test_serialize_character_list_unknown_effect_falls_back_to_generic_display(test_app):
    with test_app.app_context():
        u = User(username="unknown-effect-dash-checker", email="uedc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models import CharacterStatusEffect
        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="UnknownEffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(CharacterStatusEffect(character_id=char.id, name="future_effect_xyz", remaining=2, data="{}"))
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert len(match["effects_display"]) == 1
        eff = match["effects_display"][0]
        assert eff["label"] == "future_effect_xyz"
        assert eff["css_class"] == "effect-neutral"
        assert eff["remaining"] == 2


def test_serialize_character_list_no_effects_gives_empty_list(test_app):
    with test_app.app_context():
        u = User(username="noeffect-dash-checker", email="nedc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="NoEffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["effects_display"] == []
