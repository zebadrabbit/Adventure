# UI Redesign Phase 4 — Combat Cold Steel Theming — Design

**Date:** 2026-06-19
**Status:** Approved — ready for planning.
**Part of:** UI Redesign (follows Phases 1, 2, 3a-3d, 5a).

## Context

Combat (`app/templates/combat.html`) already uses the canonical Cold Steel
`.tactical-panel`/`.panel-header` classes (from `theme.css`) for its outer
panels, but `combat.css` and `combat-effects.css` layer a separate, older
"glassmorphism" skin on top — white-translucent blurred cards
(`.card-glass`, `.badge-glass`, `.progress-glass`), candy-colored buttons,
and an ANSI-style combat log with ~18 hardcoded hex/`rgba()` event colors
(red/green/yellow/cyan/magenta). This is the same class of leftover
third-palette debt that Phases 2 and 5a already swept from `theme.css` and
`home.css` — just not yet touched in combat's own stylesheets.

`combat-effects.js` additionally hardcodes its own independent copy of
generic damage-number/flash colors (heal=green, crit=gold, miss=gray,
damage=red), duplicating logic that should live in the CSS tokens.

## Goal

Recolor combat's existing visual surface onto the Cold Steel `--ui-*`
tokens (`theme.css`), using the same mechanical `color-mix()` technique
proven in Phases 2/5a. No markup changes, no class renames, no new
variables, no behavior changes — purely a recolor.

## Scope

### A. `app/static/css/combat.css`
- Drop the white-translucent glass look (`.card-glass`, `.card-header-glass`,
  `.card-body-glass`, `.badge-glass`, `.badge-glass-sm`, blur/backdrop-filter)
  in favor of flat Cold Steel panels: backgrounds on `--ui-panel`/`--ui-elevated`,
  borders via `color-mix(in srgb, var(--ui-accent) X%, transparent)`, text on
  `--ui-text`/`--ui-text-dim`. Matches the flat look already used by
  `.tactical-panel` elsewhere on this same page.
- Recolor `.progress-glass`/`.progress-glass-sm` track backgrounds from black
  `rgba()` to a `--ui-bg`/`--ui-elevated` color-mix.
- Recolor `.progress-bar-danger` (HP), `.progress-bar-primary` (mana),
  `.progress-bar-success` gradients onto `--ui-danger`, `--ui-accent`,
  `--ui-success` respectively (mixed with a lighter shade of itself for the
  two-stop gradient, replacing the current two-hardcoded-hex gradients).
- Recolor `.btn-combat` base + the 5 variants (`attack`, `defend`, `spell`,
  `heal`, `flee`) — semantic mapping below.
- Collapse the ~18 `.log-*` classes onto 4 semantic groups (below). `.log-miss`,
  `.log-system`, `.log-flee` already read as neutral/dim — recolor onto
  `--ui-text-dim` explicitly instead of separate grays.
- `#combat-log` background/scanline overlay: recolor from raw black/gray to
  `--ui-bg`-based color-mix; text color from `#AAAAAA` to `--ui-text-dim`.

### B. `app/static/css/combat-effects.css`
- `.status-indicator` base: recolor the black blur backdrop + white border to
  `--ui-elevated`/`--ui-accent` color-mix.
- 8 `.status-*` border-color variants recolor onto the same 4 semantic groups
  used for the log (mapping below).
- No animation/keyframe/transform changes — only colors.

### C. `app/static/js/combat-effects.js`
- The **generic** colors (`baseColor` for heal/critical/miss/damage in the
  floating-damage-number code, and the `flashElement` heal/damage defaults)
  switch from hardcoded hex literals to a small lookup that reads the Cold
  Steel CSS custom properties at call time:
  ```js
  function uiColor(name, fallback) {
      return getComputedStyle(document.documentElement)
          .getPropertyValue(`--ui-${name}`).trim() || fallback;
  }
  ```
  `isHeal -> uiColor('success', '#4caf82')`, `isCritical -> uiColor('warning', '#d6a23a')`,
  `isMiss -> uiColor('text-dim', '#8d97a3')`, default damage -> `uiColor('danger', '#c0392b')`.
- **Out of scope, explicit exception:** the elemental particle-effect color
  arrays (`fire`/`ice`/`lightning` gradients, the shield-spawn purple, the
  generic "rgba(147,197,253,...)" sparkle tint) are intentional per-spell-
  element flavor colors, not palette debt — analogous to the indigo hero
  badge Phase 5a confirmed was deliberate and left alone. Flattening fire/
  ice/lightning onto 4 generic tones would make spells visually
  indistinguishable from each other. Leave these literals untouched.

## Semantic color mapping (used by both A and B)

| Group | Token | Log events | Status indicators |
|---|---|---|---|
| Danger | `--ui-danger` | damage, crit, death, bleed, burn | burn |
| Success | `--ui-success` | heal, buff, victory | regen |
| Warning | `--ui-warning` | debuff, stun, curse, poison, loot | stun, curse, blessed |
| Accent | `--ui-accent` | shield, block, dodge, freeze | freeze, shield |
| Text-dim | `--ui-text-dim` | miss, system, flee | — |

`.log-turn` (turn announcements) recolors onto `--ui-accent` (an informational
marker, not a damage/status event).

## Testing

No unit tests apply — this is a pure CSS/color change with no logic branches
to assert on (the one JS change, `uiColor()`, is a straightforward getter with
a hardcoded fallback; not worth a Jest-style test in a repo with no JS test
infra). Verification is manual, via the `run`/`verify` skills in a live
browser:
- Start a combat encounter.
- Confirm party-card panels, action buttons, HP/MP bars, and the combat log
  render in Cold Steel tones (slate/charcoal panels, teal accent) with no
  leftover white-glass or candy-colored elements.
- Trigger at least one of each: a normal hit, a crit, a heal, a miss, a status
  effect (e.g. poison/stun if reachable), and a victory/death to eyeball log
  colors against the mapping table.
- Confirm fire/ice/lightning spell effects still show their distinct elemental
  colors (unchanged).
- Check the browser console for errors (especially around `uiColor()`).

## Out of scope
- Any markup/template changes to `combat.html`.
- Any new Cold Steel CSS variables — reuse the existing 8 tokens only.
- The Three.js dungeon renderer (separate, already-complete Phase 3).
- Elemental particle-effect colors (see explicit exception above).

## Affected files
- `app/static/css/combat.css` (full pass)
- `app/static/css/combat-effects.css` (status indicator colors + backdrop)
- `app/static/js/combat-effects.js` (generic damage/heal/crit/miss color lookup only)
