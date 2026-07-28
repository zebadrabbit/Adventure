# Character panels and the paper doll

Design direction from the player, 2026-07-28:

> "the paper doll inventory and character panels need to be part of this
> redesign. that may have been part of my confusion"

The confusion in question: the player did not know the game *had* carry weight,
because encumbrance is only visible inside a panel you have to go looking for.
That is the whole problem in one example — the character's state exists, is
computed correctly, and is not where the player is.

**Status: settled 2026-07-28.** The investigation below turned up a second,
larger instance of the same failure — gear that is equipped, affecting stats,
and not drawn anywhere the player can reach. The decisions are recorded in
[Decided](#decided-2026-07-28).

## What exists

Two paper-doll implementations, both live:

| file | lines | loaded by |
|------|-------|-----------|
| `equipment.js` | 243 | adventure **and** dashboard |
| `equipment-enhanced.js` | 657 | dashboard only |
| `equipment-shared.js` | 66 | both (extracted common logic) |

`equipment-enhanced.js` is the richer one — drag-and-drop, eight slots, item
comparison, set bonuses. `equipment.js` is the simpler panel. The dashboard
loads *both*: `equipment.js:222` delegates `.btn-equip-panel` clicks to
`window.equipmentManager` when it exists, while `equipment-enhanced.js:123`
also binds its own document-level listener for the same class, so one click
runs both paths. `equipment-shared.js` exists because the two had already
drifted apart once (encumbrance thresholds and affix totalling were
duplicated); it holds the logic they must agree on, not the markup.

So there are two paper dolls with different capabilities, and the adventure
screen gets the lesser one.

## The real defect: two slot vocabularies

Deduplication is the smaller half of this. `inventory_api.equip_item` has two
paths that write into the **same** `gear` dict using **different** slot names:

| path | reached by | slot source | names produced |
|---|---|---|---|
| gear-instance (`uid`) | procedural dungeon loot | `inst["slot"]`, validated against `archetypes.SLOTS` | `hands`, `feet`, `ring` |
| legacy slug | authored catalogue items | `_slot_for_item()` keyword inference | `boots`, `gloves`, `ring1`, `ring2` |

`inventory_api._SLOTS` accepts all thirteen names as a union, so both writes
succeed. A character's gear dict can therefore hold `gloves` **and** `hands` at
once — two pairs of gloves equipped simultaneously, both folded into derived
stats.

The panels split along the same seam:

- `equipment.js:111` renders `weapon, offhand, head, chest, legs, boots, gloves,
  ring1, ring2, amulet` — no `hands`, `feet` or `ring`.
- `equipment-enhanced.js` renders the canonical eight — no `legs`, `boots`,
  `gloves` or `ring2`.

`equipment.js` is the panel the **dungeon** gets. `app/loot/data/archetypes.py:8`
is what all procedural loot targets. The two do not intersect on three slots.

**A player loots procedural gauntlets in the dungeon, equips them, and the only
panel available in the dungeon has nowhere to draw them.** They are worn, they
change the character's stats, and they are invisible. This is the same failure
as the encumbrance complaint, one layer down, and it is why this work is worth
more than a file merge.

## Decided (2026-07-28)

### One slot vocabulary: the canonical eight

`weapon, offhand, head, chest, hands, feet, ring, amulet`.

`app/loot/data/archetypes.py:8` already defines it, and every procedural
archetype, prefix and suffix keys off it — it is what the player actually
finds. It becomes the single source of truth:

- `inventory_api._SLOTS` imports `archetypes.SLOTS` rather than restating a
  thirteen-name union.
- `_slot_for_item()` returns canonical names: `hands` not `gloves`, `feet` not
  `boots`, `ring` not `ring1`/`ring2`. This is what makes an authored catalogue
  item land in the same slot a procedural one would.

Costs: the second ring slot, and there is no canonical `legs` slot.

### Existing gear migrates in place

An Alembic **data** migration rewrites each character's `gear` JSON:

| from | to |
|---|---|
| `gloves` | `hands` |
| `boots` | `feet` |
| `ring1`, `ring2` | `ring` |
| `legs` | back to the bag — no canonical slot exists |

Where both the legacy and canonical names are occupied, the legacy item loses
and returns to the bag. Where both `ring1` and `ring2` hold items, `ring1` takes
the single `ring` slot and `ring2` returns to the bag. Nothing is deleted; the
player keeps every item.

The migration touches column *data*, not schema. It issues no DDL, so it is
not exposed to the `create_all`-pre-creates-columns hazard that requires
guards on this project's schema revisions.

### One renderer, two mounts

`app/static/js/equipment-panel.js` replaces all three existing files (966 lines
combined):

```
EquipmentPanel.mount(container)   // render the skeleton into whatever it is handed
EquipmentPanel.open(charId)       // fetch /api/characters/<id>, render, show
EquipmentPanel.close()
```

- **`/adventure`** mounts it in `<aside class="adv-character">` inside
  `.adv-hud`, occupying the box right of the party rail and above the log
  band — roughly 1050×540 at the 1366×768 design floor.
- **Dashboard** mounts it into the existing Bootstrap modal body.

One set of slot, doll, bag, encumbrance and comparison code; two thin wrappers.
`equipment-shared.js` folds in — it exists solely to stop two implementations
drifting, and there will be one.

Everything `equipment-enhanced.js` can do — drag-and-drop, comparison tooltips,
set bonuses — reaches the dungeon for the first time.

### The party rail is the character selector

The adventure HUD already puts four frames down the left edge, and
`.adv-frame-open` already opens that character. Because the panel sits *beside*
the rail rather than over it, clicking a different frame swaps the panel's
contents with the panel still open. No in-panel selector is built.

### The panel may cover the camera target, transiently

The HUD layout spec's constraint 2 forbids overlays over the party's position.
This panel is a deliberate exception: it is transient and focused, not
persistent furniture, and a player choosing gear is not reading the map.

**Moving closes the panel**, so the player never walks blind underneath it.
Esc closes it; so does its close button; clicking another frame swaps rather
than closes.

### The Bags button goes

Frames carry an Equipment button and a Bags button, and the whole frame is also
a click target — three ways to open roughly the same thing. The panel shows
slots, doll and bag together, as `equipment-enhanced.js` already does, so
`.btn-bag-panel` and its handlers are deleted.

### Encumbrance moves onto the frame

`build_party_payload` does not carry encumbrance, so the frame cannot show it.
It gains an `encumbrance` field — `encumbrance_state()` already computes it —
and `refreshPartyCards` paints an "Encumbered" / "Overloaded" marker on the
frame.

The weight numbers stay one click away in the panel. The *state* goes on the
frame, because past capacity a `dex_penalty` applies, combat movement derives
from `speed` (`8 + DEX // 2`), and a player needs to know they are a square
short *before* the fight rather than during it.

## Constraints

- **A panel that shows a stat must show the folded value.** Gear affects derived
  stats through `loot_service.gear_bonuses`, folded in by
  `combat_service._derive_stats` and `character_stats.compute_hp_mana_max`. A
  panel showing unfolded numbers will disagree with combat.
- **The token system is canonical** (`docs/DESIGN_SYSTEM.md`). The panel is
  built on it, not beside it: `--radius: 0`, semantic tokens only, no
  `!important`, scoped page CSS.
- **Equip and unequip are locked during combat** (`_reject_if_in_combat`,
  returning `in_combat` with a message). The panel surfaces that message rather
  than failing silently. A reduced in-combat mode — weapons and consumables
  live, armour locked — belongs to the combat chunk, not here.

## Scope

Not included, deliberately:

- **Combat's reduced-mode panel.** Specified in
  [2026-07-28-tactical-combat-design.md](2026-07-28-tactical-combat-design.md);
  this chunk only makes the API's existing refusal legible.
- **Item usage in combat.** Separate spec,
  [2026-07-28-combat-item-usage-design.md](2026-07-28-combat-item-usage-design.md),
  sharing the same inventory model.
- **Restoring a second ring slot or a legs slot.** If either is wanted back it
  is a change to `archetypes.SLOTS` and the loot generator, not to the panel.

One adjacent item folded in because it is a few lines and it is the most
visible flaw on the redesigned screen: `tactical-btn-primary`, `-info` and
`-success` have no base colour or border rules anywhere in the codebase, so
three of the five buttons in the new floating action bar render as bare browser
buttons. They get base styles in `theme.css`.

## Open questions

None. The three the earlier draft carried are resolved above: the panel
overlays rather than suspends, the rail is the selector rather than an in-panel
control, and the in-combat question was already decided in the tactical-combat
spec.
