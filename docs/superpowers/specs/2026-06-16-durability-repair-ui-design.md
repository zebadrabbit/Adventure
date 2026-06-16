# Durability, Repair & UI Surfacing — Design (Spec 4)

**Date:** 2026-06-16
**Status:** Design only — not yet planned/implemented.
**Part of:** Path A — the soft-extraction looter loop.

## Context

Specs 1–3 built the economy foundation (currency, vendors), the extraction loop
(hoard, run-purse, permadeath, extract/wipe), and procedural floor loot. What
remains for a complete, *playable* loop is (a) a gentle gold sink via gear durability
+ vendor repair, and (b) actually surfacing all of this in the frontend.

Durability was chosen (with the user) to be **gentle and fully config-driven** — not
punishing. Equipped gear is the only durability-bearing thing; consumables/quest items
are exempt.

This spec is two loosely-coupled halves. **Consider splitting into Spec 4a (durability)
and Spec 4b (UI)** when planning — 4a is backend + tests; 4b is frontend and benefits
from the visual companion during its own brainstorm.

## Part A — Durability & Repair (backend)

### Data
- Durability lives on the **procedural gear instance dict** (the only gear that varies):
  add `durability` and `max_durability` keys when `generate_item` creates an instance
  (`app/loot/generator.py`). Default `max_durability` from config (e.g. 100).
- Legacy catalog/slug gear has no durability (treated as indestructible) — keep simple.

### Config (`GameConfig` key `"durability"`, with hardcoded fallback)
```json
{
  "enabled": true,
  "max_durability": 100,
  "loss_per_fight": 2,
  "repair_cost_per_point": 1,
  "broken_bonus_multiplier": 0.5
}
```
All knobs adjustable without code (mirrors `fetch_encumbrance_config`). Keep losses
small so it never feels punishing.

### Mechanics
- **Degradation:** when a combat session resolves (in `combat_service`), reduce
  `durability` by `loss_per_fight` on each *equipped* instance of the surviving
  participants. Never below 0. Only when `enabled`.
- **Broken (0 durability):** the item still equips but its affix bonuses are scaled by
  `broken_bonus_multiplier` (default 0.5) — *reduced, not destroyed*. Apply this where
  gear bonuses are aggregated (`app/loot/equip.py::gear_bonuses`). Never delete gear for
  being broken.
- **Repair:** a town vendor action. New endpoint `POST /api/trade/repair`
  (`trading_api`) — repairs one equipped/hoard instance by `uid` to `max_durability`,
  costing `(max - current) * repair_cost_per_point` copper, debited from the **hoard**
  (consistent with Spec 2 trading). Reuse the auth/ownership pattern added in Spec 2.

### Tests
- `generate_item` stamps `durability == max_durability`.
- Combat resolution reduces equipped instance durability by `loss_per_fight`, floored at 0.
- `gear_bonuses` halves a broken item's contribution.
- Repair restores durability and debits the correct hoard copper; rejects if unaffordable
  or item not found; respects ownership/auth.
- `enabled: false` disables degradation and repair cost (no-ops).

## Part B — UI Surfacing (frontend)

The backend has no player-facing surface for the new systems. Add/extend
Bootstrap+JS views (`app/templates`, `app/static/js`) for:

1. **Inventory & equipment panel:** bag contents (stacks + gear instances), equipped
   slots, affix breakdown per gear (name, rarity color, affixes, durability bar),
   equip/unequip (existing `inventory_api`), and the **encumbrance bar**
   (weight/capacity/status from the inventory payload).
2. **Hoard / stash screen:** view hoard items + `copper_display`, withdraw-to-character
   (`/api/hoard/withdraw`), and equip-new-characters-from-hoard flow.
3. **Vendor screen:** buy/sell against the hoard (`/api/trade/buy|sell` — note the
   `new_balance`/`*_display` fields), and the repair action from Part A. Show 3-tier
   currency via the `*_display` strings.
4. **Run/extraction surface:** floor-loot pickups (`/api/dungeon/loot/claim/<id>`,
   which now returns gear instances), the extraction screen
   (`/api/dungeon/extraction/status|extract`), downed-ally **loot-body**
   (`/api/dungeon/loot-body`), and a clear "secured → hoard" confirmation.

### Notes
- All money should render through the Spec 1 `format_copper` output (`*_display`).
- Rarity colors should match the generator's rarity tiers
  (common→mythic) for at-a-glance loot quality.
- Frontend tests are light in this repo; prioritize wiring + manual verification via the
  `run`/`verify` skills over heavy JS test infrastructure.

## Out of scope
- Character progression (Spec 5).

## Affected files (anticipated)
- A: `app/loot/generator.py`, `app/loot/equip.py`, `app/services/combat_service.py`,
  `app/routes/trading_api.py`, migration not needed (durability lives in JSON), tests.
- B: `app/templates/*`, `app/static/js/*`, possibly small read-only API additions.
