# Loot System

The loot subsystem introduces level-aware, rarity-weighted item placements generated lazily the first time a dungeon map is requested for a given seed. Loot nodes are deterministic per seed (placement coordinates and item selection derive from a PRNG seeded with `seed ^ 0xA5F00D`) yet responsive to party progression via an average party level window (±2 levels). This keeps rewards relevant while preserving replay determinism for a given progression state.

See also: [Economy & Progression](ECONOMY_PROGRESSION.md) for the Hoard/extraction risk model that loot feeds into.

## Item Metadata
`Item` records include:
- `level` (int, 0 = utility/no-scaling items like basic potions or tools)
- `rarity` (enum string) — one of: `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythic`

Items without explicit `level`/`rarity` fall back to heuristic inference (name keywords) until seed data is enriched with explicit columns.

## Rarity Weights
Default relative spawn weights (higher = more common):
```
common: 100
uncommon: 55
rare: 25
epic: 10
legendary: 3
mythic: 1
```
These weights apply within the candidate item pool after level filtering. Adjusting them changes the expected long-run distribution but individual dungeons remain small samples (streaks possible).

## Placement Algorithm (Summary)
1. Determine average party level (mean of active characters).
2. Compute level window `(avg-2, avg+2)` clamped to `[1,20]`.
3. Candidate pool: items whose `level` is inside the window, or `level==0` (utility) to avoid starving baseline supplies.
4. Determine target loot node count: baseline (24) + small area scaler (≤ +10), never more than 15% of walkable tiles.
5. Shuffle walkable tiles deterministically; keep a `spread_factor` slice (default 0.85) to reduce clustering bias.
6. Select every Nth tile to reach target count, skipping coordinates already containing loot (idempotence).
7. Weighted rarity roulette to assign one item per chosen tile.
8. Persist placements to `dungeon_loot`.

Calling the generator again for the same seed is idempotent: existing `(x,y,z)` rows are detected and not duplicated.

## API Endpoints
```
GET  /api/dungeon/loot                -> { loot: [ {id,x,y,z,slug,name,rarity,level}, ... ] }
POST /api/dungeon/loot/claim/<id>     -> { claimed: true, item: { slug, name } }
```
Both require authentication. Claimed loot disappears from subsequent list calls.

## Tuning Knobs

| Knob | Status | Effect |
|------|--------|--------|
| `desired_chests` | code constant | Baseline loot node target per map before scaling |
| `spread_factor` | code constant | Fraction of shuffled walkables considered for sampling (lower = more dispersed) |
| Rarity weights | code constant | Relative frequency among candidate pool |
| Level window width | fixed (±2) | Determines progression tightness; wider window dilutes relevance |
| Max tile density (15%) | code constant | Upper bound on loot saturation to avoid clutter |
| Heuristic inference | startup function | Temporary level/rarity assignment for legacy data without metadata |

Planned future surfacing: move these constants into an editable `game_config` row, plus per-depth modifiers (e.g., deeper seeds bias toward higher rarity).

## Roadmap
1. Proximity & line-of-sight checks for claiming.
2. Config-surfaced rarity weights & dynamic scaling by dungeon depth or seed entropy.
3. Explicit metadata for all seed content (remove heuristic inference fallback).
4. Weighted drop tables by item type (e.g., potion bias in early levels).
