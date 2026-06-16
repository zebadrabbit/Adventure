# Extraction Economy & the Hoard — Design (Spec 2)

**Date:** 2026-06-15
**Status:** Approved, pending implementation plan
**Part of:** Path A — the soft-extraction looter loop.

## Context

This is a Flask + SocketIO + PostgreSQL multiplayer dungeon crawler. The repo
already contains a **dormant hardcore-extraction scaffold** (`extraction_service.py`,
`extraction_api.py`, Character death columns, `DungeonInstance.extraction_available`)
that was never wired into combat. Spec 2 **completes and reconciles** that scaffold
into the agreed game model rather than replacing it.

### The game model (decided with the user)

Per-character permadeath, cushioned by a persistent account-level **hoard**:

- A **run** uses a party of up to 3–4 of the user's characters.
- During a run, characters can be **downed** (`is_dead`, recoverable).
- A downed character is resurrected by (a) a revive item/spell the party carries, or
  (b) being carried out — `extract_party` already revives extracted dead characters in
  town. If a downed character **cannot be resurrected and is left behind, they are
  permadead.** Survivors may **loot the body's gear** before abandoning them.
- On **successful extraction**, the run's haul (each surviving character's bag + coin)
  pools into the **hoard**.
- The **hoard persists across characters**: new characters are equipped from it.
- A **party wipe** (no one extracts) loses that run's haul; the hoard is untouched.

Why this isn't discouraging: progression lives in the hoard, not in any one
character. Characters are expendable; the hoard endures.

### Currency model (decided: run-purse vs hoard)

- Coins drop in the dungeon into an **at-risk run-purse** (`Character.gold`,
  reinterpreted; copper units per Spec 1).
- Extraction banks each character's purse into **hoard copper** (safe).
- A wipe loses the run-purse; hoard copper is safe.

### Two confirmed assumptions

1. **Equipped gear persists on the character** as their loadout (checked out from the
   hoard). It is *not* re-pooled on every extract. It is lost only if that character
   permadies un-looted.
2. **Town vendors transact against the hoard** (`Hoard.items_json` + `Hoard.copper`),
   not individual characters. This repoints Spec 1's `trading_api`.

## Design

### A. Data model

- **New** `app/models/hoard.py` — `Hoard`:
  - `id`, `user_id` (unique, FK, indexed)
  - `items_json` (Text, default `"[]"`) — canonical inventory list reusing the
    `app/inventory/utils.py` format: `{slug, qty}` stacks + procedural gear instance
    dicts (`uid`).
  - `copper` (Integer, default 0) — safe currency.
  - Helper: `get_or_create(user_id)`.
- `Character.gold` — **run-purse** (at-risk copper). No schema change; semantics only.
- Reuse existing `Character.is_dead / permadeath / locked_in_dungeon /
  locked_dungeon_id / death_count` and `DungeonInstance.extraction_available /
  bosses_defeated`. No new death columns.
- **New** `app/economy/hoard_service.py` — pure-ish helpers operating on a Hoard:
  - `deposit_items(hoard, entries)` — merge stacks / append instances (reuse
    `inventory.utils.add_item` and instance append).
  - `deposit_copper(hoard, amount)`.
  - `withdraw_to_character(hoard, character, ref)` — move a stack (by slug) or instance
    (by uid) from hoard into a character's bag.
  - `pool_run_haul(hoard, character)` — move a character's bag + run-purse into the
    hoard and zero them (used on extract).

### B. At-risk vs. safe (single source of truth)

- **At-risk:** each party character's bag (`Character.items`), run-purse
  (`Character.gold`), found loot.
- **Safe:** the Hoard.
- Equipped gear (`Character.gear`) persists per Assumption #1.

### C. Death & permadeath (wire dormant code into combat)

- In `combat_service`, when a party member's HP reaches 0 during a session, call
  `extraction_service.handle_character_death(char, instance)` → sets `is_dead`,
  increments `death_count`, locks to the instance. (Today combat only sets the
  snapshot HP and marks the session complete; persistence to the Character is missing.)
