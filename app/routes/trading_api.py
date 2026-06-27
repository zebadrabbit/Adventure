"""
Trading & Economy System API

Handles:
- Merchant shop data retrieval
- Buy/sell transactions
- Gold management
- Stock tracking
- Transaction history
"""

import json

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.inventory.utils import (
    find_instance,
    load_inventory,
    remove_instance,
    remove_one,
)
from app.models.hoard import Hoard
from app.models.merchant import Merchant, MerchantStock, TradeTransaction
from app.models.models import Character

bp_trading = Blueprint("trading_api", __name__)


def _party_chars(user_id):
    """Return Character objects for the active session party owned by user_id."""
    party = session.get("party") or []
    ids = [p["id"] for p in party if isinstance(p, dict) and p.get("id")]
    if not ids:
        return []
    return Character.query.filter(Character.id.in_(ids), Character.user_id == user_id).all()


def _party_gold(chars):
    """Sum of gold across party characters."""
    return sum(c.gold or 0 for c in chars)


def _debit_combined(cost, party_chars, hoard):
    """Debit `cost` copper from party gold first, then hoard. Raises ValueError if insufficient."""
    available = _party_gold(party_chars) + (hoard.copper or 0)
    if available < cost:
        raise ValueError("Insufficient funds")
    remaining = cost
    for c in party_chars:
        if remaining <= 0:
            break
        take = min(c.gold or 0, remaining)
        c.gold -= take
        remaining -= take
    if remaining > 0:
        hoard.copper -= remaining


@bp_trading.route("/api/merchants/<slug>", methods=["GET"])
def get_merchant(slug):
    """Get merchant details and inventory"""
    merchant = Merchant.query.filter_by(slug=slug).first()
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 404

    # Parse inventory from JSON
    inventory_data = json.loads(merchant.inventory_json or "[]")

    # Get stock levels for items
    stocks = {s.item_slug: s.current_stock for s in MerchantStock.query.filter_by(merchant_id=merchant.id).all()}

    # Enrich inventory with pricing and stock
    enriched_inventory = []
    for item_data in inventory_data:
        item_slug = item_data.get("slug")
        base_price = item_data.get("price", 0)

        enriched_item = {
            "slug": item_slug,
            "name": item_data.get("name", item_slug.replace("-", " ").title()),
            "type": item_data.get("type", "misc"),
            "base_price": base_price,
            "stock": stocks.get(item_slug),  # None = unlimited
        }
        enriched_inventory.append(enriched_item)

    return jsonify(
        {
            "slug": merchant.slug,
            "name": merchant.name,
            "type": merchant.merchant_type,
            "icon": merchant.sprite_icon,
            "buy_modifier": merchant.buy_price_modifier,
            "sell_modifier": merchant.sell_price_modifier,
            "inventory": enriched_inventory,
        }
    )


@bp_trading.route("/api/characters/<int:character_id>/gold", methods=["GET"])
def get_character_gold(character_id):
    """Get character's current gold balance"""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    gold = character.gold or 0
    return jsonify(
        {
            "character_id": character.id,
            "name": character.name,
            "gold": gold,
            "gold_display": format_copper(gold),
        }
    )


