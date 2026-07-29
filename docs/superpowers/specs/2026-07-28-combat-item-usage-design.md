# Using inventory items in combat

Playtest, 2026-07-28:

> "add item usage from combat, theres no way to use inventory items like looted
> potions."

## What already works

More than the symptom suggests, which is why this is a contained job:

- `POST /api/combat/<id>/use_item` exists and is wired to
  `combat_service.player_use_item`.
- It decrements the character's `items` JSON and commits.
- The party snapshot carries `item_counts` so the client can grey out a button
  when a character has none left, counted **per character** rather than as a
  shared party pool.

## Correction (2026-07-29): three live bugs this spec missed

An exploration pass before implementation found the ground less solid than the
section above claims. All three are fixed as part of this work.

**1. There is an infinite-potion bug.** The line above is wrong.
`player_use_item` (`combat_service.py:1602-1622`) applies the effect on a bare
slug string match against the party snapshot, and decrements inventory
*afterwards* (`:1623-1666`) inside a `try/except` that logs at debug and
swallows everything. `removed_successfully == False` rolls nothing back. So
`POST /api/combat/<id>/use_item {"slug": "potion-healing"}` with an empty bag
heals 25 and burns a turn, repeatably. The only gate on having the item is
client-side (`combat.js:436`). **Ownership must be verified before the effect is
applied, not after.**

**2. 127 of the 154 potions are consumed and destroyed for nothing out of
combat.** `inventory_api.consume_item` (`:613-628`) matches by unanchored
substring — `"regen"`, then `"healing"`, then `"mana"`. The catalogue slugs say
`heal`, not `healing`, so all twenty `potion_heal_lN` fall through every branch,
are removed from the bag, and grant zero HP. Everything outside those three
substrings does the same.

**3. The same potion does two different things.** `potion-healing` heals **25 in
combat** (clamped to `max_hp`) and **5 out of combat** (unclamped, can exceed
max). The comment at `combat_service.py:1610` claims the two paths were aligned
deliberately; only mana actually is. Unifying them means out-of-combat healing
rises to match combat — one potion, one effect.

There are also **three** item→effect derivations in the codebase, not two:
`loot_api._get_item_effects` (`:463`, display-only), `inventory_api._item_effects`
(`:116`, load-bearing — folded into character stats), and the two consumption
paths above. The first two concern equipment rather than potions and are out of
scope here, but they are the same class of duplication as the gear-slot
vocabularies and belong in the same eventual sweep.

## Correction (2026-07-29): the catalogue does not map onto the engine

This spec's framing — a resolver and "all 154 work with no data change" — does
not survive contact with the combat engine. Most families have nothing to attach
to. What each can express today:

| family | count | verdict |
|---|---|---|
| `heal`, `mana` | 40 | **Works now.** Needs only tier scaling. |
| `buff_attack`, `buff_defense` | 40 | Needs *one* shared piece: an effect kind that modifies a derived stat and expires. The snapshot is mutable so a modifier sticks, but nothing can un-apply it — there is no expiry hook and no recompute pass. `defense` is evasion only, so a defence potion makes you harder to hit, not tougher. |
| `resist_fire` | 5 | Same extension. The resist pipe is complete (`combat_utils.apply_resistances`, called with `["fire"]` at `combat_service.py:1383`) but player `resistances` is hardcoded `{}` at `:209`, so it is live code that always no-ops. |
| `antidote` | 5 | Needs a `remove_effect` primitive — none exists; `status_effects` can add and replace but never remove, and expiry is the only route today. Must also delete the `CharacterStatusEffect` row or the poison returns via `_derive_stats:177-186`. |
| `buff_speed` | 20 | **No mechanic.** `speed` is read once, by `_calc_initiative` during `start_session`, and never again. Requires dynamic or re-rolled initiative. |
| `resist_cold`, `resist_lightning`, `resist_poison` | 15 | **No mechanic.** No cold or lightning damage ever reaches a player — monster attacks hardcode `["physical"]` and the one firebolt `["fire"]`; the `damage_types` column exists and no damage path reads it. Poison bypasses `apply_resistances` entirely. Also the element string is `"ice"`, not `cold`. |
| `stamina` | 5 | **No mechanic.** Zero references in `app/`. |
| `perception` | 5 | **No combat mechanic.** Exists only in exploration (`perception.py`), reads `Character.stats` rather than the combat snapshot. Viable as an out-of-combat consumable only. |
| `group_battle`, `invis`, `luck` | 12 | Not in this spec's original table at all. No mechanic. |

Note also `stun` has a handler (`status_effects.py:102`) that nothing can
trigger — `add_effect` is never called anywhere in `app/`.

## Decided (2026-07-29)

**Scope: the resolver and the two families that work, not the mechanics.**

- **One resolver, shared by both paths**, so a potion behaves identically in and
  out of a fight. Pattern-based, per option 1 below: parse `potion_<family>_l<N>`
  and the three legacy hyphenated slugs, return a typed effect descriptor.
