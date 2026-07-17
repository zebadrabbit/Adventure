# Adventure — Remaining Work (handoff TODO)

A running list of what's left on **Path A** (the soft-extraction looter loop) plus known
issues. Specs live in `docs/superpowers/specs/`. Suggested workflow per item: read the
spec → write an implementation plan (TDD, small tasks) → implement → verify → merge.

## Done so far
- **Spec 1 — Economy foundation** ✅ merged: copper-based currency w/ 3-tier display,
  trading bug fixes, programmatic merchant seeding (`run.py seed-merchants`).
- **Spec 2 — Extraction economy & the Hoard** ✅ merged: per-user `Hoard` (persistent
  gear + copper), at-risk run-purse (`Character.gold`), death/wipe permadeath wired into
  combat, extract pools haul → hoard, loot-the-body, trading repointed to hoard w/ auth.
- **Spec 3 — Procedural floor loot** ✅ merged: `DungeonLoot` holds gear instances,
  config-driven `procedural_gear_chance` + rarity weights (deterministic), claim into bag.

## Remaining

### Spec 4 — Durability, Repair & UI  (`specs/2026-06-16-durability-repair-ui-design.md`)
- [x] **4a Durability (backend)** ✅ merged: `durability`/`max_durability` stamped on
      generated gear (`app/loot/generator.py`), gentle config-driven loss per fight
      (`app/services/durability.py::degrade_gear`, called from `combat_service`),
      broken gear (durability 0) scales affix contribution by `broken_bonus_multiplier`
      instead of removing it (`app/loot/equip.py::gear_bonuses`), and
      `POST /api/trade/repair` restores it for hoard copper (`trading_api.py`). Tests:
      `tests/test_durability.py` (8 passed). (Discovered already implemented/merged
      under `b4371f9`/`b576cc7` — this session caught the TODO checkbox lagging behind
      and verified it end-to-end.)
- [~] **4b UI:** durability now shows in item tooltips (`app/static/js/tooltips.js`,
      flows automatically from the instance JSON). **Remaining (needs a live browser —
      do interactively with the `run`/`verify` skills + visual companion):**
      - [x] **Repoint trading UI to the hoard.** ✅ merged: `app/static/js/trading-system.js`
            header/Buy/Sell now read the hoard (`GET /api/hoard`), sell supports gear
            instances (rarity + durability), plus a new **Repair** tab calling
            `POST /api/trade/repair {uid}`. Design:
            `specs/2026-06-17-trading-hoard-repair-ui-design.md`.
      - [x] **Hoard/stash screen** ✅ merged: new dashboard "HOARD" button + modal
            (`app/static/js/hoard.js`) — view hoard copper/items, withdraw to a chosen
            character (`POST /api/hoard/withdraw`), auto-invalidates the Equipment modal's
            cache. Design: `specs/2026-06-17-hoard-stash-ui-design.md`.
      - [x] **Run/extraction surface** ✅ merged: floor-loot pickup and the extraction
            screen were already built; this pass added the "secured to hoard" confirmation
            panel (replacing a bare `alert()`) and a **Loot Body** action in the extraction
            modal for downed party members (`POST /api/dungeon/loot-body`). Small backend
            addition: `pool_run_haul`/`extract_party` now report what was secured instead of
            discarding it. Design: `specs/2026-06-17-run-extraction-surface-design.md`.
      - [x] **Encumbrance bar + affix breakdown** ✅ merged: real-affix tooltips
            (`tooltips.js` now reads gear-instance `affixes` instead of guessing), an
            encumbrance bar, and a "Gear bonus: ..." summary — added to BOTH
            `equipment.js` and (the one users actually see) `equipment-enhanced.js`'s
            `EquipmentManager`. Verification also found and fixed a pre-existing crash:
            `_computed_stats` raised `TypeError: unhashable type: 'dict'` whenever a
            character had a procedural gear instance equipped (hit `/api/characters/state`
            and `/api/characters/<id>`). Design: `specs/2026-06-17-equipment-encumbrance-affix-design.md`.
            Follow-up (Minor, non-blocking): `equipment.js` and `equipment-enhanced.js` now
            each have their own near-identical encumbrance/gear-bonus-summary helpers —
            worth hoisting into a shared module (like `tooltips.js`) if either changes again.

### Spec 5 — Character progression  (`specs/2026-06-16-progression-design.md`)
- [x] **5a XP + levels** ✅ (this session): `app/services/progression.py`
      (`level_for_xp`, `grant_xp` → levels + talent points, canonical xp curve). Combat
      kills and extraction now award XP through it; combat's old divergent quadratic curve
      removed. Tests: `tests/test_progression.py`.
      - [x] Gate `level_up_character` to earned stat points ✅ — `Character.stat_points`
            ledger (+ migration); `grant_xp` awards `stat_points_per_level`; the endpoint
            rejects over-spend + negatives. Tests: `tests/test_levelup_gating.py`.
- [~] **5b Skills/spells:** the endpoints already existed (`app/routes/skill_api.py`:
      unlock/use/grant/reset). This session **secured them**: unlock/use/reset are now
      `@login_required` + owner-checked; `grant_talent_points` is admin-only (was an
      unlimited-point cheat). Tests: `tests/test_skill_unlock.py`. Still TODO:
      - [x] Seed starter `SkillTree`/`Skill` rows ✅ — `app/seed_skills.py` +
            `python run.py seed-skills` (2 trees, 5 skills w/ prereqs); e2e seed→unlock
            test. **Run `seed-skills` on deploy.**
      - [x] Apply passive `effect_json` to derived combat stats ✅ —
            `app/services/skill_effects.py::passive_bonuses`, folded into
            `combat_service._derive_stats`. Tests: `tests/test_skill_effects.py`.
      - [x] Wire **active** skills as real combat actions ✅ —
            `combat_service.player_cast_skill` + `POST /api/combat/<id>/cast_skill`:
            validates turn/version/ownership/cooldown, applies `effect_json`
            (damage/spell_damage → monster, heal → caster, capped). Tests:
            `tests/test_cast_skill.py`. (Separate from the legacy hardcoded spell system.)
            Remaining: a UI button to invoke it (part of 5c/combat UI).
      - [x] Fold passives into the dashboard HP/mana display ✅
            (`dashboard_helpers.py`, matches combat).
- [x] **5c Progression UI** ✅ merged: found `character-progression.js` was almost entirely
      dead (fake XP curve, a CSS selector that never matched real markup so the XP bar
      never rendered at all, hardcoded placeholder stats). Rebuilt: real XP bar + a
      "stat_points > 0" allocation badge are now server-rendered in `dashboard.html`
      (`app/routes/dashboard_helpers.py` + `app/routes/inventory_api.py` now expose
      `stat_points`/XP thresholds); `character-progression.js` rewritten to handle only
      the interactive allocation modal (all 6 stats, real values) + a cosmetic level-up
      celebration. Also fixed `skill-tree.js`'s "Skill Tree" button, which was hardcoded
      to always open the first character's tree. Final review caught a real regression
      before merge: the rewrite deleted `updateXPBar`, which `combat.js`/
      `loot-distribution.js` still called post-combat/post-loot — fixed with a
      backward-compatible shim. Design: `specs/2026-06-17-progression-ui-design.md`.

