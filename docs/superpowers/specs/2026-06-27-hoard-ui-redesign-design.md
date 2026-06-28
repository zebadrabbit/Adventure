# Hoard UI Redesign — Design Spec
**Date:** 2026-06-27
**Status:** Approved

---

## Overview

Replace the current minimal hoard tab (a single "View Hoard" placeholder) with a
full-featured three-panel inventory management screen. Players can browse their vault,
select any character to view their bag alongside it, and move items or currency between
the two via drag-and-drop and tier-input controls.

---

## Layout

Bootstrap 12-column grid inside `#lobby-hoard`. Three logical zones:

```
| [A] col-1  | [B] col-4 (slides in) | [C] col-7 → col-11 |
| char strip | char detail           | hoard               |
```

**Collapsed state** (no character selected):
- `col-1` — character strip (A)
- `col-11` — hoard panel (C); (B) is hidden, zero-width

**Expanded state** (character selected):
- `col-1` — character strip (A)
- `col-4` — character detail panel (B)
- `col-7` — hoard panel (C)

The column swap is driven by toggling Bootstrap `col-*` classes and a CSS width
transition on panel B (`transition: all 0.2s ease`). No JS animation library needed.

---

## Panel A — Character Strip (`col-1`)

A vertical stack of circular avatar buttons, one per owned character (all characters,
not just the active party). Each button:

- **Background colour:** class CSS variable (e.g. `var(--class-fighter-bg)`)
- **Border:** `var(--class-fighter-border)` — provides the visual delineation
- **Label:** first letter of the character's name, uppercase, bold
- **Tooltip** (`title` attribute): `"Name — Class Lv N"`
- **Active ring:** `box-shadow: 0 0 0 2px var(--adv-primary)` on the selected character
- Clicking a character that is already selected collapses panel B and returns to col-11
  hoard layout

---

## Panel B — Character Detail (`col-4`, slide-in)

Shown when a character is selected. Contains:

### Currency row
```
<< [00]g [00]s [00]c >>
```
- `<<` button — **Withdraw**: move the entered amount from hoard copper to this
  character's stats JSON coins. Validates hoard has sufficient copper. Shows a small
  toast: _"Withdrew Xg Ys Zc from hoard"_ / _"Not enough in hoard"_.
- `>>` button — **Deposit**: move the entered amount from character stats coins to hoard
  copper. Validates character has sufficient coins. Shows toast: _"Deposited Xg Ys Zc
  to hoard"_ / _"Not enough on character"_.
- Three `<input type="number" min="0">` fields, one per tier (g / s / c). 2-char wide.
- On withdraw/deposit, both panels (hoard copper and character coins) refresh in-place.

### Item list
- Scrollable list of the character's current bag items (from `/api/characters/<id>`
  `bag` array).
- Each row: item name, type tag, quantity badge (if stackable).
- Rows are **drag sources** targeting the hoard item list.
- Hoard items are **drag targets** for character bag rows (see Drag & Drop section).

---

## Panel C — Hoard Panel (`col-11` / `col-7`)

### Header
- Hoard copper balance display (formatted, e.g. `12g 5s`).
- Brief label: `VAULT`.

### Item list
- Scrollable list of hoard items (from `/api/hoard` `items` array).
- Each row: item name, type tag, quantity badge, durability bar (if applicable).
- Rows are **drag sources** targeting the character item list.
- Character bag rows are **drag targets** for hoard item rows.
- Existing withdraw button (single-click move to selected character) remains as a
  fallback for users who don't want drag-and-drop.

---

## Drag & Drop

Uses the native HTML5 Drag and Drop API — no library.

**Hoard → Character:**
- `dragstart` on a hoard item row: store `{source: "hoard", slug, uid, qty}` in
  `event.dataTransfer`.
- `dragover` / `drop` on character bag list: call `POST /api/hoard/withdraw` with
  `{character_id, slug|uid}`. Refresh both lists on success. Toast: _"Moved [item] to
  [name]"_.

**Character → Hoard:**
- `dragstart` on a character bag row: store `{source: "character", char_id, slug, uid,
  qty}`.
- `dragover` / `drop` on hoard list: call new `POST /api/hoard/deposit-item`
  `{character_id, slug|uid}`. Refresh both lists on success. Toast: _"Stored [item] in
  hoard"_.

Drop targets get a `.drag-over` highlight class on `dragenter`, removed on `dragleave`
/ `drop`.

---

## New API Endpoints

### `POST /api/hoard/deposit-item`
Move one item from a character's bag into the hoard.

**Request:** `{character_id: int, slug?: str, uid?: str}`
**Response:** `{success: true, hoard_items: [...], char_bag: [...]}`

### `POST /api/hoard/currency`
Deposit or withdraw copper between a character and the hoard.

**Request:** `{character_id: int, direction: "deposit"|"withdraw", gold: int, silver:
int, copper: int}`

Converts tier inputs to total copper. Validates balance on the source side. Updates
character stats JSON and `hoard.copper`. Returns updated balances for both sides.

**Response:**
```json
{
  "success": true,
  "hoard_copper": 12050,
  "hoard_copper_display": "1g 20s 50c",
  "char_gold": 2, "char_silver": 0, "char_copper": 0,
  "char_display": "2g"
}
```

---

## State & Data Flow

On **tab open** (`shown.bs.tab` → `#lobby-hoard`):
1. `GET /api/hoard` — populate hoard panel.
2. `GET /api/characters/state` — populate character strip (names, classes).
3. No character selected; hoard fills full width.

On **character strip click**:
1. If same character: collapse panel B, restore col-11 hoard.
2. Else: `GET /api/characters/<id>` — populate panel B bag + coins. Apply col layout
   switch.

On **any transfer** (drag-drop or currency button):
- Re-fetch only the affected sides (hoard items if hoard changed; character bag/coins if
  character changed). No full page reload.

---

## CSS / JS Files

- **New CSS:** `app/static/css/hoard-ui.css` — hoard panel layout, char strip avatars,
  drag-over states, currency row inputs.
- **Rewrite:** `app/static/js/hoard.js` — replace current modal-render approach with
  the three-panel manager described above. Class stays as an IIFE (matches current
  style).
- **Template:** `app/templates/dashboard.html` `#lobby-hoard` pane gets the three-column
  scaffold (server-rendered character list via Jinja; hoard content rendered by JS on
  tab open).

---

## Out of Scope

- Stack splitting (moving partial quantity of a stackable — always move the full stack).
- Drag between two character bags (character → character).
- Mobile touch drag (native HTML5 drag doesn't fire touch events; accepted limitation).
