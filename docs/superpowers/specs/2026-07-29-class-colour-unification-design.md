# Class colours: one palette, twelve hues, one source

Direction from the project owner, 2026-07-29:

> "class colors has always been an issue and we need to hammer it down now; pick
> proper colors for classes so that theyre distinct and solidify those as SOT."

## Correction (2026-07-29, during Task 1)

Two claims below were wrong, found while verifying Task 1 in a browser. The
decisions stand; the diagnosis needed widening.

**There is a sixth source, and it is the one that actually paints badges.**
`theme.css:337-417` declares `.class-badge` plus twelve single-class rules
(`.fighter-badge` … `.warlock-badge`), **none of which reference
`var(--class-*)`** — every value is hardcoded. `theme.css` is loaded by
`base.html:16` on every page, so it, not `base.css`, is what a player actually
sees. There is even a comment at `theme.css:237-239` documenting a specificity
fight someone already had with these rules.

**So "six of the twelve classes have no colour outside the dungeon" is false.**
All twelve are coloured everywhere — by `theme.css`, hardcoded, in a palette
that agrees with none of the others. The real defect is not absence but
disagreement, and Task 1 could not have fixed it: pointing `tokens.css` at a new
palette changes nothing while a loaded stylesheet hardcodes past it.

**`class-badges.css` is a second orphan.** Loaded by no template
(`app.css:15` records it as "deferred"), and it is the one file that
*correctly* reads `--class-<name>-bg/-fg/-border`. The file that does the right
thing is the file nobody loads.

