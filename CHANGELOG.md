# [0.8.6] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.8.5] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.8.4] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.8.3] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.8.2] - UNRELEASED
### Added
- `GET /api/dungeon/party` — live party HP/MP, so the adventure screen's
  character cards can refresh without a page load.
- Named monster loot tables (`app/loot/tables.py`): a table name resolves to a
  tier read off its suffix, filtered against the item catalogue by type, rarity
  and level, so adding an item makes it eligible everywhere it fits.
- Design specs for the next phase of work, all cross-referenced:
  tactical combat ([spec](docs/superpowers/specs/2026-07-28-tactical-combat-design.md)),
  the adventure HUD ([spec](docs/superpowers/specs/2026-07-28-adventure-hud-layout-design.md)),
  character panels and the paper doll ([spec](docs/superpowers/specs/2026-07-28-character-panel-redesign.md)),
  item usage in combat ([spec](docs/superpowers/specs/2026-07-28-combat-item-usage-design.md)),
  and a tile atlas ([spec](docs/superpowers/specs/2026-07-27-tile-atlas-proposal.md)).

### Changed
- The dungeon map is sized from the viewport
  (`clamp(220px, calc(100vh - 390px), 720px)`) instead of a fixed 512px. The
  adventure screen needed ~880-910px of vertical space against the ~630-660
  usable on a 1366x768 laptop, so the map and the movement controls could not
  both be on screen. Large displays now get more map, not the same map.
- Equipment cannot be changed during a fight. Armour swaps are disallowed
  outright; weapon swaps are disallowed *through the inventory API* until they
  exist as a combat action that can charge one.
- Spawns above the monster catalogue's level ceiling fall back to the deepest
  band that exists rather than degrading to a nameless stub.

### Fixed
- **Reseeding aborted on any played database.** `clear_item_categories` released
  `dungeon_loot` rows for only four item types while the seed files delete a
  wider set, so one floor-loot row pointing at (say) a gem blocked that file's
  DELETE with a foreign-key violation. Everything after it — including the
  monster catalogue, loaded last — never ran, which is how both databases ended
  up with 0 monsters and 0 archetypes.
- **Monsters dropped no catalogue loot, ever.** `loot_table` values
  (`goblin_basic`, `boss_dragon`) were parsed as a CSV of item *slugs*, matched
  nothing, and returned an empty pool. Procedural gear and boss keys still
  dropped, which is why it went unnoticed.
- **Character panels never updated.** They rendered from a `session["party"]`
  snapshot frozen when the party was picked, so HP/MP showed selection-time
  values (full) for the whole run regardless of combat, poison, regen or camping.
- **The loot distribution dialog was entirely unclickable.** Click handlers were
  inline attributes with string ids interpolated unquoted, so
  `selectItem(potion-healing_0)` parsed as `potion - healing_0` and threw
  ReferenceError. Also labelled every character "Unknown" by reading `class`
  where the combat snapshot stores `char_class`.
- **Confirming a distribution 500'd.** `can_add_item(inv, character.stats, ...)`
  had its first two arguments swapped against the `(str_score, inv, ...)`
  signature. Behind that, the result was tested as a truthy tuple, so the carry
  limit would never have blocked an item anyway.
- **User accounts could not be deleted.** Seven tables reference `user` with no
  cascade, so any account that had entered a dungeon, opened a combat session or
  been given a hoard failed on a foreign key.
- Three order-dependent tests that asserted a fixture monster was the only match
  for a real family — true only while the catalogue was empty, so they passed on
  an unseeded database and failed on a seeded one.

### Notes
- `docs/TESTING.md` documents two ways to corrupt the test database, both of
  which cost hours: concurrent pytest runs (`db_isolation` tests drop and
  recreate the schema mid-run, so two runs destroy each other), and the fact
  that a `db_isolation` rebuild reseeds with a ~14-item minimal seeder rather
  than the full catalogue — so a test depending on real seed data passes alone
  and fails in the suite depending on ordering.
- Several of these were found by writing the design specs rather than by
  playing: the equipment loophole, the unenforced carry limit, and a spell that
  cost no mana when it missed.

