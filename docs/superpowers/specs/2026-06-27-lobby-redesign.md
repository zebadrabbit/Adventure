# Lobby Redesign — Design Spec

**Goal:** Replace the current stacked-row dashboard with a full-width Dark & Darker–style tabbed lobby. One horizontal nav bar, one full-content pane, a glowing center Dungeon tab as the focal point.

**Reference:** Dark and Darker lobby — horizontal top nav, atmospheric full-width content area, obvious "READY" action bottom-left.

**Constraints:** Keep the existing tactical dark theme and color palette. No new dependencies. Lightweight HTML/CSS/JS — graphics slots left empty for future art.

---

## Tab Bar

Single dark horizontal strip across the top of the main content area (below the existing site header/HUD). Seven tabs, evenly spaced:

```
PARTY  |  BARRACKS  |  RECRUIT  |  ⚔ DUNGEON ⚔  |  MERCHANTS  |  HOARD  |  ACHIEVEMENTS
```

- All tabs share the existing `nav-link` / tactical theme style.
- **DUNGEON tab** is visually distinguished: amber/gold accent color, slightly larger label, subtle glow — the obvious focal point. It sits center (index 4 of 7).
- Active tab gets the existing underline treatment scaled to page-nav size.
- Default active tab on page load: **PARTY**.
- Tab state persists in `sessionStorage` so a page reload returns to the same tab.
- The existing site HUD (top-right) and alert banners remain above the tab bar.

---

## PARTY Tab

Four equal-width character slots in a single row (`col-3` each).

**Filled slot:** The existing `operative-card` component, unchanged. Expand/collapse behavior stays. Footer gains a **REMOVE** button that clears that party slot (doesn't delete the character — returns them to barracks).

**Empty slot:** Dashed border card, same height as a collapsed operative card. Centered `+` icon, label "ADD ADVENTURER", clicking switches to the BARRACKS tab.

**Below the slots — action bar:**
- Left: compact party composition summary (e.g. `Fighter · Rogue · — · —`).
- Right: two buttons — **AUTO-FILL** (existing logic, fills empty slots from barracks) and **⚔ ENTER DUNGEON →** (switches to Dungeon tab; disabled if party is empty).

**On Party tab load (server-side or JS):** All party characters are healed to full HP and gear durability restored. Free for now — no gold cost, no animation. This replaces the old "heal on dungeon enter" assumption.

**Party limit:** 1–4 characters. The existing 1–4 validation on the server stays.

---

## BARRACKS Tab

Full-width grid of all owned characters (max 15). Shows all owned characters. Party members display an "IN PARTY" badge and are not selectable (they're already assigned). Non-party characters are selectable for adding to open slots.

**Sort controls** (top-right of pane): three buttons — **CLASS**, **LEVEL**, **NAME** — toggle sort. Default: level descending.

**Each card:** compact version of the operative card — name, class badge, level, HP bar. Clicking a card selects it (highlight border). Multi-select supported.

**Footer action bar:**
- Left: `N / 15 ADVENTURERS` count.
- Right: **ADD TO PARTY** button (enabled when 1+ non-party characters selected and party has open slots). Adds selected characters to party, switches to Party tab.
- If barracks < 15: **RECRUIT MORE →** button switches to Recruit tab.

**Delete character:** each card has a small trash icon (existing delete route). Confirm dialog before delete.

---

## RECRUIT Tab

Only accessible when barracks count < 15. If at 15, shows a "Barracks full (15/15)" message with a link to Barracks.

**Main area:** Four candidate cards side by side. Each is a procedurally generated level-1 character — name, class, full stats, starter gear — generated fresh each time the tab is opened (not saved to DB yet).

**Candidate card shows:**
- Name, class icon, class badge
- Stats block (str/dex/con/int/wis/cha)
- Starter gear list (item names)
- **2 free stat points** — `+` / `−` buttons next to any stat, max 2 total distributed across all stats. A small "STAT POINTS: 2 remaining" counter at the card bottom.
- **HIRE** button — saves that character to DB (calls existing character creation logic), switches to Barracks tab, card slot goes blank.

**REROLL ALL** button top-right: generates 4 new candidates (replaces all 4, resets any stat tweaks). No limit on rerolls.

**Generation:** Reuses `handle_autofill` logic extracted into a pure generator function that returns unsaved `Character`-like dicts without hitting the DB. On HIRE, one POST to a new `/api/recruit/hire` endpoint that saves the chosen candidate with the stat tweaks applied.

---

## ⚔ DUNGEON Tab

The "Ready room." Final check before entering.

**Layout:**
- **Top half:** Compact 4-slot party overview — one row, each slot shows name + class + level + HP bar (no expand/collapse here, read-only). Empty slots shown as dashed placeholders with "— EMPTY —".
- **Quick checks block** (below the slots): small status indicators —
  - `✓ Party assembled (N/4)` — green if ≥ 1, amber if < 4
  - `✓ All members alive` — red if any character is at 0 HP
  - (Future: gear check, etc.)
- **Center:** Seed widget (existing component, unchanged).
- **Bottom-left:** Big **⚔ ENTER DUNGEON** button (existing form POST). Disabled if party empty or any member dead. Same styling as current `deploy-btn`.
- **Bottom-right:** CONTINUE QUEST button (shown only if an active dungeon instance exists — same session logic as today).
- **Page subtitle** moves here: "Gather your party // Equip adventurers // Embark on quest"

---

## MERCHANTS Tab

Same three merchant buttons as today, but laid out as three equal cards rather than stacked buttons. Each card: merchant name, flavor description (one line), **OPEN** button. Uses existing `tradingSystem.openMerchant()`.

Merchants: General Store, The Apothecary, Dungeon Outfitter.

---

## HOARD Tab

Existing hoard panel / global inventory UI, dropped in as-is. The "Open Hoard" button stays. No changes to hoard logic.

---

## ACHIEVEMENTS Tab

Existing achievement system UI, dropped in as-is. Uses existing `achievementSystem.openAchievements()`.

---

## New Backend Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/recruit/candidates` | Returns 4 procedurally generated candidate dicts (not saved). Uses existing name/stat/gear generation logic. |
| `POST` | `/api/recruit/hire` | Accepts one candidate dict + stat tweak deltas, validates, saves character to DB. Returns new character id. |
| `POST` | `/api/party/remove/<char_id>` | Removes a character from the active party session without deleting them. |

Existing endpoints for party assembly (the `start_adventure` POST form), delete character, autofill, and dungeon entry remain unchanged.

---

## Files Changed

| File | Change |
|------|--------|
| `app/templates/dashboard.html` | Full restructure: add tab nav, restructure content into 7 tab panes |
| `app/templates/macros/seed_widget.html` | No change |
| `app/routes/dashboard.py` | Add recruit and party-remove routes |
| `app/routes/dashboard_helpers.py` | Extract pure candidate generator from `handle_autofill` |
| `app/static/js/dashboard.js` | Tab state persistence (sessionStorage), party slot interactions |
| `app/static/js/dashboard-recruit.js` | New: candidate display, stat tweak UI, hire action |
| `app/static/css/dashboard.css` | Tab bar styles, slot card styles, dungeon tab highlight |

JS files for existing systems (party-management.js, achievement-system.js, trading-system.js, hoard.js) are **not changed** — they are invoked from the new tab panes the same way as today.

---

## Out of Scope

- Character portraits / art assets (placeholder cards only)
- Gold cost for healing / durability repair
- Recruit reroll limits or cooldowns
- Leaderboard, trade, or social tabs
- Any changes to dungeon, combat, or loot logic
