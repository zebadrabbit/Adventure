# Character Cards — Phase B: New Effect Sources

**Date:** 2026-06-21
**Status:** Design approved — ready for implementation planning.

## Context

Phase A (`2026-06-20-character-cards-phase-a-status-effects-design.md`) built
the persisted per-character status-effect foundation: `CharacterStatusEffect`,
out-of-combat decay/regen via `apply_tick_decay`, and combat-start/end
round-tripping of poison. It deliberately added no new effect sources beyond
poison.

This phase adds two new effect sources on top of that foundation: a new
regen-over-time potion (usable both in and out of combat), and a "well-rested"
buff applied by camping. No card UI work — that remains Phase C
(dashboard roster redesign) and Phase D (combat party card redesign).

## Goals

1. A new item, `potion-regen`, usable both in combat and while exploring,
   that applies a temporary boosted-regen buff instead of an instant heal.
2. Camping (`POST /api/dungeon/camp`) additionally applies a longer, weaker
   version of the same buff on top of its existing instant restore.
3. Both share one new effect type, `regen_buff`, handled symmetrically by
   the in-memory combat effect registry (`status_effects.py`'s
   `EFFECT_START`) and the persisted decay pass (`apply_tick_decay`) — the
   same pattern Phase A established for `poison`.

## Non-goals

- No card UI changes (Phase C/D).
- No new `GameConfig` tuning surface — multiplier/duration values are fixed
  constants for this phase, not admin-configurable.
- No stacking of multiple `regen_buff` effects — re-applying replaces the
  existing one.
- No changes to the existing `potion-healing` item or camp's instant
  30%/50% restore — purely additive.

## Design

### Effect type: `regen_buff`

