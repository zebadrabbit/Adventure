# Phase 2 — Hub/Dashboard Visual Hierarchy Polish — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
Phase 2 of 5.

## Context

Phase 1 (merged) introduced the "Cold Steel" palette as a consolidated `--ui-*`
variable namespace, with `--dungeon-*`/`--adv-*` kept as aliases so existing CSS
didn't need call-site changes. Live verification (screenshots) confirmed the
dashboard already inherits Cold Steel correctly for borders, text, and button
colors, since most of `dashboard.css` is a generic glassmorphism overlay built on
`var(--adv-primary)`/`var(--adv-secondary)`.

Two real gaps remain, both discovered during this brainstorming session:

1. **Dead code**: `dashboard.css:4-12` redefines `--mud-orange`/`--mud-grey`/
   `--mud-purple`/`--mud-dark`/`--mud-olive`/`--mud-bg`/`--mud-bg-dark` — a
   duplicate of `base.css`'s own (separately dead) copy of the same variables.
   `grep` across every template and JS file confirms zero consumers of any
   `--mud-*` variable or a `.mud-dark`-style class. Pure leftover, safe to delete.
2. **Embedded color literals**: `theme.css`'s component-specific rules for
   `.operative-card`, `.operative-header`, `.panel-header .badge`, and
   `.stat-block` (the exact selectors `dashboard.html` uses for character cards
   and panels) still hardcode old amber/brown `rgba()` literals — e.g.
   `rgba(212, 165, 116, 0.15)`, `rgba(26, 21, 18, 0.95)` — instead of referencing
   the new namespace. Phase 1 only touched `:root` variable *definitions* and
   `font-family` declarations; it didn't sweep embedded literals inside
   component rules. 48 such literals exist in `theme.css` (confirmed via grep on
   the 6 old RGB triples: `rgb(13,10,10)`, `rgb(26,21,18)`, `rgb(18,15,13)`,
   `rgb(61,50,38)`, `rgb(40,33,26)`, `rgb(212,165,116)`). These produce faint but
   real amber-tinted glows/gradients on hover states and card backgrounds that
   contradict Cold Steel's intent, even though the visible borders/text/buttons
   already look correct.

The user explicitly scoped this phase to **visual hierarchy polish only**: no
layout/zone restructuring, no new icons, no template markup changes. Deeper
layout work (Dark-and-Darker/Arc-Raiders-style zoned hub) is deferred to a later
pass per the user's "we can do the deeper stuff later."

## Goals

1. Delete the dead `--mud-*` block from `dashboard.css`.
2. Replace `theme.css`'s embedded amber/brown `rgba()` literals (the 6 RGB
   triples above, in the `.operative-card`/`.operative-header`/`.panel-header`/
   `.stat-block`/`.panel-body`-adjacent rules) with `color-mix(in srgb, var(--x)
   N%, transparent)` expressions referencing the existing `--dungeon-*` aliases —
   preserving each rule's original alpha value, just swapping the color source.
   This matches the `color-mix()` pattern already used elsewhere in this codebase
   (`app.css`, `glass-theme.css`), so it's not a new technique.
3. Visual hierarchy improvements on the same selectors: stronger spacing/weight
   distinction between primary actions (Enter Dungeon, Hire Adventurer — already
   visually prominent via `.deploy-btn`'s full-width teal-to-elevated gradient)
   and secondary ones (`.tactical-btn-secondary`), tighter `.stat-grid` spacing,
   and slightly stronger visual separation between `.panel-header` and
   `.panel-body` (e.g. a touch more contrast in the header background via the
   same `color-mix()` approach, not a new color).

## Non-goals

- Restructuring `dashboard.html`'s zones (roster/merchants/hoard/skills) — that's
  a future, larger layout-rework pass, explicitly deferred.
- New iconography.
- Folding `skill-tree.js`'s custom `.active`-class modal onto the Bootstrap
  `Modal` API — the roadmap originally listed this under Phase 2, but given the
  quota-driven scope cut to "visual polish only" this session, it's deferred to
  whenever Phase 2's layout-rework follow-up happens (it's a JS interaction-
  pattern change, not a visual one, so it doesn't block this phase's goal).
- Touching the per-class badge colors (`.fighter-badge`, `.rogue-badge`,
  `.mage-badge`, `.cleric-badge`, `.ranger-badge`, `.druid-badge`) — these are
  intentionally varied class-identity colors, not part of the Cold Steel neutral
  palette, and were correctly left alone by Phase 1 too.