- **Resurrection:** keep `revive_character` (revive item/spell → low HP). Carry-to-
  extract revival is already in `extract_party`.
- **Loot the body:** new endpoint to transfer a downed ally's bag + (optionally)
  equipped gear onto a surviving character in the same run, before leaving.
- A downed character left behind with no resurrection → permadeath (existing
  `extract_party` marks left-behind as `permadeath`).

### D. Extraction resolution

- Extend the extract flow (`extraction_api` / `extract_party`): after the existing
  revive/penalty/unlock logic, for each **extracting** character call
  `pool_run_haul(hoard, char)` — bag + run-purse → hoard, then zero them.
- Left-behind/permadead characters contribute nothing.
- Early-extraction penalties (`-30% XP, -20% loot quality`) are retained from the
  existing service (they fit the model and are already built).

### E. Wipe resolution

- When a session ends with the whole party downed and no extraction occurs, the run's
  haul (all bags + run-purses) is lost and those characters permadie. The hoard is
  untouched. Implemented where combat detects total party defeat.

### F. Hoard in town

- **New** `app/routes/hoard_api.py`:
  - `GET /api/hoard` — view hoard items + copper (with currency display via Spec 1's
    `format_copper`).
  - `POST /api/hoard/withdraw` — withdraw a stack (slug) or instance (uid) to a
    character's bag (used to equip new/existing characters from the hoard).
- **Repoint trading** (`app/routes/trading_api.py`): in town, buy deducts
  `Hoard.copper` and adds items to the hoard; sell removes from the hoard and credits
  `Hoard.copper`. The per-character buy/sell paths from Spec 1 are migrated to the
  hoard. (Run-purse coin is only earned/lost in the dungeon, never spent at vendors.)

### G. Testing (pytest, `tests/`)

- Hoard model + `hoard_service` merge/withdraw/pool helpers (unit).
- Death wiring: a member reaching 0 HP in combat sets `Character.is_dead` + lock.
- Extract pools bag + run-purse into the hoard and zeroes them; equipped gear persists.
- Wipe loses all bags + run-purses; hoard unchanged.
- Loot-the-body transfers a downed ally's bag/gear to a survivor.
- Withdraw-from-hoard equips a character.
- Repointed buy/sell operate against the hoard (extends Spec 1's trading tests).

## Out of scope (roadmap)

- **Spec 3 — Procedural floor loot:** place `generate_item()` instances on the dungeon
  floor (extend `DungeonLoot` with a JSON-instance column), claim into bag. Self-
  contained; does not block Spec 2.
- **Spec 4 — Durability/repair + UI surfacing** (the original Spec 3).
- **Spec 5 — Character progression:** complete the existing scaffolds —
  `app/models/xp.py` (`xp_for_level`), the `level_up_character` endpoint, and
  `app/models/skill.py` (`SkillTree` / `Skill` / `CharacterSkill`) for stats, spells,
  and abilities. Per-character progression is the per-character stake that plays
  against the persistent hoard.

## Affected files

- New: `app/models/hoard.py`, `app/economy/hoard_service.py`, `app/routes/hoard_api.py`,
  tests under `tests/`.
- Modified: `app/services/combat_service.py` (death wiring, wipe), `app/services/
  extraction_service.py` / `app/routes/extraction_api.py` (pool haul on extract),
  `app/routes/trading_api.py` (repoint to hoard), blueprint registration.
- Reused unchanged: `app/inventory/utils.py`, `app/economy/currency.py`,
  existing Character/DungeonInstance death/extraction columns.

## Spec 1 reconciliation note

Spec 1 made vendors transact against `Character.gold`. Spec 2 repoints them to the
hoard and reinterprets `Character.gold` as the at-risk run-purse. The Spec 1 trading
tests will be updated accordingly; `format_copper` and the instance-aware inventory
utils carry over unchanged.
