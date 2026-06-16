"""Programmatic, idempotent seeding of town merchants.

Unlike :mod:`app.seed_items` (raw SQL files), merchants are a handful of rows
with JSON inventory blobs, so we seed them via the ORM. Running this repeatedly
is safe: merchants are upserted by ``slug`` and stock rows are rebuilt to match.

Inventory is written in the shape the buy endpoint actually consumes::

    [{"slug", "name", "type", "price"}]   # price is in COPPER

Every referenced slug is validated against the Item catalog at seed time; any
missing slug is skipped with a warning so we never seed an unbuyable item.

Note: weapons and armor are produced entirely by the procedural gear generator
(looted, then sold back to vendors). There are no catalog weapon/armor rows to
sell, so the seeded vendors stock consumables and tools. Pricing/modifiers read
from GameConfig when present so they stay tunable without code changes.

Usage (programmatic):
    from app.seed_merchants import seed_merchants
    seed_merchants()

CLI:
    python run.py seed-merchants
"""

from __future__ import annotations

import json
from typing import Dict, List

from app import app as flask_app
from app import db
from app.models.merchant import Merchant, MerchantStock
from app.models.models import GameConfig, Item

# Default price modifiers; overridable via GameConfig key "trading".
DEFAULT_BUY_MODIFIER = 1.0
DEFAULT_SELL_MODIFIER = 0.5

# Merchant definitions. Each item references a catalog slug; price is in copper.
# Stock: omit (or None) for unlimited; an int sets a limited, restockable stock.
MERCHANT_SPECS: List[Dict] = [
    {
        "slug": "general-store",
        "name": "General Store",
        "description": "Sundries and adventuring basics for the road below.",
        "merchant_type": "general",
        "items": [
            {"slug": "potion_heal_l1"},
            {"slug": "potion_heal_l2"},
            {"slug": "potion_mana_l1"},
            {"slug": "consumable_ration_basic"},
            {"slug": "scroll_identify", "stock": 10},
        ],
    },
    {
        "slug": "apothecary",
        "name": "The Apothecary",
        "description": "Potions and elixirs brewed for the descent.",
        "merchant_type": "potions",
        "items": [
            {"slug": "potion_heal_l1"},
            {"slug": "potion_heal_l2"},
            {"slug": "potion_heal_l3"},
            {"slug": "potion_mana_l1"},
            {"slug": "potion_mana_l2"},
        ],
    },
    {
        "slug": "outfitter",
        "name": "Dungeon Outfitter",
        "description": "Tools and kit for delvers who plan to come back up.",
        "merchant_type": "general",
        "items": [
            {"slug": "tool_lockpick_basic", "stock": 5},
            {"slug": "tool_camp_kit", "stock": 3},
            {"slug": "consumable_ration_basic"},
            {"slug": "consumable_ration_hearty"},
        ],
    },
]


def _modifiers() -> tuple[float, float]:
    """Read buy/sell modifiers from GameConfig, falling back to defaults."""
    raw = GameConfig.get("trading")
    if not raw:
        return DEFAULT_BUY_MODIFIER, DEFAULT_SELL_MODIFIER
    try:
        cfg = json.loads(raw)
    except Exception:
        return DEFAULT_BUY_MODIFIER, DEFAULT_SELL_MODIFIER
    return (
        float(cfg.get("buy_modifier", DEFAULT_BUY_MODIFIER)),
        float(cfg.get("sell_modifier", DEFAULT_SELL_MODIFIER)),
    )


def seed_merchants(verbose: bool = True) -> int:
    """Create or update town merchants and their stock. Returns merchant count.

    Idempotent: upserts by slug and rebuilds stock rows to match the spec.
    """
    with flask_app.app_context():
        buy_mod, sell_mod = _modifiers()
        seeded = 0

        for spec in MERCHANT_SPECS:
            # Resolve catalog items, dropping any slug that doesn't exist.
            inventory = []
            stock_levels = {}
            for entry in spec["items"]:
                slug = entry["slug"]
                item = Item.query.filter_by(slug=slug).first()
                if not item:
                    if verbose:
                        print(f"[seed-merchants] WARN {spec['slug']}: unknown item '{slug}', skipping")
                    continue
                inventory.append(
                    {
                        "slug": item.slug,
                        "name": item.name,
                        "type": item.type,
                        "price": item.value_copper or 0,
                    }
                )
                if entry.get("stock") is not None:
                    stock_levels[item.slug] = int(entry["stock"])

            merchant = Merchant.query.filter_by(slug=spec["slug"]).first()
            if not merchant:
                merchant = Merchant(slug=spec["slug"])
                db.session.add(merchant)

            merchant.name = spec["name"]
            merchant.description = spec.get("description")
            merchant.location = "town"
            merchant.merchant_type = spec["merchant_type"]
            merchant.inventory_json = json.dumps(inventory)
            merchant.buy_price_modifier = buy_mod
            merchant.sell_price_modifier = sell_mod
            merchant.is_active = True
            db.session.flush()  # ensure merchant.id is available for stock rows

            # Rebuild stock rows to match the spec (idempotent).
            MerchantStock.query.filter_by(merchant_id=merchant.id).delete()
            for slug, qty in stock_levels.items():
                db.session.add(
                    MerchantStock(
                        merchant_id=merchant.id,
                        item_slug=slug,
                        current_stock=qty,
                        max_stock=qty,
                    )
                )

            seeded += 1
            if verbose:
                print(f"[seed-merchants] {spec['slug']}: {len(inventory)} items, {len(stock_levels)} stock-limited")

        db.session.commit()
        if verbose:
            print(f"[seed-merchants] Done. {seeded} merchants seeded.")
        return seeded


__all__ = ["seed_merchants"]
