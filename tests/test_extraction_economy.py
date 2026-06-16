import json
import uuid

from app import db
from app.models.hoard import Hoard
from app.services import extraction_service
from tests.factories import create_character, create_instance, create_user


def _instance_for(user):
    inst = create_instance(user, seed=4242)
    inst.extraction_available = True  # no early-extraction penalty
    db.session.commit()
    return inst


def test_extract_pools_bag_and_purse_into_hoard():
    user = create_user("extr_a_" + uuid.uuid4().hex[:8])
    inst = _instance_for(user)
    char = create_character(user, name="A", items=[{"slug": "potion_heal_l1", "qty": 2}])
    char.gold = 300
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok, msg
    hoard = Hoard.query.filter_by(user_id=user.id).first()
    assert hoard.copper == 300
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    db.session.refresh(char)
    assert char.gold == 0
    assert json.loads(char.items) == []
