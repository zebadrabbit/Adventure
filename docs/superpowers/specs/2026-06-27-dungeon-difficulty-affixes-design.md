# Dungeon Difficulty & Affix System — Design Spec
**Date:** 2026-06-27
**Status:** Approved

---

## Overview

Scaffold the dungeon configuration screen so players can opt-in to difficulty tiers
(Normal / Heroic / Mythic) and stackable affixes before entering a run. The two systems
are fully independent and combinable. Together they produce a **Threat Rating** shown as
an edgy named tier. Affix/difficulty combos unlock achievements. Combat and loot already
read from `DungeonInstance.tier` and `DungeonInstance.affix_ids` — this spec wires up
the UI and the missing model fields; gameplay effects follow in a later pass.

---

## Difficulty Tiers

Three named tiers map onto the existing `DungeonTier` table (T1–T3 initially; T4–T7
reserved for future portal/challenge content):

| UI Name | Tier | Monster level modifier | XP multiplier | Loot bonus |
|---------|------|----------------------|---------------|------------|
| Normal  | 1    | +0                   | ×1.0          | +0%        |
| Heroic  | 2    | +1                   | ×1.5          | +15%       |
| Mythic  | 3    | +2                   | ×2.0          | +30%       |

These rows are seeded by `python run.py seed-dungeon-tiers` (idempotent). The existing
`monster_level_modifier`, `xp_multiplier`, and `loot_quality_bonus` columns cover all
three — no schema change needed for the tier table.

Default on session start: Normal (tier 1).

---

## Affixes

### Model changes — `DungeonAffix`

Three new columns added via Alembic migration:

```
monster_count_multiplier  Float   default 1.0   -- e.g. 1.2 = 20% more spawns
xp_multiplier             Float   default 1.0   -- e.g. 1.1 = 10% bonus XP
threat_weight             Integer default 1     -- contribution to Threat Rating score
```

The existing `monster_hp_multiplier`, `monster_damage_multiplier`, and `special_effect`
JSON handle all other combat modifiers. `reward_multiplier` for loot can live in
`special_effect` until it needs its own column.

### Starter affix pool (seeded)

A focused set of affixes to launch with — enough for variety, small enough to balance
properly. More added over time.

| affix_id        | Name          | Effect | Threat |
|-----------------|---------------|--------|--------|
| `swarming`      | Swarming      | +20% more monsters, +10% XP | 2 |
| `bulwark`       | Bulwark       | Monsters have +30% HP | 2 |
| `savage`        | Savage        | Monsters deal +20% damage | 2 |
| `thinned`       | Thinned Ranks | −10% monsters, monsters +10% stronger | 1 |
| `bloodthirsty`  | Bloodthirsty  | Monsters regen 2% HP/round | 3 |
| `cursed`        | Cursed        | Players take +15% damage | 3 |
| `gilded`        | Gilded        | +15% XP, −10% loot quality | 1 |
| `fortified`     | Fortified     | Bosses have +50% HP | 2 |

No cap on how many affixes can be stacked. Balance is intentionally the player's problem.

---

## Threat Rating

The Threat Rating score = `sum(affix.threat_weight for selected affixes)` +
`(tier - 1) * 2` (Heroic adds 2, Mythic adds 4).

Named tiers (internal score → display name):

| Score | Name |
|-------|------|
| 0 | Calm |
| 1–2 | Troubled |
| 3–5 | Dire |
| 6–9 | Harrowing |
| 10–14 | Catastrophic |
| 15+ | Doomed |

Exact names are a display-layer constant in JS (`hoard.js` pattern — a simple lookup
table). Can be changed without a deploy by editing one JS constant. Score is always
available on `DungeonInstance` for backend logic (daily quest gating, achievement checks).

---

## Dungeon Screen UI

The existing dungeon briefing tab gains two new sections between the party overview and
the seed widget:

### 1. Difficulty selector
Three buttons: `[ NORMAL ] [ HEROIC ] [ MYTHIC ]`. Active button gets the primary
colour highlight. Selecting one updates session state via `POST /api/dungeon/config`
(see API section). Heroic and Mythic show a brief note: *"+1 monster level, ×1.5 XP"*.

### 2. Affix picker
A grid of affix cards (one per available affix). Each card shows:
- Affix name (coloured per `DungeonAffix.color`)
- One-line effect description
- Threat weight badge (e.g. `⚠ 2`)
- Toggle state (selected = highlighted border + checkmark)

Clicking toggles selection. Selected affixes are stored client-side in a JS array and
sent with the dungeon start request. No server round-trip per toggle — only on start.

### 3. Updated checklist rows

Existing checklist gains two new items below the alive check:

```
✓ Difficulty: Normal                (or Heroic / Mythic)
— No affixes selected               (or: ⚠ Swarming, Cursed  [Threat: Harrowing])
```

Threat Rating name appears inline when any affix is selected or difficulty > Normal.

### 4. Enter Dungeon button

The existing form POST `{form: start_adventure, party_ids[]}` gains two new hidden
fields: `difficulty_tier` (int) and `affix_ids` (JSON array). The dashboard route reads
these when creating the `DungeonInstance`.

---

## Session / Config State

Difficulty and affix selections are **not** persisted between sessions — they default
to Normal / no affixes each page load. This is intentional: players configure each run
explicitly. No new DB table needed for pre-run config.

The JS on the dungeon tab maintains a local state object:
```js
const runConfig = { tier: 1, affixes: [] };
```
Updated on button/card clicks, read on form submit.

---

## API

### `GET /api/dungeon/affixes`
Returns all active affixes from `DungeonAffix` table. Called once on dungeon tab open
to populate the affix picker. Response:
```json
[{"affix_id": "swarming", "name": "Swarming", "description": "...", "threat_weight": 2, "color": "#e74c3c"}]
```

### `POST /api/dungeon/start` (modification to existing start flow)
The existing `start_adventure` form handler in `dashboard.py` reads two new form fields:
- `difficulty_tier` (int, default 1)
- `affix_ids` (JSON string, default `"[]"`)

Sets `instance.tier` and `instance.set_affixes(...)` on the new `DungeonInstance`.
Validates tier is 1–3; silently clamps unknown affix_ids to known ones.

No new endpoint — the existing POST form handler is extended.

---

## Achievements

The achievement system already exists. New achievement triggers added to the dungeon
completion path:

**Difficulty milestones:**
- First Heroic run completed
- First Mythic run completed

**Affix milestones:**
- First run with any affix
- First run with 3+ affixes simultaneously
- Reach Threat Rating "Harrowing" (score 6+)
- Reach Threat Rating "Doomed" (score 15+)

**Combo achievements:**
- Complete a Mythic run with 2+ affixes
- Complete a run with `cursed` + `savage` active ("Death Wish")
- Complete a run with `gilded` + `swarming` active ("Gold Rush")

Achievement check fires in `extraction_service.py` on successful extract (same place
XP is granted), passing `{tier, affix_ids, threat_score}` as event data.

These achievement records are seeded via `python run.py seed-achievements` (existing
pattern).

---

## Out of Scope (Future)

- Portal difficulty (T4–T7 tiers)
- Weekly quests gated by minimum Threat Rating
- Per-affix loot table modifications (uses `special_effect` JSON as placeholder)
- Negative affixes (randomly assigned curses the dungeon imposes)
- Affix synergy bonuses (two specific affixes together grant an extra effect)
- Affix unlock progression (all affixes available from the start for now)
