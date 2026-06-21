"""Camping applies a 'well-rested' regen_buff effect in addition to its
existing instant HP/mana restore -- the restore itself must stay unchanged."""

import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character


def test_camp_applies_regen_buff_alongside_existing_restore(test_app, auth_client):
    with test_app.app_context():
        char = Character.query.first()
        char.stats = json.dumps({"hp": 10, "max_hp": 100, "mana": 5, "max_mana": 50})
        db.session.commit()
        char_id = char.id

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()
    payload = resp.get_json()
    # existing instant-restore behavior unchanged: 30% of 100 = 30 hp restored
    # by camp's own restore step (reported separately from passive regen that
    # the subsequent 8-tick time-advance applies on top, via the same
    # apply_tick_decay mechanism the regen potion/combat sources rely on).
    assert payload["restored_hp_total"] == 30

    with test_app.app_context():
        char = db.session.get(Character, char_id)
        stats = json.loads(char.stats)
        # hp/mana only ever increase from camp's restore + passive regen,
        # never decrease, and must be at least the instant-restore floor.
        assert stats["hp"] >= 40
        assert stats["mana"] >= 30

        effect = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").first()
        assert effect is not None
        assert effect.remaining == 10
        data = json.loads(effect.data)
        assert data == {"hp_mult": 2.0, "mp_mult": 2.0}


def test_camp_regen_buff_replaces_not_stacks(test_app, auth_client):
    with test_app.app_context():
        char = Character.query.first()
        char.stats = json.dumps({"hp": 10, "max_hp": 100, "mana": 5, "max_mana": 50})
        db.session.commit()
        char_id = char.id
        db.session.add(
            CharacterStatusEffect(
                character_id=char_id, name="regen_buff", remaining=1, data='{"hp_mult": 3.0, "mp_mult": 3.0}'
            )
        )
        db.session.commit()

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        rows = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").all()
        assert len(rows) == 1
        assert rows[0].remaining == 10
