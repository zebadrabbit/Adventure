# Equipment Panel: Encumbrance Bar + Affix Breakdown — Design

**Date:** 2026-06-17
**Status:** Design only — not yet planned/implemented.
**Part of:** Spec 4b (UI Surfacing), fourth and final sub-spec.

## Context

Auditing `app/static/js/equipment.js` and its data source (`GET /api/characters/state`,
`app/routes/inventory_api.py`) against the last open Spec 4b item found the backend is
already fully built; only the frontend rendering is missing:

- **Encumbrance** is already computed server-side per character
  (`app/inventory/utils.py::encumbrance_state` → `{weight, capacity, status, dex_penalty,
  hard_cap_pct}`) and already included in every character-state response
  (`ch["encumbrance"]`, `inventory_api.py:276`/`355`). The equipment panel never reads it —
  `renderCharPanel` in `equipment.js` ignores `ch.encumbrance` entirely.
- **Real affixes** exist on procedural gear instances (dicts with `uid`, each carrying an
  `affixes: [{stat, val}, ...]` list — `app/loot/generator.py:322`) and are already summed
  into actual combat stats server-side (`app/loot/equip.py::gear_bonuses`, folded into
  `combat_service._derive_stats`). But the shared tooltip module
  (`app/static/js/tooltips.js::effectsText`) only checks `it.effects` (a dict, present on
  legacy `Item` rows via `_serialize_item`) and otherwise falls back to `inferEffects()` — a
  heuristic that guesses `+1 STR` for any non-bow/staff/dagger weapon, etc. Procedural
  instances' real `affixes` array is never read, so every gear-instance tooltip (bag, equip
  slots, trading, hoard — anywhere `MUDTooltips.itemHtml`/`attrForItem` is used) shows a
  fabricated guess instead of the item's actual bonus.

This sub-spec closes both gaps, entirely in the frontend — no backend changes are needed
since both data sources already exist and are already shipped in current API responses.

## Goals

1. **Encumbrance bar.** `renderCharPanel` reads `ch.encumbrance` and renders a small bar/label
   above the gear-slot column showing `weight / capacity` and a status pill
   (normal/encumbered/blocked), color-coded.
2. **Real affix tooltips.** `tooltips.js::effectsText` checks `it.affixes` (the real
   `[{stat, val}]` array) before falling back to `it.effects` or the heuristic guess. This
   fixes tooltips everywhere `MUDTooltips` is used, not just the equipment panel.
3. **Aggregate equipped-bonus summary.** A one-line summary near the top of the Equipment
   column, e.g. `"Gear bonus: +3 STR, +2 DEX"`, computed client-side in `equipment.js` by
   summing each equipped slot's `affixes` (procedural instances) or `effects` (legacy items)
   — mirroring what `app/loot/equip.py::gear_bonuses` does server-side, but read from data
   already present in the `gear` payload, so no new endpoint or backend change is needed.

## Non-goals
- No backend changes. `encumbrance_state`, gear instance `affixes`, and legacy item `effects`
  are all already correct and already shipped in `/api/characters/state` /
  `/api/characters/<id>` responses.
- Not fixing `_computed_stats` (`inventory_api.py:160`) to include procedural-instance affixes
  in the character's `stats.computed` block — that's a separate, deeper inconsistency (it
  already excludes procedural affixes from displayed computed stats, only legacy slug-based
  item effects are folded in) that's out of scope here; this sub-spec's "gear bonus" summary
  is a client-side display aggregate, not a fix to that computed-stats pipeline.
- No changes to the broken-item reduced-bonus multiplier display (`durability ==
  0 → broken_mult` from `gear_bonuses`) — out of scope; the summary will show full affix
  values as listed on the item, matching how tooltips already show durability separately.

## UI design

### Encumbrance bar
In `renderCharPanel(ch)`, above the `slots.map(...)` gear list, render:
```html
<div class="encumbrance-bar mb-2" data-status="${ch.encumbrance.status}">
  <div class="d-flex justify-content-between small">
    <span>Carry Weight</span>
    <span>${ch.encumbrance.weight.toFixed(1)} / ${ch.encumbrance.capacity.toFixed(1)}</span>
  </div>
  <div class="progress" style="height:6px;">
    <div class="progress-bar ${encClass}" style="width:${pct}%"></div>
  </div>
  ${ch.encumbrance.status !== 'normal'
    ? `<div class="small text-${encTextClass} mt-1">${statusLabel} (-${ch.encumbrance.dex_penalty} DEX)</div>`
    : ''}
</div>
```
- `pct = Math.min(100, (weight / capacity) * 100)`.
- Status → Bootstrap color: `normal` → `bg-success`/no message; `encumbered` → `bg-warning` +
  "Encumbered"; `blocked` → `bg-danger` + "Overloaded — cannot carry more".
