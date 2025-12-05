# Dungeon Generation (Current vs Legacy)

This document explains the currently active simplified generator and contrasts it with the retired (legacy) multi‑phase pipeline still partially referenced in historical docs.

## Tile Legend
| Symbol | Meaning | Walkable |
|--------|---------|----------|
| `R` | Room interior | Yes |
| `W` | Wall ring | No |
| `T` | Tunnel / corridor | Yes |
| `D` | Door | Yes |
| `L` | Locked door (walkable placeholder) | Yes |
| `S` | Secret door (unrevealed) | No (until reveal) |
| `C` | Cave / unused space | No |
| `P` | Teleport pad | Yes |

## Active Simplified Generator
Goals: determinism, clarity, low maintenance overhead.

Steps:
1. Seeded RNG chooses non‑overlapping rectangular rooms within bounds.
2. A single wall‑ring is placed around each room.
3. A minimal spanning tree is built between room centers; straight or L‑shaped tunnels carved.
4. Doors inserted where tunnels meet room walls (one per approach).
5. All rooms should be reachable from any other room.

### Determinism
For a given `(seed, size)` the layout (counts and positions of rooms, tunnels, doors) is stable. Tests regenerate dungeons multiple times to assert equality on metric subsets.

### Connectivity Strategy
Primary: corridor MST ensures baseline connectivity.
Secondary: teleport fallback ensures logical reachability without additional carving (protects wall/door invariants).

### Metrics (Active Subset)
Only a lean metrics set is guaranteed stable:
- Door counts
- Room / wall / tunnel tile counts
- Teleport service metrics (`teleport_pairs`, `unreachable_rooms_via_teleport`)
- (Optional timing) total generation runtime


## Extension Points
Planned opt‑in modules could layer back advanced features:
- Feature decorators (loot nodes, environmental hazards)
- Encounter seeds & spawn tables
- Multi-depth (z-layer) stacking
- Procedural theming / biomes (tile palette variation)
- Advanced path variety (curved or braided tunnels)

## Testing Strategy Overview
Representative seeds are sampled to assert invariants. Teleport logic tests provide coverage for logical reachability. Structural BFS is compared to teleported coverage counts for diagnostic parity.

## Performance Notes
The simplified generator targets sub‑50ms creation for medium maps on commodity hardware; caching of `Dungeon` instances avoids repeated generation per session.

## Migration Guidance
If re‑introducing a legacy phase:
1. Implement it as a pure function taking the grid & RNG.
2. Add metric counters in a dedicated metrics struct.
3. Introduce guarded tests (seed sample) verifying the new invariant.
4. Keep fallback safety (never degrade door invariants).

## Teleport Integration
See `TELEPORTS.md` for details; integration occurs after base carving but before final metrics snapshot.
