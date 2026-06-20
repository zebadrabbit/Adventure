# Dashboard Hub Layout & Flow — Design

**Date:** 2026-06-20
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
picking up the "zone restructuring" work Phase 2 explicitly deferred
(`docs/superpowers/specs/2026-06-19-phase2-hub-visual-hierarchy-design.md`).

## Context

Phase 2 (merged) fixed `dashboard.html`'s embedded color literals and gave the
existing cards (`Recruit New Adventurer`, `Party Roster`, operative cards) a
consistent Cold Steel visual treatment, but explicitly left the page's
*structure* untouched: "Restructuring `dashboard.html`'s zones (roster/
merchants/hoard/skills) — that's a future, larger layout-rework pass,
explicitly deferred."

That gap is now the user's direct complaint: "dashboard location of items,
redesign the layout to flow better." Inspecting `dashboard.html` (~lines
89–197) confirms the problem precisely — the **Party Roster** card's `<form
id="begin-adventure-form">` contains, in order: the party slot grid, the
deploy/continue buttons, the dungeon seed widget, and then four unrelated
button groups stacked vertically beneath all of that: Merchants, Hoard, Party
Management, and Achievements. These are core hub actions (visiting shops,
checking your hoard, managing the party, viewing achievements) but they read
as an afterthought tacked onto the bottom of an unrelated card, requiring a
scroll past the deploy button to find them. They're also nested inside a
`<form>` that exists for the "Enter Dungeon" submit, even though none of the
four button groups submit that form — purely incidental, fragile nesting.

## Goals

1. **Slim the Party Roster card down to its actual job**: party slot grid,
   deploy/continue buttons, dungeon seed widget. Remove the Merchants/Hoard/
   Party-Management/Achievements button groups from inside it.
2. **Give those four actions their own zone**: a new full-width "Hub Actions"
   panel, placed directly below the Recruit/Roster row and above the
   "Available Adventurers" section divider. It uses Bootstrap nav-tabs (one
   tab per action group: Merchants, Hoard, Party, Achievements), each tab
   showing that group's existing buttons unchanged.
3. **Visual polish on the affected cards**: the new Hub Actions panel gets the
   same `panel-header`/`panel-body` Cold Steel treatment as every other
   dashboard card; its tabs are styled consistently with the existing
   `.chat-header .nav-tabs` Cold Steel tab treatment already in
   `dashboard.css` (same accent/active-state colors, not a new palette). The
   Recruit and Party Roster cards get a tighter spacing pass now that they're
   no longer artificially tall from the removed content.

## Non-goals

- The "Available Adventurers" operative cards (character cards) below the
  divider — untouched, already covered by Phase 2's visual hierarchy pass.
- New iconography — reuses existing `svg_icon()` calls and Bootstrap Icons
  already used by each button.
- Changes to merchant/hoard/party-management/achievement *modal* internals or
  their JS (`tradingSystem`, `partySystem`, `achievementSystem`) — only where
  their entry-point buttons live on the page, not what they open or how.
- The dungeon seed widget's own internals — it stays inside the Party Roster
  card, unchanged, since it's tied to the deploy action.
- The game-clock widget (`#dashboard-time-tick`) — already flagged in
  `docs/superpowers/TODO.md` as purely cosmetic/optional; not part of this
  pass.

## Architecture

**Markup change (`app/templates/dashboard.html`):**

- Inside the Party Roster card's `<form id="begin-adventure-form">`, delete
  the four `<!-- Merchants -->`, `<!-- Hoard -->`, `<!-- Party Management -->`,
  `<!-- Achievements -->` blocks (current lines ~132–192). The seed widget
  block immediately above them stays.
- Immediately after the closing `</div>` of the Recruit/Roster `row` (current
  line 198) and before the `<!-- Section Divider -->` (current line 200),
  insert a new full-width row containing one `tactical-panel` card:
  - `panel-header`: a title (e.g. "HUB" with a relevant icon) — no badge
    needed (unlike Party Roster's `X / 4 READY` badge, there's no single
    count to show here).
  - `panel-body`: a Bootstrap `nav-tabs` element with four tabs (`Merchants`,
    `Hoard`, `Party`, `Achievements`) and four corresponding `tab-pane` divs,
    each containing that action group's button markup, moved verbatim from
    where it used to live (same `onclick`/button classes/icons — only the
    surrounding wrapper changes, not the buttons themselves).
  - Each button group keeps its existing `subtitle` line (e.g. "MERCHANTS")
    as the tab-pane's heading, or the tab label can replace it — decided at
    implementation time by whichever reads cleaner once both are visible
    together (tab label + redundant subtitle inside the pane would be
    visual clutter); default to **dropping the in-pane subtitle** since the
    tab label already names the section.
  - Bootstrap's native `data-bs-toggle="tab"` / `data-bs-target` attributes
    drive tab switching — no custom JS, consistent with the rest of the
    codebase's Bootstrap-first approach.

**CSS change (`app/static/css/dashboard.css`):**

- Add a new rule block (scoped to a class like `.hub-actions-panel .nav-tabs`
  and `.hub-actions-panel .nav-link`/`.nav-link.active`) mirroring the
  existing `.chat-header .nav-tabs` / `.chat-header .nav-link` / `.chat-header
  .nav-link.active` color values (lines ~147–164) — same `color-mix()` /
  `var(--ui-*)` references, not new literals.
- Minor spacing tightening on `.party-counter`, `.deployment-panel`, and/or
  the Recruit card's form spacing — exact values decided during
  implementation by comparing before/after screenshots, not pre-specified
  here (this is the "polish" half of the pass, inherently iterative).

**No JS changes**: `tradingSystem.openMerchant(...)`, `partySystem.openParty(...)`,
`achievementSystem.openAchievements(...)`, and the hoard-open button's existing
click handler are all called via the same `onclick`/class-based wiring as
today — moving their container markup doesn't change how they're invoked.

**No backend changes**: this is template + CSS only.

## Testing

This is a template/CSS-only change with no Python logic touched, so there are
no new automated (pytest) tests to write — consistent with how the earlier
mana-bar-visibility fix in this same session was verified. Verification is
manual, via the `run` skill: start the dev server, log in, load `/dashboard`,
and confirm:

- The Party Roster card no longer shows Merchants/Hoard/Party/Achievements
  buttons below the deploy button.
- The new Hub Actions panel appears below the Recruit/Roster row, with four
  working tabs.
- Clicking each tab's buttons still opens the correct existing modal/system
  (`tradingSystem`, `partySystem`, `achievementSystem`, hoard) — behavior
  unchanged, only relocated.
- No console errors, no visual regression on the Recruit/Roster cards or the
  Available Adventurers section below.
