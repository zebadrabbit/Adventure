# Using inventory items in combat

Playtest, 2026-07-28:

> "add item usage from combat, theres no way to use inventory items like looted
> potions."

## What already works

More than the symptom suggests, which is why this is a contained job:

- `POST /api/combat/<id>/use_item` exists and is wired to
  `combat_service.player_use_item`.
- It **does** consume the item: the character's `items` JSON is decremented and
  committed, so there is no infinite-potion bug.
- The party snapshot carries `item_counts` so the client can grey out a button
  when a character has none left, counted **per character** rather than as a
  shared party pool.

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
