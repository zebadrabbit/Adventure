# Character Cards — Phase C: Dashboard Roster Card Redesign

**Date:** 2026-06-21
**Status:** Design approved — ready for implementation planning.

## Context

Phase A (status-effect foundation) and Phase B (new effect sources: regen-over-time
potion, camp's well-rested buff) gave the game persistent, per-character buffs/debuffs
(`CharacterStatusEffect` rows: `poison`, `regen_buff`, more later). None of that is
visible anywhere in the UI yet — the dashboard's roster cards
(`app/templates/dashboard.html`'s `.operative-card` block, ~line 230-384) show only
static attributes (XP, the 8-stat grid, coins, inventory) and have no concept of
current HP/MP as a fraction of max, let alone active effects.

Today every card is permanently "fully expanded" — name/class/level header, XP bar,
full stat grid, coin/inventory blocks, and footer action buttons (EQUIP/BAG/SKILLS/
DISMISS, plus the SELECT checkbox) are all visible at once, for every character, all
the time. This phase reworks that into a collapsed-by-default summary that expands in
place on click, and surfaces buffs/debuffs for the first time.

This was explored with the visual companion; two layout decisions were validated
there:
- **Independent multi-expand** (not accordion-style) — any number of cards can be
  expanded simultaneously, so two characters can be compared side by side.
- **Whole-card click target** (not a dedicated caret button) — bigger touch target,
  better for low-dexterity or mobile/tablet use; the existing SELECT checkbox-label
  and footer action buttons need `stopPropagation()` so clicking them doesn't also
  toggle expand.

## Goals

1. Collapsed-by-default roster card: name/class/level header, an HP bar and an MP bar
   (current/max, not just a bare current-value number like today), and a row of
   buff/debuff chips (icon + short label, hover/title text with the full description).
2. Clicking anywhere on a collapsed card expands it in place to show everything
   today's card already shows (XP bar + stat-point button, full 8-stat grid, coins,
   inventory list, EQUIP/BAG/SKILLS/DISMISS buttons, SELECT control) **plus** a new
   "Active Effects" detail block (one line per effect: icon, name, magnitude, ticks/
   turns remaining).
3. Any number of cards can be expanded at once; each toggles independently.
4. Buff/debuff data and HP/MP max are computed server-side and baked into the
   existing one-time page render — no new live-polling or websocket channel.
5. Buff/debuff rendering is **generic**: a small `{name: {icon, label, css_class}}`
   lookup table with a sane fallback (generic icon + the raw effect name) for any
   `CharacterStatusEffect` name not yet in the table, so a future Phase B-style
   addition doesn't require a template change to become visible.

## Non-goals

- No live/real-time updates (polling, websockets) — buffs/debuffs and HP/MP refresh
  only on next page load, same cadence as everything else on this page today.
- No new quick-action buttons (e.g. a one-click "use potion" on the card) — the
  existing BAG modal's per-potion "Use" button already covers this; expanded cards
  keep exactly the action buttons they have today, unchanged.
- No expand/collapse persistence across reload (e.g. localStorage) — every page load
  starts fully collapsed, matching the page's existing one-shot render model.
- No changes to the party-selection system, the Hub Actions tabs, or any other
  dashboard section — scoped entirely to the `.operative-card` roster grid.
- No changes to Phase D (combat party cards) — separate, later phase.

## Architecture

### Server-side: expose HP/MP max + active effects

`app/routes/dashboard_helpers.py::serialize_character_list` currently backfills `hp`/
`mana` (current values only) into each character's `stats` dict but never computes or
exposes `hp_max`/`mana_max`, and never queries `CharacterStatusEffect` at all. Extend
the per-character loop to add two new keys to each serialized dict:

```python
from app.services.character_stats import compute_hp_mana_max
from app.models import CharacterStatusEffect

# ... inside the existing per-character loop, after stats are normalized:
hp_max, mana_max = compute_hp_mana_max(c)

effects = [
    {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
    for row in CharacterStatusEffect.query.filter_by(character_id=c.id).all()
]

out.append({
    # ...existing keys unchanged...
    "hp_max": hp_max,
    "mana_max": mana_max,
    "effects": effects,
})
```

`compute_hp_mana_max` already exists (added in Phase A) and is the single source of
truth for max HP/mana used by the persisted decay path — reusing it here means the
dashboard's bars agree with what combat/decay actually enforce, not a fourth
independent copy of the HP/mana formula. This mirrors the existing, deliberate
Phase-A tradeoff (three independent formula copies already exist; this would be a
fourth call site for the *shared* helper, not a new formula) — acceptable, not worth
a refactor here.

### Known-effects lookup table

A new small module-level constant, colocated with the template helpers since it's
purely a display concern:

```python
# app/routes/dashboard_helpers.py
KNOWN_STATUS_EFFECTS = {
    "poison": {"icon": "☠", "label": "Poison", "css_class": "effect-debuff"},
    "regen_buff": {"icon": "✨", "label": "Well-Rested", "css_class": "effect-buff"},
}

def describe_status_effect(effect: dict) -> dict:
    """Return display metadata for one CharacterStatusEffect dict, with a
    generic fallback for names not in KNOWN_STATUS_EFFECTS."""
    meta = KNOWN_STATUS_EFFECTS.get(effect["name"], {"icon": "◆", "label": effect["name"], "css_class": "effect-neutral"})
    return {**meta, "remaining": effect["remaining"]}
```

Called from the template (Jinja can call plain functions passed into context, or this
can be pre-computed into each character's serialized dict as
`"effects_display": [describe_status_effect(e) for e in effects]` inside
`serialize_character_list` — preferred, since it keeps the template free of Python
logic beyond iteration, consistent with how `inventory`/`coins` are already
pre-shaped before reaching the template).

### Template: collapsed summary + expanded detail

`app/templates/dashboard.html`'s `.operative-card` gets a new wrapping structure:

```html
<div class="operative-card ..." data-id="{{ c.id }}">
    <div class="operative-summary"> <!-- always visible, the new click target -->
        <div class="operative-header"> <!-- unchanged: name/class/level -->
        <div class="hp-mp-bars">
            <div class="resource-bar-track">
                <span class="bar-label">HP {{ c.stats.hp }}/{{ c.hp_max }}</span>
                <div class="bar-track"><div class="bar-fill hp-fill" data-pct="{{ ... }}"></div></div>
            </div>
            <div class="resource-bar-track">
                <span class="bar-label">MP {{ c.stats.mana }}/{{ c.mana_max }}</span>
                <div class="bar-track"><div class="bar-fill mp-fill" data-pct="{{ ... }}"></div></div>
            </div>
        </div>
        {% if c.effects_display %}
        <div class="effect-chips">
            {% for eff in c.effects_display %}
            <span class="effect-chip {{ eff.css_class }}" title="{{ eff.label }} — {{ eff.remaining }} remaining">
                {{ eff.icon }} {{ eff.label }} ×{{ eff.remaining }}
            </span>
            {% endfor %}
        </div>
        {% endif %}
    </div>

    <div class="operative-detail" hidden> <!-- everything that exists today -->
        <!-- XP bar + stat-points button (unchanged) -->
        <!-- NEW: Active Effects detail block, one line per effect -->
        <!-- stat-block / resource-bar (coins) / inventory (unchanged) -->
        <!-- operative-footer: EQUIP/BAG/SKILLS/DISMISS/SELECT (unchanged) -->
    </div>
</div>
```

`data-pct` follows the existing `data-xp-pct` pattern already used for the XP bar
(`dashboard.html`'s inline-style extraction work from an earlier session moved that
off a literal `style="width:...%"` onto a data attribute applied by JS on load) —
HP/MP bars use the same convention for consistency and to avoid reintroducing an
inline-style violation the project's pre-commit hook already guards against.

The "Active Effects" detail block (inside `.operative-detail`, only meaningful when
expanded) repeats the same `c.effects_display` list with one line per effect
including the raw magnitude from `effect.data` where present (e.g. poison's
`damage`, regen_buff's `hp_mult`/`mp_mult`) — the collapsed chips show name + ticks
only; the expanded block adds the numeric detail collapsed chips don't have room for.

### Client-side: toggle behavior

New logic in `app/static/js/dashboard-operative-cards.js` (the existing file already
owns operative-card behavior — select-button sync, gear-count badges):

```js
document.querySelectorAll('.operative-summary').forEach(summary => {
    summary.addEventListener('click', (e) => {
        // Ignore clicks that originated on the SELECT label or a footer button --
        // those have their own handlers and must not also toggle expand.
        if (e.target.closest('.select-operative-label, .operative-footer, .btn-allocate-stats')) return;
        const card = summary.closest('.operative-card');
        const detail = card.querySelector('.operative-detail');
        detail.hidden = !detail.hidden;
        card.classList.toggle('expanded', !detail.hidden);
    });
});
```

Each card's `.operative-detail` is independently toggled (no shared "currently
expanded" state, no accordion collapsing of siblings) — directly satisfies the
multi-expand decision from the visual companion session. `hidden` (not a CSS class
alone) is used so the detail content is removed from the accessibility tree and tab
order while collapsed, not just visually hidden.

Note: the SELECT checkbox/label and footer buttons live *inside* `.operative-detail`
today (footer is part of the "everything" that only shows when expanded per the
approved design), so they're naturally inert while collapsed — no separate
`stopPropagation()` plumbing is actually needed for them once they're nested inside
the initially-`hidden` `.operative-detail`. The guard in the click handler above is
defensive (e.g. if a future change moves the SELECT control above the fold), not
load-bearing under the current DOM structure — keep it for safety, but it isn't doing
the heavy lifting the visual-companion conversation assumed.

### CSS

New rules added to `app/static/css/theme.css` (where `.operative-card` already
lives): `.hp-mp-bars`, `.bar-track`/`.bar-fill` (HP red-ish, MP blue-ish, reusing the
project's existing `color-mix()`-on-`--ui-*`-token convention from the Cold Steel
theming passes, not new literal colors), `.effect-chips`/`.effect-chip` (small
pill-shaped badges) with three variants (`.effect-buff`, `.effect-debuff`,
`.effect-neutral`) for color-coding, and `.operative-detail[hidden]` (relies on the
native `hidden` attribute, no extra CSS needed for the collapse itself).

## Data Flow

```
dashboard page load
  -> serialize_character_list(user_id)
       -> existing stats/coins/inventory/gear shaping (unchanged)
       -> NEW: compute_hp_mana_max(c) -> hp_max, mana_max
       -> NEW: query CharacterStatusEffect rows for c.id -> effects_display via
          describe_status_effect()
  -> dashboard.html renders one .operative-card per character:
       .operative-summary (always visible): header, HP/MP bars, effect chips
       .operative-detail (hidden by default): XP/stats/coins/inventory/footer +
          new Active Effects block
  -> dashboard-operative-cards.js: click on .operative-summary toggles that card's
     .operative-detail[hidden], independently per card
```

## Error Handling

- The `CharacterStatusEffect` query and `compute_hp_mana_max` call follow the
  existing module's defensive style (the surrounding loop already wraps risky JSON
  parsing in try/except) — a failure to load effects for one character should not
  break the whole page; default to an empty `effects_display` list on error.
- `describe_status_effect`'s fallback path means a malformed or unrecognized effect
  name never raises — worst case it renders a generic chip with the raw name.

## Testing

This is primarily a template/CSS/JS change (no JS test infra exists in this repo, per
established project convention); the testable surface is `serialize_character_list`'s
new output shape:

- Unit test: a character with an active `poison` row appears in `effects_display`
  with `icon/label/css_class` from `KNOWN_STATUS_EFFECTS` and the correct `remaining`.
- Unit test: a character with an effect name not in `KNOWN_STATUS_EFFECTS` falls back
  to the generic icon/label (the raw name) instead of raising.
- Unit test: a character with no active effects gets an empty `effects_display` list
  (not absent key — template iterates `c.effects_display` unconditionally).
- Unit test: `hp_max`/`mana_max` match `compute_hp_mana_max(c)`'s own output for a
  representative character (guards against a future accidental second formula).
- Full backend suite run after implementation, per existing project convention.
- Manual/live-browser verification required for the actual collapse/expand
  interaction and visual layout (per the project's established pattern for
  template/CSS/JS-only changes — no automated coverage exists for this class of
  change): expand a card, confirm detail shows, confirm SELECT/footer buttons still
  work without toggling collapse, confirm a second card can be expanded
  independently, confirm a character with no effects shows no chip row at all
  (not an empty one).

## Migration

None — `CharacterStatusEffect` table already exists (Phase A); this phase only reads
it, adds no columns, and seeds nothing new.
