# Character Cards — Phase A: Persistent Status Effects Foundation

**Date:** 2026-06-20
**Status:** Design approved — ready for implementation planning.

## Context

The user wants richer character cards in two places:

- **Dashboard roster cards** — collapsed by default (base HP/MP, buffs, debuffs);
  selecting a character expands a context area with relevant actions (trade,
  cast heal, use potion, etc.) plus full stats and buffs/debuffs.
- **Combat party cards** — collapsed by default (HP/MP/buffs/debuffs); expands
  to full detail only when it's that character's turn.

Both card redesigns depend on having real buff/debuff data to show. Today,
buff/debuff data only exists in two forms, neither of which is what the cards
need:

- `PartyBuff` (`app/models/party.py`) — party-wide bonuses (leadership,
  formation, item), not per-character.
- `status_effects.py`'s in-memory `effects` list — per-character, but lives
  only inside a single combat session's transient state and is discarded the
  moment combat ends.

This project is too large for one spec, so it's split into four phases:

- **Phase A (this spec):** persistent per-character status effects + a new
  out-of-combat regen mechanic. Foundation only — no card UI changes.
- **Phase B:** new effect sources (potion regen-over-time, camp buff).
- **Phase C:** dashboard card redesign (collapsed/expand-to-context-area).
- **Phase D:** combat card redesign (collapsed/expand-on-turn) + accurate
  per-character spell costs.

## Goals (Phase A only)

1. Poison becomes a persistent, per-character effect that survives past the
   end of combat, decaying over the overworld's GameClock ticks instead of
   just combat turns.
2. Add out-of-combat HP/MP regeneration, gated to be slow enough that potions
   remain relevant — not a substitute for them.
3. Both mechanics share one decay/regen pass, hooked into the existing
   `time_service.advance_time()` call path, so they fire on every action that
   already advances the GameClock (move, search, camp) and nowhere else.
4. No card UI work in this phase. The only externally-visible behavior change
   is: poison persists after a fight instead of vanishing, and characters
   slowly heal HP/MP while exploring.

## Non-goals

- `stun` does not persist — it's meaningless outside turn-based combat and
  stays exactly as it is today (combat-only, in-memory).
