"""Consuming potion-regen outside combat applies a persisted regen_buff
CharacterStatusEffect instead of (or in addition to) the existing flat
heal/mana bump other potions get."""

import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, Item, User


def _ensure_potion_regen_item():
    item = Item.query.filter_by(slug="potion-regen").first()
    if item:
        return item
    item = Item(slug="potion-regen", name="Potion of Regeneration", type="potion", description="", value_copper=200)
    db.session.add(item)
    db.session.commit()
    return item


def test_consume_potion_regen_applies_persisted_regen_buff(test_app, auth_client):
    with test_app.app_context():
        _ensure_potion_regen_item()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-regen", "qty": 1}])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-regen"})
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        effect = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").first()
        assert effect is not None
        assert effect.remaining == 5
        data = json.loads(effect.data)
        assert data == {"hp_mult": 3.0, "mp_mult": 3.0}

        char = db.session.get(Character, char_id)
        inv = json.loads(char.items)
        assert inv == []  # single potion consumed and removed


def test_consume_potion_regen_replaces_not_stacks(test_app, auth_client):
    with test_app.app_context():
        _ensure_potion_regen_item()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-regen", "qty": 2}])
        db.session.commit()
        char_id = char.id
        db.session.add(
            CharacterStatusEffect(
                character_id=char_id, name="regen_buff", remaining=1, data='{"hp_mult": 1.5, "mp_mult": 1.5}'
            )
        )
        db.session.commit()

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-regen"})
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        rows = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").all()
        assert len(rows) == 1
        assert rows[0].remaining == 5
