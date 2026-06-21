"""Using potion-regen in combat applies a regen_buff effect instead of an
instant heal, and deducts from the acting character's own inventory only
(mirrors tests/test_potions_per_character.py's potion-healing coverage)."""

import json
import random

from app import db
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster():
    return {
        "slug": "regen-potion-test-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": 500,
        "damage": 10,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 0,
        "boss": False,
    }


def test_using_potion_regen_in_combat_applies_regen_buff_and_deducts_inventory(test_app, monkeypatch):
    with test_app.app_context():
        user = User(username=f"regenpotion-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        stats = json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12})
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=stats,
            gear="{}",
            items=json.dumps([{"slug": "potion-regen", "qty": 2}]),
        )
        db.session.add(char)
        db.session.commit()

        init_seq = iter([20, 1])  # player acts first
        monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
        session = combat_service.start_session(user.id, _simple_monster())
        initiative = json.loads(session.initiative_json)
        actor_id = initiative[session.active_index]["id"]

        result = combat_service.player_use_item(session.id, user.id, session.version, "potion-regen", actor_id=actor_id)
        assert result.get("ok") is True, result

        refreshed = combat_service._load_session(session.id)
        party = json.loads(refreshed.party_snapshot_json)
        member = next(m for m in party["members"] if m.get("char_id") == actor_id)
        assert any(e["name"] == "regen_buff" for e in member.get("effects", []))

        db.session.refresh(char)
        inv = json.loads(char.items)
        assert inv == [{"slug": "potion-regen", "qty": 1}]