# [0.8.1] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.8.0] - UNRELEASED
### Added
- `docs/DESIGN_SYSTEM.md` — the source of truth for Adventure's visual design:
  the two-realm palette, token reference, semantic colour roles,
  type/space/radius/elevation scales, the component vocabulary and what should
  replace the stock Bootstrap that carries the game screens, the rules that
  keep it consistent, and a phased migration plan.
- `app/static/css/tokens.css` — the project's single token file, replacing the
  ten `:root` blocks spread across eight files.
- **Two realms.** The warm town and the cold dungeon share one structural
  system and differ in seven values, switched by `data-realm` on `<body>`.
  Town is the default; the dungeon palette is derived from the tileset so the
  chrome and the map read as one place.
- "Lamplight" theme — warm candlelit hall with an amber accent, seeded as the
  active default. "Cold Steel" and "Classic Dungeon" stay selectable.

### Changed
- `auth.css` (login + register) rebuilt on the token system as the reference
  implementation: zero literal colours, radii, shadows or durations, and
  realm-agnostic. Serif display masthead, tapered rules, corner ticks, hard
  edges and one solid element.
- `theme.css` no longer declares tokens; its `--dungeon-*` / `--adv-*` aliases
  now resolve to the semantic layer, which makes ~234 existing call sites
  realm-aware without being touched.

### Fixed
### Notes
- The rest of the CSS has **not** been migrated — see the migration plan in
  `docs/DESIGN_SYSTEM.md`. Three defects in the theme layer are documented
  there and block phase 1, including a no-active-theme fallback that renders a
  second, unrelated palette on every page of a fresh install.

# [0.7.25] - UNRELEASED
### Added
- `tests/test_full_run_e2e.py`: end-to-end runs driven through the real HTTP API
  (enter, explore, fight, stairs both ways, boss, loot, portal, extract) plus a
  party-wipe run and a hearthstone-abandon run.
- Separate **Extract** button (hotkey `E`) on the adventure screen; it and
  **Hearth** used to share one button.
- `CombatSession.dungeon_snapshot_json` column (migration `d9e2f3a4b5c6`).
- Per-run XP baseline (`instance.dungeon_metadata["xp_at_entry"]`) recorded when
  the party locks into a run.
- Monster compendium expanded from 45 to 105 entries (SRD 5.1-derived, CC BY 4.0,
  reflavoured to house style). Dragons went from a single level-15 boss to a full
  1-20 line; undead and humanoids previously stopped at level 9-10; the 16-20
  bands and the cold/water elemental line were empty.

### Changed
- Hearthstone is now a no-fault abandon: the party is released, keeps everything
  it found, and the dungeon instance is destroyed. It no longer halves each
  character's lifetime XP.
- A party wipe now resets the run: characters are permadeathed and unlocked, the
  dungeon instance is deleted and the session pointer cleared.
- Starting *or continuing* an adventure locks the selected party to the instance
  (`locked_dungeon_id`), which is what extraction selects on, and records the
  run's XP baseline. Baselines are never rewritten on re-entry.
- Early extraction now costs **20% of the XP earned during that run** (was 30% of
  each character's *career* XP, which could erase many runs' progress and left
  `level` out of sync with `xp`). The rate is tunable from Admin → Dungeon
  Settings → Early Exit XP Penalty, which now mirrors into the `progression`
  GameConfig key the engine actually reads — previously that field was inert.

- Admin → Combat and Admin → Loot now reach the running game: the four
  monster-behaviour knobs mirror into `monster_ai`, and item rarity weights into
  `floor_loot`. Combat page defaults were aligned with the engine's so that
  saving the page untouched changes nothing. Every settings page now carries a
  banner naming which of its fields are live; the rest are still inert.
- Early extraction now also skims 20% of the copper reaching the Hoard — the
  "loot penalty" the extraction modal has always advertised but never applied.
  Items are never skimmed. `penalties.loot_quality_multiplier` is renamed
  `penalties.copper_multiplier` to say what it does.

### Removed
- `POST /api/dungeon/extract`, an unreferenced second extraction model that
  granted 1000×tier XP and pooled no haul. The live path is
  `POST /api/dungeon/extraction/extract`.