- Touching `tactical-theme.css`'s or `glass-theme.css`'s own embedded literals —
  out of scope for the dashboard-focused selectors this phase targets; a
  candidate for the later CSS-consolidation cleanup phase already noted in
  Phase 1's TODO follow-up.

## Implementation approach

`theme.css`'s 48 embedded-literal occurrences map to exactly 6 distinct old RGB
triples, each corresponding to one existing `--dungeon-*` alias:

| Old RGB literal | Maps to alias | Resolves to (Cold Steel) |
|---|---|---|
| `rgb(13, 10, 10)` | `var(--dungeon-bg)` | `#0c0e12` |
| `rgb(26, 21, 18)` | `var(--dungeon-panel)` | `#1b1f27` |
| `rgb(18, 15, 13)` | `var(--dungeon-bg)` (closest existing alias; this triple was a panel/bg blend in the old palette with no exact Cold Steel analog) | `#0c0e12` |
| `rgb(61, 50, 38)` | `var(--dungeon-border)` | `#2e3440` |
| `rgb(40, 33, 26)` | `var(--dungeon-panel)` (closest existing alias; gradient "to" stop) | `#1b1f27` |
| `rgb(212, 165, 116)` | `var(--dungeon-accent)` | `#5ad1c9` |

Each occurrence becomes `color-mix(in srgb, var(--dungeon-X) N%, transparent)`
where `N` is the literal's original alpha × 100 (e.g. `rgba(212, 165, 116, 0.15)`
→ `color-mix(in srgb, var(--dungeon-accent) 15%, transparent)`). This is a
mechanical, alpha-preserving transformation — no new visual values are invented,
only the color source changes from a hardcoded old-palette literal to the
existing alias (which already resolves to Cold Steel via Phase 1).

For the two ambiguous triples (`rgb(18, 15, 13)`, `rgb(40, 33, 26)`) that don't
have an exact one-to-one alias, the mapping above picks the closest existing
alias by visual role (background-adjacent vs. panel-adjacent) rather than
introducing a 7th/8th alias for a one-off shade — consistent with Phase 1's
"don't expand the namespace beyond what's needed" precedent.

## Hierarchy polish details

- `.stat-grid` (theme.css): reduce `gap` slightly and tighten cell padding for a
  denser, more deliberate grid (currently `gap: 8px`, cell `padding: 6px` —
  proposed `gap: 6px`, cell `padding: 8px 6px` for better vertical rhythm without
  changing the grid's column count or markup).
- `.panel-header` vs `.panel-body`: increase the header's `color-mix()` opacity
  one step (e.g. from the post-fix equivalent of today's `rgba(61,50,38,0.3)` to
  ~`35%`) so headers read as a distinct band rather than blending into the body.
- `.tactical-btn-secondary` vs `.deploy-btn`/`.select-operative`: no color
  changes (already correctly differentiated — solid teal-gradient primary vs.
  faint-bordered secondary) — confirm via screenshot that this contrast still
  reads clearly once the embedded-literal fix lands, since `.tactical-btn-
  secondary` also uses `rgba(61, 50, 38, 0.4)` for its background and is one of
  the 48 occurrences being converted.

## Error handling

None applicable — this is a pure CSS change with no runtime logic, no new
failure modes. `color-mix()` is supported in all browsers this codebase already
depends on (confirmed in use today in `app.css`/`glass-theme.css`).

## Testing

No automated CSS test suite exists in this repo (consistent with Phase 1).
Verification is visual: load `/dashboard` and confirm character cards, panel
headers, and the stat grid show only teal/charcoal tones with zero amber/brown
tint anywhere (including hover/selected states, which is where the embedded
literals were most likely to leak through), and that primary/secondary button
contrast still reads clearly. No backend changes, so the existing pytest suite
should remain unaffected — run it once at the end to confirm.

## Affected files

- `app/static/css/dashboard.css` — delete the dead `--mud-*` block (lines 4-12).
- `app/static/css/theme.css` — convert the 48 embedded `rgba()` literals (6 RGB
  triples) to `color-mix()` expressions per the mapping table; tighten
  `.stat-grid` spacing; bump `.panel-header`'s `color-mix()` opacity one step.
- No template, JS, or backend changes.
