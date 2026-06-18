# Character Progression UI — Design

**Date:** 2026-06-17
**Status:** Design only — not yet planned/implemented.
**Part of:** Spec 5 (Character Progression), third and final sub-spec (5c).

## Context

Spec 5a (XP/levels, `app/services/progression.py`) and Spec 5b (skills/spells, seed
data + secured endpoints in `app/routes/skill_api.py`) are fully built and tested. The
TODO listed 5c ("character sheet: level/XP bar, stat allocation, skill tree") as the
last open item, noting `app/static/js/character-progression.js` and
`app/static/js/skill-tree.js` "already exist substantially."

Auditing both files against the real backend found they are at very different levels
of completeness:

- **`skill-tree.js`** correctly calls the real endpoints (`GET /api/skill-trees`,
  `GET /api/characters/<id>/talent-points`, `GET`/`POST /api/characters/<id>/skills`)
  with matching response shapes (verified against `app/routes/skill_api.py`). The only
  gap: the "Skill Tree" button (`app/templates/dashboard.html:186`) is hardcoded to
  `characters[0].id`, so it always opens the first character's tree regardless of which
  character card the button is actually on.
- **`character-progression.js`** is largely disconnected from the real backend:
  - Its XP bar math uses a fake curve, `getXPForLevel(level) = (level-1)² × 100`
    (`character-progression.js:429-432`), instead of the real D&D-5e cumulative table
    in `app/models/xp.py::xp_for_level` (used by `progression.py::grant_xp` /
    `level_for_xp`, which actually drives `Character.level`/`Character.xp`).
  - The stat-allocation modal shows a hardcoded `const currentValue = 10; // Placeholder`
    (`character-progression.js:299`) instead of the character's real stats, and only
    offers 4 of the 6 stats (missing WIS/CHA, `character-progression.js:285-290`).
  - It never reads or sends `Character.stat_points` — the real earned/unspent ledger
    Spec 5a built (`app/models/models.py:143`, populated by `grant_xp`, spent by
    `POST /api/characters/<id>/level-up` in `app/routes/inventory_api.py:532-573`,
    which already validates allocations against it). Instead it tracks "did this
    character's level change" via `localStorage` polling
    (`character-progression.js:141-156, 164-169`) and assumes a fixed 5 points on every
    detected level-up — a guess that happens to not crash, but is disconnected from
    the real ledger and can drift (e.g. if `talent_points_per_level`/`stat_points_per_level`
    config changes, or a level-up happened while the player wasn't on the dashboard to
    "detect" it).
  - `Character.stat_points` is also not currently exposed by `GET /api/characters/<id>`
    or `GET /api/characters/state` at all — a real, small gap that must close before the
    frontend can read it honestly.

This sub-spec closes both gaps: a small, additive backend change plus a rework of
`character-progression.js` against real data, and a one-line fix to `skill-tree.js`'s
button wiring.

## Goals

1. **Backend:** `GET /api/characters/<id>` and `GET /api/characters/state` each gain
   three new read-only fields per character: `stat_points` (straight from the existing
   column), `xp_for_current_level`, and `xp_for_next_level` (both computed via
   `app/models/xp.py::xp_for_level`, using the same `progression_config()` difficulty
   mod the real leveling path already applies, so the UI's thresholds can never drift
   from what actually gates a level-up).
2. **`character-progression.js`:** XP bar reads the three new fields directly, no more
   guessed curve. Drop the `localStorage` "did level change" heuristic. Whenever
   character data is fetched, if `stat_points > 0`, show a persistent "Allocate N Stat
   Points" affordance on that character's card; clicking it opens the allocation modal.
   The modal fetches and displays the character's real current stat values for all 6
   stats, spends against the real `stat_points`, and POSTs to the existing
   `/api/characters/<id>/level-up` endpoint (no backend change needed there — it
   already validates against `ch.stat_points` server-side).
3. **Cosmetic level-up moment:** keep a lightweight "LEVEL UP!" particle/banner
   animation, but fire it opportunistically — when a periodic character-data fetch
   observes `level` increased since the last value this tab has seen for that
   character (client-tracked only for the animation trigger, not for gating whether
   allocation is possible — allocation is always available whenever `stat_points > 0`,
   independent of whether this tab "saw" the level-up happen).
4. **`skill-tree.js`:** fix the "Skill Tree" button to open the correct character's
   tree, using a `data-char-id`-based per-card button (matching the existing
   `.btn-equip-panel` pattern in `equipment.js`/`equipment-enhanced.js`) instead of the
   hardcoded `characters[0].id`.

## Non-goals
- The active-skill "cast in combat" button — already tracked separately in
  `docs/superpowers/TODO.md` under Spec 5b as a combat-UI concern, not a
  progression-sheet concern. Stays deferred.
- Any change to `grant_xp`, `level_for_xp`, or the leveling/talent-point award logic
  itself — already correct and tested (Spec 5a). This sub-spec only reads existing,
  correct server state.
- Consolidating the XP bar (on dashboard cards), stat-allocation modal, and skill-tree
  modal into one unified "character sheet" page. The current split-by-concern
  architecture (inline bar + two separate modals) already matches how the rest of this
  dashboard is organized (e.g. equipment and trading are also separate modals) — no
  reason to restructure that here.
- `skill-tree.js`'s `isSkillAvailable()` not checking `required_level` client-side
  (`skill-tree.js:261-279` checks prerequisite-skill and cost, but not level — the
  server enforces it and returns a clear error message on attempted unlock, so the
  failure mode is a rejected POST with a visible error toast, not a crash or silent
  no-op). Worth a future polish pass, not required here since the real gate (the
  server) is already correct.

## Backend change

