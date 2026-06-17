import json
import uuid

from app import db
from app.economy import hoard_service
from app.models.hoard import Hoard
from app.models.models import Character  # noqa: F401
from tests.factories import create_character, create_user


def _uname(prefix):
    # Unique per run: the session test DB is not reset for unmarked tests and
    # create_user is idempotent, so fixed names would collide across runs/files.
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_get_or_create_is_idempotent():
    user = create_user(_uname("hoarder_a"))
    h1 = Hoard.get_or_create(user.id)
    db.session.commit()
    h2 = Hoard.get_or_create(user.id)
    assert h1.id == h2.id
    assert h1.copper == 0
    assert h1.items_json == "[]"


def test_hoard_one_row_per_user():
    user = create_user(_uname("hoarder_b"))
    Hoard.get_or_create(user.id)
    db.session.commit()
    Hoard.get_or_create(user.id)
    db.session.commit()
    assert Hoard.query.filter_by(user_id=user.id).count() == 1


def test_deposit_items_merges_stacks_and_appends_instances():
    user = create_user(_uname("hoarder_c"))
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 2}])
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 3}])
    hoard_service.deposit_items(hoard, [{"uid": "g1", "name": "Sword", "value": 100}])
    items = json.loads(hoard.items_json)
    stack = next(i for i in items if i.get("slug") == "potion_heal_l1")
    assert stack["qty"] == 5
    assert any(i.get("uid") == "g1" for i in items)


def test_deposit_copper():
    user = create_user(_uname("hoarder_d"))
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 250)
    hoard_service.deposit_copper(hoard, 50)
    assert hoard.copper == 300


def test_withdraw_instance_to_character():
    user = create_user(_uname("hoarder_e"))
    char = create_character(user, name="Mule", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"uid": "g9", "name": "Axe", "value": 200}])
    ok = hoard_service.withdraw_to_character(hoard, char, uid="g9")
    assert ok is True
    assert json.loads(hoard.items_json) == []
    assert any(i.get("uid") == "g9" for i in json.loads(char.items))


def test_pool_run_haul_moves_bag_and_purse_then_zeroes():
    user = create_user(_uname("hoarder_f"))
    char = create_character(user, name="Runner", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char.gold = 500  # run-purse (copper)
    hoard = Hoard.get_or_create(user.id)
    moved = hoard_service.pool_run_haul(hoard, char)
    assert moved == {"copper": 500, "items": 1}
    assert hoard.copper == 500
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    assert char.gold == 0
    assert json.loads(char.items) == []