### UI Redesign Phase 1 — Design system foundation ✅
Consolidated the 4 competing CSS palettes into one canonical `--ui-*` namespace
("Cold Steel": slate/charcoal + teal accent, sans-serif), with `--dungeon-*`/
`--adv-*` kept as aliases so no call site needed to change. Shipped via the
existing `Theme` DB model — seeded "Cold Steel" (active) and "Classic Dungeon"
(the old look, still selectable) via `python run.py seed-themes`. Also discovered
and fixed: the admin theme-switcher's `/api/admin/themes/active/css` endpoint was
never linked from any template — now wired into `base.html`/`admin_base.html`/
`combat.html`, so switching themes in the admin panel actually affects what
players see for the first time. Design: `specs/2026-06-18-phase1-design-system-design.md`.
Next: Phase 2 (hub/dashboard layout redesign).

### UI Redesign Phase 2 — Hub/dashboard visual hierarchy polish ✅
Removed a dead `--mud-*` CSS variable block from `dashboard.css` (zero
consumers, confirmed via grep). Converted the last 57 hardcoded amber/brown
`rgba()` literals embedded in `theme.css`'s component rules (character cards,
panel headers, stat blocks) to `color-mix()` expressions on the Cold Steel
namespace — Phase 1 only converted `:root` variable definitions and fonts, not
these embedded literals, so faint amber tints were still leaking through on
card backgrounds/glows despite borders and text already looking correct.
Small spacing/contrast polish: tighter `.stat-grid` spacing, stronger
`.panel-header` visual separation from body content. No layout/markup
changes — deeper hub restructuring (zoned roster/merchants/hoard layout,
folding `skill-tree.js` onto the Bootstrap Modal API) deferred to a later
pass. Design: `specs/2026-06-19-phase2-hub-visual-hierarchy-design.md`.
Next: Phase 3 (Three.js dungeon view).

### UI Redesign Phase 3a — Three.js dungeon scene (static tile grid) ✅
First milestone of the Three.js dungeon view: a toggle-gated
(`?renderer=three`) scene rendering the dungeon's tile grid at a fixed
3/4-angle orthographic camera, reading the existing unmodified
`/api/dungeon/map` contract. Implements `dungeon-canvas.js`'s full public
method surface so `adventure.js` needed only a one-line renderer-selection
change — the existing 2D canvas renderer stays the unconditional default
for every real player session; this is purely a toggle-gated dev preview.
Real bug found and fixed during live-browser verification: the originally
planned 2-mesh `InstancedMesh` + `vertexColors`/`setColorAt` approach
rendered every tile solid black (vertexColors multiplies the per-instance
color against a per-vertex geometry color attribute that `BoxGeometry`/
`PlaneGeometry` don't define) — replaced with one `InstancedMesh` per
distinct tile type (up to 6 for a full map), each with its own plain
solid-color material. Confirmed working end-to-end via real screenshots
(a correctly-colored diamond-shaped room with door tiles) and a
`getCoverage()` cross-check against an independent manual tile count
(exact match). No player/entity rendering, movement, client-side fog
dimming, or minimap yet — each is its own follow-up milestone (3b/3c/3d)
per the roadmap's "room for iteration, not a fixed-scope cutover" guidance
for this phase. Design: `specs/2026-06-19-phase3a-threejs-dungeon-scene-design.md`.
Next: Phase 3b (player/entity billboards + movement).

### UI Redesign Phase 3b — Three.js entity/player billboards + movement ✅
Added `THREE.Sprite` billboards for the player (fixed `axe-sword.svg` icon)
and entities (per-entity `icon` field, falling back to `goblin-scout-t1.svg`),
with a small per-path texture cache. Entities beyond `OUTER_VIS_RADIUS` (26,
matching `dungeon-canvas.js`'s default) from the player are skipped — a
binary cutoff, not the opacity gradient (that's Phase 3c's fog-of-war work).
`updatePlayerPosition` now moves/creates the player sprite and re-centers
the camera on every call (camera-follow movement, snap-only, no easing).
`centerOnPlayer()` is a real call now, no longer a no-op stub. Real bug
found and fixed during live-browser verification: feeding a loaded SVG
`<img>` directly into a raw `THREE.Texture` uploaded nothing — every
billboard rendered fully transparent regardless of `needsUpdate`, confirmed
via a GL pixel readback at the sprite's exact screen position reading
`(0,0,0,0)` despite valid image data and correct placement (a textureless
colored sprite rendered fine in the same spot). Fixed by drawing the loaded
icon onto an offscreen canvas first and wrapping that in a
`THREE.CanvasTexture`, which does upload correctly. Design:
`specs/2026-06-19-phase3b-threejs-entity-billboards-design.md`.
Next: Phase 3c (client-side fog-of-war opacity dimming).

### UI Redesign Phase 3c — Three.js client-side fog-of-war opacity dimming ✅
Added `_buildFogOverlay()`: buckets every rendered tile by Euclidean distance
from the player into one of 5 discrete alpha levels (4 gradient buckets
between `INNER_VIS_RADIUS` (8) and `OUTER_VIS_RADIUS` (26), plus a flat
`MEMORY_DIM_ALPHA` (0.35) bucket for previously-seen-but-now-distant tiles —
all constants matching `dungeon-canvas.js` exactly), then builds one
semi-transparent black `InstancedMesh` per non-empty bucket positioned just
above each tile's visible top surface. Recomputed on `loadMap` and on every
`updatePlayerPosition` call. Deliberately approximates the 2D renderer's
continuous per-pixel gradient with 4 discrete bands rather than porting its
noise-dithering trick — banding is far less perceptible on 3D geometry at
this tile density than on a flat 2D canvas; revisit only if live feedback
says otherwise. Known simplification: wall tiles get top-surface dimming
only, not per-side-face dimming. Verified via Playwright: undimmed before
any move, visibly dimmed at room corners after moving, default 2D renderer
unaffected. Design: `specs/2026-06-19-phase3c-threejs-fog-of-war-design.md`.
Next: Phase 3d (minimap + polish).

### UI Redesign Phase 3d — Three.js minimap ✅
Added a dedicated, absolutely-positioned `<canvas id="dungeon-minimap-three">`
element (hidden by default, shown only by `DungeonCanvasThree`'s
constructor) since a single canvas can't host both a `webgl` and a `2d`
context — the minimap can't share the main WebGL canvas the way
`dungeon-canvas.js`'s own minimap shares its 2D canvas. `_renderMinimap()` is
a direct, mechanical port of `dungeon-canvas.js`'s `renderMinimap()` onto
this new element's 2D context: explored-tile colors, a gold player-position
dot, and a border, using the exact same `minimapSize = 120` and color
constants. Recomputed on `loadMap` and every `updatePlayerPosition` call,
alongside Phase 3c's fog-overlay recomputation. Verified via Playwright,
including a cropped screenshot of just the minimap element showing colored
explored tiles and the gold player dot; also confirmed the minimap/zoom-
button visual overlap in the top-right corner is pre-existing in the 2D
renderer too (identical layout), not a regression from this port. This
closes out Phase 3 (Three.js dungeon view) — `DungeonCanvasThree` now has
full feature parity with `dungeon-canvas.js` on tiles, entities, movement,
fog-of-war, and the minimap, while remaining toggle-gated behind
`?renderer=three` and never the default for real players. Design:
`specs/2026-06-19-phase3d-threejs-minimap-design.md`.
Next: Phase 4 (combat visuals), per the roadmap.

### UI Redesign Phase 5a — Cold Steel: remaining embedded literals ✅
Converted `home.css`'s 19 remaining old-palette `rgba()` literals (6 RGB
triples — 4 reused from Phase 2's `theme.css` mapping, plus 2 new ones found
only here: `rgb(193, 122, 58)` and `rgb(139, 111, 71)`, both low-opacity
hero-section background-glow blobs) to `color-mix()` expressions on the Cold
Steel namespace, via the same mechanical script-based technique Phase 2
used. Investigated and ruled out two other Phase-5-shaped candidates before
landing on this scope: (1) `auth.css` (login/register page styles) — already
clean, zero old-palette literals; (2) `account/profile.html` and
`account/settings.html`'s use of `glass-theme.css` — initially suspected as
a leftover "third palette" inconsistency per Phase 1's findings, but
confirmed on inspection that the specific classes these pages actually use
(`.section-card`, `.stat-card`) are already neutral frosted-glass cards
already referencing `var(--adv-primary)`, and the literally-purple
`.theme-purple-gradient`/`.purple-gradient` body-class rules in
`glass-theme.css` are dead code (no template ever applies either class to
`<body>`) — no fix needed there. Left `home.css`'s indigo hero-badge accent
(`rgba(99, 102, 241, ...)`) untouched — confirmed intentional, not a
leftover from the old amber/brown palette. Verified via Playwright: landing
page renders with Cold Steel tones, hero badge still indigo, zero console
errors. Design: `specs/2026-06-19-phase5a-coldsteel-remaining-literals-design.md`.
Next: the dead `glass-theme.css` body-class rules are a candidate
follow-up (need to confirm they're also unused on `admin_themes.html`
before removing), and Phase 4 (combat visuals) remains deferred pending
live user availability for its visual judgment calls.

### UI Redesign Phase 4 — Combat Cold Steel theming ✅
Dropped combat's leftover white-glass skin (`combat.css`'s `.card-glass`/
`.badge-glass`/blur effects, candy-colored buttons) for flat Cold Steel
panels; collapsed 18 ANSI-style combat-log colors onto 4 semantic tones
(danger/success/warning/accent); recolored `combat-effects.css`'s status
indicators the same way; re-keyed `combat-effects.js`'s generic damage-
number colors onto the `--ui-*` tokens via `getComputedStyle` (elemental
fire/ice/lightning particle colors left untouched as intentional flavor).
Design: `specs/2026-06-19-phase4-combat-cold-steel-design.md`; plan:
`plans/2026-06-19-phase4-combat-cold-steel-plan.md`.

