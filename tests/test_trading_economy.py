"""DB-backed tests for the trading/economy API and merchant seeding.

Covers the Spec 1 fixes:
  - transaction-history endpoints no longer crash (created_at vs timestamp)
  - selling catalog items (by slug) and procedural gear (by uid)
  - buying from a seeded merchant with copper pricing + display fields
  - merchant seeder idempotency and catalog validation
"""

import json

import pytest

from app import db
from app.models.merchant import Merchant, MerchantStock
from tests.factories import create_character, create_user, ensure_item


@pytest.fixture
def merchant(test_app):
    """A simple merchant selling one catalog item with limited stock."""
    ensure_item("potion_heal_l1")  # value_copper defaults to 100 in ensure_item
    m = Merchant.query.filter_by(slug="test-shop").first()
    if not m:
        m = Merchant(slug="test-shop", name="Test Shop", merchant_type="general")
        db.session.add(m)
    m.inventory_json = json.dumps(
        [{"slug": "potion_heal_l1", "name": "Minor Healing Potion", "type": "potion", "price": 100}]
    )
    m.buy_price_modifier = 1.0
    m.sell_price_modifier = 0.5
    db.session.flush()
    MerchantStock.query.filter_by(merchant_id=m.id).delete()
    db.session.add(MerchantStock(merchant_id=m.id, item_slug="potion_heal_l1", current_stock=5, max_stock=5))
    db.session.commit()
    return m


@pytest.fixture
def hero(test_app):
    user = create_user("trader_" + "x")
    char = create_character(user, name="Trader", items=[])
    char.gold = 1000  # copper
    db.session.commit()
    return char


def test_buy_deducts_copper_and_adds_item(client, merchant, hero):
    resp = client.post(
        "/api/trade/buy",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 2},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_cost"] == 200
    assert data["new_gold"] == 800
    assert data["new_gold_display"] == "8s"  # 800 copper
    db.session.refresh(hero)
    bag = json.loads(hero.items)
    assert any(o.get("slug") == "potion_heal_l1" and o.get("qty") == 2 for o in bag)
    # stock decremented
    stock = MerchantStock.query.filter_by(merchant_id=merchant.id, item_slug="potion_heal_l1").first()
    assert stock.current_stock == 3


def test_sell_catalog_item_by_slug(client, merchant, hero):
    hero.items = json.dumps([{"slug": "potion_heal_l1", "qty": 1}])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 1},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_value"] == 50  # 100 * 0.5
    db.session.refresh(hero)
    assert json.loads(hero.items) == []


def test_sell_procedural_instance_by_uid(client, merchant, hero):
    instance = {"uid": "gear123", "name": "Brutal Shortsword", "slot": "weapon", "value": 400}
    hero.items = json.dumps([instance])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "gear123"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_value"] == 200  # 400 * 0.5
    assert data["item"] == "Brutal Shortsword"
    db.session.refresh(hero)
    assert json.loads(hero.items) == []


def test_sell_unknown_returns_400(client, merchant, hero):
    hero.items = json.dumps([])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "does-not-exist"},
    )
    assert resp.status_code == 400


def test_buy_does_not_wipe_gear_instances(client, merchant, hero):
    """Regression: round-tripping inventory through buy must preserve gear."""
    hero.items = json.dumps([{"uid": "keepme", "name": "Heirloom", "slot": "ring", "value": 999}])
    db.session.commit()
    resp = client.post(
        "/api/trade/buy",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 1},
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(hero)
    bag = json.loads(hero.items)
    assert any(o.get("uid") == "keepme" for o in bag), "gear instance was wiped by buy!"


def test_transaction_history_endpoints_do_not_crash(client, merchant, hero):
    # Generate a transaction first
    client.post(
        "/api/trade/buy",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 1},
    )
    r1 = client.get(f"/api/characters/{hero.id}/transactions")
    assert r1.status_code == 200, r1.get_json()
    txns = r1.get_json()["transactions"]
    assert txns and "timestamp" in txns[0]  # sourced from created_at

    r2 = client.get("/api/merchants/test-shop/transactions")
    assert r2.status_code == 200, r2.get_json()


def test_seed_merchants_idempotent(test_app):
    # Ensure the catalog has the slugs the seeder references
    for slug in ("potion_heal_l1", "potion_heal_l2", "potion_mana_l1"):
        ensure_item(slug)
    from app.seed_merchants import seed_merchants

    n1 = seed_merchants(verbose=False)
    n2 = seed_merchants(verbose=False)
    assert n1 == n2
    # Running twice must not duplicate merchants
    assert Merchant.query.filter_by(slug="general-store").count() == 1
    gs = Merchant.query.filter_by(slug="general-store").first()
    inv = json.loads(gs.inventory_json)
    # Every seeded slug resolves to a real catalog item
    from app.models.models import Item

    for entry in inv:
        assert Item.query.filter_by(slug=entry["slug"]).first() is not None