@bp_trading.route("/api/trade/buy", methods=["POST"])
@login_required
def buy_item():
    """
    Purchase item from merchant

    Expects:
    {
        "character_id": int,
        "merchant_slug": str,
        "item_slug": str,
        "quantity": int
    }
    """
    data = request.get_json()

    character_id = data.get("character_id")
    merchant_slug = data.get("merchant_slug")
    item_slug = data.get("item_slug")
    quantity = data.get("quantity", 1)

    # Validate inputs
    if not all([character_id, merchant_slug, item_slug]):
        return jsonify({"error": "Missing required fields"}), 400

    if quantity < 1:
        return jsonify({"error": "Quantity must be at least 1"}), 400

    # Load merchant and character
    merchant = Merchant.query.filter_by(slug=merchant_slug).first()
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 404

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(character.user_id)
    party = _party_chars(character.user_id)

    # Check if merchant has this item
    inventory_data = json.loads(merchant.inventory_json or "[]")
    item_data = next((item for item in inventory_data if item.get("slug") == item_slug), None)

    if not item_data:
        return jsonify({"error": "Item not available from this merchant"}), 404

    # Calculate price
    base_price = item_data.get("price", 0)
    buy_price = int(base_price * merchant.buy_price_modifier)
    total_cost = buy_price * quantity

    # Check combined party gold + hoard
    if _party_gold(party) + (hoard.copper or 0) < total_cost:
        return jsonify({"error": "Insufficient funds"}), 400

    # Check stock if limited
    stock_entry = MerchantStock.query.filter_by(merchant_id=merchant.id, item_slug=item_slug).first()

    if stock_entry and stock_entry.current_stock < quantity:
        return jsonify({"error": f"Only {stock_entry.current_stock} in stock"}), 400

    # Execute transaction
    try:
        # Debit party gold first, then hoard; deposit items into hoard
        _debit_combined(total_cost, party, hoard)
        hoard_service.deposit_items(hoard, [{"slug": item_slug, "qty": quantity}])

        # Update stock if tracked
        if stock_entry:
            stock_entry.current_stock -= quantity

        # Record transaction
        transaction = TradeTransaction(
            character_id=character.id,
            merchant_id=merchant.id,
            transaction_type="buy",
            item_slug=item_slug,
            quantity=quantity,
            price_per_item=buy_price,
            total_gold=total_cost,
        )
        db.session.add(transaction)

        db.session.commit()

        db.session.commit()

        new_combined = _party_gold(party) + hoard.copper
        return jsonify(
            {
                "success": True,
                "item": item_slug,
                "quantity": quantity,
                "total_cost": total_cost,
                "total_cost_display": format_copper(total_cost),
                "new_balance": new_combined,
                "new_balance_display": format_copper(new_combined),
                "hoard_balance": hoard.copper,
                "hoard_balance_display": format_copper(hoard.copper),
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"[trading] Buy transaction failed: {e}")
        return jsonify({"error": "Transaction failed"}), 500


@bp_trading.route("/api/trade/sell", methods=["POST"])
@login_required
def sell_item():
    """
    Sell item to merchant

    Expects:
    {
        "character_id": int,
        "merchant_slug": str,
        "item_slug": str,
        "quantity": int
    }
    """
    data = request.get_json()

    character_id = data.get("character_id")
    merchant_slug = data.get("merchant_slug")
    item_slug = data.get("item_slug")
    uid = data.get("uid")
    quantity = data.get("quantity", 1)

    # Validate inputs: need either a catalog slug or a gear instance uid
    if not all([character_id, merchant_slug]) or not (item_slug or uid):
        return jsonify({"error": "Missing required fields"}), 400

    if quantity < 1:
        return jsonify({"error": "Quantity must be at least 1"}), 400

    # Load merchant and character
    merchant = Merchant.query.filter_by(slug=merchant_slug).first()
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 404

    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    from app.models.models import Item

    # Town trades operate on the per-user Hoard, not the at-risk run-purse.
    hoard = Hoard.get_or_create(character.user_id)
    inventory = load_inventory(hoard.items_json)

    try:
        if uid:
            # Procedural gear instance: priced by its own value, sold one at a time.
            instance = find_instance(inventory, uid)
            if not instance:
                db.session.rollback()
                return jsonify({"error": "Item not in inventory"}), 400

            base_value = int(instance.get("value", 0) or 0)
            sell_price = int(base_value * merchant.sell_price_modifier)
            total_value = sell_price  # instances are unique; quantity ignored
            sold_ref = instance.get("name", uid)

            remove_instance(inventory, uid)
            record_slug = instance.get("base") or instance.get("slot") or "gear"
            record_qty = 1
        else:
            # Catalog item: priced from the Item table, sold in stacks.
            item = Item.query.filter_by(slug=item_slug).first()
            if not item:
                return jsonify({"error": "Item not found"}), 404

            base_value = item.value_copper or 0
            sell_price = int(base_value * merchant.sell_price_modifier)
            total_value = sell_price * quantity
            sold_ref = item_slug

            for _ in range(quantity):
                if not remove_one(inventory, item_slug):
                    db.session.rollback()
                    return jsonify({"error": "Item not in inventory"}), 400
            record_slug = item_slug
            record_qty = quantity

        # Save updated inventory back to the hoard
        hoard.items_json = json.dumps(inventory)

        # Credit proceeds (copper) to the hoard
        hoard.copper += total_value

        # Update stock if merchant tracks it (catalog items only)
        if not uid:
            stock_entry = MerchantStock.query.filter_by(merchant_id=merchant.id, item_slug=item_slug).first()
            if stock_entry:
                stock_entry.current_stock += quantity

        # Record transaction
        transaction = TradeTransaction(
            character_id=character.id,
            merchant_id=merchant.id,
            transaction_type="sell",
            item_slug=record_slug,
            quantity=record_qty,
            price_per_item=sell_price,
            total_gold=total_value,
        )
        db.session.add(transaction)

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "item": sold_ref,
                "quantity": record_qty,
                "total_value": total_value,
                "total_value_display": format_copper(total_value),
                "new_balance": hoard.copper,
                "new_balance_display": format_copper(hoard.copper),
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"[trading] Sell transaction failed: {e}")
        return jsonify({"error": "Transaction failed"}), 500


