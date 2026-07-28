# Character panels and the paper doll

Design direction from the player, 2026-07-28:

> "the paper doll inventory and character panels need to be part of this
> redesign. that may have been part of my confusion"

The confusion in question: the player did not know the game *had* carry weight,
because encumbrance is only visible inside a panel you have to go looking for.
That is the whole problem in one example — the character's state exists, is
computed correctly, and is not where the player is.

## What exists

Two paper-doll implementations, both live:

| file | lines | loaded by |
|------|-------|-----------|
| `equipment.js` | 243 | adventure **and** dashboard |
| `equipment-enhanced.js` | 657 | dashboard only |
| `equipment-shared.js` | 66 | both (extracted common logic) |

`equipment-enhanced.js` is the richer one — drag-and-drop, eight slots
(`weapon, offhand, head, chest, hands, feet, ring, amulet`), item comparison,
set bonuses. `equipment.js` is the simpler panel. The dashboard loads *both*.
`equipment-shared.js` exists because the two had already drifted apart once
(encumbrance thresholds and affix totalling were duplicated); it holds the logic
they must agree on, not the markup.

So there are two paper dolls with different capabilities, and the adventure
screen gets the lesser one.

## What the redesign has to settle

1. **One paper doll, not two.** Which survives — the enhanced panel everywhere,
   or a new one built on the token system? The 657-line version has the features;
   it is also the one that was never available in the dungeon.
2. **Where character state lives during a run.** The adventure HUD spec puts
   party frames on the left edge showing HP/MP. The paper doll is the next layer
   down: click a frame, see the character. That is the natural home, and it means
   the frames and the doll are one design rather than two.
3. **Which numbers are always visible versus one click away.** Encumbrance is the
   worked example: weight is fine one click away, but *"you are encumbered"*
   needs to be on the frame, because it now costs movement in combat.
4. **Inventory and the bag.** Looting, using potions and managing weight all
   happen through this panel. Item usage in combat is specced separately
   ([2026-07-28-combat-item-usage-design.md](2026-07-28-combat-item-usage-design.md))
   but shares the same inventory model, and should share its presentation.

## Constraints

- **Encumbrance is real and now has teeth.** Past capacity a `dex_penalty`
  applies, and combat movement derives from `speed` (`8 + DEX // 2`), so an
  overloaded character will move fewer squares. The panel is where a player
  should understand that *before* the fight, not during it.
- **`equipment-shared.js` is the anti-drift measure.** Whatever replaces the two
  panels must keep shared rules in one place; the file exists because they
  diverged before.
- **The token system is in flight** (`docs/DESIGN_SYSTEM.md`). This panel should
  be built on it, not beside it.
- Gear affects derived stats through `loot_service.gear_bonuses`, folded in by
  `combat_service._derive_stats` and `character_stats.compute_hp_mana_max`. A
  panel that shows a stat must show the *folded* value, or it will disagree with
  combat.

## Open questions

1. **Does the paper doll open in the dungeon**, as an overlay over the map, or
   does it suspend play? Overlay fits the HUD direction; suspending is simpler
   and arguably right if the party is mid-run and the decision matters.
2. **Is the paper doll per-character or party-wide** with a character selector?
   Four characters and one screen; a selector is fewer pixels, four dolls is
   fewer clicks.
3. ~~Does it appear in combat?~~ **Decided**: weapon swaps are allowed in combat
   and cost an action; armour swaps are not allowed at all. Item use is allowed
   and costs an action. Everything else — full re-gearing, trading — is
   out-of-combat only. So the panel appears in a fight, but in a reduced mode:
   weapons and consumables live, armour slots locked. See the action-economy
   table in
   [2026-07-28-tactical-combat-design.md](2026-07-28-tactical-combat-design.md).