- No new effect sources beyond poison in this phase (no potion-regen buff, no
  camp buff yet — that's Phase B).
- No dashboard or combat card UI changes (Phases C and D).
- No changes to `PartyBuff` or the party-wide buff system — unrelated.

## Architecture

### Correction found during spec review

`Character.hp` / `Character.mana` / `hp_max` / `mana_max` are **not** real
columns — current HP/mana live inside `Character.stats` (JSON, keys `"hp"`
and `"current_mana"`/`"mana"`), and `hp_max`/`mana_max` are *computed* from
CON/INT/level/gear bonuses/passive skills, not stored. That formula is
already duplicated nearly verbatim in `dashboard_helpers.build_party_payload`
and `combat_service.py`. Writing a third copy for `apply_tick_decay` would be
a correctness risk (the three could silently drift apart), so this phase
extracts one shared helper and points both existing call sites at it:

- New `app/services/character_stats.py`: `compute_hp_mana_max(character) ->
  tuple[int, int]`, containing the formula currently duplicated in the two
  files above (base + CON/INT/level + gear bonuses + passive skill bonuses).
- `dashboard_helpers.build_party_payload` and `combat_service.py`'s
  equivalent block both call this helper instead of recomputing inline.
- `apply_tick_decay` (below) also calls this helper to know each character's
  cap for regen.

This is the one piece of "fix what's in the way" cleanup for this phase —
no other refactoring is in scope.

### New model: `CharacterStatusEffect`

New file `app/models/status_effect.py`:

```python
class CharacterStatusEffect(db.Model):
    __tablename__ = "character_status_effect"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)  # e.g. "poison"
    remaining = db.Column(db.Integer, nullable=False)  # ticks/turns remaining
    data = db.Column(db.Text, nullable=True)  # JSON payload, e.g. '{"damage": 5}'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

One row per active effect. Deleted once `remaining <= 0`. `data`'s shape
mirrors the existing in-memory effect payload from `status_effects.py` so the
same handler functions can read either source without translation.

A real Alembic migration is required (this is a new table — the
self-stamping bootstrap from the earlier migrations fix only stamps
pre-existing schema; a genuinely new model still needs `alembic revision
--autogenerate` like any other schema change).

### Decay/regen pass: `apply_tick_decay(delta)`

New function in `app/services/status_effects.py`:

```python
def apply_tick_decay(delta: int) -> None:
    """Apply delta ticks worth of persisted effect decay and passive regen
    to every character with an active effect or HP/MP below max.

    Safe to call frequently; no-ops cleanly if nothing needs updating.
    """
```

Per character with an active `CharacterStatusEffect` row or current
HP/mana below their computed max:

1. Load `stats = json.loads(character.stats)` and `hp_max, mana_max =
   compute_hp_mana_max(character)` (the new shared helper).
2. For each active effect, decrement `remaining` by `delta`. If `name ==
   "poison"`, subtract `data["damage"] * delta` from `stats["hp"]`, floored
   at 1 (never kills a character while exploring — confirmed with the user).
   Delete the row once `remaining <= 0`.
3. Apply passive regen: `stats["hp"] += ceil(hp_max * hp_pct_per_tick / 100 *
   delta)`, and the mana key (`"current_mana"` if present, else `"mana"`) +=
   the equivalent using `mana_max`, both capped at their respective max.
   Regen and poison apply independently in the same pass — a poisoned
   character still regens, netting against the poison damage that tick.
4. Write `character.stats = json.dumps(stats)` and `db.session.add(character)`.
5. Rates come from `GameConfig.get("regen_rates")`, falling back to defaults
   `{"hp_pct_per_tick": 0.5, "mp_pct_per_tick": 1.0}` if unset or invalid —
   same fallback pattern `time_service._load_action_costs()` already uses for
   `tick_costs`.

Wrapped in the same try/except + `db.session.rollback()` pattern already
used throughout `time_service.py`: a decay/regen failure must never block the
movement/search/camp action that triggered it.

### Hook point: `time_service.advance_time()`

```python
def advance_time(delta: int, reason: str, actor_id: Optional[int] = None) -> int:
    if delta <= 0:
        return GameClock.get().tick
    if in_combat():
        return GameClock.get().tick
    clock = GameClock.get()
    clock.tick += delta
    db.session.add(clock)
    db.session.commit()
    apply_tick_decay(delta)   # <-- new
    ...
```

Called only on the success path, after the tick commit, and only when not in
combat — matching the function's existing early-return for combat, so this
is a pure addition with no change to existing control flow.

### Combat integration

`combat_service.py` changes, scoped narrowly:

- **At combat start:** for each player participant, load any persisted
  `CharacterStatusEffect` rows named `"poison"` into that participant's
  in-memory `effects` list (same dict shape `status_effects.py` already
  expects), so the existing turn-based decrement/damage logic in
  `status_effects.py` needs zero changes — it just sees pre-existing poison
  the same way it'd see freshly-applied poison.
- **At combat end** (victory, flee, extraction — anywhere a participant
  survives the encounter): write back whatever poison remains in that
  participant's `effects` list to `CharacterStatusEffect`, replacing the rows
  loaded at start. If the participant died, their effects are simply not
  written back (a dead character's status effects are moot — death/revival
  handling is unrelated to this phase).
- No change to in-combat turn behavior, regen (combat has its own healing
  economy via potions/spells, unaffected by this phase), or `stun`.

## Data Flow

```
move/search/camp action
  -> advance_for(action) / advance_time(delta)
  -> GameClock.tick += delta, commit
  -> apply_tick_decay(delta)
       -> decrement + apply poison damage (floor 1 HP), prune expired
       -> apply HP/MP regen (cap at max)
  -> existing time_update socket event (unchanged payload)

combat start
  -> load CharacterStatusEffect(name="poison") rows into participant.effects

combat turn loop (unchanged)
  -> status_effects.apply_start_of_turn() ticks effects.remaining per turn

combat end (survivors only)
  -> write participant.effects poison entries back to CharacterStatusEffect
     (delete-then-recreate is simplest and avoids diffing old vs new rows)
```

## Error Handling

- `apply_tick_decay` failures roll back and are swallowed — never block the
  triggering action, consistent with every other failure path in
  `time_service.py`.
- Combat start/end load/save wrapped in try/except — a failure to load
  persisted poison should not block entering combat; a failure to save
  shouldn't block leaving it. Both log via the existing combat logging
  pattern rather than raising.
- Malformed `GameConfig` `regen_rates` (non-dict, non-numeric values) falls
  back to defaults the same way `tick_costs` already does.

## Testing

TDD per existing project convention (new tests written failing first):

- `compute_hp_mana_max` unit test: matches the previously-duplicated formula's
  output for a representative character (base + CON/INT/level + gear +
  passives), so extracting it is verified behavior-preserving.
- `apply_tick_decay` unit tests (no combat, no HTTP):
  - Poison damage applies correctly and floors at 1 HP, never 0.
  - Expired effects (`remaining <= 0` after decrement) are deleted.
  - Regen heals HP/MP, capped at max, scaling correctly with `delta`.
  - Poison + regen together net correctly in the same pass.
  - No-op (no DB writes) when a character has no active effects and is
    already at max HP/MP.
  - Custom `GameConfig` `regen_rates` override the defaults; invalid config
    falls back to defaults.
- `advance_time` integration test:
  - Decay/regen fires after a successful non-combat tick advance.
  - Decay/regen does **not** fire while `in_combat()` is True (matches the
    existing early return).
- Combat round-trip test:
  - A character with a persisted poison effect enters combat; the poison
    appears in their in-memory `effects` list at combat start.
  - Poison ticks down per-turn exactly as today's combat-only behavior.
  - Remaining poison (if any) is written back to `CharacterStatusEffect`
    after combat ends; a character who cured/outlasted the poison has no
    leftover row.
  - A character who died mid-combat has no effects written back.
- Full suite run after implementation, as with every other change this
  session.

## Migration

New table requires a real Alembic migration:
`alembic revision --autogenerate -m "add character_status_effect table"`,
reviewed before applying (per the project's existing migration discipline —
this is a fresh additive table, lowest-risk kind of migration).
