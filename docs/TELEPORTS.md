# Teleport System

Teleport pads provide a logical (non-structural) fallback for dungeon room reachability when carving leaves isolated rooms.

## Rationale
Traditional full structural repair (aggressively carving new tunnels) risks violating other invariants (wall rings, door density). Teleports preserve all existing geometry while guaranteeing that exploration cannot dead‑end solely due to generation artifacts. Tests treat teleported rooms as logically reachable.

## Tile & Symbols
`P` – Teleport pad (walkable).

## Placement Algorithm (Summary)
1. Run a flood fill from entrance over walkable tiles (room, tunnel, door, locked door, teleport).
2. Identify rooms (by interior coordinates) not reached (`unreachable_rooms`).
3. For each unreachable room pick one interior coordinate (center preference, else first).
4. Select a random reachable interior room coordinate as the destination.
5. Emit a pair of teleport pads: one in the unreachable room, one in the reachable room (unless a pad already exists there).
6. Build `teleport_pairs` list and an O(1) `teleport_lookup` dict mapping each pad -> its partner.
7. Update metrics: `unreachable_rooms_via_teleport` and reconcile with raw unreachable count for diagnostics.

Pads are only placed if unreachable rooms exist. A second discrepancy scan can add a pair if metric vs. BFS disagreement is detected.

## Data Structures
| Name | Type | Description |
|------|------|-------------|
| `teleport_pairs` | `list[tuple[(int,int),(int,int)]]` | Ordered pairs of coordinates linking pads |
| `teleport_lookup` | `dict[(int,int)->(int,int)]` | Both directions present for O(1) activation |
| `unreachable_rooms_via_teleport` | `int` | Count of unreachable rooms serviced |

## Movement Activation Flow
1. Player requests a move (or no-op stay) onto a tile.
2. Server validates walkability.
3. If the tile coordinate exists in `teleport_lookup`, position is immediately rewritten to the destination.
4. Response payload (`pos`) reflects *post* teleport coordinate; the client does not perform an extra request.

Activation is single-hop (no chaining safeguard needed because destinations are normal room tiles or another pad that maps back). A visited loop risk is negligible; if desired, future logic can mark a pad as cooled‑down for a tick.

## Tests
`test_dungeon_teleport_movement.py` forces generation of at least one teleport pair (injecting one if none exist) and asserts that stepping on the source pad warps to the destination. Connectivity tests treat rooms behind teleports as acceptable exceptions if every unreachable room is covered.

## Invariants Affected
| Invariant | Adjustment |
|-----------|-----------|
| Unreachable room cap | Relaxed when every unreachable room has a teleport pad. |
| Walkability classification | Teleports are walkable for BFS and movement. |

## Metrics & Debugging
If debug logging is enabled a mismatch between computed unreachable rooms and teleport service count will emit a warning for investigation. Duplicate or overlapping pads are avoided by checking existing tile types before placement.

## Future Extensions
- Directional or one-way teleports (consuming pad on use).
- Thematic variation (runes, portals) with per-pad metadata.
- Discovery gating (teleport inactive until item/lever triggered).
- Limited charges or cooldown timers.
- Visual client animation (fade / particle) on activation.

## Removal Strategy
If future structural connectivity becomes 100% reliable teleports can be gated by a feature flag or removed; tests should then be tightened to reassert zero unreachable rooms across seed samples.
