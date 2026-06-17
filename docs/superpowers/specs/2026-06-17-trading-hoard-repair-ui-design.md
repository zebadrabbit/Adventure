# Trading UI: Repoint to Hoard + Repair Tab — Design

**Date:** 2026-06-17
**Status:** Design only — not yet planned/implemented.
**Part of:** Spec 4b (UI Surfacing), first of several smaller sub-specs.

## Context

Spec 4 (backend) shipped hoard-backed buy/sell (`/api/trade/buy|sell`, `/api/trade/repair`)
and per-instance durability. The frontend never caught up: `app/static/js/trading-system.js`
still reads `/api/characters/<id>/gold` (the at-risk run-purse, not the hoard) and
`/api/characters/<id>/inventory` (slug-only, no gear instances) for the Sell tab. There is
no repair UI at all. This sub-spec repoints the existing shop modal to the hoard and adds a
Repair tab. It does not touch the hoard/stash screen, extraction surface, or encumbrance bar
— those are separate follow-up sub-specs.

## Goals
1. Shop header shows hoard copper (3-tier `copper_display`), not character gold.
2. Sell tab lists hoard contents: both stackable catalog items (by `slug`) and procedural
   gear instances (by `uid`), with rarity-colored names and a durability bar on instances.
3. New **Repair** tab (third tab, after Buy/Sell) lists every repairable instance the user
   owns — hoard items plus gear currently equipped on any of their characters — each with a
   durability bar, live repair cost (`*_display`), and a Repair button.
4. Buy still works as today, just confirms balance/changes against hoard copper instead of
   character gold.

## Non-goals
- Hoard withdraw-to-character flow / dedicated hoard screen (next sub-spec).
- Extraction surface, floor-loot claim UI, loot-body UI (later sub-spec).
- Encumbrance bar / affix breakdown in the equipment panel (later sub-spec).
- Any backend changes — `GET /api/hoard`, `POST /api/trade/buy|sell|repair`, and
  `GET /api/characters/state` already provide everything needed.

## Data sources
- `GET /api/hoard` → `{ items: [...], copper, copper_display }`. `items` mixes stackable
  entries (`{slug, qty}`) and gear instances (`{uid, slug, rarity, durability,
  max_durability, value, ...}` — presence of `uid` distinguishes an instance).
- `GET /api/characters/state` → per-character `gear: {slot: instanceOrItemOrNull}`. Used
  only by the Repair tab to find equipped instances; an entry counts as repairable if it's
  an object with a `uid` and `durability < max_durability`.
- `POST /api/trade/buy` — unchanged contract, still returns `new_balance`/`new_balance_display`
  (already hoard copper server-side; no client change needed besides reading the field).
- `POST /api/trade/sell` — accepts `item_slug` (stackables) or `uid` (gear instances).
- `POST /api/trade/repair` — `{uid}` → `{durability, cost, cost_display, new_balance,
  new_balance_display}`. Works for both hoard items and equipped gear, found by uid alone
  (no character_id needed).

## UI design

### Header
Replace `character-gold-amount` (raw int) with hoard `copper_display`. Drop the per-character
gold fetch in `openMerchant`; fetch `/api/hoard` instead and store `this.hoardCopper` +
`this.hoardCopperDisplay`. `characterGold` references throughout the file are renamed to
`hoardCopper` for clarity (numeric, used for afford checks) while the header renders the
display string.

### Sell tab
Render from `this.hoardItems` (from `/api/hoard`, refetched on tab switch / after trades).
For each entry:
- **Stackable** (`{slug, qty}`): same card as today — icon, name, qty badge, sell price
  (`base_price * sell_modifier`, looked up the same way as now via the merchant's catalog
  data — stackables sold here are merchant-catalog items, so `base_price` comes from the
  item catalog as today).