Live verification (with the user, in a real browser) surfaced a long tail
of real bugs beyond the recolor itself, all fixed in this branch:
- Active-turn glow was tuned for the old glass background and read too
  faint against the new flat panels — stronger glow + solid border.
- Fresh characters started at partial HP: `BASE_STATS["hp"]` (a legacy
  flat per-class baseline) was being read as *current* HP instead of full
  health on creation; also fixed an aliasing bug where the same dict
  mutation would have corrupted the shared `BASE_STATS` global.
- The action panel now re-parents into the active character's card each
  render instead of sitting as a disconnected static block — found and
  fixed a real regression of that change too (`partyContainer.innerHTML`
  was destroying the panel node outright once it had been moved inside
  it, only recoverable via full page reload).
- **Confirmed and fixed a real safety gap in `tests/conftest.py`**: the
  DB-isolation check re-read `os.getenv("DATABASE_URL")` *after*
  `from app import ...` had already run, and that import's `load_dotenv()`
  leaks the dev DB's URL into the environment as a side effect — so
  `pytest` with nothing exported was silently wiping the shared dev
  Postgres DB via `db.drop_all()` instead of refusing to run. Confirmed
  via reproduction; fixed by snapshotting env vars before the import.
- Two separate cascade bugs flattened class-badge colors: `combat.css`'s
  `.combat-container .badge` and `theme.css`'s `.panel-header .badge`
  (both 2-class selectors) always outranked the single-class
  `.fighter-badge`/`.warlock-badge`/etc rules — scoped both with
  `:not(.class-badge)`. Also: 6 of the 12 classes (barbarian/bard/monk/
  paladin/sorcerer/warlock) never had badge colors defined at all; added
  them, then raised opacity/adjusted hue (warlock vs. sorcerer) after
  live feedback.
- Combat log layout: `.combat-layout`'s `align-items: stretch` forced all
  three columns to match whichever was tallest (usually the party column)
  — reverted to `flex-start` so panels size independently. A stale
  `app.css` rule (`#combat-log { max-height: 400px }`, left over from a
  prior left/right-swapped layout) was still clamping the log despite
  combat.css's fix. Finally, `.combat-log-card`'s `min-height: 600px` was
  fighting its own `max-height: calc(100vh - 160px)` — CSS gives
  min-height the win on conflict, so it was still pushing the page into
  scrollbars on shorter viewports; lowered the floor to 300px.
- Added missing visual feedback: an attack slash (X swipe) over the
  monster panel, a defend shield pop over the defender's card, and a
  subtle highlight on the most recent combat-log entry.
- Removed a redundant "- CharName" label now that the action panel is
  visually fused to the active card.
- **Every player-action combat-log line hardcoded the word "Player"**
  instead of the acting character's name (attack/miss/defend/flee/
  use_item/cast spell/cast skill) — fixed across the board, each handler
  already had the character snapshot in scope.

Logged, not fixed here (out of scope for a theming branch, found along
the way): monster HP label never wired to live state; the action panel's
3 spells are a shared static list, not per-character; no run-end on full
party wipe; no random encounters while walking; predetermined encounters
visible before being uncovered; unconscious characters can sometimes
still attack; character cards need more detail (stats/DPS/buffs — a real
feature, not a quick fix); the landing page needs another theming pass.
See entries below.

Next: UI Redesign is now complete across Phases 1–5a and this Phase 4.
Remaining open items are the logged bugs/features above, plus the
already-noted `glass-theme.css` dead-code follow-up.

## Known issues / cleanup (not blockers)
- [x] **Test-DB targeting quirk — FIXED ✅:** `conftest.py` now sets `DATABASE_URL`
      from `TEST_DATABASE_URL` *before* importing `app`, so `pytest` with only
      `TEST_DATABASE_URL` set targets the test DB (no more dev-DB risk; both-vars no
      longer required). Verified: full suite green with `DATABASE_URL` unset.
- [x] **Flaky tests — FIXED ✅. The full suite is now green (355 passed, no deselects).**
      - `tests/test_combat_persistence.py` — was ~50% flaky; root cause was the tests
        patching `random` AFTER `start_session` (where initiative is rolled), so the
        monster sometimes acted first. Now patch `randint`/`random` before
        `start_session`. Not an engine bug.
      - `tests/test_encounter_config.py` — autouse fixture seeds a boss+common monster
        spanning the band and clears the spawn cache.
