# Combat System

The combat module implements a lightweight, deterministic (with seeded RNG) turn engine with initiative, multiple player actions, logging, and loot/XP payout. Balance guardrails are enforced by tests rather than informal expectations. Multi-character parties (up to 4 of the user's characters) are supported: each character appears independently in the initiative order, and all player action endpoints accept an optional `actor_id` (character id) so the client can act with the currently active party member.

See also: [Monster AI](MONSTER_AI.md) for the opponent side of combat, and [Combat Visual Effects](COMBAT_EFFECTS.md) for the frontend particle/animation layer.

## Core Concepts
- Session entity (`CombatSession`) persists monster state, party snapshot, initiative list, active index, version (optimistic lock), log, rewards, and status.
- Initiative = each participant `speed + d20`; sorted descending; `active_index` advances after every action or monster auto-turn; wrap increments `combat_turn`.
- Party snapshot synthesizes one row per **character** including derived stats: `attack`, `defense`, `speed`, `hp / max_hp`, `mana / mana_max`, explicit `int_stat`, resistances, temporary flags (e.g., `defending`).
- Multi-character: up to 4 of the user's characters are loaded; initiative entries look like `{"type":"player","id":<char_id>,"controller_id":<user_id>,"name":...,"roll":<int>}`. The monster appears as `{"type":"monster","id":<slug-or-id>, ...}`.
- Optimistic concurrency: every player action posts `{action, version, actor_id?}`; mismatch returns `version_conflict` and the client refetches.

## Party & Targeting
When a combat session starts, a snapshot of the user's first 1–4 characters is taken. Each character rolls initiative independently; only the actor whose entry matches `initiative[active_index]` may perform a player action. The client includes `actor_id` equal to that character's `char_id` for `attack`, `defend`, `use_item`, or `cast_spell`. If `actor_id` is omitted the server assumes the currently active player initiative entry. Authorization is enforced by verifying `controller_id == current_user.id` and `id == actor_id`.

## Player Actions

| Action | Effect |
|--------|--------|
| attack | d20 accuracy, miss/crit rules, variance, damage application (requires active `actor_id`) |
| flee | 50% chance to immediately end session (no loot) |
| defend | Sets `defending=True` on actor; next incoming hit halves post-resistance damage (min 1) then clears the flag |
| use_item | Supports `potion-healing` (+25 HP, consumes one if in inventory) on the acting character |
| cast_spell | `firebolt`: costs 5 mana, d20 accuracy & natural 1 fizzle, natural 20 crit (1.5x), damage `2d8 + INT * 0.6` (post-crit) with elemental type `fire` (resistances applied) |

## Formulas
- Accuracy Roll: `acc_roll = d20`; `accuracy = attack + acc_roll`; target evasion = `10 + armor` (monster) / `10 + defense` (player).
- Miss: natural 1 always misses; otherwise must meet or exceed evasion unless natural 20 (which always hits & crits).
- Critical Hit: natural 20 multiplies post-variance damage by 1.5 (integer truncated).
- Player Attack Damage: `base = attack`; variance = uniform int in `[-attack//4, +attack//4]`; apply crit; clamp final to `>=1`.
- Monster Attack Damage: same pattern using monster `damage` value.
- Spell (Firebolt): d20 accuracy (nat 1 = fizzle, nat 20 = auto-hit + crit 1.5x) then damage roll `2d8 + int_stat * 0.6` (rounded down). Fire element passes through the resistance table (e.g., 50% fire resist halves final pre-crit damage).
- Defend: If target had `defending=True`, halve the damage after crit & resistances (`max(1, dmg // 2)`), then clear the flag.

## Logging
Representative lines:
```
Encounter starts vs Training Dummy
Player hits Training Dummy for 14 (CRIT) damage (HP 486)
Training Dummy hits Balancer for 5 damage (HP 95)
Player braces for impact (Defend).
Player misses Training Dummy (roll 3)
```
Logs are truncated to the last 250 entries to bound payload size. WebSocket events `combat_update` and `combat_end` push full state snapshots.

## Rewards
On monster HP reaching 0: session status becomes `complete`, a loot table is rolled, XP is split equally across present characters, and loot items are appended to the first character's inventory (temporary policy). The stored `session.rewards` includes both loot diagnostics and an `xp` block summarizing total and per-member distribution.

Example (abbreviated `GET /api/dungeon/combat/<id>` after victory):

```json
{
  "id": 42,
  "status": "complete",
  "monster": {"slug": "training-dummy", "name": "Training Dummy", "xp": 40},
  "monster_hp": 0,
  "initiative": [
    {"type": "player", "id": 12, "controller_id": 7, "name": "Aria", "roll": 23},
    {"type": "player", "id": 13, "controller_id": 7, "name": "Brom", "roll": 18},
    {"type": "monster", "id": "training-dummy", "name": "Training Dummy", "roll": 11}
  ],
  "rewards": {
    "items": {"potion-healing": 1, "iron-dagger": 1},
    "items_list": ["potion-healing", "iron-dagger"],
    "rolls": {"base_pool": ["potion-healing", "iron-dagger"], "weights": {"potion-healing": 1, "iron-dagger": 1}, "special": null},
    "xp": {"total": 40, "per_member": {"12": 20, "13": 20}}
  },
  "log": ["...omitted..."]
}
```

Notes:
1. `items` is a mapping `{slug: qty}`; `items_list` provides a legacy flat list for backward compatibility.
2. `xp.per_member` keys are stringified character ids.
3. `loot` currently always awards to the first character's inventory; multi-character equitable distribution is a planned enhancement.
4. Fleeing or party defeat returns `rewards: {}` (no xp, no items).

## Balance Tests
Located in `tests/test_combat_balance.py` to lock current behavior:

| Test | Guardrail |
|------|-----------|
| variance bounds | Player damage stays within theoretical min/max (allowing crit inflation) |
| single crit occurrence | Scripted sequence guarantees exactly one crit (verifies crit logging & multiplier) |
| crit sampling distribution | Empirical sample produces at least one and not an implausibly high number of crits over forced-roll sessions |
| defend mitigation | Confirms a defended hit halves post-crit monster damage (min 1) |

These serve as regression tripwires; deliberately update them alongside any formula changes.

## Future Extensions
- Expanded spell list (elemental types, AoE, resist interaction).
- Targeted spells & attacks (choose monster vs. multiple enemies in future multi-enemy encounters).
- More nuanced flee odds (speed differential).
- Distinct STR/DEX scaling for melee/ranged vs. INT/WIS for magic, plus gear modifiers.

## Rate Limiting & Entity Overlay

All `/api/` routes are protected by a lightweight in-memory rate limiter (fixed window):
- General endpoints: 120 requests per 60 seconds (per user id, falling back to IP) per endpoint.
- Movement (`POST /api/dungeon/move`): 300 requests per 60 seconds (~5/sec).

Exceeding a limit returns HTTP 429:
```json
{ "error": "rate_limited", "retry_after": 12, "limit": 300, "window": 60 }
```
`Retry-After` header mirrors `retry_after`.

Dungeon map payloads include an `entity_overlay` field: a 2D array (same dimensions as `grid`) whose entries are `M` (monster), `T` (treasure), `E` (other/future), or `null`:
```json
{
  "grid": [["room", "room"], ["tunnel", "door"]],
  "entity_overlay": [[null, "M"], ["T", null]],
  "player_pos": [12, 34, 0]
}
```
Clients can ignore `entity_overlay` if they prefer to resolve icons purely from the `entities` array.