Data shape (mirrors poison's): `{"hp_mult": float, "mp_mult": float}`,
stored as `CharacterStatusEffect.data` (persisted) or an in-memory `effects`
entry (combat), with `remaining` counted in ticks (out of combat) or turns
(combat) — same `remaining` field Phase A already uses for poison, just a
different unit depending on context, identical to how poison itself behaves
today.

**Combat (`status_effects.py`):** new `_regen_buff_start` handler registered
in `EFFECT_START["regen_buff"]`. Heals `hp` by
`round(hp_max * (hp_mult - 1) * base_hp_regen_pct)` — concretely, for this
phase, a simple flat-percent heal scaled by `hp_mult`:
`ceil(target_max_hp * 0.02 * hp_mult)` per turn (2% base, matching the spirit
of `DEFAULT_REGEN_RATES`'s out-of-combat scale but turn-granular), capped at
`max_hp`. Mana follows the same shape with `mp_mult`. Decrements `remaining`
and is pruned at 0 via the existing `_decrement_and_prune`, unchanged.

**Persisted (`apply_tick_decay`):** alongside the existing `if effect.name ==
"poison":` branch, add `elif effect.name == "regen_buff":` that reads
`hp_mult`/`mp_mult` from `effect.data` and multiplies that tick's
`rates["hp_pct_per_tick"]`/`rates["mp_pct_per_tick"]` before computing the
heal amount for *this character only* — i.e. the regen math already present
in the function (`hp = min(hp_max, hp + math.ceil(hp_max * rates[...] / 100 *
delta))`) uses `rates["hp_pct_per_tick"] * hp_mult` instead of the flat rate
when a `regen_buff` is active for that character this pass. No change for
characters without an active buff.

**Stacking:** applying a new `regen_buff` (from either source) while one is
already active on that character deletes the existing row/in-memory entry
first, then inserts the new one — replace, not stack. A helper
`_apply_regen_buff(character_or_participant, remaining, hp_mult, mp_mult)`
encapsulates this for both the persisted and in-memory cases so the
replace-not-stack rule lives in one place per context.

### New item: `potion-regen`

- New `Item` row in `sql/items_potions.sql`, type `potion`, alongside the
  existing `potion_heal_l*` ladder (single tier for this phase — no leveled
  ladder yet, matching how `potion-healing` started before any tiering
  existed).
- **Combat path** (`combat_service.player_use_item`): new `elif slug ==
  "potion-regen":` branch alongside the existing `potion-healing` branch,
  calling `add_effect(participant, "regen_buff", turns=5, hp_mult=3.0,
  mp_mult=3.0)` (replace-not-stack per above) instead of an instant heal.
  Inventory deduction follows the exact existing per-character pattern
  `potion-healing` already uses (own `_count_potion_regen`-style helper,
  mirrors `_count_potion_healing`).
- **Out-of-combat path:** wherever the dashboard/inventory "use item" action
  currently handles `potion-healing` outside combat, add the equivalent
  `potion-regen` branch that writes a `CharacterStatusEffect(name=
  "regen_buff", remaining=5, data={"hp_mult": 3.0, "mp_mult": 3.0})` row
  (replace-not-stack), reusing the same per-character inventory deduction
  pattern.

### Camp buff

`dungeon_camp()` (`app/routes/dungeon_api.py`) keeps its existing instant
30% HP / 50% mana restore exactly as-is. After that restore commits,
for each party character apply (replace-not-stack)
`CharacterStatusEffect(name="regen_buff", remaining=10, data={"hp_mult": 2.0,
"mp_mult": 2.0})` — a longer, weaker version of the potion's buff, reflecting
the more time-costly nature of camping (8 ticks) vs. an instant potion sip.
Wrapped in the same try/except pattern the existing camp-heal loop already
uses, so a failure to apply the buff never blocks the camp action itself.

### Constants

Fixed in code for this phase (no new `GameConfig` key):
- Potion: `hp_mult=3.0, mp_mult=3.0`, `remaining=5` (ticks out of combat /
  turns in combat).
- Camp: `hp_mult=2.0, mp_mult=2.0`, `remaining=10` ticks.

## Data Flow

```
combat: use potion-regen
  -> player_use_item("potion-regen")
  -> add_effect(participant, "regen_buff", turns=5, hp_mult=3.0, mp_mult=3.0)
       (replaces any existing regen_buff entry)
  -> EFFECT_START["regen_buff"] heals participant each turn until expiry

exploring: use potion-regen
  -> inventory use-item route, potion-regen branch
  -> CharacterStatusEffect(regen_buff, remaining=5, {hp_mult:3, mp_mult:3})
       (replaces existing row if any)
  -> apply_tick_decay's regen_buff branch multiplies that tick's regen rate

camp
  -> existing instant 30%/50% restore (unchanged)
  -> apply regen_buff (remaining=10, hp_mult=2, mp_mult=2) per party character
  -> advance_non_combat_time (unchanged) -> apply_tick_decay picks up the buff
       on this and subsequent ticks until it expires
```

## Error Handling

- Camp's buff application is wrapped in try/except, matching the existing
  camp-heal loop — failure never blocks the camp action or its time advance.
- `apply_tick_decay`'s new branch follows the function's existing top-level
  try/except + rollback — a malformed `regen_buff` payload (missing/non-numeric
  `hp_mult`/`mp_mult`) falls back to multiplier `1.0` (i.e., behaves as if no
  buff were active) rather than raising.
- Combat's `_regen_buff_start` handler follows poison's defensive pattern
  (`.get()` with defaults), never raises on malformed data.

## Testing

TDD per project convention:
- `apply_tick_decay` unit tests: `regen_buff` multiplies the tick's regen
  correctly; expires and is pruned at `remaining <= 0`; replace-not-stack
  when reapplied; malformed `data` falls back to multiplier 1.0; combines
  correctly with a simultaneously-active `poison` effect on the same
  character (independent branches, same pass).
- Combat unit test: `EFFECT_START["regen_buff"]` heals the expected amount,
  caps at max HP/mana, decrements/prunes via the existing turn loop.
- `player_use_item` test: using `potion-regen` in combat applies the buff
  and deducts from the acting character's own inventory only (mirrors the
  existing per-character potion-healing test).
- Out-of-combat use-item test: using `potion-regen` outside combat inserts
  the expected `CharacterStatusEffect` row and deducts inventory.
- `dungeon_camp()` integration test: existing instant-restore assertions
  still pass unchanged, plus a new assertion that each party character has
  an active `regen_buff` effect afterward with the expected
  multiplier/duration.
- Full suite run after implementation, per existing project convention.

## Migration

None — reuses the `CharacterStatusEffect` table Phase A already migrated in.
`potion-regen` is a data-only `Item` row addition via the existing
`sql/items_potions.sql` seed file (loaded by `reseed-items`), no schema
change.