- Elite and boss spawns now take their identity (name, family, traits, loot
  table) from the monster catalogue while keeping archetype-driven stats, and
  respect the dungeon's monster family. They were announced as literal
  `"Elite (L3)"` / `"Boss (L12)"`.

- Spell and skill damage now scale with character level, not just INT (spells)
  or nothing at all (skills). `_derive_stats` never carried `level` into the
  combat snapshot, so nothing downstream could scale by it: a level-20 firebolt
  hit for the same ~17 as a level-1 one while a free weapon swing had grown to
  ~32. Adds `_spell_power` (0.6xINT + level) and applies skill bases on top of
  the caster's power. Measure with `scripts/audit_combat_damage.py`.
- Monsters no longer focus one party member: they picked the lowest-HP target
  every turn, so three of four characters were spectators.
- Turn order steps over downed characters instead of stopping on them.

- Camping now costs a `consumable_campfire_kit`, has a 40-tick cooldown, and
  carries a 25% chance of drawing an ambush. Tunable via `GameConfig["camp"]`;
  every class starts with a kit and two merchants stock them.
- Dungeon difficulty is anchored at run start and steps up per floor descended
  (`GameConfig["difficulty"]["floor_level_step"]`) instead of tracking the
  party's current level, so levelling mid-run no longer drags the world up too.

### Fixed
- Characters could not be deleted. Ten tables carry a foreign key to
  `character` and none cascade, so `db.session.delete()` raised a
  ForeignKeyViolation for any character with a skill row — i.e. all of them,
  since every character is granted a starting skill. `character_service`
  clears owned rows (skills, talents, effects, achievements, quests, party
  membership, trade history), nulls the references that outlive a character
  (party leader, shared-inventory contributor), then deletes.
- Permadeathed characters were auto-added to parties: formation took "the
  first four characters by id", which after a wipe is exactly the four
  corpses. Autofill, Start Adventure (including its lenient name-matching
  fallback) and Continue Adventure now all skip them. The roster still lists
  them, marked LOST, with a BURY button.
- Camping *reduced* the HP of any character above 100: it read
  `stats["max_hp"]` (which characters never store) with a default of 100 and
  clamped `min(100, current + restore)`. Now uses `compute_hp_mana_max`, and
  resting can only ever increase HP/mana.
- Kill tracking never ran: `start_session` skipped writing the dungeon snapshot
  because the column did not exist, so `bosses_defeated`, `elites_defeated`,
  `monsters_defeated`, the extraction unlock and quest kill progress were all
  silently dead.
- Boss kills were not recognised: `trigger_collision_combat` dropped `archetype`
  (and xp/loot_table/resistances) when building the combat payload.
- Extraction was impossible in a real run: nothing set `locked_dungeon_id`, so
  `extract_party` always reported "No characters in this dungeon".
- Deleting a dungeon instance always failed on `dungeon_entity`'s foreign key,
  breaking both `/api/dungeon/hearth` and `/api/dungeon/extract`.
- `_level_window` inverted past party level 18, raising an empty-range
  `randrange` and silently generating no floor loot.
- `populate_spawn_stats` swallowed missing-reference-data errors silently,
  substituting junk monsters ("Elite Monster", hp = level*20, no loot table).
  It now logs `spawn_stats_fallback` with the archetype, level and family.

### Notes
- Reward-granting failures in `_check_end` now log instead of rolling back
  silently — that rollback also discards kill-tracking increments.

# [0.7.24] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.23] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.22] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.21] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.20] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.19] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.18] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.17] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.16] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.15] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.14] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.13] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.12] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.11] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.10] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.9] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.8] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.7] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.6] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# [0.7.5] - UNRELEASED
### Added
### Changed
### Fixed
### Notes

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Looter-extract economy & progression (Path A, Specs 1–5)
- **Currency**: copper-internal with 3-tier (g/s/c) display (`app/economy/currency.py`).
- **Hoard**: per-user persistent vault of gear + copper (`app/models/hoard.py`,
  `app/economy/hoard_service.py`, `app/routes/hoard_api.py`). Run-purse (`Character.gold`)
  is at-risk; extraction pools the haul into the Hoard; party wipe loses it.
