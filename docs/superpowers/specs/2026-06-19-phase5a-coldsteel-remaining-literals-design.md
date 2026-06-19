# Phase 5a — Cold Steel Design System: Remaining Embedded Color Literals — Design

**Date:** 2026-06-19
**Status:** Design only — not yet planned/implemented.
**Part of:** The full UI/visual redesign roadmap (`/home/winter/.claude/plans/mossy-petting-crane.md`),
Phase 5 of 5 ("remaining surfaces").

**Process note:** Continuing under the established session pattern —
decisions below are self-documented with their reasoning.

## Context

Phase 4 (combat visuals) is explicitly the roadmap's riskiest remaining
phase — it calls for evaluating a 3D "stage" reusing the Three.js pipeline,
and the roadmap itself warns "don't design it blind," meaning camera angle,
stage proportions, and lighting are judgment calls that need a live user's
visual feedback, not just screenshot review. With no live user currently
available to make those calls, this milestone instead continues with
**Phase 5** (remaining surfaces) — explicitly described by the roadmap as
lower-risk, CSS/template-only work suited to exactly this situation: "Account
pages, auth pages, admin pages get the Phase 1 design system applied for
consistency but don't need bespoke redesign attention."

A survey of these surfaces found:
- `app/templates/login.html`, `register.html`, `index.html` all extend
  `base.html`, which already loads `theme.css` (the Phase 1 Cold Steel
  consolidation) and the active `Theme` row's CSS globally — so these pages
  already inherit Cold Steel for borders/text/buttons, same finding Phase 2
  made for the dashboard before its own literal-sweep.
- `app/static/css/home.css` (the landing page, `index.html`'s page-specific
  stylesheet) still has **17 occurrences of the same old amber/brown
  `rgba()` literals** Phase 2 already swept out of `theme.css` — this phase
  is that exact same fix, just on a file Phase 2's scope didn't cover.
- `app/templates/account/profile.html` and `account/settings.html` load
  `glass-theme.css` (Phase 1's identified "third, unrelated purple
  glass-morphism palette"). Investigated further: the specific classes these
  two templates actually use (`.section-card`, `.stat-card`, etc.) are
  *already* mostly neutral (`rgba(255,255,255,...)` frosted-glass cards) and
  already reference `var(--adv-primary)` for accent borders — Cold Steel's
  own alias namespace. The literally-purple rules in `glass-theme.css`
  (`.theme-purple-gradient body`, `.purple-gradient`) are dead code — neither
  template's `<body>` ever gets either class (confirmed: `base.html`'s
  `<body>` only ever has `class="d-flex flex-column min-vh-100"`). **No real
  visual inconsistency exists here** — this finding changes this phase's
  scope from "redesign account pages" to "nothing to do," which is itself a
  useful, concrete outcome of this investigation.
- `auth.css` (login/register page-specific styles) has zero old-palette
  literals already — clean.

This narrows Phase 5a to exactly one concrete, well-precedented fix:
sweeping `home.css`'s embedded literals, using the exact same
`color-mix()`-on-alias technique Phase 2 already proved and shipped.

## Goals

1. Convert `home.css`'s old-palette `rgba()` literals to `color-mix(in srgb,
   var(--dungeon-X) N%, transparent)` expressions, using Phase 2's existing
   6-triple mapping table where the triple matches exactly, and two new
   mappings for two triples Phase 2 didn't encounter (see table below).
2. Leave the `rgba(99, 102, 241, ...)` / `#a5b4fc` hero-badge colors
   (`home.css:91-92,97`) untouched — confirmed via inspection this is a
   distinct, intentional indigo accent for the landing page's hero badge,
   not a leftover from the old amber/brown palette. Sweeping every
   non-Cold-Steel color in a file regardless of origin would be scope creep;
   only the *old-palette* literals are this phase's target, matching Phase
   2's own discipline.
3. Document the account-pages investigation finding (no fix needed) in the
   TODO entry, so a future session doesn't re-investigate the same question.

## Mapping table

The 6 triples Phase 2 already established, reused as-is:

| Old RGB literal | Maps to alias |
|---|---|
| `rgb(212, 165, 116)` | `var(--dungeon-accent)` |
| `rgb(61, 50, 38)` | `var(--dungeon-border)` |
| `rgb(26, 21, 18)` | `var(--dungeon-panel)` |
| `rgb(13, 10, 10)` | `var(--dungeon-bg)` |

Two new triples found only in `home.css`, mapped by the same "closest
existing alias by visual role" reasoning Phase 2 used for its own two
ambiguous triples — both appear only in `home.css:26-27` as a pair of very
low-opacity (`0.08`/`0.06`) radial-gradient background-glow blobs on the
landing page's hero section:

| New RGB literal | Maps to alias | Reasoning |
|---|---|---|
| `rgb(193, 122, 58)` | `var(--dungeon-accent)` | A darker shade of the same amber-glow family as the existing `rgb(212, 165, 116)` → accent mapping; both are warm, mid-brightness glow colors. |
| `rgb(139, 111, 71)` | `var(--dungeon-border)` | A duller, darker brown closer in lightness/role to the border-tier mapping than the bright accent tier. |

## Non-goals

- Touching `auth.css` — already clean (zero old-palette literals).
- Touching `glass-theme.css` or the account pages — confirmed no real issue
  exists (see Context). Removing the genuinely-dead `.theme-purple-gradient`/
  `.purple-gradient` body-class rules from `glass-theme.css` is tempting
  (it's dead code, matching Phase 2's `--mud-*` precedent) but is deferred:
  `glass-theme.css` is also loaded by `admin_themes.html`, and confirming
  those specific rules are *also* unused there (not just on the two account
  pages this investigation checked) needs its own grep pass — worth a
  separate, quick follow-up rather than bundling an unverified admin-page
  claim into this phase's scope.
- Admin pages generally — explicitly "functional-over-pretty" per the
  roadmap, no bespoke work needed.
- The `rgba(99, 102, 241, ...)` indigo hero-badge accent — confirmed
  intentional, not a leftover, see Goals.

## Error handling

None applicable — pure CSS literal substitution, no runtime logic, no new
failure modes. Same `color-mix()` browser-support precedent as Phase 2.

## Testing

No automated CSS test suite exists (consistent with every prior phase).
Verification is visual: load `/` (the landing page) and confirm the
background glow blobs and any other converted elements show only Cold Steel
teal/charcoal tones, with the indigo hero badge unchanged. No backend
changes — run the existing pytest suite once at the end as a regression
check only.

## Affected files

- `app/static/css/home.css` — convert 17 old-palette `rgba()` literals (6
  triples) to `color-mix()` expressions per the mapping table above.
- No template, JS, or backend changes.