- New CSS rules added to `app/static/css/equipment.css` (`.encumbrance-bar`, reusing Bootstrap
  `.progress`/`.progress-bar` rather than inventing new bar classes — the existing
  `.durability-bar` pattern is for item-level durability and is a different concept/scale, so
  it's not reused here, but the same "small labeled progress bar" visual language is matched).

### Real affix tooltips (`tooltips.js`)
Add affix-aware branch to `effectsText`, checked first:
```javascript
function effectsText(it) {
  if (it && Array.isArray(it.affixes) && it.affixes.length) {
    return it.affixes
      .filter(a => a && a.stat && typeof a.val === 'number')
      .map(a => formatEffect(a.stat, a.val))
      .join(' ');
  }
  if (it && it.effects && typeof it.effects === 'object' && Object.keys(it.effects).length) {
    return Object.entries(it.effects).map(([k, v]) => formatEffect(k, v)).join(' ');
  }
  return inferEffects(it).map(e => formatEffect(e.stat, e.delta)).join(' ');
}
```
`formatEffect` already rounds via template (`+${delta}`); affix `val`s can be non-integer
(e.g. `2.5`), so `formatEffect` gets a small update to format with at most 1 decimal place
when non-integer, to avoid `+2.5000001`-style float noise:
```javascript
function formatEffect(stat, delta) {
  const sign = delta >= 0 ? '+' : '';
  const num = Number.isInteger(delta) ? delta : Math.round(delta * 10) / 10;
  return `${sign}${num} ${stat.toUpperCase()}`;
}
```

### Aggregate equipped-bonus summary (`equipment.js`)
New helper, called from `renderCharPanel`:
```javascript
function gearBonusSummary(gear) {
  const totals = {};
  Object.values(gear || {}).forEach(inst => {
    if (!inst) return;
    const affixes = Array.isArray(inst.affixes) ? inst.affixes
      : (inst.effects && typeof inst.effects === 'object'
          ? Object.entries(inst.effects).map(([stat, val]) => ({ stat, val }))
          : []);
    affixes.forEach(a => {
      if (!a || !a.stat || typeof a.val !== 'number') return;
      totals[a.stat] = (totals[a.stat] || 0) + a.val;
    });
  });
  const parts = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([stat, v]) => `${v >= 0 ? '+' : ''}${Number.isInteger(v) ? v : Math.round(v * 10) / 10} ${stat.toUpperCase()}`);
  return parts.join(', ');
}
```
Rendered as `<div class="small text-info mb-2">Gear bonus: ${summary}</div>` above the
encumbrance bar, only when `summary` is non-empty (no gear equipped → omit the line entirely,
matching the existing pattern of hiding inapplicable UI rather than showing "Gear bonus: none").

## Error handling
- `ch.encumbrance` missing (e.g. an older cached response shape) → encumbrance bar section is
  skipped entirely (guard with `if (ch.encumbrance) { ... }`), rest of the panel renders
  normally.
- Malformed affix entries (missing `stat`/`val`, non-numeric `val`) are filtered out silently
  in both the tooltip and the summary — consistent with the existing tolerant style of this
  codebase's frontend JSON handling (e.g. `_serialize_gear_slot`'s defensive checks).

## Testing
No JS test runner in this repo (consistent with prior Spec 4b sub-specs). Manual verification
via the `run`/`verify` skills:
- Open the Equipment panel for a character carrying enough weight to be `encumbered` (or
  `blocked`); confirm the bar renders with the right color/status text and DEX-penalty note,
  and that an unencumbered character shows the bar in its normal/green state.
- Equip a procedural gear instance with known affixes (e.g. seed/loot a `rare` item); hover it
  in the bag list and in its equipped slot; confirm the tooltip shows the item's *real* affix
  values (cross-check against the instance JSON, e.g. via `/api/characters/<id>`), not the old
  heuristic guess.
- With at least one affix-bearing item equipped, confirm the "Gear bonus: ..." summary line
  appears above the encumbrance bar and matches the sum of equipped affixes; unequip
  everything and confirm the line disappears.
- Confirm legacy slug-based equipped items (no `affixes`, only `effects`) still show correct
  tooltips and are correctly folded into the gear-bonus summary (regression check for the
  `it.effects` fallback path).

## Affected files
- `app/static/js/equipment.js` — `renderCharPanel` (encumbrance bar + gear-bonus summary
  line), new `gearBonusSummary` helper.
- `app/static/js/tooltips.js` — `effectsText` (real-affix branch), `formatEffect` (decimal
  rounding for non-integer affix values).
- `app/static/css/equipment.css` — new `.encumbrance-bar` rules (additive only).
- No backend files; no new endpoints; no new tests beyond manual verification (no behavior
  change to any Python code path).
