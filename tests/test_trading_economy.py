"""DB-backed tests for the trading/economy API and merchant seeding.

Town trading transacts against the per-user Hoard (Spec 2), not the at-risk
Character run-purse. Covers:
  - transaction-history endpoints no longer crash (created_at vs timestamp)
  - selling catalog items (by slug) and procedural gear (by uid) from the hoard
  - buying from a seeded merchant with copper pricing + display fields
  - merchant seeder idempotency and catalog validation
"""

import json
import uuid

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
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    user = create_user("trader_" + uuid.uuid4().hex[:8])  # unique per run
    char = create_character(user, name="Trader", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 1000)
    db.session.commit()
    return char


def test_buy_deducts_copper_and_adds_item(client, merchant, hero):
    from app.models.hoard import Hoard

    resp = client.post(
        "/api/trade/buy",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 2},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_cost"] == 200
    assert data["new_balance"] == 800
    assert data["new_balance_display"] == "8s"  # 800 copper
    hoard = Hoard.get_or_create(hero.user_id)
    assert hoard.copper == 800
    bag = json.loads(hoard.items_json)
    assert any(o.get("slug") == "potion_heal_l1" and o.get("qty") == 2 for o in bag)
    # stock decremented
    stock = MerchantStock.query.filter_by(merchant_id=merchant.id, item_slug="potion_heal_l1").first()
    assert stock.current_stock == 3


def test_sell_catalog_item_by_slug(client, merchant, hero):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    hoard = Hoard.get_or_create(hero.user_id)
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 1}])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 1},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_value"] == 50  # 100 * 0.5
    hoard = Hoard.get_or_create(hero.user_id)
    bag = json.loads(hoard.items_json)
    assert not any(o.get("slug") == "potion_heal_l1" for o in bag)


def test_sell_procedural_instance_by_uid(client, merchant, hero):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    hoard = Hoard.get_or_create(hero.user_id)
    hoard_service.deposit_items(
        hoard, [{"uid": "gear123", "name": "Brutal Shortsword", "slot": "weapon", "value": 400}]
    )
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "gear123"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_value"] == 200  # 400 * 0.5
    assert data["item"] == "Brutal Shortsword"


def test_sell_unknown_returns_400(client, merchant, hero):
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "does-not-exist"},
    )
    assert resp.status_code == 400


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
