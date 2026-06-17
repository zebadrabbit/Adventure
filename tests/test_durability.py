"""Tests for gentle gear durability + repair."""

import json
import uuid

from app import db
from app.loot.equip import gear_bonuses
from app.loot.generator import generate_item
from app.models.models import GameConfig
from app.services import durability
from tests.factories import create_character, create_user


def _rng():
    import random

    return random.Random(123)


def test_generate_item_stamps_durability():
    GameConfig.set("durability", '{"max_durability": 100}')
    inst = generate_item(5, rarity="rare", rng=_rng())
    assert inst["durability"] == 100
    assert inst["max_durability"] == 100


def test_gear_bonuses_full_when_not_broken():
    gear = {"weapon": {"uid": "a", "durability": 50, "affixes": [{"stat": "str", "val": 10}]}}
    assert gear_bonuses(gear) == {"str": 10}


def test_gear_bonuses_reduced_when_broken():
    GameConfig.set("durability", '{"broken_bonus_multiplier": 0.5}')
    gear = {"weapon": {"uid": "a", "durability": 0, "affixes": [{"stat": "str", "val": 10}]}}
    assert gear_bonuses(gear) == {"str": 5}


def test_degrade_gear_reduces_equipped_durability():
    GameConfig.set("durability", '{"enabled": true, "loss_per_fight": 2}')
    user = create_user("dur_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", items=[])
    char.gear = json.dumps({"weapon": {"uid": "w", "durability": 10, "max_durability": 100, "affixes": []}})
    db.session.commit()
    changed = durability.degrade_gear(char)
    assert changed is True
    gear = json.loads(char.gear)
    assert gear["weapon"]["durability"] == 8


def test_degrade_gear_floors_at_zero_and_respects_disabled():
    GameConfig.set("durability", '{"enabled": false, "loss_per_fight": 5}')
    user = create_user("dur2_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", items=[])
    char.gear = json.dumps({"weapon": {"uid": "w", "durability": 3, "max_durability": 100, "affixes": []}})
    db.session.commit()
    assert durability.degrade_gear(char) is False  # disabled
    GameConfig.set("durability", '{"enabled": true, "loss_per_fight": 5}')
    durability.degrade_gear(char)
    assert json.loads(char.gear)["weapon"]["durability"] == 0  # floored


def test_repair_cost_and_apply():
    GameConfig.set("durability", '{"repair_cost_per_point": 2, "max_durability": 100}')
    inst = {"uid": "x", "durability": 40, "max_durability": 100}
    assert durability.repair_cost(inst) == (100 - 40) * 2
    durability.apply_repair(inst)
    assert inst["durability"] == 100
    assert durability.repair_cost(inst) == 0


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def test_repair_endpoint_repairs_hoard_instance_from_copper(client):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    GameConfig.set("durability", '{"enabled": true, "repair_cost_per_point": 1, "max_durability": 100}')
    user = create_user("rep_" + uuid.uuid4().hex[:8])
    create_character(user, name="H", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 1000)
    hoard_service.deposit_items(
        hoard, [{"uid": "brk", "name": "Worn Blade", "durability": 40, "max_durability": 100, "affixes": []}]
    )
    db.session.commit()
    _login(client, user)

    resp = client.post("/api/trade/repair", json={"uid": "brk"})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["cost"] == 60  # (100-40)*1
    assert data["durability"] == 100
    assert data["new_balance"] == 940
    h = Hoard.query.filter_by(user_id=user.id).first()
    assert json.loads(h.items_json)[0]["durability"] == 100


def test_repair_rejects_unowned_or_missing(client):
    user = create_user("rep2_" + uuid.uuid4().hex[:8])
    db.session.commit()
    _login(client, user)
    resp = client.post("/api/trade/repair", json={"uid": "nope"})
    assert resp.status_code == 404