- **`heal` and `mana` scale with the `_lN` tier.** They are the only two families
  the engine can express without new machinery, and the tier suffix is the only
  strength signal that exists — `Item.level` is `0` for all 154, `rarity` is 153
  common, and `description` contains no digits. `value_copper` is the sole other
  monotonic correlate and it is price, not potency.
- **A family with no implemented effect refuses and keeps the item.** The player
  gets a readable "that has no effect yet" and loses nothing. This replaces the
  current silent destruction, and it makes the content gap visible instead of
  hiding it — which matters, because 100 of the 154 potions are in that state
  and will be until the mechanics exist.
- **Ownership is verified before the effect is applied.** Closes the infinite
  potion.

Deliberately **not** built: the expiring stat-modifier effect kind, the
`remove_effect` primitive, dynamic initiative, typed damage reaching players, and
stamina. Each is a combat-mechanics change that competes with the tactical
combat overhaul rather than belonging to an item-usage chunk, and the resolver is
designed so adding a family later is a table entry plus a handler.

## What is missing

Two hardcoded lists, and the catalogue has long since outgrown both.

**The service knows three slugs** (`combat_service.player_use_item`):

| slug | effect |
|------|--------|
| `potion-healing` | +25 HP, flat |
| `potion-mana` | +5 MP, flat |
| `potion-regen` | regen buff, 5 ticks |

**The UI offers two buttons** (`combat.html`, `combat.js`): heal and mana. Note
`potion-regen` is implemented in the service but has no button at all — it is
unreachable from combat.

**The catalogue holds 154 potions.** Everything else a player finds, buys or
loots is dead weight in a fight:

| slug family | count |
|---|---|
| `potion_heal_lN`, `potion_mana_lN` | 20 each |
| `potion_buff_attack_lN`, `potion_buff_defense_lN`, `potion_buff_speed_lN` | 20 each |
| `potion_resist_fire/cold/lightning/poison_lN` | 5 each |
| `potion_antidote_lN`, `potion_stamina_lN`, `potion_perception_lN` | 5 each |

So the loot the player just fought for cannot be used in the next fight. The
three hardcoded slugs are not even part of that scheme — they are the old
kebab-case starter items.

## The design question

How does an arbitrary item become a combat effect? Three options:

1. **Pattern-based resolution** (recommended). The catalogue's slugs are highly
   regular: `potion_<effect>_l<level>`. A resolver maps the effect word to a
   handler and scales by the level suffix, so all 154 work with no data change
   and any future `potion_x_lN` is free. Risk: it is a naming convention, and a
   typo silently yields nothing.
2. **An `effect_json` column on Item**, mirroring `Skill.effect_json`. Explicit
   and inspectable, works for non-potions too, and the admin panel could edit
   it. Costs a migration plus backfilling 154 rows.
3. **A registry keyed by slug pattern** in code — a middle road. No migration,
   explicit, but a second place to update whenever items are added.

Worth knowing before choosing: **`Item.level` is 0 for every potion in the
catalogue** (see the table above — `min(level), max(level)` are both 0), so the
`_lN` suffix is currently the *only* signal of a potion's strength. Whichever
option is chosen, either the suffix is parsed or those levels need backfilling.

`loot_api._get_item_effects` already derives display-only effects from slug and
type heuristics, and `inventory_api.consume_item` has out-of-combat potion
logic. Both are precedents, and both would ideally collapse into whatever
resolver this produces so a potion behaves identically in and out of combat.

## UI

The two fixed buttons should become an item panel for the *active* character:

- Lists their usable inventory, with counts, from `item_counts` (which needs to
  carry more than two slugs).
- Disabled entries when the count is zero, as the current buttons already do.
- Grouped by effect so a bag of twenty potions is not a wall.
- Keyboard-reachable, consistent with the existing hotkeys.

Note the combat screen is also due a redesign (see the HUD layout spec) — the
panel should be designed to live inside that, not bolted onto the current
layout.

### What the paper-doll chunk already built (2026-07-29)

This spec predates the panel consolidation, and three of its assumptions have
moved:

- **There is one inventory renderer now**, `equipment-panel.js`, mounting into
  any container it is handed (a modal on the dashboard, a HUD panel on
  `/adventure`). A combat item panel is a third mount, not a fourth
  implementation. `equipment.js` and `equipment-enhanced.js` are gone.
- **Its bag grid already resolves an item's verb from its type** — potions POST
  `/consume`, equippables POST `/equip` — with a tooltip action line, `title`,
  `role="button"`, `tabindex="0"`, Enter/Space activation and an `e.repeat`
  guard. Combat use is the same shape against a different endpoint, so "grouped
  by effect, disabled at zero, keyboard-reachable" is largely a restyle of a
  working control rather than new interaction work.
- **`inventory_api.consume_item` is now reachable from the dungeon**, so the
  "collapse both precedents into one resolver" note above has a live second
  caller and is worth more than when it was written.

The action-economy rule still holds: `player_use_item` sets `phase = "end"` and
progresses the turn, so item use already costs an action.

## Scope

Deliberately not included: throwables, scrolls with combat effects, and using an
item on *another* party member (all current effects apply to the actor). Each is
a real feature; none is required to make looted potions usable.
