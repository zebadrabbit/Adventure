# Landing Page Hero — Asymmetric Split Layout — Design

**Date:** 2026-06-20
**Status:** Design only — not yet planned/implemented.

## Context

The landing page (`app/templates/index.html` + `app/static/css/home.css`) was
already given a Cold Steel color-literal sweep this session (see the
`05e3ce3` commit), but the user's complaint was structural, not color: "it
just feels weirdly placed and awkward." Inspecting the template confirmed why
— it's a single everything-centered hero block: badge → title → description
→ two CTA buttons → four small inline feature icons, all stacked in one
column with no visual weight distribution. There's also a deliberate, pre-
existing `display: none !important` override in the template's `<style>`
block that hides the site's navbar/header/footer on this page only, rendering
hero content via the `after_main` block instead of `content` — confirmed via
brainstorming conversation to be **intentional** (a distinct full-screen
marketing page, not a bug) and explicitly out of scope for this pass.

Brainstormed with the visual companion: presented three mockup directions
(A: tightened version of the current centered stack, B: asymmetric split with
feature highlights as a card column, C: banded vertical zones with a divider
rule). User picked **B** outright ("B definitely").

## Goals

1. Replace the single centered hero column with a two-column asymmetric
   split on `≥lg` viewports: text content (badge/title/description/CTAs) on
   the left, four feature highlight cards stacked on the right.
2. Convert the four feature items from small inline icon+text
   (`.feature-item`) into bordered panel-style cards (`.feature-card`) that
   match the Cold Steel `var(--dungeon-panel)`/`var(--dungeon-border)`
   variables already used elsewhere in `home.css`.
3. On `<lg` viewports, stack vertically: text content first, then the
   feature cards below — per the user's explicit answer.
4. No copy changes. No new content sections. No backend changes.

## Non-goals

- Changing whether the navbar/header/footer are hidden on this page — that
  hidden behavior is confirmed intentional and stays exactly as-is.
- Adding new marketing content (screenshots, testimonials, additional
  sections) — the user confirmed the awkwardness is about layout/spacing
  within the existing single hero, not insufficient content.
- Changing the hero footer (copyright + Terms/Privacy/Support links) below
  the hero content — unchanged.
- Any color/literal changes — `home.css`'s Cold Steel literal sweep already
  happened this session; this pass only restructures layout.

## Architecture

**Markup change (`app/templates/index.html`):**

Inside `.hero-content` (within the existing `.hero-container` →
`.row.justify-content-center` → `.col-lg-10.col-xl-8` wrapper), restructure
from one flat stack into a Bootstrap two-column row:

- A new wrapping `<div class="row hero-split align-items-center g-4">`
  replaces the current flat sequence of `.hero-badge`, `.hero-title`,
  `.hero-description`, `.hero-actions`, `.hero-features`.
- **Left column** (`<div class="col-lg-7 hero-text">`): contains the existing
  `.hero-badge`, `.hero-title` (with its `.gradient-text` span, unchanged),
  `.hero-description`, and `.hero-actions` markup verbatim — only their
  wrapping `<div>` changes, not their internal content or classes.
- **Right column** (`<div class="col-lg-5 hero-feature-grid">`): contains the
  four feature entries, each upgraded from the current
  `<div class="feature-item"><i class="bi ..."></i><span>Label</span></div>`
  to `<div class="feature-card"><i class="bi ..."></i><span>Label</span></div>`
  — same icon classes and label text, only the wrapping class renames from
  `feature-item` to `feature-card` and the parent container class renames
  from `hero-features` to `hero-feature-grid` (a flex column instead of the
  current flex row, since these are now stacked cards, not an inline icon
  row).
- Because Bootstrap's grid already reflows `col-lg-*` columns to full-width
  stacked at `<lg`, and DOM order is left-column-then-right-column, the
  mobile stacking order (text first, then feature cards) falls out of the
  existing grid behavor for free — no extra media-query reordering needed.

**CSS change (`app/static/css/home.css`):**

- Add `.hero-split` (the row wrapper): no new properties needed beyond what
  `g-4`/`align-items-center` (already Bootstrap utility classes) provide —
  only add this selector if a gap/padding tweak proves necessary once
  rendered; default to relying on Bootstrap's row gutter.
- Rename `.hero-features` (flex row, `gap` between inline icon items) to
  `.hero-feature-grid`: change `flex-direction` from `row` to `column`, keep
  a `gap` between stacked cards (reuse the existing gap value).
- Rename `.feature-item` to `.feature-card` and restyle from "icon + text in
  a thin pill" to a proper card: background `color-mix(in srgb,
  var(--dungeon-panel) 50%, transparent)` (reuses the exact value
  `.feature-item` already had from the Phase 5a sweep — just renamed),
  border `1px solid color-mix(in srgb, var(--dungeon-border) 50%,
  transparent)` (also reused as-is), increased `padding` (from the current
  `0.5rem 1rem` to something more card-like, e.g. `1rem 1.25rem`), and
  `border-radius` increased slightly (from `0.5rem` to `0.75rem` to read as
  a card rather than a pill). Icon and label keep their current font-size/
  color rules (`.feature-card i`/`.feature-card:hover` mirror the existing
  `.feature-item i`/`.feature-item:hover` rules, just renamed).
- No other rules change. `.hero-badge`, `.hero-title`, `.gradient-text`,
  `.hero-description`, `.hero-actions`, `.btn-hero-primary`,
  `.btn-hero-secondary`, `.hero-footer`, `.footer-link` are untouched.

**No backend changes, no JS changes.**

## Testing

Template/CSS-only change, consistent with the dashboard hub layout pass
earlier this session — no new pytest tests. Verification is manual:

- Load `/` and confirm the hero renders as a left-text / right-feature-cards
  split on a desktop-width viewport.
- Narrow the viewport below Bootstrap's `lg` breakpoint and confirm it
  stacks with text content first, then the four feature cards below.
- Confirm the navbar/header/footer remain hidden (unchanged behavior).
- Confirm both CTA buttons still link to `/register` and `/login`
  respectively, and the feature card icons/labels are unchanged
  (Procedural Dungeons, Real-time Combat, Multiplayer Co-op, Epic Loot).
- No browser console errors.
