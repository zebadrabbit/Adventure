# Procedural Floor Loot — Design (Spec 3)

**Date:** 2026-06-16
**Status:** Approved, pending implementation plan
**Part of:** Path A — the soft-extraction looter loop.

## Context

The procedural gear generator (`app/loot/generator.py::generate_item`) produces
affixed gear instances (`uid/base/slot/name/rarity/ilvl/affixes/value`), but those
only reach players as combat rewards. Floor loot (`generate_loot_for_seed` →
`DungeonLoot` rows, claimed via `loot_api.claim_loot`) places **catalog `Item`s
only**. For a looter, the dungeon floor should also be a source of exciting
procedural gear. This spec adds that, controlled by config.

`DungeonLoot` today: `item_id` is a NOT-NULL FK to `Item`; `claim_loot` adds the item
to a character's bag by slug. The inventory utils (`app/inventory/utils.py`) are
already instance-aware (a bag mixes `{slug,qty}` stacks and `{uid,...}` instances),
so a claimed instance just appends to the bag.

## Design

### A. Schema — `DungeonLoot` (`app/models/loot.py`)

- `item_id`: change to **nullable** — a node is *either* a catalog item or a gear
  instance.
- Add `instance_json` (Text, nullable) — a JSON-encoded generated gear instance dict.
- Invariant (enforced in placement/claim code, documented on the model): exactly one
  of `item_id` / `instance_json` is set per row.
- Alembic migration, hand-authored off the current head (do not autogenerate — the
  dev DB may be in a `create_all` state).

### B. Placement — `generate_loot_for_seed` (`app/loot/generator.py`)

- Read floor-loot config once per call from `GameConfig` key `"floor_loot"`, with a
  hardcoded fallback (mirrors `app/inventory/utils.py::fetch_encumbrance_config`):
  ```json
  {
    "procedural_gear_chance": 0.25,
    "rarity_weights": {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1}
  }
  ```
- For each chosen tile, roll `rng.random() < procedural_gear_chance`:
  - **hit:** pick a `rarity` via weighted choice from `rarity_weights` (using the
    call's `rng` for determinism); derive `level` from the existing party-level
    window; call `generate_item(level, rarity=rarity, rng=rng)` (the generator picks
    the `slot`/archetype itself from its `SLOTS` when `slot` is omitted); place
    `DungeonLoot(seed, x, y, z, item_id=None, instance_json=json.dumps(inst))`.
  - **miss:** place a catalog `Item` exactly as today.
- The existing idempotence guards, tile selection, spacing, and target-count logic are
  unchanged. Determinism is preserved: the same seed yields the same placements
  because all rolls use the seeded `rng`.

### C. Claim — `claim_loot` (`app/routes/loot_api.py`)

- After resolving `target_char`, branch on the row:
  - **instance node** (`row.instance_json` set): parse the instance; encumbrance check
    uses the instance's own `weight` (default 1.0) via the instance-aware utils;
    on allow, append the instance dict to the bag and persist; response item block is
    `{"name", "uid", "rarity"}` (no slug).
  - **catalog node** (`row.item_id` set): the existing slug-based path, unchanged
    (including the legacy list-of-slugs persistence compatibility).
- Keep the existing "encumbered → rollback claim, return 400" behavior for both kinds.

### D. Testing (pytest, `tests/`)

- **Placement, all-instances:** with `procedural_gear_chance` forced to 1.0 (via a
  seeded `GameConfig` "floor_loot" row or monkeypatched config), every created
  `DungeonLoot` has `item_id is None` and valid `instance_json` (parses to a dict with
  a `uid`).
- **Placement, all-catalog:** with chance 0.0, behavior is unchanged (all rows have
  `item_id`, no `instance_json`) — protects the existing path.
- **Determinism:** two runs with the same seed produce the same set of placements
  (same coords + same instance uids/rarities).
- **Claim instance:** claiming an instance node appends the gear (matchable by `uid`)
  to the character's bag and marks the node claimed; response carries name/uid/rarity.
- **Claim catalog:** the existing catalog claim still works (regression).
- **Encumbrance:** claiming an instance while over hard-cap returns 400 and leaves the
  node unclaimed.

## Out of scope

- **Spec 4:** durability/repair + frontend UI surfacing.
- **Spec 5:** character progression (xp/skill scaffolds).

## Affected files

- Modified: `app/models/loot.py`, `app/loot/generator.py`, `app/routes/loot_api.py`.
- New: an Alembic migration under `migrations/versions/`, tests under `tests/`.
- Reused unchanged: `app/loot/generator.py::generate_item`, `app/inventory/utils.py`
  (instance-aware bag), `GameConfig`.
