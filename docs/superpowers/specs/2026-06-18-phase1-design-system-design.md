# Phase 1 — Design System Foundation — Design

**Date:** 2026-06-18
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
Phase 1 of 5.

## Context

The roadmap plan identified the design system as fragmented rather than absent: four
CSS files (`theme.css`, `tactical-theme.css`, `glass-theme.css`, `app.css`, ~3,000
lines combined) each define their own color namespace (`--dungeon-*`, `--adv-*`, a
third unrelated purple glass-morphism set, and Bootstrap overrides), all-serif
Georgia typography reads as "medieval brown" rather than the modern, atmospheric
ARPG-hub feel the redesign is aiming for (Dark and Darker / Arc Raiders).

A `Theme` DB model (`app/models/theme.py`) and admin UI (`admin_themes.html`,
`theme_api.py`) already exist for live theme switching — full CRUD, an "activate"
endpoint, and a `GET /theme/active/css` endpoint that serves the active theme's
`to_css_variables()` output as a CSS document. **Investigation during brainstorming
found this endpoint is never actually linked from any template** (`grep` across
`app/templates/*.html` and `app/static/js/*.js` for `active/css` returns nothing) —
the admin theme system has been fully built but disconnected from what players
actually see. This phase both ships the new palette through this mechanism and
wires the mechanism in for the first time.

Brainstorming explored three palette directions visually (Cold Steel — slate/teal,
Arc Raiders-like; Ember Noir — desaturated warm-dark with gold accent; Violet Rune —
arcane violet-black) and a variant of Violet Rune with Cold Steel's typography. The
user chose **Cold Steel** as-is.

## Goals

1. One canonical CSS custom-property namespace, replacing the `--dungeon-*` /
   `--adv-*` / glass-theme split, expressed as the **Cold Steel** palette.
2. Sans-serif typography everywhere in UI chrome (drop Georgia/serif), using the
   system font stack — no new web-font dependency.
3. Ship Cold Steel as a new `Theme` DB row, seeded as the active/default theme.
   Preserve the current look as a second, selectable "Classic Dungeon" `Theme` row
   (not deleted — just no longer active by default).
4. Wire `GET /theme/active/css` into the actual page templates so the `Theme`
   mechanism has real effect for players, not just inside the admin panel.
5. Consolidate the 4 CSS files' overlapping variable definitions down to one
   canonical set, with `--dungeon-*` / `--adv-*` kept only as **aliases** pointing
   at the new names — so none of the ~234 existing call sites across templates/JS
   need to change in this pass. That cleanup is deferred to whichever later phase
   (2 or 5) actually touches each call site.

## Non-goals

- Touching `app/static/css/tactical-theme.css`'s or `glass-theme.css`'s actual
  *visual* treatment beyond pointing their variable references at the new
  canonical names — Phase 2 (hub/dashboard redesign) is where `glass-theme.css`'s
  purple glass-morphism look on admin pages gets reconsidered, if at all (admin is
  explicitly lower priority per the roadmap).
- Any template markup/layout changes — this phase is CSS custom properties, font
  stack, and the `Theme` DB/template wiring only. No new icons, no layout rework
  (that's Phase 2).
- Renaming every `--dungeon-*`/`--adv-*` reference across the codebase. Aliasing
  is intentional scope control, not a shortcut to be "fixed later" as tech debt —
  it's the correct boundary for this phase per the roadmap's "later phases consume
  Phase 1's output" ordering.
- Extending the `Theme` model with new fields for the consolidated namespace.
  Reusing the existing Bootstrap-shaped fields (`primary`, `success`, `danger`,
  `warning`, `body_bg`, `body_color`, `border_color`, `card_bg`) is sufficient —
  see "Theme model usage" below for the mapping. No migration needed.

## Palette — Cold Steel

| Role | Hex | Theme field |
|---|---|---|
| Background | `#0c0e12` | `body_bg` |
| Panel | `#1b1f27` | `card_bg` |
| Elevated / border | `#2e3440` | `border_color` |
| Accent / primary | `#5ad1c9` | `primary` |
| Accent hover | `#7adbd4` (lightened) | `secondary` |
| Danger | `#c0392b` | `danger` |
| Success | `#4caf82` | `success` |
| Warning | `#d6a23a` | `warning` |
| Text | `#dfe4ea` | `body_color` |
| Text (dim) | `#8d97a3` | *(new alias var, not a Theme field — see below)* |

`info`/`light`/`dark` (existing `Theme` fields not covered by the brainstorm) get
sensible Cold-Steel-consistent values rather than new design discussion: `info`
reuses the accent teal, `light` is the text color, `dark` is the background.

Text-dim (`#8d97a3`) and the new canonical namespace's full variable list aren't
modeled as `Theme` columns — they're computed in the template-level CSS (see
"Consolidated namespace" below) from the `Theme` fields that *are* columns, so no
migration is needed for this phase.

## Typography

Replace `Georgia, 'Times New Roman', serif` (current `body` font-family in
`theme.css`) and any other serif declarations in the 4 CSS files with:

```css
font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
```

applied at `:root`/`body` level so it cascades everywhere by default. No `<link>`
to a web font, no FOUT/FOIT concern, no new dependency — matches the "no new
animation/font library" precedent already set elsewhere in this redesign.

## Consolidated namespace