- [x] **Test isolation — fixed for real via per-test SAVEPOINT rollback.** Added
      `_db_transaction_rollback` to `tests/conftest.py`: wraps every unmarked test in a
      connection + outer transaction + nested SAVEPOINT, rebinds `db.session` to that
      connection for the test's duration, and an `after_transaction_end` listener restarts
      the SAVEPOINT every time application code calls `session.commit()` — so commits
      never reach the outer transaction. After the test, the outer transaction rolls back
      and the connection closes, discarding every write (committed or not). Had to
      preserve the app's real `session_options` (notably `expire_on_commit=False`) when
      rebinding — dropping it caused `DetachedInstanceError` the moment a test's own
      nested `with test_app.app_context():` usage tore down an intermediate
      scoped-session entry. `@pytest.mark.db_isolation` tests are skipped by this fixture
      (they call `drop_all()`/`create_all()` directly, which would fight SAVEPOINT
      nesting) — they already get full isolation from `_conditional_db_isolation`'s
      rebuild. Verified: full suite green across 3 consecutive runs (388 passed,
      identical results every time) — the previously-flaky `test_combat_flee_and_monster.py`
      and `test_auth_routes.py` register-test failures, both confirmed shared-DB-state
      symptoms, did not reappear. Audited beforehand for the same
      bug class as the fix below (hardcoded low integer IDs colliding with real leftover
      rows) and found two more candidates, both confirmed safe on inspection, not bugs:
      `test_time_and_encounters.py`'s `DummyInstance.id = 1` only feeds a fabricated
      monster slug (`"m1"`) that can't match real seeded data; `test_unconscious_actions.py`'s
      `skill_id=1` is short-circuited by the downed-character check firing before any real
      Skill/CharacterSkill lookup (confirmed by the test's own comment and the code path).
      - [x] Concrete instance fixed: `test_payload_reflects_gear_hp`'s mock character
            hardcoded `id = 1`, colliding with a real leftover `Character` row id=1 with
            unlocked skills (+3 con) — `passive_bonuses(c.id)` hit the real DB and leaked
            +6 hp_max into the assertion. Changed to `id = -1` (no real row can collide).
- [x] **Tracked bytecode — DONE ✅:** the 7 committed `.pyc` files were `git rm --cached`d
      (`__pycache__/` was already gitignored). Working tree stays clean now.
- [x] **loot-body has no same-run guard — FIXED ✅** (`app/routes/hoard_api.py`): added a
      guard requiring both `downed_id` and `survivor_id` to be in
      `session['last_party_ids']` (the current run's party) — the same source-of-truth
      used by `combat_service.party_is_wiped()`. Tests: `tests/test_hoard_api.py` (5
      passed, TDD).
- [x] **Monster HP label never updates — FIXED ✅**: `render()` now updates the actual
      `#monster-hp-text` label instead of writing into `#monster-hp-bar`'s fill div.
      Found and fixed during Phase 4 live verification.
- [x] **Combat action panel is one static spell list for every character — FIXED ✅**
      (`app/templates/combat.html`'s single `#combat-action-panel`, hardcoded Firebolt/Ice
      Shard/Lightning buttons): not class- or character-specific, so every party member
      appears to have identical abilities. The real per-character skill system already
      exists end-to-end (`POST /api/combat/<id>/cast_skill`, Spec 5b) but had no UI button
      wired to it — this static panel was the older "legacy hardcoded spell system" the
      Spec 5 entry above already flags as separate. Found during Phase 4 live verification.
      Wired via two tasks: Task 1 added a `cooldown` field to
      `GET /api/characters/<id>/skills`'s response; Task 2 added a per-character
      active-skills cache/fetch helper and `renderSkillButtons()` in `combat.js`, rendering
      one button per unlocked active skill (disabled with a cooldown tooltip when
      applicable) inserted before the Flee button, wired to the existing
      `POST /api/combat/<id>/cast_skill` endpoint via a new `doSkillAction()` handler.
      `node --check` confirms the JS is syntactically valid; manual browser verification
      (start combat, confirm skill buttons appear/cooldown/disable correctly, swap active
      character, check devtools for errors) has not yet been performed and remains
      outstanding.
- [x] **No run-end on full party wipe — FIXED ✅**: combat already correctly marked every
      character `is_dead=True` on a wipe, but nothing outside combat checked it. Added
      `combat_service.party_is_wiped()` and wired it into `process_movement()` (the one
      function both the REST and WebSocket move paths call) and the `/adventure` page
      route (redirects to dashboard). Tests:
      `tests/test_party_wipe_blocks_exploration.py` (3 passed). Found during Phase 4 live
      verification — not a combat-theming issue, just noticed along the way.
- [x] **No random encounters while walking the dungeon — FIXED ✅**: `MonsterCatalog` was
      permanently empty (confirmed by forcing a guaranteed roll and removing the outer
      `except Exception: pass` in `maybe_spawn_encounter` that was silently swallowing
      `spawn_service.choose_monster()`'s `ValueError: No monsters available`). Turned out
      `sql/monsters_seed.sql` already had 38 fully-designed monsters across every level
      band/family/rarity/boss — it was just never added to `reseed-items`'s loading list
      (`app/seed_items.py`). No content needed, pure wiring fix. Verified end-to-end:
      `reseed-items` now loads it, `choose_monster()` returns real monsters at level 1
      and level 10. The silent-exception-swallowing itself is still a latent footgun
      (failed invisibly with zero log output) but isn't blocking now that the data exists.
- [x] **Predetermined encounters visible before being uncovered — FIXED ✅**: the server's
      `entities_update` broadcast has no visibility filtering at all (sends every
      `spawn_manager.spawns` entry unconditionally); `dungeon-canvas.js`'s
      `renderEntities()` only checked raw distance (`OUTER_VIS_RADIUS`), never the grid's
      own `cell === 'unknown'` fog-of-war marker that the *tile* renderer already uses a
      few lines below it. Mirrored that same check onto entities. No automated test (no
      JS test infra for canvas rendering) — needs live-browser confirmation.
- [x] **Unconscious characters could act — FIXED ✅**: `player_attack` was the only one
      of six action handlers checking `hp<=0`; `flee`/`defend`/`use_item`/`cast_spell`/
      `cast_skill` had no guard at all. Extracted a shared `_skip_if_unconscious()` helper
      used by all six. Tests: `tests/test_unconscious_actions.py` (5 passed, TDD —
      confirmed each failed for the right reason before the fix). Found during Phase 4
      live verification.
- [x] **Character cards Phase A: persistent status effects — done.** Added
      `CharacterStatusEffect` (new table, migration `c7d8e9f0a1b2`) so poison
      survives past combat instead of vanishing at combat end, decaying via
      the overworld GameClock (`apply_tick_decay`, hooked into
      `time_service.advance_time`) when out of a fight, and via the existing
      turn-based loop in combat (now actually wired for players too --
      `apply_start_of_turn` previously only ever ran for the monster).
      Out-of-combat poison floors at 1 HP (can't kill while exploring).
      Added slow passive HP/MP regen on the same tick hook, rates tunable
      via `GameConfig` `regen_rates` (defaults 0.5%/1% of max per tick).
      Extracted `compute_hp_mana_max` as the one place this phase's new code
      computes HP/mana caps -- deliberately did **not** touch the two
      pre-existing duplicated copies in `combat_service._derive_stats` and
      `dashboard_helpers.build_party_payload` to avoid risking working
      combat/dashboard code for a tangential dedup. Spec:
      `docs/superpowers/specs/2026-06-20-character-cards-phase-a-status-effects-design.md`.
      Foundation only -- no card UI changes yet. Three more phases remain,
      each its own future brainstorm/spec:
      - [x] **Phase B: new effect sources ✅ merged** (`specs/2026-06-21-character-cards-phase-b-effect-sources-design.md`,
            `plans/2026-06-21-character-cards-phase-b-effect-sources.md`): a new shared
            `regen_buff` status-effect type alongside `poison`, with both an in-memory
            combat handler (`status_effects.py::EFFECT_START["regen_buff"]`, heals %
            of max HP/mana per turn scaled by `hp_mult`/`mp_mult`) and a persisted
            out-of-combat counterpart (`apply_tick_decay` multiplies that tick's base
            regen rate while a `regen_buff` row is active). A new `replace_effect`
            helper enforces replace-not-stack semantics. `combat_service.py`'s existing
            poison-only combat start/end round-trip was generalized to also carry
            `regen_buff`. Three sources wired in: a new `potion-regen` item (combat via
            `player_use_item`, out-of-combat via `inventory_api.py::consume_item`'s new
            `"regen" in slug` branch) and `dungeon_camp()`'s instant restore now
            additionally grants a 10-tick "well-rested" buff. Two non-obvious fixes
            found independently by two different implementer subagents (Tasks 5 and 6):
            `advance_for`/`advance_non_combat_time` immediately invoke
            `apply_tick_decay`, which unconditionally decrements *every* active
            `CharacterStatusEffect` row for that character by the tick delta -- so a
            freshly-granted buff inserted *before* that call self-decays the instant it's
            created. Both call sites now insert the buff *after* the time-advance call.
            Built via 6 TDD tasks, each independently subagent-reviewed (Approved, no
            fix rounds needed); full suite green throughout (437 passed, up from a 421
            baseline, no regressions). Phase C/D (card UI redesigns) remain as the next
            steps in this series.
      - [x] **Phase C: dashboard roster card redesign — done.** Dashboard roster
            cards (`.operative-card`) now collapse by default and expand
            independently per card on click (multi-expand, not an accordion) —
            each card has its own `.operative-summary` header and a hidden
            `.operative-detail` panel toggled in place, no shared/global expand
            state. Collapsed summary shows HP/MP bars; expanded detail adds
            generic buff/debuff chips (driven by Phase A/B's
            `CharacterStatusEffect` rows — `poison` and `regen_buff` both
            render, plus any future effect type without template changes) and
            the existing stats/inventory/footer actions (EQUIP, etc.).
            Live-browser-verified end-to-end with Playwright against a real
            dev server + Postgres: collapsed-by-default, click-to-expand,
            independent multi-expand confirmed with 2+ real roster cards
            (registered a fresh `tester` user and used `/autofill_characters`
            to seed 4 characters), collapse-again, and a footer-button
            spot-check (EQUIP) with no console errors after re-expand. All
            assertions passed on the first run — no template/CSS/JS bugs
            found during this task's verification pass. Full suite:
            441 passed (matching the pre-Phase-C baseline), confirmed after
            isolating a `pytest-randomly` test-order flake (6 unrelated tests —
            camp regen buff, cast-spell mana cost, poison persistence x3,
            dashboard theme assignment — all pass individually and with
            `-p no:randomly`; same category of pre-existing cross-test-order
            flakiness already on file, not a Phase C regression).
      - [x] **Phase D: combat party card redesign — done. Closes out the full
            Character Cards series (Phases A-D).** The legacy static spell
            panel UI was retired entirely. Every combat party card
            (`.party-member`) now renders an `.effect-chips` container with
            generic buff/debuff chips driven by Phase A/B's
            `CharacterStatusEffect` rows (`poison`, `regen_buff`, and any
            future effect type without template changes) via a shared
            `describe_status_effect` helper that now lives in
            `app/services/status_effects.py` (reused from the chip-rendering
            logic Phase C introduced for the dashboard roster cards). The
            active character's card additionally auto-reveals a `.stat-breakdown`
            ATK/DEF/SPD panel — exactly one visible at a time, tracking whoever's
            turn it is. Live-browser-verified end-to-end with Playwright
            against a real dev server + Postgres: legacy spell-cast buttons
            confirmed absent, exactly one visible stat breakdown, an
            effect-chips container present on every party card (including a
            real seeded `poison` effect), and no console errors. All
            assertions passed on the first run — no template/CSS/JS bugs
            found during this task's verification pass. Full suite: 446
            passed (within the expected 444-446 range for this branch,
            confirmed after isolating a `pytest-randomly`-style test-order
            flake on one run — camp regen buff + poison persistence x3 +
            dashboard theme assignment all passed individually and on a
            clean re-run with `-p no:randomly`; same pre-existing
            cross-test-order flakiness category as Phase C, not a Phase D
            regression).
- [x] **Test isolation fix from earlier this session never actually worked —
      found and fixed while verifying Phase A.** The `_db_transaction_rollback`
      SAVEPOINT fixture committed earlier today silently did nothing:
      Flask-SQLAlchemy 3.x's `Session.get_bind()` resolves every query through
      `self._db.engines[bind_key]`, never consulting a sessionmaker-level
      `bind=` kwarg, so `db.session` kept committing for real to the test DB
      the whole time -- invisible to pytest's pass/fail output since test
      usernames were unique enough to avoid visible collisions (confirmed: 40+
      permanently-leaked "Hero" characters from this session's own TDD work).
      Real fix required three iterations: (1) patch `Session.get_bind` at the
      class level instead, gated to leave `db.engines[None]`/`db.engine`
      untouched (an `engines[None]` swap looked equivalent but broke
      `app/seed_items.py` and `tests/test_monsters.py`'s `raw_connection()`
      calls); (2) give `do_commit`/`do_rollback` SAVEPOINT semantics at the
      connection's dialect *class* level rather than a flat no-op (a no-op
      commit made any later, unrelated `rollback()` -- e.g. one buried inside
      Flask-SocketIO's test client -- wipe out everything committed earlier in
      the test, not just the current unit of work); (3) gate that dialect
      patch by `dbapi_connection` identity, since the class-level patch
      affects every connection the engine hands out, not just the held one
      (`db.create_all()` opens its own separate connection mid-test and must
      fall through to the real implementation). Verified: 4 consecutive full
      runs post-fix, 402 passed / 0 failed / 0 errors every time, including
      once against a `db.drop_all()` + `alembic upgrade head`-rebuilt DB.
      Also marked `tests/test_legacy_sha256_upgrade.py` and
      `tests/test_legacy_password_upgrade.py` `@pytest.mark.db_isolation`:
      both swap `app.config["SQLALCHEMY_DATABASE_URI"]` to an in-memory
      SQLite DB mid-test, a pattern Flask-SQLAlchemy 3.x silently ignores
      (engine is cached at init, confirmed empirically that config changes
      after that point have zero effect) -- their `db.drop_all()` has
      therefore always targeted the real Postgres test schema the whole time,
      "fixed" afterward only because other tests' fixtures defensively call
      `create_all()` again.
      - [x] **Follow-up — FIXED ✅:** removed the dead
            `SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"` override from both
            files' fixtures (`app_mem`/`legacy_app`) — confirmed it had zero
            effect (Flask-SQLAlchemy caches the engine at `create_app()` time,
            before the override runs), so both tests were always running
            against the real Postgres test DB via the `db_isolation` marker's
            full rebuild. Deleted in favor of the now-working Postgres
            isolation per the option already logged above. Behavior
            unchanged, confirmed by running both files (4 passed) and the
            full suite (454 passed, 0 regressions).
- [x] **Landing page theming literal sweep** — root cause: Phase 5a only converted
      `rgba(...)`-with-alpha literals in `home.css` to `color-mix()` and missed solid hex
      colors (`--hero-gradient-1/2/3`, the hero section's dark-brown background gradient,
      and ~9 more `color:` literals on the hero badge/title/description, CTA buttons,
      feature items, footer links). Mapped each to the matching `var(--dungeon-*)` Cold
      Steel alias. Mechanical literal sweep, same category as the navbar/`app.css` fixes —
      didn't need a separate brainstorm. The one remaining hex (`#a5b4fc`, indigo hero-badge
      accent) is an unrelated distinct accent, left alone.
- [x] **Landing page hero layout redesign** — the user did come back with the predicted
      "still feels weirdly placed and awkward" layout complaint, so this got its own
      brainstorm (with the visual companion: 3 mockup directions, user picked the
      asymmetric split outright). Restructured the single centered hero stack
      (badge/title/description/CTAs/four-inline-icons) into a two-column split: text
      content left, four feature highlights upgraded from small inline icons to bordered
      cards stacked right; collapses to text-first-then-cards on `<lg` via Bootstrap's
      existing grid order (no extra media query needed). Navbar/header/footer stay
      intentionally hidden on this page (confirmed deliberate, not a bug) — unchanged. No
      copy changes. Spec:
      `docs/superpowers/specs/2026-06-20-landing-hero-layout-design.md`. Template/CSS-only,
      no automated tests; full suite green (388 passed).
- [x] **Landing page footer repaired** — 3 issues: (1) a page-wide inline `.container`
      CSS override (meant for `.hero-container` specifically) also stripped the footer's
      own `.container` padding/max-width, smashing the copyright text and links against
      the viewport edges — removed the redundant rule. (2) Terms/Privacy links were dead
      `#` placeholders despite real routes already existing (`main.terms`/`main.privacy`)
      — wired them up. (3) hardcoded "© 2025" — now passed from the `index` route as
      `current_year`. Full suite green (388 passed).
- [x] **No "Support" destination exists anywhere in the app**: added a self-serve `/help`
      route + `help.html` template (no live GMs/support exist for this game, so this is a
      wiki-style help page, not a ticket/contact form) and wired both footers' "Support"
      links to it. Captured 5/5 reference screenshots for the page via
      `scripts/screenshot_help.py` (Playwright-driven against the real dev app/DB):
      dashboard overview, combat action panel, skill tree modal, extraction modal, hoard
      modal — all captured successfully, no follow-up run needed. Along the way found and
      worked around (did not fix, out of scope) a pre-existing bug in
      `app/static/js/skill-tree.js`'s `switchTree()`: it reads `event.target` after an
      `await fetch(...)`, by which point the browser has cleared the legacy `window.event`
      it was relying on, so every tree-selector click threw (silently, into its own
      try/catch) and the skill canvas never rendered after switching trees in real usage
      either, not just under Playwright.
- [x] **`skill-tree.js` tree-switching bug — FIXED ✅** (follow-up to the item above):
      replaced the implicit-global-`event` lookup with a `data-tree-id` attribute on each
      tree-selector button, looked up explicitly by the known `treeId` after the `await`
      instead of relying on `event.target` (which is unreliable post-await and absent
      entirely when `switchTree()` is called programmatically, e.g. the initial
      auto-select on modal open — that path happened to keep working by accident via
      Chromium's non-standard `window.event` leaking from whatever click opened the
      modal). Root-caused and verified with a one-off Playwright repro script (no JS test
      infra exists in this repo): confirmed RED (`TypeError: Cannot read properties of
      undefined (reading 'target')` thrown on every tree switch, active class never
      applied, `renderSkillTree()` never called) before the fix, and GREEN (no console
      errors, correct active class, canvas re-renders) after. Full backend suite still
      green (405 passed) since this is a JS-only change.
- [x] **Dashboard hub layout & flow** — fixed the concrete complaint ("dashboard
      location of items, redesign the layout to flow better"): Merchants/Hoard/
      Party-Management/Achievements were stacked vertically inside the Party Roster
      card's `<form>`, buried below the deploy button. Moved them into a new full-width
      tabbed "Hub Actions" panel (Bootstrap nav-tabs) below the Recruit/Roster row;
      buttons keep identical `onclick`/class wiring, only their container moved. Tabs
      styled consistently with the existing `.chat-header .nav-tabs` Cold Steel pattern
      (`color-mix()`/`var(--adv-*)`, no new literals). Spec:
      `docs/superpowers/specs/2026-06-20-dashboard-hub-layout-design.md`, plan:
      `docs/superpowers/plans/2026-06-20-dashboard-hub-layout.md`. Template/CSS-only, no
      automated tests (verified via curl-based structural check — no Playwright/
      chromium-cli available in this environment to screenshot it; recommend a quick
      manual eyeball pass in a real browser). The game-clock widget
      (`#dashboard-time-tick`, `app/static/js/time-widget.js`) remains purely cosmetic/
      optional and untouched — still safe to remove/restyle/relocate if a future pass
      wants to. Broader "badly broken" theming complaint is otherwise resolved; the
      landing page item below is the only theming work left unscoped.
- [x] **Hide the mana bar for manaless classes** (combat screen): added a
      `MANALESS_CLASSES = {'barbarian'}` set in `combat.js`, wrapped the MP bar in a
      `data-field="mana-group"` element in `combat.html`, and hide that group entirely
      for manaless classes instead of showing a permanently-empty 0/0. Dashboard's plain
      `c.stats.mana` text (not a bar, no 0/0 bug) left as-is — folds into the already-logged
      dashboard theming pass below if it needs the same treatment. Barbarian still has no
      rage/energy-style alternate resource (confirmed via grep, not implemented in any
      form) — that remains a separate, unscoped feature idea if ever revisited.
- [x] **Autofill character names are unrealistic (e.g. "Barbarian735")**: fixed two root
      causes in `handle_autofill` (`app/routes/dashboard_helpers.py`). (1) 6 of 12 classes
      (barbarian/bard/monk/paladin/sorcerer/warlock) had no `NAME_POOLS` entry at all
      (`app/routes/main.py`), always falling back to `cls.capitalize()`; added a 12-name
      fantasy pool for each. (2) the dedupe logic always appended a numeric suffix even
      when an unused pool name existed — now shuffles the pool and tries unsuffixed names
      first, only falling back to `f"{base_name}{suffix}"` once the whole pool for that
      class is taken within the same autofill batch. TDD'd via
      `tests/test_autofill_name_pools.py`; full suite green (386 passed).
- [x] **`app.css`'s remaining amber literals swept** (`.card-header`, `--bs-primary-rgb`,
      `.btn-primary`'s box-shadows, `.icon-glow`, dungeon player-marker glow, movement-pad
      focus ring, form focus shadow, table hover background) — same "Medieval Stone"
      leftover category as the navbar fix (`f7aa067`), just not behind an `!important` so
      individually less visible, but rendering brown glows/shadows site-wide on any page
      without its own override. Swapped to `color-mix()` against `var(--adv-primary)` (and
      `--bs-primary-rgb` to the matching Cold Steel teal triple `90, 209, 201`). Also
      relabeled two stale "Medieval" comments. Full suite green (388 passed).
- [x] **Ambient encounters are now a finite per-instance pool, not an infinite random
      roll** — implemented per
      `docs/superpowers/specs/2026-06-21-ambient-encounters-finite-pool-design.md` across
      5 tasks: (1) added proximity aggro to `SpawnManager`-placed monsters; (2) added a
      shared collision-trigger helper wired into both directions of player/monster contact
      on the grid; (3) retired the random per-move combat-encounter roll entirely — across
      6 call sites, more than the original plan scoped, a real discovery made mid-task;
      (4) removed the now-dead `encounter_spawn_rate` admin control; (5) fixed
      `populate_spawn_stats` (`app/dungeon/spawn_integration.py`) so PATROL/WANDERER/GUARD/
      AMBIENT spawns draw real monster names from `spawn_service.choose_monster` (the
      `MonsterCatalog`) instead of generic archetype labels like "Trash (L3)", while
      BOSS/ELITE spawns deliberately keep the existing tier/affix-driven
      `choose_archetype_monster` system unchanged (set-piece placements, separate scaling
      mechanic, out of scope). Final suite: 409 passed, 2 skipped, 3 deselected, 1 xpassed.
      Play-feel tuning of `aggro_radius` and overall spawn density is explicitly out of
      scope for this spec and is left as an easy follow-up once verified live.
- [x] **Dungeon enemy theming — DONE ✅**: each `DungeonInstance` now gets a single
      deterministic enemy theme (one `MonsterCatalog` family, e.g. all-undead) instead of a
      true random spread of families per instance. Added a `monster_family` column to
      `DungeonInstance` (nullable, defaults to `None` for pre-existing rows), a
      deterministic `pick_monster_family(seed)` picker in `spawn_service` (seeded by the
      instance's own seed, so re-deriving the same instance always yields the same theme),
      and an optional `family=` filter on `spawn_service.choose_monster`. Every
      real-gameplay `DungeonInstance(...)` construction site (`dashboard.py`'s
      `start_adventure` and `continue_adventure` fallback branches, and `seed_api.py`'s
      instance-creation branch) now assigns the theme via `pick_monster_family(seed)` at
      creation time. `populate_spawn_stats`'s ambient-tier branch now passes
      `family=getattr(instance, "monster_family", None)` through to `choose_monster`, so
      ambient (PATROL/WANDERER/GUARD/AMBIENT) spawns are restricted to the instance's theme
      when one is set, and unrestricted (original random-family behavior) when it's
      `None`. BOSS/ELITE spawns via `choose_archetype_monster` are deliberately left
      untouched (separate set-piece/scaling mechanic, out of scope). Final suite: 421
      passed, 2 skipped, 3 deselected, 1 xpassed.
      Follow-up found during final review (sanctioned by the design spec's graceful-
      degradation section, not a defect, just worth tracking): `MONSTER_THEME_FAMILIES`'
      7 values have very uneven low-level coverage in `sql/monsters_seed.sql` -- `beast`/
      `humanoid`/`undead` have non-boss rows from level 1, but `demon` starts at level 4
      and `aberration`/`construct`/`elemental` start at level 7. A new low-level dungeon
      themed as one of those three sparse families finds zero eligible ambient monsters,
      hits `choose_monster`'s `ValueError`, and falls back to generic "Trash Monster"
      stats for its whole ambient pool -- a visible, themed-by-luck regression in
      encounter quality for roughly 4/7 of new low-level dungeons. Two candidate fixes,
      neither done yet: widen low-level `MonsterCatalog` coverage for the sparse
      families, or bias `pick_monster_family` away from families with no rows in the
      dungeon's likely level band.
      **Fixed ✅** (2026-06-21): added `spark_wisp_t1`/`gust_elemental_t2`
      (elemental), `rubble_construct_t1`/`animated_armor_t2` (construct),
      `spore_crawler_t1`/`gloom_tendril_t2` (aberration), and `imp_lesser_t1`
      (demon) to `sql/monsters_seed.sql` -- every family now has T1 (1-3) and
      T2 (4-6) coverage. No code changes needed (`choose_monster`/
      `_eligible_monsters` already query generically). Tests:
      `tests/test_monster_family_low_level_coverage.py` (8 passed, loads the
      real seed file via the same pattern `tests/test_monsters.py` already
      established). Spec: `specs/2026-06-21-monster-family-low-level-coverage-design.md`.
      Re-run `python run.py reseed-items` on any running dev/prod DB to apply.
- [x] **Combat log clears and retypes after a spell cast — FIXED ✅**: every action
      handler emits `combat_update` twice per turn (player's action + the internal emit
      inside `monster_auto_turn()`), with no client-side ordering guarantee — if the
      second (longer-log) emit arrived before the first, `appendLog()` saw the log
      "shrink" and wiped + retyped everything. Not spell-exclusive in principle (matches
      the user's own observation), just more visible during spell casts since the
      particle-effect animation competes for the main thread, widening the race window.
      Added a version-monotonicity guard at `combat.js`'s single `render()` entry point
      (covers REST responses, all socket events, and the polling fallback). No automated
      test (no JS test infra for socket-timing races) — needs live-browser confirmation.
- [x] **Combat potions were a shared party pool — FIXED ✅**: `item_counts["potion-
      healing"]` changed from a flat int (always `chars[0]`'s count) to a per-character
      dict; `player_use_item` now deducts from the *acting* character's own row.
      `_potion_counts_by_character()` helper used consistently at session start, after
      loot rewards, and in `combat_api.py`'s legacy backfill path. Tests:
      `tests/test_potions_per_character.py` (2 passed, TDD — first run was a false
      positive because the random seed happened to make character #1 act first,
      coincidentally matching the bug; re-biased initiative to expose it for real).
      Still true and unaddressed: the "Potion" action is hardcoded to `potion-healing`
      only (flat 25 HP) — there's no mana-potion action at all.
- [x] **Combat instance resolution** fixed: `_current_instance_for_user` guessed via
      "most recent `DungeonInstance` row for this user" instead of reading
      `session['dungeon_instance_id']` — the canonical current-instance pointer every
      dungeon route (`dungeon_api.py`) already uses. A user with multiple instance rows
      (e.g. an old abandoned run) could have death/extraction effects silently locked to
      the wrong instance. Now prefers the session pointer, falling back to "most recent
      row" only when there's no request context (direct service-level calls). TDD'd via
      `tests/test_combat_current_instance.py`; full suite green (388 passed).
- [x] **Migrations vs dev DB fixed** — root cause was deeper than "needs stamping": three
      schema systems (`db.create_all()`, `app/server.py`'s legacy `_run_migrations()`, and
      `app/migrations/__init__.py`'s separate versioned `apply_migrations()`) all run as a
      module-level import-time side effect, so anything importing `app` (including
      Alembic's own `env.py`) rebuilds the schema before Alembic's migration chain gets a
      chance to run — confirmed directly: `alembic upgrade head` against a freshly dropped
      DB failed with `DuplicateColumn` because the import-time bootstrap re-added the
      column moments before Alembic's migration tried to. Fixed by self-stamping to `head`
      once, in `app/__init__.py`, immediately after the existing bootstrap — but only if
      `alembic_version` doesn't exist yet (never touches a DB already under real Alembic
      control). Verified: fresh `drop_all()` + reimport auto-stamps, `alembic upgrade head`
      then no-ops cleanly, re-import doesn't error/double-stamp. Also fixed the actual dev
      DB (restarted the server, confirmed `alembic current` now reports `head`,
      `b2c3d4e5f6a7`, with the existing 25 characters/data untouched). Spec:
      `docs/superpowers/specs/2026-06-20-migrations-self-stamp-design.md`. Full suite green
      (388 passed).
- [x] **Pre-commit hook bypass fixed (ratchet, not full cleanup)**: `inline-style-check`
      and `inline-script-check` failed on any edit to one of 13 templates with
      pre-existing violations (confirmed via `git stash`, predating this work), forcing
      `--no-verify` on every such commit. Restored the `ALLOWED_FILES` ratchet pattern
      (already present but emptied in `check_inline_styles.py`) and added the same to
      `check_inline_scripts.py`: grandfathered the 13 known violators so the hooks stop
      blocking unrelated commits, while still catching any *new* inline style/script
      usage anywhere else — verified with a synthetic violation in a throwaway file.
      `pre-commit run --all-files` now passes both hooks cleanly.
- [x] **Inline style/script extraction (the full cleanup, done file-by-file)**: all 13
      grandfathered templates cleaned and removed from both `ALLOWED_FILES` ratchets —
      both sets are now empty. Pattern used throughout: constant-value `style=` attrs
      became classes (existing CSS files, or the page's own inline `<style>` block where
      one already existed, e.g. `adventure.html`/`admin_themes.html`); the one genuinely
      per-request dynamic style (`dashboard.html`'s XP bar `width:{{ xp_pct }}%`) moved to
      a `data-xp-pct` attribute applied by JS on load instead. Inline `<script>` blocks
      with no Jinja templating moved verbatim into new `static/js/*.js` files; the two
      blocks that did template a URL (`fog_settings.html`'s save/reset endpoints) had
      those moved to `data-*` attrs on the form instead so the script itself stayed
      static. Each file verified individually: hook scripts re-run clean, full pytest
      suite green after each commit, and a render-test (real authenticated request,
      asserting `"style=" not in body`) confirmed no inline style leaked into the actual
      rendered HTML for the four largest/most dynamic templates (dashboard, adventure,
      admin_themes, plus combat's progress-bar JS behavior check). Files done: 9 admin
      settings/tools pages, `account/settings.html`, `combat.html`, `dashboard.html`,
      `adventure.html`, `admin_themes.html`. Pre-existing shared-DB test flakiness
      (`test_combat_flee_and_monster.py`, `test_dungeon_api.py`, `test_auth_routes.py`
      register test, varies by run) surfaced twice during verification — reproduced on a
      clean stash of this work, confirming it's unrelated and already covered by the test
      isolation audit above.
- [x] **Dashboard stat-backfill defaults missing `hp` to 0, not a computed
      max — FIXED ✅.** `dashboard_helpers.py`'s `serialize_character_list`
      now backfills missing `hp`/`mana` via `compute_hp_mana_max(c)` (the
      same helper added for status-effect decay) instead of a literal `0`;
      the other stat keys (`str`/`dex`/.../`cha`) still default to `0` since
      those have no computed equivalent. TDD'd via
      `tests/test_gear_party_payload.py::test_serialize_character_list_backfills_missing_hp_to_computed_max`.
      Removed the now-redundant post-login `hp` re-set workaround in
      `tests/conftest.py`'s `auth_client` fixture. Full suite green (402
      passed).
- [x] **`manage.sh restart` silently did nothing when the server wasn't already
      running — FIXED ✅.** Found while capturing help-page screenshots
      (worked around there by starting `run.py` directly). Root cause:
      `cmd_stop`'s "nothing to stop" early-return called `exit 0`
      (`manage.sh:111`) rather than `return 0`; since `cmd_restart` calls
      `cmd_stop` as a plain function call in the same shell process (not a
      subprocess), that `exit` terminated the whole script before
      `cmd_restart` could reach `cmd_start`. `./manage.sh restart` would log
      "Restarting server..." → "Server is not running" → nothing — exit
      code 0, no PID file, no server, no error surfaced. Reproduced with a
      one-off repro script (no bash test infra in this repo) confirming RED
      (no "Starting Adventure MUD server" line, no PID file) before the fix
      and GREEN after. Single-line fix (`exit 0` → `return 0`); confirmed
      `./manage.sh stop` standalone (no server running) still exits 0
      cleanly, unaffected by the change.

## 2026-07-16 maintenance pass (ponytail audit cleanup + follow-ups)
- **Whole-repo cleanup merged** (plan: `plans/2026-06-26-ponytail-audit-cleanup.md`, 10 tasks,
  net ~-1,400 lines): dead files/JS deleted, logging unified on structlog, loot micro-modules
  consolidated into `loot_service`, redis fully removed (dep/compose/env), SECRET_KEY
  production guard (rejects both shipped placeholder keys), the two admin blueprints merged
  into one (`admin.py` deleted), and **alembic is now the only migration system** (all guarded
  DDL ported into the idempotent `legacy_baseline_guards` revision; startup = create_all +
  programmatic upgrade; fresh DBs stamp to head, pre-alembic DBs stamp then upgrade).
- **⚠️ Three.js renderer (UI Redesign Phases 3a-3d) deleted from the tree** as part of the
  audit (`dungeon-three.js` + `?renderer=three` toggle plumbing, commit `f6ae0c1`). Decision
  confirmed with the user 2026-07-16: the 2D canvas renderer is the shipped default; the
  completed Phase 3 work remains recoverable from git history (revert `f6ae0c1`) if the
  Three.js direction is ever resumed. Phase 4 (combat visuals) was done as Cold Steel theming
  and did not depend on it.
- **Suite is fully green for the first time** — the camp-regen flake was root-caused (unscoped
  `Character.query.first()` picking up cross-session stray rows) and fixed; same hardening
  applied to `test_continue_adventure.py`.
- **eventlet → gevent**: Socket.IO async backend migrated (eventlet is in maintenance mode
  upstream); gunicorn uses the `geventwebsocket` worker. Also fixed Dockerfile's CMD, which
  targeted a nonexistent `run:app` (standalone image would crash on boot; compose was fine).
- **Live-browser verification pass done ✅ (Playwright vs real dev server):** all three
  outstanding confirmations PASS — combat skill buttons (render/cast/cooldown/character-swap),
  entities hidden on `unknown` fog cells (verified deterministically incl. an injected probe),
  combat log append-only across ~13 casts (MutationObserver, 0 full-clears). Zero console
  errors. Along the way found and fixed two real client bugs in the cooldown display
  (`combat.js`, `57573b6`): stale `activeSkillsCache` after a cast meant the cooldown branch
  never fired, and naive-UTC `last_used` parsed as browser-local skewed a 5s cooldown to ~5h
  on a UTC-5 host. Report: `.superpowers/sdd/browser-verify-report.md` (screenshots alongside).
- **New known issue found during that pass: `run.py reseed-items` is broken** — its item-clear
  step violates `dungeon_loot_item_id_fkey` now that `DungeonLoot` rows reference items
  (Spec 3). Workaround used: load `sql/monsters_seed.sql` directly. Needs a proper fix
  (clear/cascade dungeon_loot first, or upsert instead of delete).
- Still open from the lists above: `glass-theme.css` dead body-class rules, no mana-potion
  action, aggro/spawn-density play-feel tuning, multi-worker Socket.IO (sticky sessions +
  message queue) if `--workers > 1` is ever real.

## How to run the suite
```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q   # full suite, no deselects needed (511 passed)
```