- **Gear instance** (has `uid`): name colored by `rarity` (reuse the rarity color map already
  used by `tooltips.js`/`equipment.js` — extract if not already a shared constant), a thin
  durability bar (`durability / max_durability`, using the existing `.durability-bar`/
  `.durability-fill` high/medium/low classes from `equipment.css`), sell price from
  `value * sell_modifier` (mirrors the backend's own
  pricing in `sell_item`).
- Clicking either kind starts a sell flow through the existing confirm dialog
  (`startSell` currently sells immediately without confirmation for slug items — bring gear
  instances through the same confirm dialog as buy, since they're non-stackable and a misclick
  is costlier; quantity selector is hidden/locked to 1 for instances).

### Repair tab
New third tab `data-tab="repair"`. On activation:
1. Fetch `/api/hoard` (if not already fresh) and `/api/characters/state`.
2. Build a flat list of repairable instances: every hoard item with a `uid` plus every
   equipped gear instance across all characters, filtered to `durability < max_durability`.
   Tag each with its source (`hoard` or character name + slot) for display only — the
   backend repair endpoint doesn't need that tag, it resolves by `uid` alone.
3. Render a card per instance: name (rarity-colored), source label ("In Hoard" / "Equipped —
   <Character> <Slot>"), durability bar, computed cost via the same formula the backend uses
   (`(max - current) * repair_cost_per_point` — cost is also returned by the response, but
   showing it before clicking needs the config; simplest is to show the durability bar and a
   "Repair" button with cost computed client-side from `max_durability`/`durability` diff
   using a cost-per-point constant fetched once... see Open Question below).
4. Repair button → `POST /api/trade/repair {uid}`. On success: update the hoard copper header
   from `new_balance_display`, update that card's durability bar to full, remove it from the
   repairable list (since it's no longer below max), toast success. On insufficient funds /
   404, toast the error.
5. Empty state: "Nothing needs repair."

### Open question — resolved
Computing repair cost client-side requires `repair_cost_per_point`, which isn't currently
exposed to the frontend. Rather than add a new config-read endpoint (out of scope for a
frontend-only sub-spec), the Repair tab shows the durability bar and a plain "Repair" button
without a pre-computed price; the toast on success shows the actual `cost_display` charged.
This keeps the sub-spec backend-free. A follow-up could expose the cost via a small addition
to `GET /api/hoard` or a dedicated config-read endpoint if players want to see the price
before committing — not needed for v1.

### Toasts / events
Reuse `showToast`. `trade-complete` event still fires for buy/sell. Add a `repair-complete`
event (`{uid, new_balance}`) in case other widgets (none currently) want to react.

## Error handling
- Hoard fetch failure on modal open: toast "Failed to load shop" (existing pattern), abort.
- Repair/sell/buy failures: surface the backend's `error` message via toast (existing pattern
  for buy/sell; same for repair).
- No client-side balance precheck for repair (since cost isn't known until the response) —
  rely on the backend's "Insufficient funds" error.

## Testing
Frontend tests are light in this repo (per Spec 4 notes) — prioritize manual verification via
the `run`/`verify` skills with a live browser:
- Open shop as a character with hoard copper, gear instances, and at least one damaged
  equipped/hoard item (seed or manually damage via combat).
- Verify header shows 3-tier copper display.
- Buy an item, confirm header updates from hoard balance.
- Sell a stackable and a gear instance, confirm both work and hoard updates.
- Switch to Repair tab, confirm damaged items list (both hoard and equipped), repair one,
  confirm durability bar fills and copper deducts.
- Confirm an undamaged-only state shows the empty-state message.

## Affected files
- `app/static/js/trading-system.js` — header/balance source, Sell tab data source + gear
  instance rendering, new Repair tab, tab markup, possible shared rarity-color helper.
- `app/static/css/trading-system.css` — durability bar styling; reuse the existing
  `.durability-bar`/`.durability-fill` (`.high`/`.medium`/`.low`) classes from
  `app/static/css/equipment.css` rather than inventing new ones.
- No backend or template changes anticipated.
