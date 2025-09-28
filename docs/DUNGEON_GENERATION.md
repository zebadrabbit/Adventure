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
5. Invariants enforced (no adjacent doors, door adjacency semantics).
6. Teleport fallback adds logical links if unreachable rooms remain.

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

## Legacy Multi-Phase Pipeline (Retired)
Previously the generator performed numerous normalization and repair phases (chain collapse, dense cluster pruning, orphan tunnel pruning, corner nub pruning, probabilistic carve guards). While powerful, the complexity raised maintenance cost and flakiness risk in edge seeds.

Key retired phases (may return selectively):
- Corridor graph loop enrichment & pruning heuristics
- Door chain / cluster reduction passes (some logic retained in simplified form)
- Hidden area downgrading (rooms -> tunnels) fallback
- Fine-grained phase timing metrics per sub-phase

## Invariants Matrix
| Invariant | Status | Notes |
|----------|--------|-------|
| Deterministic tile counts | Enforced | Seed + parameters => stable metrics |
| No orphan doors | Enforced | Door must border 1 room + 1+ walkable neighbor |
| No adjacent doors | Enforced | Orthogonal adjacency disallowed |
| Corridor repair correctness | Enforced | Gap repairs ensure no wall flanked by 2+ tunnels persists |
| Unreachable rooms <= threshold | Soft | Waived when each unreachable room has teleport coverage |
| Secret door presence | Best-effort | Tests may inject for coverage rather than fail |

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