- **Trading** repointed to the Hoard; `seed-merchants` CLI; `POST /api/trade/repair`.
- **Procedural floor loot**: `DungeonLoot` can hold generated gear instances; config-driven
  drop chance + rarity weights (deterministic per seed).
- **Durability & repair**: gentle, config-driven gear wear; broken = reduced bonuses.
- **Progression**: XP→levels→talent+stat points (`app/services/progression.py`); awarded on
  kills and extraction; gated `level-up` allocation.
- **Skills**: starter seeder (`seed-skills`); passive effects feed combat/dashboard stats;
  active skills as combat actions (`POST /api/combat/<id>/cast_skill`).
- **Persistent status effects**: poison now survives past combat (decays via the overworld
  game clock instead of vanishing at combat end, floored at 1 HP outside combat), plus slow
  passive HP/MP regen while exploring (tunable via `GameConfig` `regen_rates`). Foundation
  for richer character-card UI in a future release.
- New docs: `docs/ECONOMY_PROGRESSION.md`.

### Fixed
- Skill/trade/level-up endpoints hardened (auth + ownership; admin-gated talent grant).
- Test suite fully green: fixed `combat_persistence` (initiative determinism) and
  `encounter_config` (monster seed) flakiness; `conftest` binds the test DB before import;
  untracked stale `.pyc` files; `manage.sh` uses `.venv` + Alembic and seeds merchants/skills.
- Test isolation: the suite now wraps every test in a real per-test transaction (commit and
  rollback both redirected to a SAVEPOINT at the database-driver level), so tests can no
  longer leak permanent writes into the shared test database regardless of how many times a
  test or its fixtures call `commit()`/`rollback()`.
- Migrations: the dev/test database bootstrap now self-stamps Alembic to `head` the first
  time it's ever touched, so `db.create_all()`'s import-time convenience and a real
  `alembic upgrade head` no longer fight each other on a fresh checkout.

## [0.7.0] - 2025-12-02

### Added
- Purple gradient glass-morphism theme system with centralized CSS architecture
- `base.css` - Core theme system with CSS custom properties and utilities (281 lines)
- `glass-theme.css` - Reusable glass-morphism components library (870+ lines)
- Glass-morphism styling for navbar with purple accent colors and backdrop blur
- Glass-morphism styling for footer with purple brand colors and hover effects
- SVG icons: `plus-circle.svg`, `people-fill.svg`, `shuffle.svg`, `dice-5.svg`

