# Hoard / Stash Screen — Design

**Date:** 2026-06-17
**Status:** Design only — not yet planned/implemented.
**Part of:** Spec 4b (UI Surfacing), second of several smaller sub-specs (follows the
trading hoard-repoint + repair tab work).

## Context

The per-user Hoard (persistent vault: copper + items, separate from any one character's
at-risk run-purse/bag) has had a read/withdraw API since Spec 2 (`GET /api/hoard`,
`POST /api/hoard/withdraw`) but no frontend surface at all. Players currently have no way
to see what's in their hoard or move it onto a character outside of the shop modal's Sell
tab (which only shows sellable items, not the full hoard, and never withdraws).

This sub-spec adds a standalone "Hoard" screen: view contents (copper + items) and withdraw
items to a chosen character. It does not add any way to *deposit* into the hoard manually —
deposits already happen automatically via extraction and buy-side trading; no manual-deposit
endpoint exists, and adding one is out of scope (would require a backend change, and no
deposit flow is in this sub-spec's brief).

There is an existing stubbed "Party Stash" button in the dungeon view (`adventure.html`,
`partyInventoryBtn`) that currently just shows a "coming soon" alert describing a
*shared-party* stash — a different, not-yet-built concept (multiple characters in one run
contributing to a shared pool). It is **not** repurposed here; this sub-spec's Hoard screen
is a new, separate entry point on the town/dashboard view, since the Hoard is a per-user
town-side vault, not an in-dungeon party mechanic. The dungeon button is left as-is for a
future, separate feature.

## Goals
1. A new "Hoard" button on `dashboard.html` (alongside the existing Merchants section)
   opens a modal showing: copper (`copper_display`), and all items — both stackable
   (slug + qty) and gear instances (uid, rarity-colored name, durability bar if applicable).
2. A single character selector at the top of the modal ("Withdraw to: [dropdown]"),
   populated from the user's characters. Each item row has a "Withdraw" button that sends
   the item to whichever character is currently selected via `POST /api/hoard/withdraw`.
3. After a successful withdraw, the item disappears from the hoard list and the existing
   equipment/bag UI (`equipment.js`) is invalidated so the destination character's bag
   reflects the new item without a manual page refresh.

## Non-goals
- Manual deposit into the hoard (no backend support; out of scope).
- The shared "Party Stash" dungeon feature (separate, unbuilt concept — not touched).
- Equipping the withdrawn item — that's already handled by the existing Equipment modal
  (`equipment.js`); this screen only moves the item into the character's bag.
- Any backend changes — `GET /api/hoard`, `POST /api/hoard/withdraw`, and
  `GET /api/characters/state` (for the character-selector list) already provide everything
  needed.

## Data sources
- `GET /api/hoard` → `{ items: [...], copper, copper_display }`, same shape already
  consumed by `trading-system.js` (stackables are `{slug, qty}`; gear instances have `uid`,
  `rarity`, `durability`, `max_durability`, `value`, etc.).
- `GET /api/characters/state` → `{ characters: [{id, name, ...}] }`, used only to populate
  the character-selector dropdown (name + id).
- `POST /api/hoard/withdraw` — `{character_id, slug}` or `{character_id, uid}` →
  `{success: true}` or `{error: "..."}` (404 if character not found/not owned, 400 if item
  not in hoard or missing fields).

## UI design

### Entry point
New section on `dashboard.html`, modeled on the existing "Merchants" button group
(`dashboard.html` around the `MERCHANTS` subtitle block): a "HOARD" subtitle with a single
button, `onclick="window.hoardSystem && hoardSystem.open()"`. No character id needed in the
trigger — the modal's own character selector handles targeting.

### Module structure
New file `app/static/js/hoard.js`, following the existing `equipment.js` IIFE-module
pattern (not the `trading-system.js` ES6-class pattern — this screen is simpler and closer
in shape to the equipment panel: a single modal, a state fetch, a re-render-on-change loop).

```javascript
(function () {
  const modalId = 'hoardModal';
  let hoardState = null;       // last GET /api/hoard response
  let characters = [];         // [{id, name}] from /api/characters/state
  let selectedCharId = null;

  function ensureModal() { /* builds #hoardModal once, like equipment.js's ensureModal */ }
  async function loadHoard() { /* fetch /api/hoard -> hoardState */ }
  async function loadCharacters() { /* fetch /api/characters/state -> characters */ }
  function renderItemRow(item) { /* one hoard item, with a Withdraw button */ }
  function render() { /* copper header + character <select> + item list */ }
  async function withdraw(opts) { /* POST /api/hoard/withdraw, then reload + re-render */ }
  async function open() { /* ensureModal, load both, render, show */ }

  window.hoardSystem = { open };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.btn-hoard-open').forEach(btn => {
      btn.addEventListener('click', open);
    });
  });
})();
```

### Modal contents
- Header: "Hoard" title + copper display (reuse the same plain-text rendering pattern as
  the shop modal's header — `copper_display` string, never a hand-rolled number).
- A `<select id="hoard-withdraw-target">` populated with `characters` (value = id, label =
  name), defaulting to the first character. Changing it just updates `selectedCharId`; no
  re-render needed since item rows don't show the target, only the button's behavior changes.
- Item list: one row per hoard item, reusing the same per-row rendering conventions
  introduced in the trading UI sub-spec — rarity-colored name + durability bar for gear
  instances (`window.MUDTooltips.rarityClass`, the `.durability-bar`/`.durability-fill`
  classes from `equipment.css`), plain name + qty badge for stackables. Each row ends with a
  "Withdraw" button.
- Empty state: "Your hoard is empty." when `items` is `[]`.
- No characters: if the user has zero characters, show "Create a character first" in place
  of the selector and disable all Withdraw buttons (withdrawing requires a destination).

### Withdraw flow
1. Click "Withdraw" on a row → `withdraw({slug, uid, characterId: selectedCharId})`.
2. POST to `/api/hoard/withdraw` with `{character_id: selectedCharId, slug}` or
   `{character_id: selectedCharId, uid}` depending on which the row has.
3. On success: re-fetch `/api/hoard` (so the row disappears / stack qty decrements), re-render
   the list, and dispatch `mud-characters-state-invalidated` (the same event `equipment.js`
   already listens for to invalidate its cache — see `equipment.js:39`) so the destination
   character's bag is correct the next time the Equipment modal opens, without needing a new
   contract between the two modules.
4. On failure (400/404): toast or inline error text in the modal body (reuse a simple
   Bootstrap alert div rather than building a new toast system — this module has no existing
   toast helper, unlike `trading-system.js`).

### Error handling
- Hoard/character fetch failure on open: show an inline error message in the modal body,
  leave the modal openable (don't block on a hard failure — mirrors `equipment.js`'s
  try/catch-and-warn pattern at `loadState`).
- Withdraw failure: inline error message near the button clicked, item stays in the list
  (no optimistic removal before the response confirms success).

## Testing
No JS test runner in this repo — manual verification via the `run`/`verify` skills with a
live browser:
- Open the Hoard screen with a hoard containing both stackables and gear instances, and at
  least two characters.
- Confirm copper renders as the 3-tier display string.
- Switch the character selector and confirm it doesn't trigger a re-render of the item list
  (just changes the target silently).
- Withdraw a stackable and a gear instance; confirm both succeed, disappear/decrement
  correctly, and that opening the Equipment modal for the destination character afterward
  shows the item in their bag without a page reload.
- Trigger a withdraw failure (e.g. stale uid after withdrawing twice quickly) and confirm the
  inline error shows without crashing the modal.
- Open with an empty hoard and confirm the empty-state message.
- Open with zero characters and confirm the disabled-selector fallback.

## Affected files
- Create: `app/static/js/hoard.js`.
- Modify: `app/templates/dashboard.html` (new "HOARD" button section, new `<script>` tag),
  `app/templates/dashboard_base.html` if a new stylesheet is added (expected not to be
  needed — reusing Bootstrap utility classes + existing `equipment.css` rarity/durability
  classes already loaded on this page).
- No backend or other template changes.