@bp_trading.route("/api/trade/repair", methods=["POST"])
@login_required
def repair_item():
    """Repair a gear instance (by uid) to full durability, paid from the hoard.

    Searches the user's hoard items and their characters' equipped gear for the
    uid. Cost = (max - current) * repair_cost_per_point, debited from hoard copper.
    """
    from app.services import durability

    data = request.get_json() or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"error": "Missing uid"}), 400

    cfg = durability.durability_config()
    if not cfg.get("enabled", True):
        return jsonify({"error": "Durability is disabled"}), 400

    hoard = Hoard.get_or_create(current_user.id)

    # Find the instance: hoard items first, then equipped gear on owned characters.
    target = None
    container = None  # ("hoard", inv_list) or ("gear", character, gear_dict)
    hoard_items = load_inventory(hoard.items_json)
    found = find_instance(hoard_items, uid)
    if found is not None:
        target, container = found, ("hoard", hoard_items)
    else:
        for ch in Character.query.filter_by(user_id=current_user.id).all():
            try:
                gear = json.loads(ch.gear) if ch.gear else {}
            except Exception:
                gear = {}
            if isinstance(gear, dict):
                for inst in gear.values():
                    if isinstance(inst, dict) and inst.get("uid") == uid:
                        target, container = inst, ("gear", ch, gear)
                        break
            if target is not None:
                break

    if target is None:
        return jsonify({"error": "Item not found"}), 404

    cost = durability.repair_cost(target)
    party = _party_chars(current_user.id)
    if _party_gold(party) + (hoard.copper or 0) < cost:
        return jsonify({"error": "Insufficient funds"}), 400

    try:
        durability.apply_repair(target)
        _debit_combined(cost, party, hoard)
        if container[0] == "hoard":
            hoard.items_json = json.dumps(container[1])
        else:
            _, ch, gear = container
            ch.gear = json.dumps(gear)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[trading] Repair failed: {e}")
        return jsonify({"error": "Transaction failed"}), 500

    new_combined = _party_gold(party) + hoard.copper
    return jsonify(
        {
            "success": True,
            "uid": uid,
            "durability": target.get("durability"),
            "cost": cost,
            "cost_display": format_copper(cost),
            "new_balance": new_combined,
            "new_balance_display": format_copper(new_combined),
            "hoard_balance": hoard.copper,
            "hoard_balance_display": format_copper(hoard.copper),
        }
    )


@bp_trading.route("/api/characters/<int:character_id>/inventory", methods=["GET"])
def get_character_inventory_for_trade(character_id):
    """Get character inventory with pricing info for selling"""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    # Parse inventory using the utility
    inventory = load_inventory(character.items)

    # Get item details from database
    from app.models.models import Item

    enriched_items = []

    for inv_item in inventory:
        # Procedural gear instance: sellable by uid, priced by its own value.
        if inv_item.get("uid"):
            value = int(inv_item.get("value", 0) or 0)
            enriched_items.append(
                {
                    "uid": inv_item["uid"],
                    "name": inv_item.get("name", "Unknown Gear"),
                    "type": inv_item.get("slot", "gear"),
                    "rarity": inv_item.get("rarity"),
                    "base_price": value,
                    "base_price_display": format_copper(value),
                    "quantity": 1,
                    "equipped": inv_item.get("equipped", False),
                }
            )
            continue

        item_slug = inv_item.get("slug")
        item = Item.query.filter_by(slug=item_slug).first()

        if item:
            base_price = item.value_copper or 0
            enriched_items.append(
                {
                    "slug": item.slug,
                    "name": item.name,
                    "type": item.type,
                    "base_price": base_price,
                    "base_price_display": format_copper(base_price),
                    "quantity": inv_item.get("qty", 1),
                    "equipped": inv_item.get("equipped", False),
                }
            )

    return jsonify({"character_id": character.id, "items": enriched_items})


@bp_trading.route("/api/merchants/<slug>/transactions", methods=["GET"])
def get_merchant_transactions(slug):
    """Get transaction history for a merchant"""
    merchant = Merchant.query.filter_by(slug=slug).first()
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 404

    transactions = (
        TradeTransaction.query.filter_by(merchant_id=merchant.id)
        .order_by(TradeTransaction.created_at.desc())
        .limit(50)
        .all()
    )

    return jsonify(
        {
            "merchant": merchant.name,
            "transactions": [
                {
                    "id": t.id,
                    "character_id": t.character_id,
                    "type": t.transaction_type,
                    "item": t.item_slug,
                    "quantity": t.quantity,
                    "price_per_item": t.price_per_item,
                    "total": t.total_gold,
                    "timestamp": t.created_at.isoformat(),
                }
                for t in transactions
            ],
        }
    )


@bp_trading.route("/api/characters/<int:character_id>/transactions", methods=["GET"])
def get_character_transactions(character_id):
    """Get transaction history for a character"""
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    transactions = (
        TradeTransaction.query.filter_by(character_id=character.id)
        .order_by(TradeTransaction.created_at.desc())
        .limit(50)
        .all()
    )

    return jsonify(
        {
            "character": character.name,
            "transactions": [
                {
                    "id": t.id,
                    "merchant_id": t.merchant_id,
                    "type": t.transaction_type,
                    "item": t.item_slug,
                    "quantity": t.quantity,
                    "price_per_item": t.price_per_item,
                    "total": t.total_gold,
                    "timestamp": t.created_at.isoformat(),
                }
                for t in transactions
            ],
        }
    )