### Changed
- **Major CSS consolidation**: Extracted 1400+ lines of inline CSS from templates into static files
- Dashboard page (`dashboard.html`) reduced from 738 to 267 lines
- Profile page (`account/profile.html`) reduced from 560 to 216 lines
- Settings page (`account/settings.html`) reduced from 340 to 190 lines
- Admin dashboard (`admin_dashboard.html`) reduced from 434 to 258 lines
- All pages now use consistent purple gradient (#4c5270 → #5a3a52) background
- Navbar and footer now use glass-morphism effects matching the overall theme
- Moved documentation files to `docs/`: MONSTER_AI.md, CORRIDOR_GAP_FIX.md, DASHBOARD_FIX.md, INFRASTRUCTURE_SUMMARY.md, PROJECT_HEALTH_REPORT.md, STRUCTLOG_PROGRESS.md, exception_report.md

### Improved
- CSS maintainability through centralized theme files
- Consistent visual design across all application pages
- Performance through reduced HTML size and reusable CSS classes
- Code organization with documentation consolidated in docs/ directory

## [Untagged] - Dungeon, Combat & Persistence Expansion (between 0.6.0 and 0.7.0)

> The work below shipped after 0.6.0 and before 0.7.0 but was never cut into a tagged
> release at the time — recorded here under its own heading rather than assigned a
> retroactive version number it never actually had.

### Added
- **HP/MP Persistence Fixes**:
  - `_derive_stats()` reads persisted current HP from `Character.stats['hp']`.
  - Combat sessions start with actual current HP instead of always max HP.
  - Dashboard party payload shows real current HP/MP values (not hardcoded full).
  - Dungeon state API (`/api/dungeon/state`) includes a party array with current HP/MP.
  - Fixes free healing between combats and incorrect HP/MP bars on the adventure screen.
- **Boss Combat System** (`app/services/boss_abilities.py`):
  - Boss-specific abilities: AOE attacks, self-buffs, healing, minion summoning.
  - Phase transitions at 25% HP (enrage) and 10% HP (desperate).
  - Cooldown system for abilities (3–6 turns depending on ability).
  - Level-gated ability unlocks (AOE at 1, buff at 3, summon at 5, heal at 7).
  - Enhanced loot: 3x item drops, 75% special drop chance, guaranteed key drop.
- **Dungeon Extraction System** (`POST /api/dungeon/extract`):
  - Progress tracking: bosses_defeated, bosses_total, elites_defeated, monsters_defeated.
  - Extraction available once all bosses are defeated.
  - Completion rewards: 1000×tier base XP + 50×elites + 10×monsters (capped at 500).
- **Locked Door System** (see `docs/LOCKED_DOORS.md`):
  - Locked doors (`L`) non-walkable until unlocked.
  - Key items: rusty-key (common), master-key (rare), boss-key (epic).
  - Rogue lockpicking: DEX-based skill check (DC = 10 + tier×2), critical failure breaks lockpicks.
  - Unlock API (`POST /api/dungeon/unlock`); unlocked state persists per dungeon instance.
- Combat targeting: monster/boss AI now selects valid alive targets with lowest HP instead
  of a hardcoded index, and AOE abilities skip dead party members.
- Dead characters (HP=0) can no longer take actions; auto-advance turn with an
  "unconscious" message on attempted action.
- Frontend Autofill button on Dashboard (`POST /autofill_characters`), with a richer JSON
  response (stats, coins, inventory).
- Corner tunnel nub pruning and a door-inference safety pass (new metrics:
  `corner_nubs_pruned`, `doors_inferred`); final post-pruning invariant re-run guards
  against late structural changes.
- Modular dungeon package: `app/dungeon/` decomposed into `pipeline.py`, `generator.py`,
  `doors.py`, `pruning.py`, `connectivity.py`, `features.py`, `cells.py`, `metrics.py`.
- Dungeon API decomposed into focused helpers under `app/dungeon/api_helpers/`: movement,
  tile-type mapping, dashboard payload serialization, encounter/patrol logic, perception &
  search, treasure claiming.
- Turn-based combat (initial implementation): session model, initiative ordering, player
  actions (attack, flee, defend, cast_spell, use_item), monster auto-AI turn, loot + XP
  distribution, optimistic concurrency via `version`. Phased turn engine scaffold (`phase`
  field: start → action → end) for future start/end-of-turn triggers.

### Changed
- Adventure client fog-of-war moved entirely client-side (local storage + in-memory sets).
- Admin fog modal simplified to local coverage only.

### Removed
- Legacy seen-tiles subsystem (`/api/dungeon/seen*`): rate limiting, compression, merge,
  metrics, and admin clear endpoints, plus their tests. Breaking change for any external
  clients depending on server-side fog-of-war; migrate to client-managed fog-of-war.

## [0.6.0] - 2025-09-24

### Added
- Equipment & Bags modal with drag-and-drop equip, per-slot Unequip buttons, and consumable Use actions.
- Equipment UI on both Dashboard and Adventure party cards.
- Inventory API: `GET /api/characters/state`, `POST /api/characters/<cid>/equip`,
  `POST /api/characters/<cid>/unequip`, `POST /api/characters/<cid>/consume`.
- Dungeon perception/search flow: persistent notice markers, Search gated after perception,
  tooltipped clickable loot.

### Changed
- Character creation/autofill initialize `gear` as `{}` instead of a list for consistency.

### Fixed
- Hardened `/api/characters/state` against 404/500s: robust user ID extraction, legacy gear
  normalization (list → dict), per-character try/catch shielding for partial results.
- Loot markers removed after claim and persist correctly across refresh.

## [0.5.0] - 2025-09-22

### Added
- Dedicated Moderation Panel (filter All/Banned/Muted, search, direct Ban/Unban/Mute/Unmute).
- Temporary mute durations (in-memory auto-expire; persistent DB `muted` flag remains for hard mutes).
- Dungeon pipeline phase-timing metrics (`phase_ms`) for profiling.
- Deterministic `_admin_status_snapshot()` helper stabilizing ban-visibility regression tests.

### Changed
- Dungeon pipeline: conditional second invariant/inference sweep only runs if corner-nub
  pruning changed cells, recovering performance headroom.
- Removed the legacy monolithic `app/dungeon.py` compatibility shim; imports now target the
  `app.dungeon` package directly (public import path unchanged).
- Door guarantee logic carves outward minimal tunnels for rooms lacking a viable exit.

### Fixed
- Intermittent ban-visibility test failure resolved via the deterministic status helper.
- Performance regression addressed (median runtime back under threshold).

## [0.4.0] - 2025-09-21

### Added
- Dense door cluster pruning (2x2 windows with 3+ doors collapsed to one, preserving
  legitimate fork/junction double-door patterns).
- Orphan tunnel pruning (unreachable, non-room-adjacent tunnels removed when hidden-area
  flags are disabled).
- New metrics: `door_clusters_reduced`, `tunnels_pruned`; `@pytest.mark.structure` regression coverage.

### Fixed
- Eliminated visually noisy door bands and stray disconnected tunnel fragments.

## [0.3.4] - 2025-09-21

### Added
- Lightweight SVG normalization pre-commit hook (`optimize_svgs`) across ~2,700 icon assets.
- CI workflow alignment with badge (`build-test` job id), explicit pre-commit run before tests.

### Changed
- Repository renamed from `adventure-mud` to `Adventure`.

## [0.3.3] - 2025-09-21

### Added
- `/api/dungeon/state` endpoint for initial cell description & exits (no blank-move hack).
- In-memory dungeon cache (seed, size) → Dungeon object reuse for performance.
- Pytest suite (movement & seed determinism) + GitHub Actions CI workflow.
- Centralized `/api/dungeon/seed` endpoint (numeric, string→hash, or random regenerate).
- Door normalization refactored into a shared helper with a probabilistic outward-carve
  guard; orphan door repair, connectivity repair (BFS), and a "guarantee every room has a
  door" pass.

## [0.3.2] - 2025-09-21

### Added
- Compass movement pad with dynamic exit enablement.
- Keyboard movement (WASD + arrows) toggle, request queue, 120ms rate limiting, ARIA improvements.
- Centralized class colors as CSS custom properties.

## [0.3.1] - 2025-09-21

### Added
- Cache-busting `asset_url()` helper for static assets (mtime-based versioning).
- Pre-commit governance: no inline styles/scripts, enforced `asset_url()` usage.
- Socket.IO client/server version alignment and stability tuning.

## [0.3.0] - 2025-09-20

### Added
- **Backend modularization**: split into blueprints (`dashboard.py`, `dungeon_api.py`, `config_api.py`).
- **Dungeon state persistence**: moved from Flask session to a `DungeonInstance` DB model.
- **Deterministic dungeon generation**: seed handling for both alphanumeric and integer seeds.
- **Config API**: name pools, starter items, base stats, class map served via API.

### Fixed
- Session size bug (dungeon state now in DB, not session).
- Seed mismatch between frontend and backend.

## [0.2.1] - 2025-09-19

### Changed
- Enforced 4-player party selection limit on the dashboard; checkboxes disable past 4;
  Begin Adventure enabled only with 1-4 selected; card click toggles selection.

## [0.2.0] - 2025-09-18 / 2025-09-17

> Two releases were tagged `0.2.0` on consecutive days during early rapid iteration; both
> are recorded here as they appeared in project history rather than renumbered.

### Added
- Chatbox UI: title bar removed, collapse button moved to tab row, input anchored at bottom.
- Account & Settings section: update email, change password with current/new/confirm validation.
- Party selection flow: select up to 4 characters via checkbox or card click, "Your Party"
  summary card, Begin Adventure posting the selection with validation.
- Adventure briefing page (`/adventure`) summarizing the selected party.

### Changed
- Chatbox uses flex layout; color scheme matches dashboard.
- Dashboard theme polish for readability and feedback.

## [0.1.0] - 2025-09-16

### Added
- Initial CLI with `server` and `admin` commands; `.env` support.
- Flask app with login, registration, dashboard, and character creation.
- Item catalog seeding; starter inventory and coins; character cards.
