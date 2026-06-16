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
