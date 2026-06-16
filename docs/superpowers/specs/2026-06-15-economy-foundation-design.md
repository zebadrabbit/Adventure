# Economy Foundation — Design (Spec 1)

**Date:** 2026-06-15
**Status:** Approved, pending implementation plan
**Part of:** Path A — closing the inventory + economy loop for a soft-extraction looter (SSI Gold Box × Dark and Darker, casual one-shot adventure).

## Context

The repo is a Flask + Flask-SocketIO + PostgreSQL web dungeon game. An inventory,
procedural gear generator, and buy/sell trading API already exist, but the economy
loop has real holes. This is the **first of three sequential specs**:

1. **Economy foundation** (this spec) — bug fixes, merchant seeding, currency tiers.
2. **Extraction loop** — bag (at-risk) vs. town stash (secured), securing-on-return,
   soft death-drop, procedural gear on the dungeon floor.
3. **Maintenance & UI** — config-driven durability + vendor repair, frontend surfacing.

### Game-design frame (informs all three specs)

- **Soft extraction:** dying drops only *unsecured* bag loot; equipped gear is kept.
- **Securing = town banking:** returning to town moves the bag into a safe stash
  (Diablo-ish). Decided here, *built in Spec 2*.
- **Casual one-shot:** the run should be compelling but not discouraging. Economy is
  about per-run kit-up choices, not a long grind.

## Problems this spec fixes (verified in code)

1. **Transaction-history crash.** `trading_api.py` orders/serializes by
   `TradeTransaction.timestamp` (lines 324, 341, 358, 375) but the model column is
   `created_at` (`app/models/merchant.py:71`). Both history endpoints `AttributeError`.
2. **Selling looted gear is broken.** `sell_item` looks up `Item.query.filter_by(slug=...)`
   and 404s if absent (`trading_api.py:216`). Procedural gear lives in inventory as
   `uid` dicts with their own `value`, not catalog `Item` rows — so found gear is unsellable.
3. **Inventory field-name mismatch.** `get_character_inventory_for_trade` reads
   `inv_item.get("quantity")` (`:307`) but the canonical bag format uses `qty`.
4. **No merchants in DB.** Merchant rows exist only if a raw SQL migration was hand-run
   (`sql/trading_system_migration.sql`). There is no programmatic seeder, and the
   `inventory_json` shape in that SQL (`stock`) disagrees with what the buy endpoint
   reads (`price`).
5. **Currency unit ambiguity.** `sell_item` adds `value_copper * modifier` straight onto
   `Character.gold` (`:224-243`), conflating copper and gold.

## Design

### A. Currency model (B-lite: copper internal, 3-tier display)

- The stored integer `Character.gold` is **reinterpreted as copper** — the single
  smallest unit. **No schema change.** All internal prices are copper.
- New module `app/economy/currency.py`:
  - `format_copper(n: int) -> str` → `"12g 5s 5c"`. 100 copper = 1 silver,
    100 silver = 1 gold. Omits zero tiers; always shows at least `"0c"`.
    - `0 → "0c"`, `150 → "1s 50c"`, `10000 → "1g"`, `120505 → "12g 5s 5c"`.
  - `split_copper(n: int) -> {"gold": int, "silver": int, "copper": int}` for API/UI.
- Money-returning API responses gain a parallel `*_display` string alongside the raw
  integer (e.g. `new_gold` + `new_gold_display`), so the frontend renders tiers without
  re-deriving. The raw integer field keeps its current name for backward compatibility.

### B. Bug fixes

1. **Transaction history:** replace `TradeTransaction.timestamp` → `.created_at` in all
   four spots. The JSON response key stays `"timestamp"`, sourced from `created_at`.
2. **Sell both item kinds:** `sell_item` accepts either `item_slug` *or* `uid`:
   - Catalog item (`{slug, qty}` bag entry): price from `Item.value_copper`, removed
     by slug-stack (existing behavior).
   - Procedural instance (bag dict with `uid`): price from the instance's own `value`,
     removed by matching `uid`.
   - Returns `404` only when neither lookup matches.
3. **Inventory field:** `get_character_inventory_for_trade` reads `qty` (not `quantity`)
   and includes procedural instances (with `uid`, `name`, `value`) in the sellable list.

### C. Merchant seeding

- New `app/seed_merchants.py` with `seed_merchants()`:
  - **Idempotent** upsert by `slug` (running twice yields 3 merchants, not 6).
  - ORM-based (not raw SQL) — avoids the SQL-dialect munging in `seed_items.py`.
  - Wired into `run.py` as `python run.py seed-merchants`, matching the existing
    `reseed-items` CLI pattern.
- Seeds **three town vendors**, all prices in **copper**, inventory drawn from real
  `Item` slugs that exist in the catalog:
  - `general-store` (general) — potions, torches, keys.
  - `weaponsmith` (weapons) — basic catalog weapons.
  - `armorer` (armor) — basic catalog armor.
- Writes `inventory_json` in the shape the buy endpoint actually consumes:
  `[{"slug", "name", "type", "price"}]`. Populates `MerchantStock` rows only for
  limited-stock items; most basics are unlimited (`None`).
- Default modifiers `buy_price_modifier=1.0`, `sell_price_modifier=0.5`, both read from
  `GameConfig` when present so they are tunable without code changes.

### D. Testing & verification (pytest, in `tests/`)

- **currency:** `format_copper` boundary cases above; tier omission.
- **transaction history:** both endpoints return 200 and include a `timestamp` key
  sourced from `created_at` (regression for the crash).
- **sell:** catalog-by-slug and instance-by-uid paths — correct copper paid, item
  removed, gold updated; `404` only when neither exists.
- **buy:** purchase against a seeded merchant — copper deducted, item added to bag,
  limited stock decremented, `*_display` present.
- **seeder:** idempotent (3 merchants after two runs); every seeded slug resolves to a
  real `Item`.

## Out of scope (deferred)

- Bag/stash split, securing-on-return, soft death-drop, floor procedural loot → **Spec 2**.
- Durability, vendor repair, frontend UI → **Spec 3**.
- Player-to-player trading → not planned for Path A.

## Affected files

- New: `app/economy/currency.py`, `app/seed_merchants.py`, tests under `tests/`.
- Modified: `app/routes/trading_api.py`, `run.py`.
- Unchanged schema: `app/models/merchant.py`, `Character.gold` (semantics only).