`app/routes/inventory_api.py`, both `list_characters_state` and
`get_character_state`. Each character's response dict gains:
```python
from app.models.xp import xp_for_level
from app.services.progression import progression_config

mod = float(progression_config().get("xp_difficulty_mod", 1.0))
level = ch.level or 1
# ... inside each character's response dict:
"stat_points": ch.stat_points or 0,
"xp_for_current_level": xp_for_level(level, mod),
"xp_for_next_level": xp_for_level(level + 1, mod),
```
(`progression_config` and `xp_for_level` are already imported/used elsewhere in the
codebase — `app/services/progression.py` — so this introduces no new dependency, just
a cross-module import.)

## UI design

### XP bar (per character card, `character-progression.js`)
Replace `getXPForLevel`'s fake formula and `renderXPBar`'s call sites with direct reads:
```javascript
renderXPBar(charId, xp, xpForCurrentLevel, xpForNextLevel) {
  const currentLevelXP = xp - xpForCurrentLevel;
  const requiredXP = xpForNextLevel - xpForCurrentLevel;
  const percent = requiredXP > 0 ? Math.min(100, (currentLevelXP / requiredXP) * 100) : 100;
  // ... same fillEl/textEl/percentEl updates as today, just no fake-curve inputs
}
```
`updateXPBar(charId)` fetches `/api/characters/${charId}` and passes
`char.xp, char.xp_for_current_level, char.xp_for_next_level` straight through.

### Stat-points badge + allocation modal
On each character-data fetch, if `char.stat_points > 0`, render a small badge (e.g. a
pulsing "✦ N Stat Points" pill) on that character's card, wired to open the existing
level-up/allocation modal. The modal's `createStatAllocationRow` reads the character's
real fetched stats (`char.stats.base[stat.key]`, falling back to `10` only if truly
absent, matching the rest of the codebase's stat-default convention) instead of the
hardcoded `10`, and the stats list grows to all 6 (`str, dex, int, con, wis, cha`,
matching `level_up_character`'s `valid_keys`). `pendingStatPoints` initializes from
`char.stat_points` rather than a guessed `5`. On confirm, POST the same
`{stat_allocations}` body to the same `/api/characters/<id>/level-up` endpoint — no
endpoint contract change.

### Level-up cosmetic trigger
A small per-tab `Map<charId, lastSeenLevel>` (in-memory, not `localStorage` — no need
to persist across reloads, since the *real* gate is `stat_points`, not this) replaces
today's `localStorage` calls. When a fetch shows `char.level > lastSeenLevel.get(charId)`
(or no prior entry — first load doesn't fire the animation, avoiding a spurious
celebration on every page load), play the existing particle/banner animation, then
update the map. The animation is purely cosmetic now — closing it does not gate
allocation, since the badge/modal flow (Goal 2) is the real, durable way to spend
points.

### Skill-tree button fix
`app/templates/dashboard.html:186`'s `onclick="...openSkillTree({{ characters[0].id
... }})"` is replaced with a `data-char-id="{{ c.id }}"` attribute on each character's
"Skill Tree" button (mirroring the existing per-card `.btn-equip-panel` markup
elsewhere in the same template), and `skill-tree.js` gains an event-delegation listener
(matching `equipment.js`'s `init()` pattern) reading `data-char-id` instead of relying
on an inline `onclick` with a hardcoded id.

## Error handling
- Missing/zero `stat_points` → badge simply doesn't render (matches existing "hide
  inapplicable controls" convention from prior sub-specs).
- `xp_for_next_level <= xp_for_current_level` (shouldn't happen given the real curve,
  but guards against a future curve edge case) → bar renders at 100% rather than
  dividing by zero or going negative.
- Allocation POST failure (e.g. a race where points were spent in another tab first) →
  surface the existing error JSON via the modal's existing error-display convention
  (this codebase's prevailing pattern for this file is `console.error` + a `confirm()`/
  alert-style notice; keep consistent with that rather than introducing a new toast
  system here).

## Testing
Backend: extend the existing character-state test coverage
(`tests/test_inventory_encumbrance.py` or a dedicated progression-API test) to assert
the three new fields are present and numerically correct for a known `level`/`xp`/
`stat_points` fixture.

Frontend (manual, via `run`/`verify`, learning from the equipment-panel sub-spec where
the planned file turned out not to be the one users actually see): before writing the
implementation plan in detail, confirm in a live dashboard load which DOM elements
`character-progression.js` actually attaches to (`.operative-card`, `.stats-block`) are
present in the current `dashboard.html`, and that there is exactly one progression
script in play (no second "enhanced" variant shadowing it, unlike the equipment case).
Manual checks once implemented:
- A character with `stat_points > 0` shows the badge; allocating and confirming spends
  the real points and updates `Character.stats`.
- A character with `stat_points == 0` shows no badge.
- The XP bar's percentage matches `(xp - xp_for_current_level) / (xp_for_next_level -
  xp_for_current_level)` for a known character.
- The "Skill Tree" button on each character's card opens that character's own
  trees/skills/talent-points, not always the first character's.

## Affected files
- `app/routes/inventory_api.py` (`list_characters_state`, `get_character_state` — add
  three fields each), `tests/` (extend for the new fields).
- `app/static/js/character-progression.js` (XP bar math, stat-allocation modal, drop
  `localStorage` heuristic, add stat-points badge).
- `app/static/js/skill-tree.js` (event-delegation button wiring).
- `app/templates/dashboard.html` (skill-tree button: hardcoded id → `data-char-id`).
- No changes to `app/services/progression.py`, `app/routes/skill_api.py`, or any
  combat/extraction XP-granting code — all already correct (Spec 5a/5b).