**A live markup bug, unrelated to the palette.** `adventure.html:118` emits
`class-badge-{{ class_lower }}` — a single class token, e.g.
`class-badge-fighter`. Every selector in the codebase is `.class-badge.fighter-badge`
or `.fighter-badge`, two tokens. So the party rail's class badge matches no rule
at all and renders unstyled. Introduced by `7dfcf1e` ("Fix HP/MP persistence
throughout dungeon and combat"), not by the recent HUD work.
`dashboard.html:112` and `combat.js:437` both emit the correct two-token form.

Consequences for the plan: Task 2 must additionally point `theme.css`'s twelve
badge rules at the derived tokens, delete `class-badges.css` as well as
`classes.css`, and fix `adventure.html:118`. Without the `theme.css` change,
"one source of truth" remains false no matter what else is deleted.

## What exists

Six sources. Measured, not estimated.

| # | source | covers | live? |
|---|---|---|---|
| 1 | `tokens.css` `--class-<name>` (12 single hues) | 12 | yes — `equipment.css` derives from it |
| 2 | `base.css:34+` `--class-<name>-bg/-fg/-border` | **6** | yes, every page |
| 3 | `classes.css:3+` — same 18 keys, **15 with different values** | 6 | **no — loaded by no template** |
| 4 | `config_api.CLASS_COLORS` → `/api/config/class_colors` → `adventure.js:112-148` | 12 | yes, `/adventure` only, with `!important` |
| 5 | `equipment.css` `.eq-class-bg-*` | 12 | yes — already derives from #1 |

Source 3 is an orphan. Sources 2 and 4 disagree with each other and with 1.

### What that costs the player

- **A Fighter's badge is `#7a3314` on the dashboard and `#301d0b` in the
  dungeon.** Same class, different colour per screen, because the runtime
  injector overrides the static values on `/adventure` and nowhere else.
- **Six of the twelve classes have no colour outside the dungeon.**
  `base.css` covers only fighter, rogue, mage, cleric, druid and ranger — which
  is precisely why `adventure.js:119` carries a hardcoded
  `predefined = new Set([...those six])` and `!important`-injects rules for the
  rest. A Barbarian, Bard, Monk, Paladin, Sorcerer or Warlock badge is unstyled
  on the dashboard.
- **`CLASS_COLORS["cleric"]` is `bg: #c3ccd1` with `fg: #f5f5f5`** — near-white
  text on near-white ground, about 1.2:1. Unreadable.
- The injector hides from grep: it builds `--class-${slug}-bg` by
  interpolation, so `--class-fighter-bg` never appears as a searchable string.

### Why the palette itself needed replacing

The `tokens.css` hues have the right instinct — muted, candlelit, made for this
palette — but they are not distinguishable, and three fail contrast. Measured
against both realm grounds (`#0f0c09` warm, `#0b0d11` cold):

| problem | detail |
|---|---|
| `bard` and `paladin` | **0° apart** — literally the same hue |
| `cleric`, `bard`, `paladin` | three golds within **6°** |
| `ranger` / `druid` | 22° apart, both desaturated green |
| `rogue` / `warlock` | 14° apart, both muted violet |
| `fighter` 3.95, `warlock` 3.76, `rogue` 4.31 | **below the 4.5:1 floor** — they fail as text |

Nine pairs sat under 25° of hue.

## Decided

### The palette

Twelve hues, solved numerically for spacing and contrast rather than picked by
eye. Every one clears **5.40:1** against both grounds — comfortably past the
4.5:1 floor — and no pair is close in both hue and lightness.

```css
--class-fighter:   #d1666d;  /* 356° — blade red                  */
--class-barbarian: #d57434;  /*  24° — burnt orange                */
--class-cleric:    #d8af4f;  /*  42° — lamplight gold              */
--class-paladin:   #e0dcb3;  /*  55° — pale luminous               */
--class-ranger:    #82964a;  /*  76° — olive                       */
--class-druid:     #5dac68;  /* 128° — leaf green                  */
--class-monk:      #44a796;  /* 170° — jade                        */
--class-mage:      #5c94cc;  /* 210° — steel blue                  */
--class-rogue:     #908cb5;  /* 246° — slate violet, low saturation */
--class-warlock:   #b179cd;  /* 280° — violet                      */
--class-bard:      #c964b5;  /* 312° — magenta                     */
--class-sorcerer:  #d16691;  /* 336° — rose                        */
```

| | before | after |
|---|---|---|
| worst contrast, either ground | 3.76 ✗ | **5.40** ✓ |
| closest pair by hue | **0°** | 13°, separated by 21 points of lightness |
| pairs under 25° hue | 9 | 4, every one lightness-separated |

Closest remaining neighbours, for the record: `cleric`/`paladin` 13° but 21
lightness apart (saturated gold against pale luminous); `barbarian`/`cleric`
18°; `fighter`/`sorcerer` 20°; `bard`/`sorcerer` 24°.

Two hues are unchanged on purpose. `cleric` stays gold because it *is* the
warm accent (`--ui-accent: #d9a441`) and the holy association is worth keeping;
`mage` stays steel blue for the same reason on the cold side.

`rogue` moves off violet to slate at low saturation — shadow reads better as
desaturation than as a hue, and it was colliding with `warlock`.

### One source

`tokens.css` holds the twelve hues **and derives** `-bg`, `-fg` and `-border`
from each via `color-mix()`, for all twelve classes. That is what makes it the
single source of truth: consumers keep reading the derived names they already
read, so nothing else has to change to get correct colour.

Deleted:

- `app/static/css/classes.css` — orphaned, never loaded, and disagreeing.
- `base.css`'s `--class-*-bg/-fg/-border` block — superseded.
- `config_api.CLASS_COLORS`, the `/api/config/class_colors` route, and
  `adventure.js`'s `fetchAndApplyClassColors` — a runtime injector that
  `!important`-overrode the token system for one screen.

That last deletion is the point. A palette that a script rewrites at runtime is
not a source of truth, and `!important` from injected `<style>` is unanswerable
from a stylesheet.

### What stays

Consumers are untouched: `class-badges.css`, `hoard.js:34`,
`equipment.css`'s `.eq-class-bg-*`, and the `border-<class>` / `class-badge`
markup in the templates. They read the derived custom properties, which now
resolve identically on every screen and for all twelve classes.

## Constraints

- **`--radius` is `0`; no `!important` in static CSS.** The injector's
  `!important` rules are being removed, not relocated.
- **Both realms.** Every value derives from the hue, so a class reads the same
  in town and underground. Verify rather than assume.
- **Never hard-code a class colour at a call site** (`DESIGN_SYSTEM.md`, rule
  "Class identity"). This work is what makes that rule enforceable.
- **Twelve, not six.** Any solution that leaves half the roster unstyled off
  `/adventure` has not fixed the problem.

## Out of scope

- The `--realm-*` palette, the rarity ramp, and the semantic role tokens.
- Class *icons* (`adventure.html:99-115` has a six-branch `if/elif` for class
  icons with a letter-avatar fallback — the same six-vs-twelve gap, in a
  different medium). Worth its own pass.
- `CLASS_MAP` and the class stat blocks in `config_api.py`, which are game
  data rather than colour and stay where they are.
