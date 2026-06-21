# Character Cards — Phase D: Combat Party Card Redesign

**Date:** 2026-06-21
**Status:** Design approved — ready for implementation planning.

## Context

Phases A-C built persisted status effects (`poison`, `regen_buff`), surfaced them
generically on the dashboard's roster cards (Phase C, with collapse/expand and a
`KNOWN_STATUS_EFFECTS` display-metadata lookup in `app/routes/dashboard_helpers.py`),
and this is the final phase in the series: combat's party cards.

Combat's party cards (`app/templates/combat.html`'s `party-member-template`,
rendered by `app/static/js/combat.js`'s `render()`) are already fairly minimal —
name/class/level + HP/MP bars, with the active character's card getting a highlight
(`border-warning`/`shadow`/`active-turn`) and the action panel re-parenting into it
each render. Two gaps remain, both logged as follow-ups from earlier phases:

1. **Buffs/debuffs exist in combat state but are never shown.** Each party member's
   in-memory snapshot (`mem`) already carries an `effects` list (loaded from
   persisted `CharacterStatusEffect` rows at session start, ticked per-turn) — this
   data flows to the client today but `combat.js` never renders it.
2. **The action panel's 3 spells are a shared static list, not per-character**
   (already logged in `docs/superpowers/TODO.md`'s Phase 4 section). The legacy
   Firebolt/Ice Shard/Lightning buttons are identical for every "spellcasting"
   character (gated by a crude class/INT heuristic, flat mana costs 5/6/8), while a
   real per-character skill system (unlocked skills, cooldown-gated, its own
   dynamically-rendered buttons via `renderSkillButtons`) already exists separately
   and is the only system that's genuinely per-character.

## Goals

1. Retire the legacy static spell panel's **UI** entirely — remove the
   Firebolt/Ice Shard/Lightning buttons and their class-heuristic gating from
   `combat.html`/`combat.js`. The real skill system becomes the only way to cast
   anything in combat.
2. Always show buff/debuff chips on every party card (not just the active one) —
   useful for seeing e.g. an ally is poisoned even when it's not their turn.
   Reuses Phase C's `.effect-chip`/`.effect-buff`/`.effect-debuff`/`.effect-neutral`
   CSS classes verbatim (already loaded on the combat page via `theme.css`, no
   duplication needed).
3. Auto-reveal a stat breakdown (ATK/DEF/SPD) on the active character's card only,
   driven purely by `state.active_index` on each render — no click handler, no
   manual toggle. Every other card stays at its bare HP/MP-bars-plus-chips summary.
4. Consolidate the buff/debuff display-metadata lookup (`KNOWN_STATUS_EFFECTS` +
   `describe_status_effect()`, introduced in Phase C inside `dashboard_helpers.py`)
   into `app/services/status_effects.py` — the natural shared home, since both
   `dashboard_helpers.py` and `combat_service.py` already import from there — so
   dashboard and combat use one canonical mapping instead of two.

## Non-goals

- No backend changes to `player_cast_spell`, `/api/combat/<id>/cast_spell`, or
  their existing tests (`test_combat_spell_outcomes.py`, `test_combat_actions.py`,
  `test_unconscious_actions.py`) — this is a UI-only removal. The route and service
  function remain reachable and fully tested; only the combat screen's buttons and
  client-side gating logic that invoke them are removed.
- No manual click-to-expand on combat cards (unlike Phase C's dashboard pattern) —
  purely automatic, tied to whose turn it is. Combat already fully re-renders on
  every state update, so a manually-expanded card would just be overwritten on the
  next render anyway.
- No changes to the monster panel, the skill-button system itself, or `GameConfig`.
- No mana-cost concept added to the real skill system — it stays cooldown-only,
  unchanged.

## Architecture

### Shared effect-display helper relocates to `status_effects.py`

`KNOWN_STATUS_EFFECTS` (the `{name: {icon, label, css_class}}` lookup) and
`describe_status_effect(effect: dict) -> dict` move from
`app/routes/dashboard_helpers.py` into `app/services/status_effects.py` (which
already owns all effect-handling logic — `EFFECT_START`, `apply_tick_decay`, etc.).
`dashboard_helpers.py` updates its import accordingly; its own call site and
behavior are unchanged, just re-pointed at the shared location. This is a pure
move, not a rewrite — same dict contents, same function body.

### Combat snapshot gains `effects_display`

`combat_service.py`'s player-snapshot builder (the function that already returns
each `mem` dict with `hp`/`max_hp`/`mana`/`mana_max`/`attack`/`defense`/`speed`/
`effects`, and which already loads `effects` from `CharacterStatusEffect` at
session start per Phase A/B's combat round-trip work) gains one more derived key:

```python
"effects_display": [describe_status_effect(e) for e in effects],
```

computed from the same `effects` list it already builds, immediately after that
list is assembled — no new query, no new round-trip, just a derived display-shape
view of data the function already has in hand. This flows to the client inside the
existing `party_snapshot_json` the same way every other `mem` field does — no new
API endpoint, no new socket event.

### Template: chip row + hidden-by-default stat block

`app/templates/combat.html`'s `party-member-template` gains two additions inside
the existing `.party-member` card, after the `stats-bars` block:

```html
<div class="effect-chips" data-field="effect-chips"></div>
<div class="stat-breakdown" data-field="stat-breakdown" hidden>
    <span data-field="atk">ATK 0</span>
    <span data-field="def">DEF 0</span>
    <span data-field="spd">SPD 0</span>
</div>
```

`.effect-chips`/`.effect-chip`/`.effect-buff`/`.effect-debuff`/`.effect-neutral`
are unchanged CSS class names from Phase C's `theme.css` rules — combat.html
already loads `theme.css` (via `{{ url_for('theme.get_active_theme_css') }}`)
alongside `combat.css`, so these rules apply with zero new CSS needed for the
chips. `.stat-breakdown` gets one small new combat.css rule (flex row, small font,
matching `.stats-bars`' existing sizing) since it has no Phase C equivalent.

The legacy spell button group (`cast_firebolt`/`cast_ice_shard`/`cast_lightning`,
currently three `<button>` elements inside `#combat-action-panel`) is deleted
entirely from the template's static action-panel markup; the Attack/Defend/Potion/
Flee buttons and the dynamically-rendered skill-button group are unaffected.

### JS: populate chips on every card, stat breakdown on the active card only

In `combat.js`'s `render()`, inside the existing `party.forEach(mem => { ... })`
loop (right after the existing HP/mana field updates, before
`partyContainer.appendChild(clone)`):

```js
// Buff/debuff chips -- always shown, every card, regardless of turn.
const chipsEl = clone.querySelector('[data-field="effect-chips"]');
if (chipsEl) {
    chipsEl.innerHTML = '';
    (mem.effects_display || []).forEach(eff => {
        const chip = document.createElement('span');
        chip.className = `effect-chip ${eff.css_class}`;
        chip.title = `${eff.label} — ${eff.remaining} remaining`;
        chip.textContent = `${eff.icon} ${eff.label} ×${eff.remaining}`;
        chipsEl.appendChild(chip);
    });
}

// Stat breakdown -- only the active character's card reveals it.
const statBlock = clone.querySelector('[data-field="stat-breakdown"]');
if (statBlock) {
    if (isActive) {
        statBlock.hidden = false;
        statBlock.querySelector('[data-field="atk"]').textContent = 'ATK ' + (mem.attack ?? 0);
        statBlock.querySelector('[data-field="def"]').textContent = 'DEF ' + (mem.defense ?? 0);
        statBlock.querySelector('[data-field="spd"]').textContent = 'SPD ' + (mem.speed ?? 0);
    } else {
        statBlock.hidden = true;
    }
}
```

`isActive` is the boolean `render()` already computes a few lines earlier (used
for the `border-warning`/`active-turn` class toggle) — reused directly, not
recomputed. Since `render()` already rebuilds `partyContainer.innerHTML` from
scratch every call, "auto-expand on that character's turn" falls out naturally:
whichever card is active this render gets `hidden = false`, every other card gets
`hidden = true`, and the next render (next turn) recomputes it for the new active
character with no transition/animation logic needed.

The legacy spell removal deletes: the `spellcastingClasses`/`canCastSpells`/
`meleeFocused`/`isPhysical` local variables, the
`if (action.startsWith('cast_') && !canCastSpells)` gating branch, and (since the
buttons themselves are gone from the template) the `data-mana-cost` mana-gating
branch becomes dead code for this button set specifically — it stays in place
unchanged since `renderSkillButtons`' own buttons don't use `data-mana-cost` and
nothing else currently sets that attribute, so it simply never fires post-removal;
no need to delete it defensively.

## Data Flow

```
combat render (every state update, every turn change)
  -> combat_service's party snapshot already includes mem.effects_display
     (computed once, server-side, alongside the existing effects list)
  -> combat.js render():
       for each party member:
         populate effect-chips from mem.effects_display (always)
         if this member is state.active_index's character:
           reveal stat-breakdown (ATK/DEF/SPD from mem.attack/defense/speed)
         else:
           keep stat-breakdown hidden
  -> action panel re-parents into the active card (unchanged existing behavior)
  -> renderSkillButtons populates per-character skill buttons (unchanged)
```

## Error Handling

- `describe_status_effect`'s existing fallback behavior (generic icon/label for
  unrecognized names) is inherited unchanged by this phase — no new error paths.
- `effects_display` defaults to `[]` if `effects` is empty, matching the existing
  `effects` list's own default; `(mem.effects_display || [])` in JS guards against
  an absent key on older cached state shapes.
- Removing the legacy spell buttons is a pure deletion — no error path to add.

## Testing

- Backend unit test: `combat_service`'s player-snapshot builder includes
  `effects_display` with the correct icon/label/css_class/remaining for a known
  effect (`poison`), a generic fallback for an unrecognized effect name, and an
  empty list when no effects are active — mirrors Phase C's
  `test_gear_party_payload.py` tests exactly, applied to the combat snapshot
  instead of the dashboard one.
- Regression check: existing combat tests that touch `_base_player_snapshot`
  output shape (if any assert on the full dict) still pass with the new key
  present.
- `node --check` on `combat.js` after the JS edits.
- Live Playwright verification against a real combat session (same pattern as
  Phase C's Task 5): start a fight, confirm chips render on a character with an
  active effect, confirm only the active character's card shows the stat
  breakdown, confirm it moves to the new active character's card after a turn
  passes, confirm the legacy spell buttons are gone from the DOM, confirm skill
  buttons (if any unlocked) still work, confirm no console errors.
- Full backend suite run after, confirming `test_combat_spell_outcomes.py`/
  `test_combat_actions.py`/`test_unconscious_actions.py` (the legacy spell
  backend's existing tests) still pass unmodified, since the backend itself is
  untouched.

## Migration

None — no schema change. `effects_display` is computed, not persisted.
