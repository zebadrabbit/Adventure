# Combat: zoom into the tile you are standing on

Design direction from the player, 2026-07-28:

> "combat should be its own screen, its an abstraction away from the map itself,
> we 'zoom into' the maps location and the square we're on becomes a larger
> 'zoomed in' grid where we can place 4v1~6 creatures. complete battle, zoom out
> to map."

References (`~/screenshots/`, 2026-07-27): Gold Box tactical grid, Final Fantasy
Pixel Remaster enemy groups, Phantasy Star party panels.

## The idea

Combat is not a separate place. It is the **same place at higher magnification**:
the 16×16 map tile the party occupies becomes an 8×8-ish battlefield. Zoom in,
fight, zoom out. That framing does three useful things at once:

- It explains *where* the fight is happening, which a modal log never did.
- It gives positioning a natural scale — one map tile is a room's worth of floor.
- It makes the existing pack-spawning work pay off: the 1–5 monsters clustered
  near your tile are exactly the group you zoom in on.

## What has to change in the model

`CombatSession` can only express **one** monster:

| column | today |
|---|---|
| `monster_json` | a single monster dict |
| `monster_hp` | one integer |
| `initiative_json` | party members + one monster entry |
| `active_index` | index into that list |

Multi-enemy is therefore a real schema change, not a UI change:

- `monsters_json` — a list, each with its own id, hp, position and status.
- Initiative spanning every combatant, with per-entry references rather than a
  single "monster" type.
- Targeting: every action needs a target id. `player_attack` currently assumes
  "the monster"; `monster_auto_turn` picks a party member via
  `_pick_monster_target` (added 2026-07-27) and would need the mirror image.
- Positions: each combatant needs a grid cell.

`monster_hp` and `monster_json` should stay as read-only accessors over the
first entry for a release, so nothing that reads them breaks mid-migration.

## The battlefield

- **Grid**: one map tile magnified. 8×8 is the working proposal — enough for
  front/back lines and flanking, small enough to read at 1366×768 and to place
  without a pathfinder.
- **Party**: 4 characters, deployed on the side they entered from. Formation
  carries over from the map (front rank melee, back rank casters).
- **Enemies**: 1–6, from the pack that triggered the encounter. Pack size is
  already configurable (`SpawnConfig.group_size_max`, currently capped at 3
  precisely because combat could not field more — raise it once this lands).
- **Terrain**: the tile's own type should colour the field (room floor, corridor,
  doorway), reusing the tileset. A corridor fight should *look* cramped.

## Transitions

Zoom in on encounter, zoom out on resolution. Worth being deliberate: the
transition is what sells "same place, closer" rather than "different screen".
The map already knows the tile coordinates and the renderer already scales
cleanly, so a camera zoom into the party's cell is achievable with the existing
canvas rather than a new one.

While combat runs, the map screen is suspended — movement is already blocked
server-side during combat (`GameClock.combat`), so this is a presentation
concern rather than a new rule.

## What this replaces

The current model is one party vs one monster resolved through a text log, which
produced the playtest complaints directly: "its not fun fighting 1 mob at a
time", "4v1 isn't fun", "everything seems to only attack one character", "feels
more like an idle clicker as all attacks feel lackluster".

Note two of those were separate bugs, already fixed (monsters focused the
lowest-HP character; downed characters still took turns). The remaining
complaints are structural and this design is the answer to them.

## Phasing

1. **Multi-enemy encounters.** Model change, targeting, initiative across all
   combatants. No grid yet — the existing screen with several enemies listed.
   This is the biggest win per unit of work and unblocks raising pack sizes.
2. **The grid.** Positions, deployment, reach/range, movement as an action.
3. **The zoom.** Camera transition, terrain-aware battlefield, the visual layer:
   damage numbers on actors, hit/miss/crit on the sprite rather than only in the
   log.

Each phase is playable on its own, and phase 1 alone fixes the "one at a time"
complaint.

## Settled alongside this

From the same conversation, recorded in the HUD layout spec: no on-screen
movement pad (WASD is bound and the pad only costs vertical space), party frames
on the left edge, and combat as its own screen rather than sharing the explore
frame.

That last one is the decision that shapes this spec: because combat is its own
screen, it can own its layout entirely — party frames, enemy group, log and
action bar arranged for a fight, not inherited from the map view.

## Open questions

1. **Grid size.** 8×8 is a proposal, not a measurement. Worth prototyping with
   six enemies and four characters before committing.
2. **Does movement cost a turn?** Gold Box says yes and it is what makes
   positioning matter. It also lengthens fights, which cuts against "combat
   drags".
3. **Ranged vs melee reach.** Currently every attack is implicitly in range.
   Reach is what makes back-rank casters meaningful — and what makes the grid
   more than decoration.
4. **Fleeing.** `player_flee` exists for a one-monster fight. With a group, does
   the whole party flee, and from which edge?
