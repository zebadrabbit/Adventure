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


def test_party_wipe_marks_characters_dead_and_permadeath():
    import uuid
    from app.services import combat_service

    user = create_user("extr_b_" + uuid.uuid4().hex[:8])
    create_instance(user, seed=909)
    char = create_character(user, name="Doomed", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char.gold = 99
    db.session.commit()

    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    for m in party["members"]:
        m["hp"] = 0
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    wiped = combat_service.resolve_party_defeat_if_any(session)
    assert wiped is True
    db.session.refresh(char)
    assert char.is_dead is True
    assert char.permadeath is True


def test_downed_member_is_marked_dead_not_permadeath():
    import uuid
    from app.services import combat_service

    user = create_user("extr_c_" + uuid.uuid4().hex[:8])
    create_instance(user, seed=910)
    char = create_character(user, name="Downed", items=[])
    db.session.commit()

    monster = {"slug": "rat", "name": "Rat", "hp": 1, "damage": 0, "speed": 1}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    party["members"][0]["hp"] = 0
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    combat_service.sync_member_death_states(session)
    db.session.refresh(char)
    assert char.is_dead is True
    assert char.permadeath is False
