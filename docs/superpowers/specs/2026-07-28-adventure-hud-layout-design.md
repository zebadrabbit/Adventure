# Adventure screen: full-bleed map with a floating HUD

Design direction from the player, 2026-07-28:

> "we dont need a navbar at the top anymore at this point (maybe account access
> somewhere) but we dont need to read any of the links at the top. we can fill
> the screen with the map itself, float a log/combat log/chat log, float+static
> character frames above or the left side."

This is a layout spec only — no implementation. It belongs to the styling work
(`docs/DESIGN_SYSTEM.md`, the `styling` agent) and should be built on the token
system rather than beside it.

## Why now

The current screen does not fit on a 1366×768 laptop, and not marginally:

| element | px |
|---|---|
| browser chrome (Chrome/Linux) | ~110–140 |
| navbar | ~56 |
| panel body padding | 40 |
| panel header | ~50 |
| map canvas (`.map-fluid-fixed-height`, **fixed** `height: 512px`) | 512 |
| controls row — five stacked full-width buttons beside the log | ~220 |
| **total** | **~880–910** |

Usable viewport on that screen is roughly 630–660px, so the layout overflows by
around 250px: **the map and the movement controls cannot both be on screen**,
and the player scrolls mid-fight. On a 2K monitor the same layout is fine, which
is why this went unnoticed.

The direction below fixes the cause rather than shrinking parts: stop spending
vertical space on chrome that the player does not read, and let the map have the
frame.

## Target

- **Floor: 1366×768.** Everything essential visible without scrolling.
- Scales up cleanly to 2560×1440 — the map gets bigger, the HUD does not.
- Not a mobile design. Narrow viewports can keep the current stacked layout.

## Layout

```
┌──────────────────────────────────────────────────────────┐
│ ░░░ map fills the frame ░░░░░░░░░░░░░░░░░░░  [⚙ account] │  ← corner affordance
│ ┌──────────┐                                             │
│ │ party    │                                  [minimap]  │
│ │ frames   │                                             │
│ │ (static) │                                             │
│ │  ×4      │                                             │
│ └──────────┘                                             │
│                                    ┌────────────────────┐│
│  [move pad]                        │ log  ▸ adv/cbt/chat││  ← floating, collapsible
│                                    └────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

- **Map**: full bleed, sized from the viewport. The canvas already resizes its
  backing store to the CSS box × devicePixelRatio, so it will sharpen rather
  than stretch — tiles stay crisp.
- **Party frames**: left edge, static (not draggable). Always visible, always
  live — HP/MP/status per character, which is also what the combat overhaul
  needs. Four frames at ~90px each ≈ 360px, comfortable at 768. The frames are
  the top layer of the character panel work — clicking one opens that
  character's paper doll. See
  [2026-07-28-character-panel-redesign.md](2026-07-28-character-panel-redesign.md).
- **Log**: floating panel, bottom-right, collapsible, with tabs for
  adventure / combat / chat. Solves the "log window is restrictive" complaint
  and gives looting somewhere to live that is not a wall of text.
- **Account**: a single icon affordance in a corner. No link bar.
- **Existing overlays** (`#hotkeys-panel`, `.map-controls`) are already
  absolutely positioned over the canvas — the pattern is proven, this extends
  it.

## Constraints the implementation must respect

1. **The canvas owns pointer input.** It binds `mousedown`, `mousemove`,
   `wheel`, and three `touch*` handlers for pan and zoom
   (`dungeon-canvas.js:182-199`). Every floating panel must stop propagation on
   its own events, or dragging a log panel will pan the map underneath it and
   scrolling the log will zoom.
2. **Overlays must not cover the player.** The camera centres on the party;
   panels sitting over that spot make the game unplayable. Reserve the centre,
   or inset the camera target by the occupied margins.
3. **`.map-fluid-fixed-height` is declared twice** — `app.css:273` and
   `utilities.css:41`, both `512px`, different borders. Whichever loads last
   wins silently. Collapse to one token-driven rule as part of this work.
4. **Keyboard shortcuts already exist** (WASD/arrows, Space, C, E, H, I, Esc).
   A focused log or chat input must not swallow movement keys — the current
   handler only guards `INPUT`/`TEXTAREA`.
5. **The map must never be shorter than it is wide by much** — the dungeon is
   75×75; an extremely letterboxed viewport makes navigation worse, not better.

## Decided: the navbar (2026-07-28)

> "once you ENTER THE DUNGEON youre in the game, the game is the focus, the
> adventure is more important than 'Getting Started' 'Items' and 'Rules', now i
> do think there should be an account anchor in the top-right and we can provide
> essential items (account config, etc.)."

**Drop the informational links; keep an account anchor top-right.**

The four links in question are `#getting-started`, `#classes`, `#items` and
`#rules` — anchors into sections of the *landing page*. On `/adventure` no such
elements exist, so they already scroll nowhere. They are not merely
out of place in a dungeon; they are dead there.

What stays, in a single top-right anchor: the existing user dropdown, which
already carries Dashboard, Profile, Settings, Admin and Themes (for admins), and
Logout. Nothing new needs designing — it needs relocating and shrinking to an
avatar/gear affordance.

What must **not** move into that menu: **Extract** and **Hearth**. They are game
actions with consequences (banking the run; abandoning it), not account
settings, and burying them costs a player their haul. They belong with the other
game controls.

Implementation note: the navbar lives in `base.html`, which every page inherits
through `dashboard_base.html`, and it is *not* wrapped in a block. Suppressing it
for one screen needs either a new block around the header or a context flag
(e.g. `chrome="minimal"`) that `base.html` honours — the latter is likely
cleaner, since the combat screen will want the same treatment.

## Decided: layout questions (2026-07-28)

- **Party frames go on the left edge.** Common, and it spends horizontal space,
  which is the axis this laptop has to spare.
- **No on-screen movement pad.** WASD and the arrows are already bound; the pad
  was costing vertical space on the scarce axis to duplicate a working control.
  Removing it also reclaims part of the controls row.
- **Combat is its own screen**, not this frame with the scene swapped. It is an
  abstraction away from the map: the tile the party stands on is magnified into
  a battlefield. Because it is separate, it owns its own layout entirely rather
  than inheriting this one. See
  [2026-07-28-tactical-combat-design.md](2026-07-28-tactical-combat-design.md).

## Open questions

1. **Where does the minimap live** once the map is full-bleed? It is currently
   drawn into the canvas at the top-right; that corner is now the account
   anchor.
2. **What happens on a narrow viewport?** The stacked layout is the fallback,
   but the party frames and floating log need a defined behaviour rather than
   overlapping.
