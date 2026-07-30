# Adventure — Design System

**Status:** canonical. This document and `app/static/css/tokens.css` are the
source of truth for how Adventure looks. If a CSS file disagrees with this
document, the CSS file is wrong.

Here to build a screen? You need [The one rule](#the-one-rule),
[Two realms](#two-realms-one-structure), [Tokens](#tokens) and
[Components](#components). The rest is background and history.

---

## What we are making

A candlelit dungeon hall, not a dashboard.

The visual reference is the **Dark and Darker lobby** — and specifically its
*UI language*, not its rendered art. What that language actually consists of:

- A **warm near-black** ground. Brown-black and candlelit, not cool slate.
- **Chrome that barely exists.** Navigation is plain text on the background,
  separated by a hairline with small ornamental ends. No boxes around it.
- **A single accent**, used sparingly — the active item, small icons, thin
  dividers. Everything else is muted bone on dark.
- **Framed panels are rare and earned.** Two on the whole screen. A panel is a
  statement, not the default container you put things in.
- **Typography carries the theme.** A serif display face, letterspaced, with
  tapered rules and decorative separators. That is where the fantasy comes
  from — which is why we need almost no ornament anywhere else.
- **Low ambient contrast with exactly one bright element.** Everything
  recedes except the thing you are meant to press.
- **Hard or ornamental edges. No soft diffuse shadows.** Bootstrap's default
  `border-radius` and `box-shadow` are the two single biggest reasons the app
  currently reads as a demo page.

That last pair is worth restating, because it is cheap and it is most of the
gap: **rounded corners and blurry drop shadows are the "Bootstrap demo" look.**
`--radius` is `0` and `--elev-flat` is `none` for exactly this reason.

---

## The one rule

> **Every colour, size, radius, shadow and duration in `app/static/css/` comes
> from a token in `tokens.css`. If the token you need does not exist, add it
> there — do not write a literal, and do not open a new `:root` block.**

`tokens.css` is the only file that declares custom properties at the root
level. There used to be ten `:root` blocks across eight files declaring 154
properties with **38 direct conflicts**. That is what "the styling is all over
the place" looked like from the inside. One token file is the fix, and it only
stays fixed if nobody adds an eleventh.

Corollaries:

- No raw hex or `rgba()` outside `tokens.css`. Derive with
  `color-mix(in srgb, var(--token) N%, transparent)` — already used throughout
  the codebase, so browser support is settled.
- **No component may hard-code a hue.** If a component only looks right in one
  realm, it is hard-coding something it should be taking from a token. This is
  the single most useful test of whether a component is correctly built.
- No inline `style="…"` and no inline `<script>` in templates — pre-commit
  rejects both. Inline `<style>` blocks are not yet checked but are equally
  forbidden (`app/templates/index.html` has a grandfathered one).
- Extend an existing component class before inventing a parallel one.

---

## Two realms, one structure

The game is about leaving safety and trying to return to it. The palette
expresses that mechanic rather than decorating it.

| | **WARM — town** | **COLD — dungeon** |
|---|---|---|
| Feels like | amber, candlelight, wood, parchment, company | slate, blue-grey, stone, damp, isolation |
| Ground | `#0f0c09` | `#0b0d11` |
| Panel | `#181310` | `#161a22` |
| Edge | `#2b231b` | `#2f3745` |
| Accent | lamplight amber `#d9a441` | cold lantern-steel `#8ab4d8` |
| Ink | bone `#d6c9b3` | pale slate `#c3ccd8` |

**Shared, defined once:** the type scale, the space scale, edge and corner
treatment, component shapes and sizes, elevation rules, focus and disabled
states, motion, feedback hues, rarity hues, class hues, and the semantic role
names themselves.

**Varies by realm:** surface colours, ink colours, accent hue, and the warmth
of any glow.

Contrast is matched between the realms on purpose — ink lands at ~12:1 and
accent at ~8.7:1 in both — so a component carries exactly the same emphasis
whichever realm it is standing in.

### The switch

One attribute on `<body>`. Town is the default, so an unmarked page is warm.

```html
<body data-realm="dungeon">
```

In CSS, `[data-realm="dungeon"]` redefines seven `--realm-*` values; every
semantic token derives from those, so one attribute flips the entire screen.
Nothing else changes — no alternate stylesheet, no component variants.

You can watch it work: load `/login` and run
`document.body.setAttribute('data-realm','dungeon')` in the console.

### Screen mapping

| Realm | Screens |
|---|---|
| **Warm** | dashboard / barracks roster, lobby, merchants and trading, the Hoard, account and settings, help, character creation, auth |
| **Cold** | the adventure map screen, combat, and anything shown while a run is in progress |

Rule of thumb: **if the party can die on this screen, it is cold.**

### Warm chrome, cool viewport — a deliberate decision

The dungeon tileset (`docs/ASSETS.md`) is cool slate/blue-grey. The town chrome
is warm. Those two meet on the adventure screen, and that is intended, not an
accident:

- In the **cold realm** the chrome and the map agree — the cold palette is
  derived from the tileset's own colours (void `#0a0b0f`, tunnel `#242a36`,
  floor `#2d3340`, wall `#39414f`), so the UI and the art read as one place.
- Anywhere **warm** chrome frames a cool viewport (a map preview on the
  dashboard, for instance), the temperature break makes the map read as a
  *window into somewhere colder* rather than as another panel. That is a
  feature. Use `--viewport-frame` for the frame and let the contrast stand.

The alternative — going cool everywhere to match the tiles — was considered and
rejected. Cool-on-cool makes the map compete with the chrome instead of sitting
inside it, and it gives back the one thing the palette is being asked to do:
make the town feel like a different place from the dungeon.

### Transitions (do not build yet)

The loop is: leave warmth → go cold → try to get back. Worth expressing, cheaply:

- **Entering a dungeon** — a ~400ms cross-fade of the realm tokens as the run
  starts. Because every colour is a custom property, this is a `transition` on
  the seven `--realm-*` values, not a rewrite.
- **Extracting** — the same transition in reverse, slightly slower. Arriving
  back in warmth should feel like relief.
- **A party wipe** — the player does not get the warm screen back that run.
  Stay cold through the death summary; return to warmth only at the roster.

Noted for later. Do not build it as part of the migration.

---

## Designed for a long session

"Comfortable to play for a long time" is a testable constraint, not decoration.
Each of these is a token decision with a reason:

1. **Restrained contrast, rationed peaks.** Body ink sits at ~12:1, not the
   15:1 the old palette used. Bright text on near-black haloes, and haloing is
   what makes a two-hour session tiring. Maximum contrast is rationed to
   `--ink-strong`, for the few numbers that must punch — damage, HP, gold.
2. **Calm surfaces.** The step from ground to panel is ~1.1:1. Separation
   comes from rules and spacing, not from value jumps that chop the screen into
   blocks. Density is bought with the space scale, never by shrinking type.
3. **No high-chroma on large areas.** Accent, danger, success and gold appear
   on small elements — buttons, bars, badges, rules. Never as a panel fill or
   page background. One bright element per screen is the target.
4. **A reading floor.** `--text-sm` (14px) is the smallest size allowed for
   anything read as prose, and the combat log gets `--leading-loose` (1.75).
   `--text-2xs` (11px) is legal *only* for uppercase tracked micro-labels,
   which are glanced at, not read.
5. **Nothing loops.** Motion marks a state change and then stops. An animation
   that runs forever is fatigue with extra steps. The landing page's 15-second
   `gradientShift` and its `shimmer` are on the list to remove.
6. **Panels do not twitch.** No `transform` on hover for containers on game
   screens. `.tactical-panel:hover { transform: translateY(-1px) }` makes a
   dense screen ripple as the cursor crosses it.

---

## Tokens

The annotated list lives in `app/static/css/tokens.css`. This is the map.

### Layer 0 — theme primitives (`--ui-*`)

Eleven values describing the **town**, each mapped to a `Theme` DB column.
This is the surface an admin re-skins. The dungeon realm is deliberately *not*
theme-controlled: it is matched to the tileset, and letting an admin recolour
it would desynchronise the chrome from the art.

| Token | Value | `Theme` column |
|---|---|---|
| `--ui-bg` | `#0f0c09` | `body_bg` |
| `--ui-panel` | `#181310` | `card_bg` |
| `--ui-elevated` | `#2b231b` | `border_color` |
| `--ui-accent` | `#d9a441` | `primary` |
| `--ui-accent-hover` | `#e8bc63` | `secondary` |
| `--ui-danger` | `#cf6047` | `danger` |
| `--ui-success` | `#87a865` | `success` |
| `--ui-warning` | `#d4813c` | `warning` |
| `--ui-text` | `#d6c9b3` | `body_color` |
| `--ui-text-dim` | `#a2937d` | `light` |

The seeded **"Lamplight"** theme (`app/seed_themes.py`) carries exactly these
values and is the active default. "Cold Steel" and "Classic Dungeon" remain
selectable.

### Layer R — the realm (`--realm-*`)

Seven values: `bg`, `panel`, `edge`, `accent`, `accent-hover`, `ink`,
`ink-dim`. Town maps them from Layer 0; `[data-realm="dungeon"]` replaces them.
A third realm later (a burning town? a flooded level?) is seven lines.

### Layer 1 — semantic roles

Named for **what a thing is**, never what colour it happens to be. Components
consume this layer and Layer 2 *only*. A component reading `--ui-*` or
`--realm-*` directly is reaching through the system.

**Surfaces**

| Token | Use for |
|---|---|
| `--surface-sunken` | the page; wells, insets, log backgrounds, input fills |
| `--surface` | the default panel fill |
| `--surface-raised` | panel headers, hovered rows, nested blocks |
| `--surface-overlay` | modals, dropdowns, tooltips — the only surfaces allowed a shadow |
| `--surface-hover` | a surface under the cursor |
| `--scrim` | the dim behind a modal |

**Edges and rules** — rules do the work that boxes do in Bootstrap.

| Token | Use for |
|---|---|
| `--edge-subtle` | hairlines *inside* a panel: list separators, table rules |
| `--edge` | the edge of a panel or input |
| `--edge-strong` | selected / active / focused container; ornamental frames |
| `--rule-tapered` | the house divider — a rule that fades at both ends. Use as a `background` on a 1px-tall element, never as a `border` |

**Ink** — colour is `--ink*`; *size* is `--text-*`. Do not confuse them.

| Token | Use for | Contrast on `--surface` |
|---|---|---|
| `--ink-strong` | numbers that must punch: damage, HP, gold totals | ~15:1 |
| `--ink` | body copy, values, anything read | ~11:1 |
| `--ink-muted` | labels, captions, metadata, timestamps | ~6:1 |
| `--ink-faint` | placeholders and disabled text **only** | fails AA by design |
| `--ink-on-accent` | text sitting on an `--accent` fill | — |

**Accent and feedback.** Each role has three forms: the solid (`--danger`), a
14% tint for backgrounds (`--danger-wash`), and a 45% tint for borders
(`--danger-line`). Same shape for `--accent`, `--warn`, `--success`, `--info`.

One accent per realm. It marks the thing you can act on, and nothing else. If
everything is amber, nothing is.

Feedback hues stay constant across realms — "you failed" must not look
different because of where you are standing.

### Layer 1b — game semantics

These exist because this is a dungeon crawler and must mean the same thing in
both realms. They are **not** interchangeable with the feedback roles: an HP
bar is red because it is HP, not because something went wrong. If HP and danger
ever need to diverge, this separation makes that a one-line change.

| Token | Notes |
|---|---|
| `--hp`, `--mp`, `--xp` | `--mp` is the one blue in the chrome, deliberately not the accent, so a mana bar never reads as clickable |
| `--hostile`, `--ally` | monsters vs party; enemy turn vs your turn |
| `--coin-gold/-silver/-copper` | **coin gold stays warm in both realms.** Underground it is the only warm thing on screen — down there, gold is the light you came for |
| `--rarity-common … -legendary` | fixed; a player must be able to learn that purple means epic and have it survive a re-skin |
| `--class-fighter … -warlock` | one hue per class; badges and the equipment header strip derive from it. There is no border-ring presentation — see [Class identity](#class-identity) |
| `--viewport-bg`, `--viewport-frame` | the frame around the map canvas. The map's own tile colours live in `dungeon-canvas.js` — do not restate them |

### Layer 2 — type, space, shape, depth, motion

Shared by both realms. This is the *register*, and the register does not change
when the palette does.

**Fonts.** Three, and the split matters:

| Token | Use for |
|---|---|
| `--font-display` | Georgia-class serif. Nav, headings, the few numbers a player is proud of. This is where the fantasy register comes from |
| `--font-ui` | sans. Everything read rather than admired — body copy, form controls, log lines, dense panel text |
| `--font-mono` | anything read as data: coordinates, seeds, dice, damage, the HUD |

> This deliberately **reverses** the 2026-06-18 decision to strip all serif
> type. That decision was right that all-serif reads as "medieval brown"; the
> fix is serif for *display only*, never for body or data. Note that
> `theme.css`'s own header comment has described a warm candlelit Dark & Darker
> palette since it was written — the Cold Steel pass overwrote the values and
> left the intent.

**Type scale.** Eight steps, replacing 49 distinct `font-size` values (four of
which sat inside a 3px band).

`--text-2xs` 11px (tracked uppercase micro-labels only) · `--text-xs` 12px
(stat labels, chips, badges) · `--text-sm` 14px (dense body, log lines; the
prose floor) · `--text-base` 16px · `--text-lg` 18px (card titles) ·
`--text-xl` 22px (panel headings, display) · `--text-2xl` 28px (page headings,
display) · `--text-3xl` fluid (the landing hero, and nothing else).

Weights 400/500/600/700 only — `800` and `900` are retired. Tracking:
`--tracking-label` `0.14em` for uppercase micro-labels, `--tracking-display`
`0.06em` for serif headings, `--tracking-wide` for buttons. Small text is made
legible by tracking it, not by growing it — that is how the HUD stays dense.

**Space.** 4px base: `--space-1` … `--space-6`, `--space-8`
(4/8/12/16/24/32/48px). 6, 10, 15, 18 and 25px are retired.

**Shape.** `--radius: 0` is the default; you should need a reason to leave it.
`--radius-sm` 2px only where 0 collides with a focus ring. `--radius-pill` for
status dots and avatar rings — never buttons. 6, 8, 10, 12, 16 and 20px are
retired.

**Depth.** Panels do not float. Three tokens replace 113 distinct `box-shadow`
values: `--elev-flat` (`none`, the default for every panel), `--elev-overlay`
(modals, dropdowns, tooltips — and nothing else), `--inset-well` (sunken
tracks: HP bars, log wells, inputs). Glows carry state, not decoration:
`--glow-accent`, `--glow-danger`, `--glow-success` — all three at 14px/30%, so
no hover restates a blur radius or an alpha. (There is no `--glow-info`: its one
consumer, `.tactical-btn-info`, was deleted with the Party Stash button, and a
token with no consumer is just another thing to keep true.) `--focus-ring` is
the only focus treatment.

**Motion.** `--dur-fast` 120ms · `--dur` 200ms · `--dur-slow` 320ms · `--ease`.
All collapse to `0ms` under `prefers-reduced-motion`, handled once in
`tokens.css` — do not re-handle it per component.

**Layers.** `--z-base/raised/hud/dropdown/sticky/scrim/modal/tooltip/toast`,
aligned with Bootstrap's own scale so the two never fight. Never write a bare
`z-index: 9999`.

---

## Components

### The real problem, measured

Token consolidation makes the app *consistent*. It does not make it *good*.
Here is what the templates actually contain:

| | game screens | admin / other |
|---|---|---|
| stock `card` | 10 | 53 |
| `form-control` | 9 | 109 |
| `form-label` | 4 | 142 |
| `btn` (any) | 29 | 47 |
| `badge bg-*` | 8 | 126 |
| `progress` | **13** | 1 |
| `modal` | 23 | 39 |
| `table` | 0 | 72 |
| **custom vocabulary** | **54** | 21 |

Two conclusions, and they are not the obvious ones:

1. **The "Bootstrap demo" problem is concentrated in admin**, which the player
   never sees. On player-facing screens the custom vocabulary (54) already
   slightly outnumbers stock Bootstrap (63, and 23 of those are modals).
2. **So the reason it still feels generic is not headcount — it is that the
   custom components are shallow.** `.tactical-panel` is a rounded rectangle
   with a border and a hover lift. `.deploy-btn` is a
   `linear-gradient(to bottom, teal, gold)` with a leftover brown border and a
   hard-coded near-black text colour from a retired palette. Same silhouette as
   Bootstrap, different fill.

The fix is therefore **depth, not breadth**: give the custom components a real
identity, and replace the short list of stock components that carry the game
screens. That is roughly 63 elements across five types, not 106 cards.

### Designed replacements — what they should look like

Every one of these must work in **both realms from one definition**.

| Priority | Replaces | New component | What it looks like |
|---|---|---|---|
| 1 | `progress` ×13 | `.bar` + `.bar-fill` | A sunken track (`--inset-well`, `--surface-sunken`), square, 1px `--edge` outline, fill in `--hp`/`--mp`/`--xp` with no gradient and no rounding. The value in `--font-mono`, `--ink-strong`, sitting *beside* the bar, not inside it. Every HP/MP/XP bar in the game is currently stock Bootstrap — this is the highest-value single replacement. |
| 2 | `.tactical-panel` (rework) | `.panel` / `.panel.framed` | Flat `--surface`, hard edges, 1px `--edge`. **No hover lift, no glow, no gradient.** `.framed` adds the corner ticks and an `--edge-strong` hairline — and is used sparingly, because a frame is a statement. Header is a `--rule-tapered` under a tracked uppercase label, not a filled bar. |
| 3 | `.deploy-btn` → `.btn-primary` | one button family | Solid `--accent`, `--ink-on-accent`, square, uppercase + `--tracking-label`, no gradient. Secondary is text + hairline underline on hover — no box. Danger is `--danger` outline, filling only on hover. **One bright element per screen.** |
| 4 | `form-control` ×9 | `.field` | Sunken `--surface-sunken` with `--inset-well`, 1px `--edge`, `--radius-sm`, label above in tracked uppercase `--ink-muted`. Focus takes `--focus-ring` and an `--accent` border. See `auth.css` — already built. |
| 5 | `modal` ×23 | `.overlay` | `--surface-overlay`, the only thing allowed `--elev-overlay`, `--scrim` behind, hard edges, `.framed` treatment on the dialog. |
| 6 | `card` ×10 on game screens | use `.panel` | Delete the stock `card`/`card-body`/`card-header` markup on `adventure.html`, `dashboard.html`, `index.html`. |
| 7 | `badge bg-*` ×8 | `.chip` | Hairline outline + wash fill, tracked uppercase `--text-2xs`, square. Never a solid Bootstrap pill. |
| — | admin `card`/`table`/`form` ×376 | **leave them** | Explicitly functional-over-pretty. Lowest value in the project. |

### Current vocabulary — what to use today

| Situation | Class | Defined in |
|---|---|---|
| A game screen panel | `.tactical-panel` + `.panel-header` + `.panel-body` | `theme.css` |
| A character in a roster or party | `.operative-card` | `theme.css` |
| A character row in the dashboard roster | `.barracks-card` | `dashboard.css` |
| A frosted panel on admin / account | `.glass-card`, `.section-card` | `glass-theme.css` |
| Stat readouts | `.stat-card`, `.stat-block`, `.stat-grid` | `glass-theme.css`, `theme.css` |
| Screen-corner readout | `.tactical-hud` + `.hud-status` | `theme.css` |
| Page-level banner | `.alert-tactical` | `theme.css` |
| Primary action | `.deploy-btn` | `theme.css` |
| Secondary / destructive | `.tactical-btn-secondary` / `-danger` | `theme.css` |
| Admin / account buttons | `.btn-glass`, `-secondary`, `-danger` | `glass-theme.css` |

`glass-theme.css` is the **admin and account** dialect. Do not use `.glass-*`
on a player-facing screen or `.tactical-*` in the admin panel; keeping them
apart is what stops them merging into a third thing.

> **Known wart:** the primary game button is `.deploy-btn` while its siblings
> are `.tactical-btn-*`. It should be `.tactical-btn-primary`.

### Class identity

Twelve classes, one hue each: `--class-fighter` … `--class-warlock` in
`tokens.css`. `-bg`, `-fg` and `-border` are derived from that hue with
`color-mix()`, in `tokens.css`, for all twelve — not restated, not
hand-picked.

**Two** presentations consume the hue, not three:

| Presentation | Selector | Reads |
|---|---|---|
| Roster / party / combat badge | `.class-badge.<class>-badge` (`theme.css`) | the `-bg`/`-fg`/`-border` triplet |
| Equipment panel header strip | `.eq-class-header` + `.eq-class-bg-<class>` (`equipment.css`) | the hue directly, with its own mix ratios |

`.class-header-<class>` and `.border-<class>` **do not exist.** They were
defined only in `class-badges.css`, which class-colour-unification deleted, and
no markup ever emitted either class name — dead selectors for dead markup. An
earlier version of this section listed them as live; they are not, and a
`border-<class>` ring resolves for zero classes.

`.adventurer-badge` is the neutral fallback for a party member with no class
(`dungeon_api.py` falls back to the string `"Adventurer"`); it derives from
`--surface-raised` / `--ink` rather than a thirteenth hue.

Never hard-code a class colour at a call site — `tests/test_class_colour_tokens.py`
enforces it: all twelve classes have a hue and derived `-bg/-fg/-border`, the
derived values reference the hue rather than a hex literal, **no reachable
stylesheet sets a `.class-badge` or `.<class>-badge` colour outside
`var(--class-*)`, and none uses `!important`**, every hue clears 4.5:1 against
both realm grounds, and no two classes sit close in both hue and lightness.

No file is exempt. `tactical-theme.css` used to be — six pre-token class rules,
excused only while nothing `<link>`ed or `@import`ed it, with a companion test
that chased both routes to prove it. That file has since been **deleted**, and
the exemption went with it rather than being left as an empty set: a
reachability check with nothing to check passes on nothing and reads like a
guard. Every stylesheet on disk is now held to the rule whether it is reachable
or not, so a stray palette cannot go live by someone adding one `<link>`.

> **Known wart:** `combat.html` loads `glass-theme.css` in its `{% block head %}`,
> which breaks the admin-and-account boundary stated above. That is how six
> `!important` per-class gradients in `glass-theme.css` stayed live on `/combat`
> through two audit sweeps — a sweep that trusted this document would never open
> that file. The gradients are deleted; the stray `<link>` remains.

---

## Rules that keep this consistent

1. **One token file.** `tokens.css`. A second `:root` is the failure mode this
   document exists to prevent.
2. **Semantic names only.** `--surface-raised`, not `--slate-700`. If you can
   answer "what colour is it" but not "what is it for", it is misnamed.
3. **No component hard-codes a hue.** Test: does it look right in both realms?
4. **Derive, don't restate.** New shade of an existing role?
   `color-mix()`. New role? Add it to Layer 1 and write down what it means.
5. **Extend before you invent.** Check the tables above first.
6. **Page CSS styles the page, not the app.** No bare element selectors like
   `body { … }` in a page stylesheet — that leaks. Scope to the page root class.
7. **No `!important` in static CSS.** The generated theme layer already uses it
   and will win anyway; more only makes the cascade unreadable.
8. **Terminology is styling.** Player-facing copy uses D&D register — party,
   roster, provisions, delve, hoard, spoils. Not "Party Stash", not
   "operatives", not "deploy". CSS class names may lag; copy may not.
9. **Verify it renders.** Run the app and look. After template work:
   `python -m pytest tests/test_theme_css_variables.py tests/test_main_pages.py -q`
   (needs `TEST_DATABASE_URL` — see `docs/TESTING.md`).

---

## Reference implementation

`app/static/css/auth.css` (login + register) is the worked example: ~250 lines,
**zero** literal colours, radii, shadows or durations, realm-agnostic, and it
covers surfaces, edges, tapered rules, corner ticks, all five ink roles, focus,
the one-bright-element button, all four feedback states, and the type, space
and motion scales. Copy the shape of that file when in doubt.

---

## How the cascade works

`base.html` loads stylesheets in this order:

| # | Stylesheet | Role |
|---|---|---|
| 1 | Bootstrap 5.3.2 (CDN) | the base layer we override |
| 2 | `css/tokens.css` | **the design system** |
| 3 | `css/base.css`, `css/app.css`, `css/theme.css` | component CSS |
| 4 | `GET /api/admin/themes/active/css` | **the active Theme row, generated per request** |
| 5 | Bootstrap Icons (CDN) | |
| 6 | the page's `{% block head %}` | page CSS (e.g. `auth.css`) |

Two non-obvious consequences:

1. **The database wins.** Layer 4 is rendered from the active `Theme` row by
   `Theme.to_css_variables()` and loads after every static file, so it owns
   `--ui-*`. Nothing static can beat it. That is deliberate — it is how an
   admin re-skins without a deploy. It also means **the palette lives in the
   seed, not only in the CSS**: `tokens.css`'s Layer 0 values are fallbacks,
   and `app/seed_themes.py` carries the real ones.
2. **Custom properties resolve at use time.** A stylesheet at layer 3 may
   reference `var(--accent)` even though the winning value arrives at layer 4.

### Known defects in the theme layer

These block phase 2 and are the highest-value fixes in the project:

1. **The no-active-theme fallback is a different palette entirely.** When no
   `Theme` row is active, `app/routes/theme_api.py` serves a hardcoded block of
   Tailwind slate `#0f172a` + indigo `#6366f1` + violet `#8b5cf6` — **and it
   emits only `--bs-*`, no `--ui-*`.** The result, verified in the browser on a
   fresh database:

   ```
   --bs-primary : #6366f1   (indigo — every Bootstrap button, link, badge, navbar)
   --ui-accent  : #d9a441   (amber  — every panel, card, bar and badge)
   ```

   Two unrelated palettes on every page at once. `scripts/bootstrap_db.sh` does
   not call `seed-themes`, so this is the state of every fresh install.
   **Fix:** make the fallback mirror the seeded default and emit `--ui-*`; call
   `seed-themes` from bootstrap.

2. **Two column mappings are miscalibrated.** `to_css_variables()` maps
   `secondary → --ui-accent-hover` and `light → --ui-text-dim`, but the
   seeded "Cold Steel" row sets `secondary` to its *border* colour and `light`
   to its *body* colour. Under that theme, `--ui-text-dim` equals `--ui-text`
   — muted text is not muted at all. The new "Lamplight" row sets both
   correctly; "Cold Steel" and "Classic Dungeon" still need fixing.

3. **The theme layer `!important`s the cascade.** `to_css_variables()` emits
   `!important` on `body`'s background, on `a` colour, and on
   `.card, .glass-panel, .section-card`. Two visible consequences: the page
   background cannot go cold under `data-realm="dungeon"`, and every link is
   forced to the theme's link colour regardless of context. **Fix:** drop
   `!important` and let the static CSS carry those, or scope them.

---

## Migration plan

`tokens.css` exists, every page loads it, and the alias layer in `theme.css`
now resolves to the semantic tokens — so ~234 legacy `--dungeon-*` / `--adv-*`
call sites became realm-aware without being touched. Most stylesheets are
otherwise unconverted.

Phases are ordered by value-per-risk; each is independently shippable and
revertable.

| Phase | Scope | Blast radius |
|---|---|---|
| 0 ✅ | `tokens.css`, this document, `auth.css` as reference, `theme.css` alias rewire, the "Lamplight" seed | login + register redesigned; palette changes app-wide |
| 1 | Fix the three [theme-layer defects](#known-defects-in-the-theme-layer); call `seed-themes` from `bootstrap_db.sh` | **every page** — but it is what stops two palettes rendering at once |
| 2 | Delete the 1,422 lines of never-loaded CSS that remain; **link** the four orphans whose markup is live and unstyled | small; four screens visibly *improve* |
| 3 | Component layer, items 1–3 in [the table above](#designed-replacements--what-they-should-look-like): bars, panel, buttons | dashboard, adventure, combat — the highest-value visual work in the project |
| 4 | Delete the competing `:root` blocks in `base.css`, `app.css`, `adv-theme.css`, `footer.css`, `home.css` (`classes.css`'s is gone — the file was deleted in class-colour-unification, Task 2) | every page; do after phase 1, with a rendering pass per screen |
| 5 | Apply `data-realm="dungeon"` to the adventure and combat templates | those two screens go cold — the payoff for all of the above |
| 6 | The generated-CSS cohort (below): 340 of the 619 hex literals | all dashboard tabs; convert one file per commit |
| 7 | Component layer, items 4–7: fields, modals, remaining cards, chips | dashboard, adventure, combat |
| 8 | `glass-theme.css` (admin + account) | lowest value; functional-over-pretty |
| 9 | Guardrail: `scripts/check_css_tokens.py` pre-commit hook failing on a `:root` outside `tokens.css`, with a ratcheting raw-hex count in the style of the existing exception-handling ratchet | none — **this is what makes it stick** |

---

## Appendix: what the audit found

Measured 2026-07-27 against 27 files / 10,628 lines in `app/static/css/`.

- **10 `:root` blocks in 8 files**, 154 declarations, 96 unique properties,
  **38 declared in more than one file with different values.** `--bs-primary`
  three times, `--bs-danger` three times, the six `--class-*` triples twice
  with entirely different hues.
- **213 unique hex colours across 619 usages**, plus 829 `rgb()`/`rgba()`
  literals.
- **113 distinct `box-shadow` values**, 49 `font-size`, 101 `padding`, 27
  `transition`, 22 `border-radius`.
- **Two `--adv-*` namespaces with different meanings.** `adv-theme.css` uses it
  for a CRT palette (`--adv-ink`, `--adv-crt`); `app.css`/`theme.css` use it
  for semantic roles (`--adv-primary`, `--adv-surface`). Same prefix,
  unrelated systems.

### Why one gold

Four were in circulation; one survives.

| Colour | Uses | Verdict |
|---|---|---|
| `#f0a500` | 24, all `dashboard.css` | **Dead.** Every use is a `var(--adv-primary, #f0a500)` fallback from when the accent was amber. Renders only if the token system fails. |
| `#ffd700` | 11, achievements + skill tree | **Retire.** CSS `gold`, 13.8:1 on the ground — it glares and pulls the eye off whatever is actually interactive. |
| `#fbbf24` | 20, seven files | **Retire.** Tailwind `amber-400`, arrived with generated feature CSS. Near-max chroma, same glare. |
| **`#d9a441`** | `--ui-accent` | **Keep**, with `#e8b64c` reserved for `--coin-gold`. |

`#d9a441` is a token rather than a literal, so it is the only one the theme
system can drive. At 8.0:1 on `--surface` it leads the eye without shouting —
which matters when it is now the *accent* and therefore on screen constantly.
And it sits inside the tileset's own warm range (door timber `#9a6b35`,
down-stairs `#8f7a3f`), so it reads as part of the world rather than pasted
over it. Coin gold is deliberately a step brighter so treasure still pops on a
screen whose accent is already gold.

The same logic retires the other near-duplicates: greens `#4ade80`/`#48bb78`/
`#22c55e`/`#38a169` → `--success`; blues `#3498db`/`#64b4ff`/`#4299e1` →
`--info`, with `#6d9ed6` reserved for `--mp`; reds `#ef4444`/`#e74c3c`/
`#c0392b` → `--danger`.

### Orphans — 1,422 lines remaining, of 1,607 measured

1,607 was the 2026-07-27 measurement. `class-badges.css` (164) and
`classes.css` (21) have since been deleted, so **1,422 lines remain** — the
table below is annotated in the present tense and sums to that.

Four of these style markup that is **live in the app right now**:

| File | Lines | Status |
|---|---|---|
| `tactical-theme.css` | 688 | **Deleted** (2026-07-30). Superseded — `theme.css` carried a newer superset all along, since no template ever loaded this file. |
| `utilities.css` | 220 | Merged into `app.css`. Delete. (`wc -l` now reports **211** — a pre-existing 9-line drift from the 2026-07-27 count, not re-tabulated here so the column keeps summing to 1,422. Re-measure the whole column when phase 2 runs.) |
| `class-badges.css` | 164 | **Deleted** (class-colour-unification, Task 2). Superseded once `theme.css`'s badges were pointed at `tokens.css`. |
| `adv-theme.css` | 40 | Abandoned CRT palette. Delete. |
| `classes.css` | 21 | **Deleted** (class-colour-unification, Task 2). Superseded by the twelve-class palette in `tokens.css`, not `base.css` — `base.css`'s own six-class block was dropped in the same task. |
| `chat-widget.css` | 240 | **Live markup, unstyled.** `.mud-chat-widget` renders on the dashboard with only `dashboard.css`'s partial rules. |
| `hoard-ui.css` | 128 | **Live markup, unstyled.** `hoard.js` builds `.hoard-layout` / `.hoard-char-strip`; nothing styles them. |
| `dungeon-config.css` | 63 | **Live markup, unstyled.** `.difficulty-btn-group`, `.affix-grid`, `.fs-heroic-note` are in `dashboard.html`. |
| `footer.css` | 43 | **Live markup, unstyled.** `base.html` says "footer.css merged into app.css" — it was not. `app.css` has no footer rules, so `.footer-dark` on every page is unstyled. |

### The generated-CSS cohort

Eight files carry 340 of the 619 hex literals and share a fingerprint —
Tailwind default palette (`#fbbf24`, `#22c55e`, `#ef4444`, `#3b82f6`), 12px and
16px radii, `rgba(255,255,255,0.1)` frosted cards. They predate the palette
consolidation and were never swept: `party-management.css` (70 hexes),
`skill-tree.css` (65), `equipment.css` (51), `achievement-system.css` (38),
`trading-system.css` (30), `quest-system.css` (27),
`character-progression.css` (21), `loot-distribution.css` (12). All eight load
on the dashboard. That is phase 6.