New canonical variables (defined once, in `theme.css`'s `:root`, replacing its
current Cold-Steel-incompatible values):

```css
:root {
    --ui-bg: #0c0e12;
    --ui-panel: #1b1f27;
    --ui-elevated: #2e3440;
    --ui-accent: #5ad1c9;
    --ui-accent-hover: #7adbd4;
    --ui-danger: #c0392b;
    --ui-success: #4caf82;
    --ui-warning: #d6a23a;
    --ui-text: #dfe4ea;
    --ui-text-dim: #8d97a3;

    /* Back-compat aliases — existing call sites keep working unchanged */
    --dungeon-bg: var(--ui-bg);
    --dungeon-panel: var(--ui-panel);
    --dungeon-border: var(--ui-elevated);
    --dungeon-accent: var(--ui-accent);
    --dungeon-danger: var(--ui-danger);
    --dungeon-success: var(--ui-success);
    --dungeon-warn: var(--ui-warning);
    --dungeon-text: var(--ui-text);
    --dungeon-text-dim: var(--ui-text-dim);

    --adv-primary: var(--ui-accent);
    --adv-primary-hover: var(--ui-accent-hover);
    --adv-secondary: var(--ui-elevated);
    --adv-success: var(--ui-success);
    --adv-danger: var(--ui-danger);
    --adv-warning: var(--ui-warning);
    --adv-link-color: var(--ui-accent);
    --adv-link-hover-color: var(--ui-accent-hover);
}
```

`tactical-theme.css` and `glass-theme.css` keep their own structural rules but have
their *hardcoded* hex values (where they duplicate `--dungeon-*`/`--adv-*` intent)
replaced with `var(--ui-*)` references, so they inherit Cold Steel automatically
rather than silently keeping the old purple/brown look on the pages that include
them (`admin_base.html`, `combat.html`).

`Theme.to_css_variables()` is extended to also emit the `--ui-*` block (sourced
from its own columns, per the mapping table above) alongside its existing
`--bs-*`/`--adv-*` output, so a `Theme` row fully controls the canonical namespace
too — not just the legacy aliases.

## Theme model usage — no migration

No new columns. The mapping table above uses only fields the `Theme` model already
has. Two `Theme` rows are seeded (via a script/migration data-seed, consistent with
the existing `seed-skills`/`seed-merchants` precedent):

1. **"Cold Steel"** — the palette above, `is_active=True`.
2. **"Classic Dungeon"** — the current brown/amber/Georgia values, `is_active=False`,
   preserved so it's still selectable from the existing admin theme-switcher UI
   without anyone having lost the old look.

## Wiring `Theme` into player-facing pages

`base.html`, `dashboard_base.html`, `admin_base.html`, and `combat.html` each gain,
after their existing static theme `<link>` tags:

```html
<link rel="stylesheet" href="{{ url_for('theme.get_active_theme_css') }}">
```

(resolves to `/api/admin/themes/active/css` — despite the `/api/admin` prefix this
route has no `@admin_required`/auth decorator, confirmed in `theme_api.py`; it's
explicitly commented "public endpoint"). Because it's loaded *after* the static CSS files, the active
`Theme` row's `--ui-*`/`--bs-*` output overrides the static defaults, giving the
admin theme-switcher real effect for the first time. The endpoint already sets
`Cache-Control: no-cache` so switching themes in the admin panel reflects on next
page load without a hard cache-bust being needed.

## Error handling

- `GET /theme/active/css` already has a fallback branch when no `Theme` row is
  `is_active` (returns a hardcoded default block) — untouched by this phase, still
  correct as a safety net.
- If both seeded rows somehow end up `is_active=False` (e.g. an admin deactivates
  Cold Steel without activating anything else), the existing fallback CSS keeps the
  site usable rather than unstyled; not a new failure mode introduced here.

## Testing

- No JS test runner in this repo (consistent with all prior frontend work this
  session) — verification is visual/manual via the `run`/`verify` skills:
  dashboard, combat, and an admin page each load with the Cold Steel palette and
  sans-serif type, with zero console errors.
- Backend: a small test asserting `Theme.to_css_variables()` emits the `--ui-*`
  block with the correct values for a known `Theme` fixture (extends test coverage
  the same way prior sub-specs added targeted backend tests alongside larger UI
  changes).
- Manual check: switching the active theme to "Classic Dungeon" in the admin panel
  and reloading the dashboard shows the old brown palette — confirms the wiring (not
  just the new default) actually works end-to-end.

## Affected files

- `app/static/css/theme.css` — new canonical `:root` block + aliases, sans-serif
  `body` font-family.
- `app/static/css/tactical-theme.css`, `app/static/css/glass-theme.css` — hardcoded
  hex values referencing dungeon/adv intent swapped for `var(--ui-*)`.
- `app/static/css/app.css` — any serif declarations or duplicate color literals
  swapped to reference the same variables.
- `app/models/theme.py` — `to_css_variables()` extended to emit the `--ui-*` block.
- `app/templates/base.html`, `dashboard_base.html`, `admin_base.html`,
  `combat.html` — add the `theme.get_active_theme_css` stylesheet link.
- A seed script/migration (new, e.g. `app/seed_themes.py` mirroring
  `app/seed_skills.py`'s pattern) creating the two `Theme` rows.
- `tests/` — new small test for `to_css_variables()`'s `--ui-*` output.
