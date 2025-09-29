# Adventure

_Formerly: Adventure MUD (Multi-User Dungeon)_

[![CI](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml/badge.svg)](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml)

A modern web-based multiplayer dungeon adventure game built with Python (Flask, Flask-SocketIO), SQLite, and Bootstrap.

> Quick Links: [Dungeon Generation](docs/DUNGEON_GENERATION.md) · [Teleports](docs/TELEPORTS.md) · [Development Workflow](docs/DEVELOPMENT.md) · [Architecture](docs/architecture.md) · [Combat System](#combat-system)

## TL;DR Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py server  # visit http://localhost:5000

# Run tests / lint / format
pytest -q
ruff check .
black --check .
```

Want to format and auto-fix imports / simple issues:
```bash
ruff check --fix .
black .
```

---

## Code Style & Linting

The project uses Ruff + Black with a unified line length of 120 characters (relaxed from 100) to reduce noisy wrapping in
tests and data-heavy assertions. Previous per-file ignores for `E501` in `tests/` were removed; instead, we favor clearer
one-line payload constructions and assertion context. Long, descriptive comments are still welcome; if an exceptional
line exceeds 120 for readability (rare), it may be annotated with `# noqa: E501` along with a brief rationale.

Enforced rule families (see `pyproject.toml`):
- E, W (pycodestyle)
- F (pyflakes)
- I (import sorting)
- UP (pyupgrade), B (bugbear), SIM (simplify), C4 (comprehensions)

Rationale for 120:
1. Reduces churn when adding parameters to test payloads.
2. Keeps assertion messages (especially with f-string context) readable without artificial fragmentation.
3. Aligns with common wider-line conventions (PSF tooling supports 120 as an accepted alternative to 79/88/100).

If you prefer a stricter wrap in a particular block (e.g., documentation examples), you can manually format and optionally
add a `# fmt: off / # fmt: on` pair for Black isolation (use sparingly).

### Docstring Style
Docstrings follow a lightweight Google style variant:

```python
def player_attack(session_id: int, user_id: int, version: int) -> dict:
	"""Execute a player attack action.

	Args:
		session_id: Active combat session id.
		user_id: Acting user's id (authorization verified internally).
		version: Optimistic concurrency token; must match current session.version.

	Returns:
		dict: Serialized session delta or version_conflict payload.

	Raises:
		ValueError: If the session is not found or action not permitted.
	"""
	...
```

Guidelines:
1. Module-level docstring: 1–3 line summary + (optional) longer paragraph describing invariants or side effects.
2. Public functions / service entry-points get full Google-style sections (Args / Returns / Raises). Internal helpers may use a single-sentence docstring if obvious.
3. Keep imperative mood: "Return" vs "Returns" acceptable; be consistent within file.
4. Avoid restating parameter types already in annotations unless clarifying semantic domain (e.g., "seed: Deterministic dungeon seed (int <= 2^63-1)").
5. Prefer documenting important invariants (e.g., idempotence, optimistic lock behavior) over trivial echoing of names.

Rationale: Emphasis on operational contracts and invariants supports contributors making balance / pipeline changes without regressions.

### Running Lint & Format Locally

Automation-friendly one-liners:
```bash
ruff check . && black --check . && pytest -q
```
Or with auto-fix:
```bash
ruff check --fix . && black .
```

Pre-commit integration (optional):
```bash
pip install pre-commit
pre-commit install
```
The existing repo hooks (see `.pre-commit-config.yaml`) will then enforce style (including template inline-style bans) before each commit.

### Common Ruff Suppressions
Use inline `# noqa: <RULE>` only when **necessary** and add a brief reason, e.g. `# noqa: E501 (example payload clarity)`.

---


## Generation Guarantees (Summary)
Core invariants (doors, corridor repair, determinism, logical reachability via teleports) are enforced by the test suite. For the full invariant matrix and legacy vs. current generator details see [Dungeon Generation](docs/DUNGEON_GENERATION.md).

### Teleports (Overview)
Teleport pads (`P`) provide a logical fallback for unreachable rooms without additional corridor carving. An O(1) lookup (`teleport_lookup`) enables instant activation in movement. See the dedicated [Teleports](docs/TELEPORTS.md) document for placement algorithm, data structures, and test strategy.


### Updated Tunnel & Door Rules (v0.6.x)
The tunnel algorithm now enforces a strict "single-door-per-approach" rule:

* Tunnels only carve through `CAVE` tiles.
* When a carving path encounters the first `WALL` tile adjacent to a `ROOM`, that wall is converted to a single `DOOR` and carving stops.
* Additional walls are never overwritten in the same approach, preventing multi-door bursts along one wall segment.
* Post‑carve a localized de-duplication sweep collapses any accidental adjacent door placements, restoring one canonical door.

Rationale:
1. Preserves clean wall rings and readable silhouettes for rooms.
2. Eliminates confusing double/triple doorway clusters that added little tactical differentiation.
3. Simplifies invariant reasoning (tests now assert absence of orthogonally adjacent doors globally).

Door variants (`SECRET_DOOR = 'S'`, `LOCKED_DOOR = 'L'`) are probabilistic and may not appear in small sample sizes or narrow seed ranges. Tests therefore treat their absence as an expected (xfail) condition rather than a hard failure. Secret doors are non-walkable until revealed; locked doors are currently walkable placeholders for future lock/key logic.

#### Secret Door Reveal API
Players (or future perception / skill systems) can reveal a planted secret door using a lightweight endpoint:

```
POST /api/dungeon/reveal
Body: { "x": <int>, "y": <int> }
```

Rules / Validation:
1. User must have an active dungeon instance (session keys: `dungeon_instance_id`, `dungeon_seed`).
2. `(x,y)` must be inside current map bounds (75x75 default).
3. Tile at `(x,y)` must currently be a secret door (`'S'`).
4. Player must be within Manhattan distance `<= 2` of the target (placeholder proximity rule; will evolve into perception/search mechanics).

Successful response (HTTP 200):
```
{ "revealed": true, "tile": "D" }
```

Failure responses (HTTP 400/404):
```
{ "error": "x and y required" }
{ "error": "No dungeon instance" }
{ "error": "Out of bounds" }
{ "error": "Too far" }
{ "error": "Not a secret door" }
{ "error": "Reveal failed" }
```

Implementation Notes:
* The endpoint mutates the live cached dungeon grid in-place (revealing updates subsequent map/state fetches immediately).
* Future extensions may gate success behind a perception check or a required item (e.g., magnifying lens) before promoting `S -> D`.
* Distance rule kept intentionally small to discourage blind coordinate probing.
* The current test suite includes positive and negative cases (distance and wrong-tile) ensuring baseline contract stability.

If future design favors richer tactical entry options (multiple doors) this rule can be relaxed by reintroducing controlled multi-door generation and adjusting the xfailed legacy test `test_multiple_doors_possible`.

---

## Loot System (Experimental)
The new loot subsystem introduces level-aware, rarity-weighted item placements generated lazily the first time a dungeon map is requested for a given seed. Loot nodes are deterministic per seed (placement coordinates and item selection derive from a PRNG seeded with `seed ^ 0xA5F00D`) yet responsive to party progression via an average party level window (±2 levels). This keeps rewards relevant while preserving replay determinism for a given progression state.

### Item Metadata
`Item` records now include:
* `level` (int, 0 = utility/no-scaling items like basic potions or tools)
* `rarity` (enum string) – one of: `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythic`

Bulk item seeds (weapons, armor, potions, misc) live under `sql/`. Startup loads these `.sql` files idempotently; items without explicit `level`/`rarity` fallback to heuristic inference (name keywords) until the SQL is enriched with explicit columns. You can safely re-run the server; existing slugs are skipped.

### Rarity Weights
Current default relative spawn weights (higher = more common):
```
common: 100
uncommon: 55
rare: 25
epic: 10
legendary: 3
mythic: 1
```
These weights apply within the candidate item pool after level filtering. Adjusting them changes the expected long-run distribution but individual dungeons remain small samples (streaks possible). Future tuning will surface these in a config table / admin UI.

### Placement Algorithm (Summary)
1. Determine average party level (simple mean of active characters; placeholder currently – may extend to median or weighted).
2. Compute level window `(avg-2, avg+2)` clamped to `[1,20]`.
3. Candidate pool: all items whose `level` is inside the window OR `level==0` (utility) to avoid starving baseline supplies.
4. Determine target loot node count: baseline (24) + small area scaler (≤ +10) but never more than 15% of walkable tiles.
5. Shuffle walkable tiles deterministically; keep a `spread_factor` slice (default 0.85) to reduce clustering bias.
6. Select every Nth tile to reach target count, skipping coordinates already containing loot (idempotence).
7. Weighted rarity roulette to assign one item per chosen tile.
8. Persist placements to `dungeon_loot`.

Calling the generator again for the same seed is idempotent: existing `(x,y,z)` rows are detected and not duplicated.

### API Endpoints
```
GET  /api/dungeon/loot                -> { loot: [ {id,x,y,z,slug,name,rarity,level}, ... ] }
POST /api/dungeon/loot/claim/<id>     -> { claimed: true, item: { slug, name } }
```
Both require authentication; claiming currently lacks proximity checks (TODO) and simply marks the node claimed. Claimed loot disappears from subsequent list calls.

### Tuning Knobs (Current / Planned)
| Knob | Status | Effect |
|------|--------|--------|
| `desired_chests` | code constant | Baseline loot node target per map before scaling |
| `spread_factor` | code constant | Fraction of shuffled walkables considered for sampling (lower = more dispersed) |
| Rarity weights | code constant | Relative frequency among candidate pool |
| Level window width | fixed (±2) | Determines progression tightness; wider window dilutes relevance |
| Max tile density (15%) | code constant | Upper bound on loot saturation to avoid clutter |
| Heuristic inference | startup function | Temporary level/rarity assignment for legacy SQL without metadata |

Planned future surfacing: move these constants into a `game_config` table with admin editing or environment overrides, plus per-depth modifiers (e.g., deeper seeds bias toward higher rarity).

### Extending
To add new items with explicit metadata, update (or create) an `.sql` file including `level` and `rarity` columns, or insert via an admin management route (future). Re-run the server; migration logic will not duplicate rows.

### Testing Strategy
Upcoming tests will validate:
* Idempotence (second generation produces zero new rows).
* Presence of at least one loot item for typical map sizes.
* Rarity distribution sanity over a batched seed sample (statistical tolerance, not strict).
* Level window filtering (no items above `avg+2`).

### Roadmap
1. Proximity & line-of-sight checks for claiming.
2. Inventory integration (add claimed item to character stash / equipment slots where relevant).
3. Config-surfaced rarity weights & dynamic scaling by dungeon depth or seed entropy.
4. Explicit SQL seed metadata (remove heuristic inference fallback).
5. Weighted drop tables by item type (e.g., potion bias in early levels).

---

## Features
	- Autofill endpoint to instantly create a 4-character party (`POST /autofill_characters`)
	- Automatic starter gear auto-equip (weapon + optional armor) on both manual creation and autofill (centralized in `app/services/auto_equip.py` for single‑source preference logic)
 - Centralized Seed API for deterministic or random dungeon regeneration
 - Persistent dungeon entities (monsters + treasure) seeded deterministically on first `/api/dungeon/map` call per dungeon instance. Entities exposed via `GET /api/dungeon/entities` and included inline in map payload under `entities`.
 - Continue Adventure dashboard button rehydrates your last party selection and reuses the existing dungeon instance (seed & explored state) without re-seeding the world.
- Turn-based combat (initial version):
	- Automatic encounter spawning during movement
	- Combat session persistence with initiative order, turn tracking, logging
	- Player actions: attack, flee (optimistic locking via version field)
	- Monster auto-turn resolution
	- Loot generation on victory (reuses loot service)
	- WebSocket events: `combat_update`, `combat_end`, plus global `combat_state` flag

## Combat System

The combat module implements a lightweight, deterministic (with seeded RNG) turn engine with initiative, multiple player actions, logging, and loot/XP payout. Balance guardrails are enforced by tests rather than informal expectations. Multi‑character parties (up to 4 of the user's characters) are now supported: each character appears independently in the initiative order and all player action endpoints accept an optional `actor_id` (character id) so the client can act with the currently active party member.

### Core Concepts
- Session entity (`CombatSession`) persists monster state, party snapshot, initiative list, active index, version (optimistic lock), log, rewards, and status.
- Initiative = each participant `speed + d20`; sorted descending; `active_index` advances after every action or monster auto-turn; wrap increments `combat_turn`.
- Party snapshot synthesizes one row per **character** including derived stats: `attack`, `defense`, `speed`, `hp / max_hp`, `mana / mana_max`, explicit `int_stat`, resistances, temporary flags (e.g., `defending`).
- Multi-character: up to 4 of the user's characters are loaded; initiative entries look like `{"type":"player","id":<char_id>,"controller_id":<user_id>,"name":...,"roll":<int>}`. The monster appears as `{"type":"monster","id":<slug-or-id>, ...}`.
- Optimistic concurrency: every player action posts `{action, version, actor_id?}`; mismatch returns `version_conflict` and the client refetches.

### Party & Targeting
When a combat session starts, a snapshot of the user's first 1–4 characters is taken. Each character rolls initiative independently; only the actor whose entry matches `initiative[active_index]` may perform a player action. The client includes `actor_id` equal to that character's `char_id` for `attack`, `defend`, `use_item`, or `cast_spell`. If `actor_id` is omitted the server assumes the currently active player initiative entry. Authorization is enforced by verifying `controller_id == current_user.id` and `id == actor_id`.

### Player Actions
| Action | Effect |
|--------|--------|
| attack | d20 accuracy, miss/crit rules, variance, damage application (requires active `actor_id`) |
| flee | 50% chance to immediately end session (no loot) |
| defend | Sets `defending=True` on actor; next incoming hit halves post‑resistance damage (min 1) then clears the flag |
| use_item | Supports `potion-healing` (+25 HP, consumes one if in inventory) on the acting character |
| cast_spell | `firebolt`: costs 5 mana, d20 accuracy & natural 1 fizzle, natural 20 crit (1.5x), damage `2d8 + INT * 0.6` (post‑crit) with elemental type `fire` (resistances applied) |

### Formulas
- Accuracy Roll: `acc_roll = d20`; `accuracy = attack + acc_roll`; target evasion = `10 + armor` (monster) / `10 + defense` (player).
- Miss: natural 1 always misses; otherwise must meet or exceed evasion unless natural 20 (which always hits & crits).
- Critical Hit: natural 20 multiplies post-variance damage by 1.5 (integer truncated).
- Player Attack Damage: `base = attack`; variance = uniform int in `[-attack//4, +attack//4]`; apply crit; clamp final to `>=1`.
- Monster Attack Damage: same pattern using monster `damage` value.
- Spell (Firebolt): d20 accuracy (nat 1 = fizzle, nat 20 = auto‑hit + crit 1.5x) then damage roll `2d8 + int_stat * 0.6` (rounded down). Fire element passes through resistance table (e.g., 50% fire resist halves final pre‑crit damage).
- Defend: If target had `defending=True`, halve the damage after crit & resistances (`max(1, dmg // 2)`), then clear flag.

### Logging
Representative lines:
```
Encounter starts vs Training Dummy
Player hits Training Dummy for 14 (CRIT) damage (HP 486)
Training Dummy hits Balancer for 5 damage (HP 95)
Player braces for impact (Defend).
Player misses Training Dummy (roll 3)
```
Logs are truncated to the last 250 entries to bound payload size. WebSocket events `combat_update` and `combat_end` push full state snapshots.

### Rewards
On monster HP reaching 0: session status becomes `complete`, a loot table is rolled, XP is split equally across present characters, and loot items are appended to the first character's inventory (temporary policy). The stored `session.rewards` now includes both the loot diagnostics and an `xp` block summarizing total and per‑member distribution.

Example (abbreviated `GET /api/dungeon/combat/<id>` after victory):

```
{
	"id": 42,
	"status": "complete",
	"monster": {"slug":"training-dummy","name":"Training Dummy","xp":40,...},
## Monster AI (Overview)

The monster AI system introduces modular, opt‑in behaviors controlled by per‑monster flags and global probabilities stored in the `GameConfig` row with key `monster_ai`.

Implemented behaviors:
* Ambush (pre‑combat surprise strike) – gated by `enable_ambush` and `ambush_chance`.
* Spell casting (currently `firebolt`) – `enable_monster_spells`, uses `spell_chance`; full hit / crit / fizzle and resistance logic.
* Flee attempts – `enable_monster_flee` with `flee_threshold` & `flee_chance` (HP ratio trigger).
* Help calls – `enable_monster_help` (log placeholder) with `help_threshold` & `help_chance`.
* Action cooldown – global `cooldown_turns` (stores `last_turn` in monster JSON to throttle actions).
* Status effects scaffold (poison DoT, stun veto) processed each monster turn.
* Resistances & vulnerabilities – `resistances` mapping (multipliers <1 resist, >1 vulnerability).
* Patrol wandering – governed by `patrol_enabled`, `patrol_step_chance`, `patrol_radius`; excludes DOOR & TELEPORT tiles (see `app/services/monster_patrol.py`).
* Icon support – `icon_slug` now included in spawned monster dicts (fallback `family-slug`). UI can map to `static/icons/<icon_slug>.svg` (asset pipeline TBD).

Configuration example (`monster_ai` JSON):
```json
{
	"ambush_chance": 0.5,
	"spell_chance": 0.4,
	"flee_threshold": 0.2,
	"flee_chance": 0.3,
	"help_threshold": 0.5,
	"help_chance": 0.2,
	"cooldown_turns": 0,
	"patrol_enabled": false,
	"patrol_step_chance": 0.1,
	"patrol_radius": 5
}
```

On server startup a default config is auto‑seeded if missing (idempotent). You can override values at runtime via:
```python
from app.models.models import GameConfig, json
cfg = {"spell_chance": 0.6, "patrol_enabled": True}
GameConfig.set("monster_ai", json.dumps(cfg))
```

See `MONSTER_AI.md` for the authoritative, detailed documentation and maintenance notes.

	"monster_hp": 0,
	"initiative": [
		{"type":"player","id":12,"controller_id":7,"name":"Aria","roll":23},
		{"type":"player","id":13,"controller_id":7,"name":"Brom","roll":18},
		{"type":"monster","id":"training-dummy","name":"Training Dummy","roll":11}
	],
	"rewards": {
		"items": {"potion-healing": 1, "iron-dagger": 1},
		"items_list": ["potion-healing","iron-dagger"],
		"rolls": {"base_pool":["potion-healing","iron-dagger"],"weights":{"potion-healing":1,"iron-dagger":1},"special":null},
		"xp": {"total": 40, "per_member": {"12": 20, "13": 20}}
	},
	"log": ["...omitted..."]
}
```

Notes:
1. `items` is now a mapping `{slug: qty}`; `items_list` provides a legacy flat list for backward compatibility.
2. `xp.per_member` keys are stringified character ids.
3. `loot` currently always awards to the first character's inventory; multi‑character equitable distribution is a planned enhancement.
4. Fleeing or party defeat returns `rewards: {}` (no xp, no items).

### Balance Tests
Located in `tests/test_combat_balance.py` to lock current behavior:
| Test | Guardrail |
|------|-----------|
| variance bounds | Player damage stays within theoretical min/max (allowing crit inflation) |
| single crit occurrence | Scripted sequence guarantees exactly one crit (verifies crit logging & multiplier) |
| crit sampling distribution | Empirical sample produces at least one and not an implausibly high number of crits over forced-roll sessions |
| defend mitigation | Confirms a defended hit halves post-crit monster damage (min 1) |

These serve as regression tripwires; deliberately update them alongside any formula changes.

### Future Extensions
Planned roadmap items:
- Expanded spell list (elemental types, AoE, resist interaction)
- Targeted spells & attacks (choose monster vs. multiple enemies in future multi-enemy encounters)
- More nuanced flee odds (speed differential)
- Status effects (poison, stun, bleed) with per-turn resolution
- Distinct STR/DEX scaling for melee/ranged vs. INT/WIS for magic, plus gear modifiers

## Dungeon Generation Pipeline (Overview)
> NOTE: A simplified char-grid generator (rooms + wall rings + tunnel connectors) is now the default runtime implementation exposed via `from app.dungeon import Dungeon`. The detailed multi-phase pipeline described below is retained as historical documentation and for potential future reintroduction of advanced features. Current tests assert only the simplified invariants: room connectivity, no orphan doors (each door has one room neighbor and at least one walkable neighbor), and deterministic seed layout.

### Simplified Generator (Overview)
Deterministic room placement + MST corridor carving + door insertion + teleport fallback. Legacy multi-phase normalization has been retired for maintainability. See [Dungeon Generation](docs/DUNGEON_GENERATION.md) for comparison and extension points.

---
The procedural dungeon system is deterministic per (seed, size) and built from a multi-phase pipeline. Each phase is implemented in a dedicated module under `app/dungeon/` to keep responsibilities isolated and testable. The pipeline orchestrator (`app/dungeon/pipeline.py`) wires the phases together; helper modules are intentionally free of Flask/web concerns for ease of profiling and future reuse.

1. Grid Initialization – Allocate empty cell matrix and seed RNG.
2. BSP Partitioning – Recursively subdivide space into candidate room regions (rejecting undersized leaves).
3. Room Placement – Carve rooms inside accepted leaves using jitter to avoid rigid alignment.
4. Corridor Graph – Build a k-nearest graph across room centroids, generate an MST for baseline connectivity, then probabilistically add loop edges.
5. Corridor Carving – For each graph edge, carve a path (L-shaped or occasionally irregular) ensuring minimal wall tunneling.
6. Early Normalization – Clean stray artifacts, ensure corridors interface cleanly with room perimeters.
7. Feature Assignment – (Future expansion) Hooks for populating decorative / gameplay features.
8. Accessibility Pruning – Remove dead-end noise if it does not reduce required connectivity.
9. Room–Tunnel Separation Enforcement – Prevent accidental room fusion by reintroducing separating walls where needed.
10. Door Guarantee – Ensure every distinct room connectivity set has at least one viable door to a corridor network.
11. Connectivity Repair – Detect and bridge any isolated reachable sets still remaining (safety net).
12. Final Repair & Validation – Invoke `_repair_and_validate_doors` which:
	- Repairs orphan doors (a door with no adjacent corridor/tunnel).
	- Optionally carves a minimal tunnel if repairable via a single cell carve.
	- Applies a probabilistic carve guard (e.g., 0.4) to avoid explosive late-stage expansion.
	- Gathers diagnostic statistics (debug hooks) and enforces final invariants.

### Door Invariants
A door cell must:
* Border exactly one room cell (prevents door-in-room or door-floating cases).
* Border at least one traversable corridor/door cell (prevents orphan doors).
* Not create direct room-to-room adjacency bypassing a corridor.

Violations detected during final repair are either fixed (if a single carve resolves them within guard probability) or the door is downgraded/removed.

### Probabilistic Carve Guard
Late-stage carving uses a probability threshold to prevent the normalization pass from aggressively expanding narrow corridors simply to satisfy seldom edge cases. This maintains layout character while still repairing the majority of structural issues.

### Determinism & Caching
The pipeline is deterministic for a given (seed, size). Generated `Dungeon` instances are cached in-memory keyed by these parameters allowing instant retrieval for repeat visits or seed replays.

### Hidden Areas Flags
Two configuration flags influence late-stage connectivity behavior (set in Flask config):

| Flag | Default | Behavior |
|------|---------|----------|
| `DUNGEON_ALLOW_HIDDEN_AREAS` | `False` | Skips active connectivity carving repairs; unreachable rooms from the structural phase are tolerated during repair, but a final safety sweep still converts unreachable rooms to tunnels so invariants (tests) retain full reachability. |
| `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT` | `False` | Superset of the above: also skips the final unreachable-room conversion, allowing persistent unreachable rooms (use only for manual debugging / experimental secret areas; never enabled in tests). |

If both flags are false the generator performs dynamic connectivity repairs and, if some rooms remain unreachable, downgrades those entire rooms to tunnels (incrementing `rooms_dropped`). If only the non-strict flag is true, repairs are skipped but the final downgrade still normalizes the layout. Strict mode leaves unreachable rooms intact (they will appear as isolated room cells not connected to the entrance component).

### Generation Metrics
When `DUNGEON_ENABLE_GENERATION_METRICS` (default True) is enabled, a metrics dictionary is attached to the dungeon object and exposed via the admin endpoint `/api/dungeon/gen/metrics`.

| Key | Description |
|-----|-------------|
| `doors_created` | Reserved for future proactive placements (currently 0). |
| `doors_downgraded` | Doors converted to wall/tunnel due to invalid adjacency. |
| `doors_inferred` | Tunnel cells promoted to doors by final inference safety pass. |
| `repairs_performed` | Number of connectivity repair attempts executed (skipped when hidden areas flag avoids repair). |
| `chains_collapsed` | Door tiles removed from linear chains along the same wall. |
| `orphan_fixes` | Door fixes (either carving an adjacent tunnel or degrading the door). |
| `rooms_dropped` | Entire rooms converted to tunnels in fallback when still unreachable after repairs. |
| `runtime_ms` | Generation wall-clock duration (ms). |
| `debug_allow_hidden` | Echo of `DUNGEON_ALLOW_HIDDEN_AREAS` at generation time. |
| `debug_allow_hidden_strict` | Echo of `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT`. |
| `debug_room_count_initial` | Room cell count immediately after structural pipeline. |
| `debug_room_count_post_safety` | Room cell count after final safety (may shrink if unreachable rooms were downgraded). |
| `door_clusters_reduced` | Dense (3+ doors in a 2x2) clusters collapsed into a single door. |
| `tunnels_pruned` | Unreachable tunnel cells (not adjacent to any room) removed when hidden areas disabled. |
| `corner_nubs_pruned` | Cosmetic corner tunnel 'nub' cells removed (single-cell tunnels only diagonally touching a room). |
| `phase_ms` | Dict mapping phase name -> duration (ms) when metrics enabled; aids profiling & performance triage. |

These metrics support regression tests and profiling of the consolidated final pass.

### Persistent Entities & Continue Flow

As of v0.7.x the dungeon world gains a light persistence layer:

* When a new `DungeonInstance` is first visualized via `GET /api/dungeon/map`, a deterministic RNG (`seed ^ 0xE7717`) selects a handful of walkable tiles and seeds:
	* Monster entities (level-scaled to your average character level) persisted as rows in `DungeonEntity`.
	* Simple treasure cache markers (`type="treasure"`).
* Subsequent map loads reuse the same set (idempotent) – no duplicate spawns or shifting coordinates.
* The map JSON now includes an `entities` array of slim dicts: `{id,type,slug,name,x,y,z,hp_current}`.
* A companion endpoint `GET /api/dungeon/entities` mirrors this for lighter polling.
* The dashboard stores your last successful party selection in `session['last_party_ids']`; if a dungeon instance exists you'll see a Continue button which restores the party and jumps straight into the adventure using the existing seed/state.

Planned extensions:
1. Monster patrol positions updating the persisted entity rows (currently patrol operates in-memory only).

## Data Import & Expansion (Items / Monsters)

The project ships with extensible SQL seed files under `sql/` plus CSV templates under `data_templates/` to streamline bulk content creation.

### SQL Seed Files
Location: `sql/`

| File | Purpose |
|------|---------|
| `items_weapons.sql` | Weapon catalog (levels 1–20) plus expanded categories (crossbows, flails, throwing, fist, scepters, orbs). |
| `items_armor.sql` | Armor slots + accessories + new bracelet/earring/back variants + class-themed set pieces. |
| `items_potions.sql` | Healing/mana/buff potions + stamina, invisibility, regeneration, perception, luck, elemental resist, group buffs. |
| `items_misc.sql` | Tools, crafting mats, gems, scrolls (teleport/summon/ward), keys, quest items (expanded). |
| `monsters_seed.sql` | `monster_catalog` schema + baseline & expanded families (construct, aberration, demon, beasts) + mini-bosses & extra bosses. |

Each file is idempotent via targeted `DELETE` patterns (e.g., `DELETE FROM item WHERE slug LIKE 'weapon_sword_l%'`). Re-running imports updates rows cleanly without duplicating unrelated content.

### Applying Seeds
From project root (ensure the SQLite file exists at `instance/mud.db`):

```
sqlite3 instance/mud.db < sql/items_weapons.sql
sqlite3 instance/mud.db < sql/items_armor.sql
sqlite3 instance/mud.db < sql/items_potions.sql
sqlite3 instance/mud.db < sql/items_misc.sql
sqlite3 instance/mud.db < sql/monsters_seed.sql
```

You can safely re-run only the file you modified while iterating.

### CSV Import Templates
Location: `data_templates/`

| File | Description |
|------|-------------|
| `item_import_template.csv` | Column headers for bulk item ingest: `slug,name,type,description,value_copper,extra_json` + sample rows. |
| `monster_catalog_template.csv` | Headers mirroring `monster_catalog` columns; sample goblin, skeleton, and boss entries. |

Use these to stage new content in spreadsheets (Excel / LibreOffice). Export as UTF‑8 CSV, then write a small loader (future admin route) or ad‑hoc Python script (example below) to insert rows:

```python
import csv, sqlite3, json
conn = sqlite3.connect('instance/mud.db')
cur = conn.cursor()
with open('data_templates/item_import_template.csv') as f:
	reader = csv.DictReader(f)
	for row in reader:
		cur.execute('INSERT OR REPLACE INTO item (slug,name,type,description,value_copper) VALUES (?,?,?,?,?)',
					(row['slug'], row['name'], row['type'], row['description'], int(row['value_copper'] or 0)))
conn.commit()
```

Monsters (assuming table already created):
```python
with open('data_templates/monster_catalog_template.csv') as f:
	reader = csv.DictReader(f)
	for r in reader:
		cur.execute('''INSERT OR REPLACE INTO monster_catalog
			(slug,name,level_min,level_max,base_hp,base_damage,armor,speed,rarity,family,traits,loot_table,special_drop_slug,xp_base,boss)
			VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
			r['slug'], r['name'], int(r['level_min']), int(r['level_max']), int(r['base_hp']), int(r['base_damage']),
			int(r['armor']), int(r['speed']), r['rarity'], r['family'], r['traits'], r['loot_table'],
			r['special_drop_slug'] or None, int(r['xp_base']), int(r['boss'])
		))
conn.commit()
```

### Designing New Content
Guidelines:
1. Keep `slug` stable & lowercase with underscores; use prefixes for grouping (`weapon_`, `armor_`, `potion_`, `scroll_`).
2. Favor incremental commits: extend a single category per change to ease review and rollback.
3. For monsters: choose rarity carefully (overuse of `rare`/`elite` erodes excitement). Use `boss=1` exclusively for encounter anchors.
4. Introduce new loot tables via code when diversifying families (placeholder names in expansion are stubs until implemented in loot logic).
5. Maintain value growth curves consistent with peers to avoid economic inflation spikes.

### Future Tooling
Planned enhancements:
* Admin UI upload for CSV with diff preview.
* Automatic curve validation (detect abrupt value or stat deviations).
* Version tagging (content packs) for modular distribution.

Feel free to propose additional categories (e.g., relics, sigils, glyph-inscribed armor) by opening an issue.

2. Treasure interaction / claiming endpoint to convert caches into actual inventory loot.
3. NPC entity types (merchants / quest givers) leveraging the same persistence scaffold.

### Modular Dungeon Package
As of v0.4.x the former monolithic `app/dungeon.py` has been decomposed into a package:

```
app/dungeon/
	__init__.py        # Re-exports Dungeon, DungeonCell for backwards compatibility
	pipeline.py        # Dungeon dataclass + end-to-end generation orchestration
	generator.py       # Structural phases: grid init, BSP, rooms, corridors
	doors.py           # Door normalization, chain collapse, invariant enforcement
	pruning.py         # Layout cleanup: door clusters, orphan tunnels, corner nubs
	connectivity.py    # Flood fills, reachability repair, safety consolidation
	features.py        # Feature and special-room assignment (entrance, boss, water)
	cells.py           # DungeonCell class & cell-level utilities
	metrics.py         # init_metrics() and metric key centralization
```

Design goals:
1. Separation of concerns – each file focuses on a narrow generation concern.
2. Deterministic, side‑effect contained helpers – pure functions given RNG & grid.
3. Fast iteration – failing invariants can be traced to a specific module.
4. Backwards compatibility – external imports (`from app.dungeon import Dungeon`) still work.

Adding a new phase? Prefer a new function in an existing module (or a new module) and a single call site added to the ordered list inside `Dungeon._run_pipeline()`. Keep any new metrics registered in `metrics.init_metrics()` so tests gain them automatically.

Legacy note: The former monolithic and advanced multi-phase pipeline documentation below represents the prior implementation. The compatibility shim now points to the simplified generator; external imports (`from app.dungeon import Dungeon`) continue to work. Advanced phases can be reintroduced module-by-module without breaking the current API.

### Route Map Suppression
During development the app prints a route map once at startup. Suppress this by setting `ADVENTURE_SUPPRESS_ROUTE_MAP=1` (or `true/yes`) or programmatically via `app.config['SUPPRESS_ROUTE_MAP']=True` before initialization completes.

## Testing & Invariants
Key automated tests (pytest) protect the generation contract:

| Test | Purpose |
|------|---------|
| Seed persistence test | Ensures dashboard-selected seed matches the adventure instance seed (deterministic replay). |
| Multi-door presence sweep | Confirms that across a sampled seed range, rooms can legitimately present multiple door placements where distinct corridors meet. |
| No orphan doors invariant | Validates every door satisfies adjacency rules (one room neighbor + at least one corridor/door neighbor). |
| Strict hidden areas mode | Verifies that when `DUNGEON_ALLOW_HIDDEN_AREAS_STRICT` is enabled unreachable rooms may persist (skips if rare fully-connected range). |
| Performance regression | Guards average generation `runtime_ms` across representative seeds against excessive slowdown. |

Future candidates: cycle length distribution, corridor branching factor bounds, entrance accessibility proofs.

### Test Infrastructure (Selective DB Isolation & Factories)

Recent test scalability and flakiness work introduced three important utilities:

1. Selective SQLite DB isolation marker: only rebuilds the schema for tests that truly need a pristine database (heavy data mutation / migration cases).
2. Lightweight object factories: fast creation of users, characters, dungeon instances, and ensuring items without repeating boilerplate.
3. Deterministic websocket helpers: eliminate timing races in moderation/admin Socket.IO tests by snapshotting state or forcing actions synchronously.

#### 1. `@pytest.mark.db_isolation`
Placed on a test (or class) to request a fresh database setup before it runs. Non‑isolated tests reuse the shared test database which dramatically cuts suite runtime and avoids excess "database is locked" contention.

Example:
```python
import pytest

@pytest.mark.db_isolation
def test_inventory_encumbrance(factory):
	user = factory.user()
	char = factory.character(user, str_val=10)
	# ... perform heavy write operations safely ...
```

Implementation summary (in `conftest.py`):
* Registered marker `db_isolation` (pytest will show it in `--markers`).
* An autouse session fixture intercepts each test; when the marker is present it drops & recreates tables inside an application context.
* WAL mode & a `busy_timeout` remain enabled globally to mitigate concurrent access blocking.

Guidelines:
* Use the marker only for tests that genuinely depend on a pristine schema or predictable autoincrement IDs.
* Prefer shared DB for pure read tests or those that can tolerate existing rows (factory methods generate unique usernames / slugs).

#### 2. Factories
Exposed via a single `factory` fixture that returns a namespaced helper with methods:
* `user(username=None, role='user', banned=False)`
* `character(user=None, str_val=10, dex_val=10, **overrides)`
* `instance(user=None, seed=12345)` – ensures a `DungeonInstance` row
* `ensure_item(slug, **attrs)` – create or fetch an `Item`

Behavior:
* Commits after each object for simplicity; for very hot paths you can batch by creating inside a transaction block (future optimization if needed).
* Auto‑generates unique usernames / slugs when not provided to avoid collisions in the shared DB mode.

Usage pattern:
```python
def test_party_capacity(factory):
	u = factory.user(role='user')
	c1 = factory.character(u, str_val=14)
	potion = factory.ensure_item('potion-healing', weight=0.5)
	# ... mutate inventory JSON, assert encumbrance ...
```

#### 3. Deterministic Websocket Test Helpers
Race‑prone admin moderation tests (e.g., kicking a user and then validating their absence) previously relied on asynchronous disconnect timing. To stabilize:
* A private snapshot function (`_admin_status_snapshot`) surfaces the in‑memory lobby/admin presence map synchronously for assertions.
* A test‑only Socket.IO event (`__test_force_kick`) triggers the same internal removal logic as a real admin kick but executes inline so the test can immediately assert disconnection without sleeps or polling.

These helpers are guarded so they don't expand production capabilities; they are only invoked by tests importing the lobby module directly or emitting the reserved event name. If you add new realtime moderation flows, mirror this pattern to keep tests deterministic.

#### When to Add Another Isolation Layer
Before adding new global teardown/setup logic ask:
1. Can a factory object with unique identifiers coexist instead?
2. Is the flakiness due to timing? (Prefer a deterministic helper/event.)
3. Does the test really require a clean autoincrement or empty table? (Mark with `db_isolation` if yes.)

This layered approach keeps the majority of tests fast (shared DB) while still offering precise isolation where truly needed.

### Coverage
Continuous Integration enforces a minimum line coverage threshold of **80%** (raised from 60% after broadening test focus to admin shell, websocket edge cases, and moderation features). The suite currently meets or exceeds this mark with critical generation logic and XP progression at or near 100%. New contributions must not drop overall coverage below 80%; add focused tests for any new dungeon pipeline branch, seed handling logic, websocket behavior, or admin moderation path.

## Architecture Diagram

See `docs/architecture.md` for a high-level Mermaid diagram of core components (Flask blueprints, Socket.IO layer, dungeon generation pipeline, persistence), plus request and movement flows and extension points.

## Asset Optimization
SVG icon assets are automatically normalized on commit (whitespace + non-license comment stripping) via a lightweight pre-commit hook (`optimize_svgs`). For deeper path/precision optimization you can still run external tools (e.g., svgo) before committing.

## Contributing & Development
See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for coding conventions, pre-commit policy (no inline styles/scripts), asset guidelines, and test instructions.


## What's New (v0.6.0 latest)
### v0.6.0 (Equipment, Inventory, Search UX)
- Equipment & Bags modal with drag-and-drop equip, per-slot Unequip, and Use actions for consumables.
- Equipment/Bags buttons on both Dashboard and Adventure party cards; improved outline-warning styling.
- New Inventory API: `/api/characters/state`, `/equip`, `/unequip`, `/consume` with computed stats.
- Dungeon perception/search improvements: persistent notice markers; Search enabled after perception; loot is clickable with tooltips.
- Backend hardening: normalized legacy gear shapes and robust user ID extraction to resolve 404/500s on `/api/characters/state`.
 - Auto-equip baseline gear on creation/autofill: characters now begin with a class-appropriate weapon (and armor when available) populated in the `gear` JSON for immediate dungeon readiness.

### v0.5.0 (Moderation & Performance Insight)
- Dedicated Moderation Panel UI with filtering (All / Banned / Muted), search, and action buttons.
- Temporary mute durations (seconds) with automatic expiry; persistent DB mute flag remains authoritative for hard mutes.
- Dungeon pipeline phase timing metrics (`phase_ms`) for profiling (generate, collapse, consolidation, pruning, safety, invariants, inference, features).
- Conditional invariant re-run optimization (skip second full sweep if corner nub pruning made no changes) improving median generation time and restoring performance regression headroom.
- Admin status payload enriched with `temporary_mutes` map (username -> expiry epoch seconds).

### v0.4.0 (Door & Tunnel Clarity)
### v0.4.0 (Door & Tunnel Clarity)
- Dense 2x2 door cluster reduction (retain one representative door) with preservation of meaningful door pairs.
- Orphan tunnel pruning (unreachable, non-room-adjacent) for cleaner maps when hidden areas disabled.
- New generation metrics: `door_clusters_reduced`, `tunnels_pruned`.
- New pytest marker: `structure` with regression test for clusters & unreachable tunnels.

### v0.3.4 (Maintenance & Tooling)
- Repository renamed to `Adventure` (formerly `adventure-mud`).
- Added lightweight SVG normalization pre-commit hook (trims/strips non-license comments across ~2.7K icons).
- CI workflow aligned with badge (job id `build-test`), explicit pre-commit run before tests.
- README branding & Asset Optimization section added.
- Persistent explored tiles column migration (lazy + script), compression & admin management.
- CHANGELOG entry for maintenance release.

### v0.3.3
**Release date:** 2025-09-21

Highlights across recent patches (0.3.1 → 0.3.3):

### (From previous release) v0.3.3
- New `/api/dungeon/state` endpoint for initial cell description & exits (no blank move hack).
- In-memory dungeon cache (seed,size) → Dungeon object reuse for performance.
- Pytest test suite (movement & seed determinism) + GitHub Actions CI workflow.
- Client updated to call state endpoint post map render.
 - Temporary universal branding/icon now uses `treasure-map.svg` (favicon, navbar, player marker).
 - Centralized `/api/dungeon/seed` endpoint (numeric, string->hash, or random regenerate) with UI controls in adventure view.
 - Cached dungeon entrance coordinate eliminates per-request entrance scan.

### v0.3.2
- Compass movement pad with dynamic exit enablement.
- Keyboard movement toggle + request queue + rate limiting (120ms) + ARIA improvements.
- Centralized class colors as CSS custom properties.

### v0.3.1
- Extraction of all inline CSS/JS to static files & cache-busting via `asset_url()`.
- Pre-commit governance hooks (no inline styles/scripts, enforce asset_url usage).
- Socket.IO version alignment & stability improvements.
- Utility CSS consolidation & favicon addition.

Refer to docs/CHANGELOG.md for full historical details.

## What's New in v0.3.0
- **Modular backend:** All major logic split into blueprints/modules (`dashboard.py`, `dungeon_api.py`, `config_api.py`)
- **Dungeon state in DB:** Player position and dungeon grid are now persistent and not stored in session
- **Deterministic dungeons:** Seed handling supports both alphanumeric and integer seeds
- **Config API:** All game config is now fetched via API endpoints
- **UI overhaul:** WASD/regenerate controls removed, dynamic exit buttons added, improved comments and docstrings
- **Project headers:** All code files now include project name, license, and GitHub info

## Getting Started

### 1. Create a virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the server
```bash
python run.py server
```

### 3. Open in browser
Visit http://localhost:5000

### VS Code tasks (optional)
If you use VS Code, this repo includes ready-to-use tasks and recommendations:
- Run task: "Run Adventure (bg)" to start the server in the background using the workspace venv.
- The workspace is configured to use `.venv/bin/python` automatically.

Recommended extensions are listed in `.vscode/extensions.json` (Python, Pylance, Ruff, Black, Jupyter, Docker).

## Project Structure
- `models/` - Database models
- `routes/` - Flask blueprints (auth, main, dashboard, dungeon_api, config_api)
- `websockets/` - WebSocket event handlers
- `static/` - Static files (JS, CSS)
- `templates/` - HTML templates

## Command Line Usage

The entry point `run.py` provides a robust CLI with subcommands and flags.

Show help:
```bash
python run.py --help
python run.py server --help
python run.py admin --help
```

Run server (defaults HOST=0.0.0.0, PORT=5000):
```bash
python run.py server
python run.py server --host 127.0.0.1 --port 8080
python run.py server --db sqlite:///instance/dev.db
```

You can also load variables from a `.env` file automatically (python-dotenv is included):
```bash
python run.py --env-file .env server
```

Admin shell:
```bash
python run.py admin
```

### Admin / Moderation Commands
The interactive admin shell now includes user moderation helpers in addition to basic CRUD:

| Command | Description |
|---------|-------------|
| `create user <username> [<password>]` | Create user (default password `changeme` if omitted) |
| `list users` | List all users with role and ban status |
| `delete user <username>` | Delete a user |
| `reset password <username> <new_password>` / `passwd <username> <new_password>` | Reset password |
| `set role <username> <admin|mod|user>` | Change role |
| `ban <username> [reason..]` | Ban user with optional reason (stores timestamp & reason) |
| `unban <username>` | Lift a ban |
| `list banned` | Show all banned users |
| `show user <username>` | Detailed user info (role, email, ban state, notes) |
---

## Monster Catalog & Encounters (New)

| `set email <username> <email|none>` | Set or clear email |
| `note user <username> <text>` | Append a timestamped moderation note |

Login attempts by banned accounts are blocked with a flash message including the ban reason if present.

WebSocket admin events:
- `admin_online_users` (request) -> emits `admin_online_users_response` only to the requesting admin's socket (renamed response event to avoid accidental delivery to non-admin listeners).
	- NOTE: Legacy event name `admin_online_users` is still emitted (to the requesting admin only) for a transitional period. A TODO deprecation marker is present; clients should migrate to `admin_online_users_response`.

## Environment configuration
### Quick Start Setup Script
An interactive, colorful bootstrap script is provided:
```
python scripts/setup_adventure.py
```
Features:
- Generates / updates `.env` with sensible defaults (SECRET_KEY, DATABASE_URL, CORS origins)
- Ensures `instance/` directory exists
- Runs lightweight runtime migration logic (via importing server module)
- Creates or updates an admin user (optional) and can rotate password
- Shows compression & fog features already enabled in the codebase during normal runtime

Re-run safe: existing values become defaults; choose whether to rotate the admin password.

Flags / automation:
```
--yes / -y                Accept all defaults (non-interactive)
--non-interactive         Non-interactive mode (fails if required value missing)
--json                    Emit machine-readable JSON summary only
--no-admin                Skip ensuring/creating admin user
--admin-username NAME     Set admin username in non-interactive runs
--admin-password PASS     Set admin password (use with care; consider env injection)
--generate-admin-password Auto-generate a secure password (printed once)
--alembic                 Run `alembic upgrade head` after DB init if migrations present
--quiet-routes            Suppress route map printing during setup
--quiet                   Minimal output (suppresses normal info; errors still shown)
--verbose                 Extra informational output (sets log-level debug)
--log-level <level>       Explicit verbosity: debug|info|warn|error|silent
```
Example CI usage:
```
python scripts/setup_adventure.py --yes --no-admin --alembic --quiet-routes --json > setup_summary.json
```


Local development uses a `.env` file (auto-loaded):

Key variables:
- `SECRET_KEY` - Flask secret key. If a placeholder value (dev-secret-change-me, changeme, etc.) is detected, the setup script auto-generates a secure random 32-byte urlsafe token and writes it to `.env` (reported in JSON summary as `secret_key_generated: true`).
- `DATABASE_URL` - SQLAlchemy database URI (default: SQLite in ./instance/mud.db)
- `CORS_ALLOWED_ORIGINS` - Allowed origins for Socket.IO (default: *)

## Explored Tiles Persistence (Fog-of-War Memory)

### Door Placement & Pruning (v0.4.0+)
Door tiles are refined to maximize clarity while preserving organic branching:

1. Linear chain collapse removes long straight runs of doors along the same wall (retains boundary door).
2. Dense cluster pruning detects 2x2 windows containing 3+ doors (all bordering the same room) and collapses them to a single door.
3. Legitimate adjacent door pairs (e.g., corridor forks/junctions) are preserved to maintain expressive connectivity.
4. Orphan tunnel pruning removes unreachable tunnel pockets not adjacent to a room (skipped when hidden areas flags are enabled), reducing map clutter.
5. Corner tunnel nub pruning removes single-cell tunnel pixels that only diagonally touch a room creating a visual corner artifact without meaningful traversal value.

Metrics `door_clusters_reduced` and `tunnels_pruned` quantify pruning impact for regression tracking.

Explored dungeon tiles are stored per user and seed to allow long-term mapping memory across sessions and devices.

Storage layers:
- Client: `localStorage` (fast immediate recall) keyed by `adventureSeenTiles:<seed>`.
- Server: `user.explored_tiles` TEXT column (JSON object mapping seed -> compressed or raw tile list).

API contract:
```
// NOTE: Legacy `/api/dungeon/seen*` endpoints removed. Fog-of-war now handled entirely client-side.
```

Compression:
- Tile lists may be delta-compressed automatically (prefix `D:`). The server transparently decompresses before returning to clients.
- If compression doesn't reduce size, raw form is stored.

Admin management:
// Removal: clearing individual seed's tiles no longer needed; client may clear local cache via console helper.
- Payload examples:
	- Clear current user's all seeds: `{}`
	- Clear current seed for user `alice`: `{ "username": "alice", "seed": 12345 }`

Migration:
- Column added automatically on startup via lightweight `_run_migrations()`.
- Manual script available: `python scripts/upgrade_explored_tiles.py` (idempotent).

- If persistence temporarily unavailable, API returns HTTP 202 with a warning instead of failing gameplay.

### Rate Limiting & Payload Guards
Legacy rate limiting for `POST /api/dungeon/seen` removed along with endpoint deprecation.
```
{ "error": "rate limit exceeded", "retry_after": 10 }
```
Additional guards:
- Single request tile submission hard limit: 4000 tiles (HTTP 413 if exceeded)
- Per-seed retained tile cap: 20,000 (excess silently truncated, oldest coordinates dropped after sort)
- Global per-user seed cap: 12 seeds; least-recently updated seeds are evicted (LRU) when exceeded.

### Compression & Metrics Endpoint
Tiles are delta-compressed automatically if it saves space. The admin metrics endpoint surfaces compression efficiency:
```
// Metrics endpoint for seen tiles removed.
Response:
{
	"user": "alice",
	"seeds": [
		{ "seed": 12345, "tiles": 812, "compressed": true, "raw_size": 5120, "stored_size": 1480, "saved_pct": 71.09, "last_update": "2024-09-22T11:06:22Z" }
	],
	"totals": { "tiles": 812, "raw_size": 5120, "stored_size": 1480, "saved_pct": 71.09 }
}
```
Server responses for POST now include additional metrics:
```
{ "stored": <count>, "compressed": <bool>, "raw_size": <int>, "stored_size": <int>, "compression_saved_pct": <float> }
```

### Pruning Metadata Format
Each seed entry in `user.explored_tiles` now stores an object:
```
{ "<seed>": { "v": "D:<compressed-or-raw>", "ts": <epoch-seconds> }, ... }
```
Backward compatibility: legacy string values (raw or `D:`) are still accepted; they are upgraded to the object form upon next write.

### Admin Fog Modal Enhancements
The Fog & Visibility modal now shows a per-seed metrics table with compression savings, sizes, last update timestamps, and per-seed clear buttons powered by the metrics endpoint.

### Alembic Migration Scaffold
Alembic has been introduced for future schema evolution:
- Config: `alembic.ini`
- Scripts dir: `migrations/` (env.py + versions/)
- Generate a revision (example): `alembic revision --autogenerate -m "add new table"`
- Apply: `alembic upgrade head`

Current lightweight runtime migration logic remains; Alembic will take over for new structural changes. Keep both until all environments are validated under Alembic.


## VS Code tasks

Predefined tasks to run the project from the Command Palette are defined in `.vscode/tasks.json` and use the selected Python interpreter.

## Architecture Notes
- All major backend logic is modular and API-driven for maintainability and DM-driven content
- Dungeon state is persistent and deterministic by seed
- All config is managed via API endpoints for easy customization
- UI is dynamic and adapts to available exits and party state

## Frontend Asset Conventions

Recent refactors consolidated inline JavaScript and CSS into versioned static assets for maintainability:

- `static/js/adventure.js` – Adventure map rendering, movement & exit handling (Leaflet based)
- `static/js/admin-settings.js` – Admin broadcast & online user modal logic (Socket.IO)
- `static/utilities.css` – Reusable utility classes replacing prior inline styles:
	- Typography: `.u-mono`, `.badge-mono`
	- Layout & alignment: `.u-flex-center`, `.mw-240`, `.chat-body-240`, `.chat-header`
	- Icon sizing/effects: `.icon-28`, `.icon-32`, `.icon-dropshadow`
	- Components: `.map-box`, `.dungeon-output`, `.scroll-area-200`
	- Lists & resets: `.list-reset`
	- Currency colors: `.coin-gold`, `.coin-silver`, `.coin-copper`

### Guidelines
1. Prefer adding a utility class in `utilities.css` over introducing new inline `style` attributes.
2. If a style is used 2+ times, convert it into a utility.
3. Avoid one-off color filters on icons; create a semantic class where appropriate.
4. JavaScript tied to a template belongs in `static/js/` with a clear, focused filename.
5. New templated scripts should use a named `<script src=...>` include instead of inline IIFEs.

### Removing Inline Styles
The only previously allowed exception (the `style` param on the `svg_icon` macro) has been removed in favor of class-based styling. Run a grep for `style="` during code review to ensure no regressions:
```bash
grep -R "style=\"" app/templates || echo "No inline styles found"
```

### Cache Busting
Static assets now use an `asset_url(filename)` Jinja helper that appends a `?v=<mtime>` query string based on the file's modification time. Example:
```jinja2
<link rel="stylesheet" href="{{ asset_url('utilities.css') }}">
```
This removes the need to manually bump query tokens. If the file is missing, it gracefully falls back to a normal `url_for('static', ...)` URL.

### Pre-Commit Style Enforcement
A pre-commit hook is provided to block reintroduction of inline `style="..."` attributes in templates.

Install pre-commit locally:
```bash
pip install pre-commit
pre-commit install
```
Run hooks against all files:
```bash
pre-commit run --all-files
```
Hooks included:
- Trailing whitespace removal
- EOF fixer
- Inline style attribute check (fails build if any `style="` appears in templates)
- Inline script block check (disallows inline `<script>` code blocks)
- Manual version token check (enforces `asset_url()` usage)

See `docs/STYLE_GUIDE.md` for the full set of frontend conventions.

## Admin & Data Management

The project now ships with a lightweight, secure admin surface (web + CLI parity) for managing users, game configuration, and bulk content (items & monsters) via validated CSV uploads.

### Access & Authorization
Route prefix: `/admin`

All admin views require an authenticated account whose `User.role == 'admin'`:
* Non‑authenticated users are redirected to the login page (JSON requests receive `401 {"error":"unauthorized"}`).
* Authenticated non‑admin users receive HTTP 403 (JSON: `{"error":"forbidden"}`).

The base navigation (`base.html`) automatically shows an Admin Panel link for eligible users.

### Admin Dashboard Overview
Landing page: `/admin/` – provides quick links to:
* Users list & role / ban management
* Game Config key/value editor
* Item catalog (listing + CSV import)
* Monster catalog (listing + CSV import)

### CSV Imports (Items & Monsters)
Upload forms are available at:
* Items: `/admin/items`
* Monsters: `/admin/monsters`

Process (Items or Monsters):
1. Upload UTF‑8 CSV (≤500 KB, ≤5000 data rows).
2. Server parses & normalizes headers (case/whitespace stripped).
3. Validation pass collects all errors (no partial writes).
4. If zero errors: atomic upsert transaction by `slug`.

Safety Guards:
* File size hard limit: 500,000 bytes.
* Row hard limit: 5,000 (excluding blank lines).
* All‑or‑nothing: any validation error aborts without DB changes.

#### Item CSV Required Columns
`slug,name,type,description,value_copper,level,rarity` (+ optional `weight`)

Validation Highlights:
* `slug` unique within file, no spaces.
* Integers: `value_copper >= 0`, `level >= 0`.
* `rarity` ∈ {common, uncommon, rare, epic, legendary, mythic}.
* Optional `weight` must be numeric if present.

#### Monster CSV Required Columns
`slug,name,level_min,level_max,base_hp,base_damage,armor,speed,rarity,family,xp_base`

Optional columns honored if present: `traits,loot_table,special_drop_slug,boss,resistances,damage_types`.

Validation Highlights:
* `slug` unique; `name`, `family` required.
* All numeric fields ≥ 0; `level_max >= level_min`.
* `rarity` ∈ {common, uncommon, rare, elite, boss, epic, legendary, mythic}.
* `boss` must be boolean-ish (0/1/true/false/yes/no) if provided.

Refer to `data_templates/` and `data_templates/README.md` for canonical column explanations and sample rows.

### CLI Parity
The same validation logic powers mirrored CLI subcommands (implemented in `run.py`):

```
python run.py import-items-csv path/to/items.csv
python run.py import-monsters-csv path/to/monsters.csv
```

On failure, each validation error is printed (`ERROR: ...`) and exit code is non‑zero.

### Quick Examples
Create or promote an admin user:
```
python run.py make-admin alice
```

Set / get a game config key:
```
python run.py config-set encumbrance '{"base_capacity":12,"per_str":6}'
python run.py config-get encumbrance
```

Import new item definitions:
```
python run.py import-items-csv snippets/new_items.csv
```

### User Management
Web UI: `/admin/users`

Capabilities:
* List users (paged 50 per page)
* Change role (`user|mod|admin`) – self‑role change blocked
* Ban / Unban with optional reason (self‑ban blocked)

JSON workflows (supply `Accept: application/json`):
```
POST /admin/users/<id>/role {"role":"mod"}
POST /admin/users/<id>/ban  {"action":"ban","reason":"abuse"}
POST /admin/users/<id>/ban  {"action":"unban"}
```
Responses include status or structured errors for invalid input.

### Game Configuration
Web UI: `/admin/game-config`

Stores arbitrary key/value pairs in `GameConfig` (raw string). For JSON semantics, provide serialized JSON string; consumers are responsible for parsing. CLI mirrors this via `config-get` / `config-set`.

### Error Patterns
| Scenario | Result |
|----------|--------|
| Missing CSV required column | `Missing required columns: ...` (no write) |
| Duplicate slug in file | `Line N: duplicate slug '...'` |
| Invalid rarity | `Line N: rarity '...' not in [...]` |
| File > size/row limit | Explicit size/row error, abort |
| Bad integer field | `Line N: <field> must be integer (got '...')` |

### Extension Ideas (Future)
Planned but not yet implemented – contributions welcome:
* Dry‑run mode (show diff preview before commit).
* Import history & audit log (who imported what & when).
* Structured JSON field editing for complex configs.
* Bulk user moderation actions & search filters.
* Download current catalog as CSV.

### Troubleshooting
| Symptom | Check |
|---------|-------|
| 403 on `/admin/...` | Confirm logged in user has role `admin` |
| CSV import silently reorders rows | Normal (DB commit order not guaranteed); verify counts |
| Weight not applied | Ensure numeric; invalid values ignored, see validation logs |
| Boss flag ignored | Ensure value is one of: 1,true,yes,0,false,no (case-insensitive) |

If an import fails, fix all listed errors then re-upload; partial progress is never applied so retries are safe.


## CSS Custom Properties (Theming)
Class color theming is centralized and available both server-side and via `/api/config/class_colors`. Corresponding CSS variables (custom properties) are injected in the stylesheets so you can reskin without hunting through multiple files.

Example variables (one per class):
```
--class-fighter-bg / --class-fighter-fg / --class-fighter-border
--class-rogue-bg   / --class-rogue-fg   / --class-rogue-border
--class-mage-bg    / --class-mage-fg    / --class-mage-border
--class-cleric-bg  / --class-cleric-fg  / --class-cleric-border
--class-druid-bg   / --class-druid-fg   / --class-druid-border
--class-ranger-bg  / --class-ranger-fg  / --class-ranger-border
```
Usage in CSS:
```css
.character-card.class-fighter { background: var(--class-fighter-bg); color: var(--class-fighter-fg); }
.character-card.border-fighter { border-color: var(--class-fighter-border); }
```
Override strategy (create a new CSS file loaded after defaults):
```css
:root {
  --class-mage-bg: #123b52;
  --class-mage-border: #1d6c91;
}
```
You can dynamically fetch colors client-side:
```js
fetch('/api/config/class_colors').then(r=>r.json()).then(colors => console.log(colors.mage.bg));
```

## Adventure Movement UX
The adventure interface now provides:
- Compass movement pad (N/W/E/S) with dynamic enabling based on backend exits
- Keyboard movement (WASD + Arrow keys) toggle (accessible form-switch)
- Movement request queue & 120ms rate limiting to prevent spamming the server
- ARIA live region updating only the non-exit portion of the room description for screen readers

Client flow: initial map render -> `/api/dungeon/state` -> show description & exits -> button/keypress -> queue -> `/api/dungeon/move` -> JSON `{ pos, desc, exits }` -> update marker & enable next directions. Caching avoids regenerating the same dungeon structure each request.

## Seed API

The dungeon seed determines the procedural layout. A central POST endpoint manages creation, hashing, and regeneration so clients and templates no longer manipulate seeds via query parameters.

Endpoint:
```
POST /api/dungeon/seed
```
Body (JSON, all optional):
```
{
	"seed": <int|string|null>,
	"regenerate": <bool>
}
```
Behavior:
- If `regenerate` is true and `seed` is omitted/`null`, a new random seed is generated.
- If `seed` is an integer, it is used directly (clamped to 64-bit signed range for SQLite).
- If `seed` is a string, a deterministic SHA-256 hash (first 8 bytes) is converted to an integer.
- The user's active `DungeonInstance` is updated or created; position resets to `(0,0,0)` so the next map fetch relocates to the entrance.

Response:
```
{
	"seed": <int>,
	"dungeon_instance_id": <int>
}
```

Client Usage (JS):
```js
window.dungeonNewSeed();        // random regenerate
window.dungeonNewSeed('alpha'); // deterministic from string
window.dungeonNewSeed(12345);   // specific numeric seed
```

UI Controls:
- Adventure screen includes a "New Seed" button (random) and an input + Apply button for custom seeds.

Caching:
- Dungeon objects are cached in-process per (seed,size) reducing generation overhead.
- Entrance coordinate is cached within each `Dungeon` instance, removing an O(N^2) scan at map retrieval.

## Versioning and Changelog

This project follows Semantic Versioning (SemVer): MAJOR.MINOR.PATCH.

See docs/CHANGELOG.md for a curated list of notable changes per release.

### Automated Version Bump
An automated workflow (`auto-bump.yml`) examines the latest commit message on pushes to `main`. If the commit uses a Conventional Commit type (e.g., `feat:`, `fix:`, `perf:`) and the `VERSION` file was not modified in that commit, it will:
1. Decide bump type (`feat`/`perf` -> minor, `fix`/others -> patch).
2. Run the bump script (`scripts/bump_version.py <type>`).
3. Commit and push the updated `VERSION` (and `CHANGELOG.md` if modified).

To skip auto-bump, either include a manual version bump in your PR (changing `VERSION`) or use a non-triggering type (like `docs:`) when appropriate.

### Release Process
See `docs/RELEASING.md` for the full release checklist (tests, changelog finalize, version bump, tag & push). A quick TL;DR:
```
pytest -q
python scripts/bump_version.py <patch|minor|major>
git add VERSION docs/CHANGELOG.md && git commit -m "release: v$(cat VERSION)" && git push
git tag -a v$(cat VERSION) -m "Adventure v$(cat VERSION)" && git push --tags
```

## Inventory Stacking & Encumbrance

Inventories use a stacked JSON representation:

```
[ {"slug": "potion-healing", "qty": 3}, {"slug": "short-sword", "qty": 1} ]
```

Legacy inventories stored as a flat slug list are migrated lazily on first load.

Each `Item` has a `weight` (default 1.0). Total carried weight = sum(weight * qty).

Encumbrance configuration lives in the `game_config` table (key = `encumbrance`) and defaults to:
```
{
	"base_capacity": 10,
	"per_str": 5,
	"warn_pct": 1.0,
	"hard_cap_pct": 1.10,
	"dex_penalty": 2
}
```

Capacity = `base_capacity + STR * per_str`.

### Automatic Starter Gear (Creation & Autofill)
When a character is created (either manually via the dashboard form or through the `POST /autofill_characters` endpoint), the server now performs a lightweight auto-equip pass. It inspects the starter item list for the chosen class and selects the first matching entries from a preference table:

```
fighter: weapon [short-sword, long-sword, club]; armor [leather-armor, chain-shirt]
rogue:   weapon [dagger, short-sword];         armor [leather-armor]
mage:    weapon [oak-staff, wand];             armor []
cleric:  weapon [mace, club];                  armor [leather-armor]
ranger:  weapon [hunting-bow, short-sword];    armor [leather-armor]
druid:   weapon [oak-staff, club];             armor [leather-armor]
```

Behavior:
1. Starter inventory is generated first (existing `STARTER_ITEMS` mapping).
2. The auto-equip routine normalizes the starter item list (supports future dict-shaped entries) and searches for the first available preferred weapon, then armor.
3. Equipped slots are stored as a simple mapping in `character.gear` (JSON) e.g. `{ "weapon": "short-sword", "armor": "leather-armor" }`.
4. If a preferred slot cannot be satisfied (e.g., mage armor), the slot is simply omitted – clients should treat missing keys as unequipped.

Backwards Compatibility:
- Existing characters with empty or list-form `gear` remain supported; normalization logic elsewhere still tolerates older shapes.

Testing:
- New tests (`tests/test_autofill_gear.py`) assert that autofill characters always have a `weapon` slot populated and optionally an `armor` slot.

Extending:
- To add or rebalance starter equipment, update `STARTER_ITEMS` and/or expand the preference lists in the auto-equip block inside `app/routes/dashboard.py`.
- Future roadmap: incorporate gear stats into derived combat attributes and allow rarity-tier starter variations.

States:
* normal: weight <= capacity
* encumbered: capacity < weight <= capacity * hard_cap_pct (DEX reduced by `dex_penalty` for computed stats)
* blocked: weight > capacity * hard_cap_pct (new loot claims rejected and endpoint returns HTTP 400 with `error: encumbered`)

Loot claim responses now include post-claim encumbrance snapshot:
```
{
	"claimed": true,
	"item": {"slug": "lockpicks", "name": "Lockpicks"},
	"character_id": 5,
	"encumbrance": {"weight": 27.0, "capacity": 25, "status": "encumbered", "dex_penalty": 2, "hard_cap_pct": 1.1}
}
```

Character state endpoint (`/api/characters/state`) returns stacked bag entries with `qty` and per-character `encumbrance` object. A DEX penalty is applied to base stats prior to gear-derived adjustments when status is `encumbered` or `blocked`.

Tuning: update the JSON in `game_config` (key `encumbrance`) and restart (or hot-reload) the server. Future admin UI will expose these sliders.

---

## Quality Gates & CI ✅

The project enforces a small set of "quality gates" both locally and in CI. A change should pass all of them before merge:

| Gate | Tool / Location | Threshold / Expectation |
|------|------------------|-------------------------|
| Lint | `ruff check .`  | Zero errors (warnings allowed only if explicitly ignored in `pyproject.toml`) |
| Format | `black --check .` | No diffs (line length 120) |
| Imports | Ruff (rule I) | Auto-sorted; no manual isort run needed |
| Tests | `pytest -q` | 100% passing; flakiness not tolerated (stochastic tests use deterministic seeds) |
| Coverage | CI report | >= 80% line coverage overall (raise only after major feature sets stabilize) |
| Security (light) | Basic review | No hard-coded secrets / credentials committed |
| Docs | README + key module docstrings | New public services & routes documented |

Status (last local run example):
```
ruff: PASS (0 findings)
black: PASS (no changes)
pytest: 235 passed, 2 skipped
coverage: >= 80% (see CI badge/report)
```

### Adding New Gates
Proposed additions (open an issue before implementing):
1. Mypy strict type checking for core services.
2. Bandit or Semgrep security scan.
3. Performance budget test for dungeon generation (already partially covered by runtime metric assertion).

### Failing a Gate
Fail fast & fix in the same PR. If a deliberate behavior change breaks a balance or invariant test, update the test with an inline rationale in the diff.

---
