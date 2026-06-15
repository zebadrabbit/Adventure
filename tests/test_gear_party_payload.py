import json
from app.routes.dashboard_helpers import build_party_payload


class _C:
    def __init__(self, stats, gear):
        self.id = 1
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
