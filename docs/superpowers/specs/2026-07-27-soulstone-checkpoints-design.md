# Soulstones — one-shot checkpoints

## The problem being solved

Playtest, 2026-07-27:

> "if we're going to keep this map so much of a tight maze, we should make
> checkpoints (name them something like Soulstone) that will allow a party deep
> in a maze to teleport to that specific stone 1 time, then its burned out. I
> ask for this because I spent a loooong time in a maze and got to the end and
> nothing was there and was frustrated I had to find my way back."

Two distinct frustrations are bundled there, and they want different fixes:

1. **Backtracking has no gameplay in it.** Walking a known corridor back is
   pure time. Soulstones address this.
2. **A long dead end contained nothing.** That is a *generator* problem — the
   maze rewards exploration with emptiness. Soulstones make it cheaper to
   recover from, but the real fix is that dead ends should hold something
   (treasure, a room event, a prop worth seeing). Tracked separately in the
   playtest triage under "props" and "maze tuning". **Do not let Soulstones
   become the excuse not to fix that.**

## Design

A **Soulstone** is a placed, per-floor anchor that a party can attune to and
later recall to, exactly once.

### Lifecycle

| State | Meaning | Player sees |
|-------|---------|-------------|
| Dormant | Placed, not yet touched | Dim stone on the map |
| Attuned | Party has touched it; recall available | Lit stone; recall button enabled |
| Burned | Recall used | Cracked/dark stone; no longer usable |

Only the most recently attuned stone is the recall target — attuning to a second
stone replaces the first as the destination but does **not** re-arm a burned
one. One recall per stone, ever, per run.

### Placement

- Deterministic from the floor seed, like treasure caches and room events, so a
  seed always produces the same stones.
- **2 per floor**, in *dead-end rooms* — the very places that are expensive to
  walk back from. Deliberately not on the critical path.
- Never within `_MIN_ENTRANCE_DISTANCE` of the floor entrance (recalling to
  where you started is worthless).
- One per room maximum.

### Recall

- Available only when the party has an attuned, unburned stone **on the current
  floor**. Cross-floor recall is out of scope for v1: it interacts with stairs,
  the sealed loot room and extraction in ways worth thinking about separately.
- Recall moves the party to the stone's tile, burns it, and costs game ticks
  (proposed: same as a camp, 8) so it is a real decision rather than a free
  rewind.
- Refused during combat.
- Refused if the party is wiped (consistent with movement).

### Why "one shot"

The player asked for it explicitly, and it is the right shape: a reusable
teleport network removes the maze entirely, while a single-use anchor makes
"where do I attune?" the interesting decision. Burning is what gives the choice
weight.

## Implementation sketch

Existing machinery covers almost all of this:

- **Entity**: a new `DungeonEntity` type `"soulstone"`, seeded per floor in
  `app/dungeon/room_events.py` alongside shrines/traps/ambushes, keyed off
  `floor_seed(instance.seed, z)`. Unlike traps and ambushes it **is** sent to
  the client (it must be visible), so it does not belong in
  `HIDDEN_ROOM_EVENT_TYPES`.
- **Attune**: stepping onto the tile, handled by `resolve_events_at` like a
  shrine. State recorded in `instance.dungeon_metadata["soulstone"]` as
  `{"attuned": [x, y, z], "burned": [[x, y, z], ...]}`.
- **Recall**: `POST /api/dungeon/recall`, mirroring `dungeon_camp`'s shape —
  validate, mutate position, advance time, return the new position. The client
  already knows how to re-render after a position change (`floor_changed`
  handling in `process_movement` is the closest precedent).
- **Rendering**: a tile sprite, or an entity icon. The tileset has candidate
  art — `Set 1.1.png` cell `(4,6)` is a floor with a circular seal, and the
  fountain cells at rows 8–9 read as "special place".

## Open questions

1. **Two per floor, or scale with floor size?** A 27-room floor may want three.
2. **Should attuning cost anything?** Currently free; the cost is that stones
   are off the critical path.
3. **Does recall survive a floor change?** v1 says no. If a player attunes on
   floor 1, descends, and dies on floor 2, is losing the anchor correct? Leaning
   yes — anchors are per-floor conveniences, not a save system.
4. **Interaction with the wipe rule.** A wipe deletes the instance, so stones die
   with it. Consistent, and worth stating so it does not surprise anyone.
5. **Name.** "Soulstone" is the player's word and it is good. Worth checking it
   does not collide with existing terminology (it does not today).

## What this does not fix

Backtracking is only painful because the map is a tight maze with empty ends.
Soulstones are an escape hatch. The maze tuning pass (`dead_end_keep`,
`extra_connection_chance`, `straight_max`) and putting *something worth finding*
in dead ends are the real fixes, and should not be deprioritised because a
mitigation exists.
