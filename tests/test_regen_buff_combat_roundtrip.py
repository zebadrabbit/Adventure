"""regen_buff must round-trip through combat the same way poison already
does: loaded into the in-memory participant snapshot at session start, and
written back to CharacterStatusEffect for survivors at combat end."""

import json
import random

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster(hp=10):
    return {
        "slug": "regen-test-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": hp,
        "damage": 1,
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


def test_regen_buff_loaded_into_combat_snapshot_at_session_start(test_app):
    with test_app.app_context():
        user = User(username=f"regenbuff-start-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12, "hp": 50}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(
            CharacterStatusEffect(
                character_id=char.id, name="regen_buff", remaining=3, data='{"hp_mult": 3.0, "mp_mult": 3.0}'
            )
        )
        db.session.commit()

        session = combat_service.start_session(user.id, _simple_monster())
        party = json.loads(session.party_snapshot_json)
        member = party["members"][0]
        assert any(e["name"] == "regen_buff" and e["remaining"] == 3 for e in member.get("effects", []))


def test_regen_buff_written_back_to_db_for_survivors_at_combat_end(test_app, monkeypatch):
    with test_app.app_context():
        user = User(username=f"regenbuff-end-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12, "hp": 50}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()

        init_seq = iter([20, 1])  # player acts first
        monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
        session = combat_service.start_session(user.id, _simple_monster(hp=10))

        party = json.loads(session.party_snapshot_json)
        member = party["members"][0]
        member["effects"] = [{"name": "regen_buff", "remaining": 2, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}]
        session.party_snapshot_json = json.dumps(party)
        db.session.commit()

        initiative = json.loads(session.initiative_json)
        actor_id = initiative[session.active_index]["id"]
        result = combat_service.player_attack(session.id, user.id, session.version, actor_id=actor_id)
        assert result.get("ok") is True

        row = CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").first()
        assert row is not None
        # Mirrors poison's existing semantics: apply_start_of_turn decrements
        # the acting character's effects at the start of their own turn (see
        # _skip_if_unconscious), so one player_attack call from remaining=2
        # leaves remaining=1, not 2. Verified against poison's identical
        # in-combat decrement behavior before adjusting this expectation.
        assert row.remaining == 1
