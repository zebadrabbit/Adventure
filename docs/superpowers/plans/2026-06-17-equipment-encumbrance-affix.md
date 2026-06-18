# Equipment Panel: Encumbrance Bar + Affix Breakdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the already-computed-server-side encumbrance state and real gear-instance affixes in the Equipment modal, replacing the tooltip module's heuristic affix guessing with real data.

**Architecture:** Frontend-only change across two existing JS modules (`equipment.js`, `tooltips.js`) plus additive CSS. No backend changes — `ch.encumbrance` and each gear instance's `affixes` array are already present in `/api/characters/state` responses; we're just reading and rendering data that already exists.

**Tech Stack:** Vanilla JS (IIFE modules), Bootstrap 5 (`.progress`/`.progress-bar`), existing `MUDTooltips` shared module.

## Global Constraints
- No backend/Python changes; no new endpoints; no DB/schema changes.
- Reuse Bootstrap's `.progress`/`.progress-bar` for the encumbrance bar — do not invent a new bar widget or redefine `.durability-bar`/`.durability-fill` (those are a different per-item concept on a different scale).
- Malformed/missing affix or encumbrance data must degrade gracefully (section omitted), never throw or render "undefined"/"NaN".
- Manual verification only (no JS test runner in this repo) — use the `run`/`verify` skills against a live browser session.

---

### Task 1: Real-affix tooltips in `tooltips.js`

**Files:**
- Modify: `app/static/js/tooltips.js:289-318` (`effectsText`, `formatEffect`)

**Interfaces:**
- Consumes: item objects already passed into `MUDTooltips.itemHtml(it)` / `attrForItem(it)` everywhere they're called today (bag items, equipped gear, trading/hoard cards). A procedural gear instance has an `affixes: [{stat: string, val: number}, ...]` array (see `app/loot/generator.py:322`); a legacy `Item` has an `effects: {stat: number}` dict (see `app/routes/inventory_api.py::_serialize_item`).
- Produces: `effectsText(it)` returns a space-joined string of `"+N STAT"` tokens, preferring real `it.affixes`, then `it.effects`, then the existing heuristic `inferEffects(it)` fallback — used by `itemHtml(it)` (no signature change, so no other file needs touching).

This task is a pure data-source fix to an existing, already-shared function — every tooltip in the app (equipment, bag, trading, hoard) is exercised by this one change, so it's tested broadly even though only one file changes.

- [ ] **Step 1: Read current `effectsText`/`formatEffect` to confirm exact text to replace**

Run: `sed -n '289,318p' app/static/js/tooltips.js`

Expected output (current code, for reference — do not skip this read, line numbers may have drifted slightly):
```javascript
  // --- Effects inference helpers ---
  function effectsText(it) {
    if (it && it.effects && typeof it.effects === 'object' && Object.keys(it.effects).length) {
      return Object.entries(it.effects).map(([k, v]) => formatEffect(k, v)).join(' ');
    }
    // Fallback inference (mirror server logic heuristics)
    return inferEffects(it).map(e => formatEffect(e.stat, e.delta)).join(' ');
  }
  function formatEffect(stat, delta) {
    const sign = delta >= 0 ? '+' : '';
    return `${sign}${delta} ${stat.toUpperCase()}`;
  }
```

- [ ] **Step 2: Replace `effectsText` and `formatEffect` with affix-aware versions**

Replace the block found in Step 1 with:
```javascript
  // --- Effects inference helpers ---
  function effectsText(it) {
    if (it && Array.isArray(it.affixes) && it.affixes.length) {
      const tokens = it.affixes
        .filter(a => a && a.stat && typeof a.val === 'number')
        .map(a => formatEffect(a.stat, a.val));
      if (tokens.length) return tokens.join(' ');
    }
    if (it && it.effects && typeof it.effects === 'object' && Object.keys(it.effects).length) {
      return Object.entries(it.effects).map(([k, v]) => formatEffect(k, v)).join(' ');
    }
    // Fallback inference (mirror server logic heuristics)
    return inferEffects(it).map(e => formatEffect(e.stat, e.delta)).join(' ');
  }
  function formatEffect(stat, delta) {
    const sign = delta >= 0 ? '+' : '';
    const num = Number.isInteger(delta) ? delta : Math.round(delta * 10) / 10;
    return `${sign}${num} ${stat.toUpperCase()}`;
  }
```

- [ ] **Step 3: Sanity-check with node (no browser needed for a pure-function check)**

Run:
```bash
node -e "
function formatEffect(stat, delta) {
  const sign = delta >= 0 ? '+' : '';
  const num = Number.isInteger(delta) ? delta : Math.round(delta * 10) / 10;
  return \`\${sign}\${num} \${stat.toUpperCase()}\`;
}
function effectsText(it) {
  if (it && Array.isArray(it.affixes) && it.affixes.length) {
    const tokens = it.affixes.filter(a => a && a.stat && typeof a.val === 'number').map(a => formatEffect(a.stat, a.val));
    if (tokens.length) return tokens.join(' ');
  }
  if (it && it.effects && typeof it.effects === 'object' && Object.keys(it.effects).length) {
    return Object.entries(it.effects).map(([k, v]) => formatEffect(k, v)).join(' ');
  }
  return '';
}
console.log(effectsText({affixes: [{stat: 'str', val: 2.5}, {stat: 'dex', val: -1}]}));
console.log(effectsText({effects: {con: 3}}));
console.log(effectsText({}));
"
```
Expected output:
```
+2.5 STR -1 DEX
+3 CON

```
(last line is empty string for the no-data case — confirms no crash, no fallback heuristic invoked since `inferEffects` isn't defined in this snippet, matching real behavior would fall back further but we're only checking the affix/effects branches here)

- [ ] **Step 4: Commit**

```bash
git add app/static/js/tooltips.js
git commit -m "fix(tooltips): render real gear-instance affixes instead of guessing"
```

---

### Task 2: Encumbrance bar in the Equipment panel

**Files:**
- Modify: `app/static/js/equipment.js:89-105` (`renderCharPanel`)
- Modify: `app/static/css/equipment.css` (append new rules after the Durability Indicator section, i.e. after line ~479)

**Interfaces:**
- Consumes: `ch.encumbrance` from character-state payloads — shape `{weight: number, capacity: number, status: "normal"|"encumbered"|"blocked", dex_penalty: number, hard_cap_pct: number}` (see `app/inventory/utils.py::encumbrance_state`). Already present on every `ch` object passed into `renderCharPanel(ch)` today; no fetch changes needed.
- Produces: a `.encumbrance-bar` block prepended inside the Equipment column's `<div class="col-md-6">` in the HTML `renderCharPanel` returns. No other function signature changes.

- [ ] **Step 1: Read the current `renderCharPanel` to confirm exact text to replace**

Run: `sed -n '89,105p' app/static/js/equipment.js`

Expected (for reference):
```javascript
  function renderCharPanel(ch) {
    const gear = ch.gear || {};
    const slots = ['weapon', 'offhand', 'head', 'chest', 'legs', 'boots', 'gloves', 'ring1', 'ring2', 'amulet'];
    let html = `<div class="row g-3" data-char-id="${ch.id}">
      <div class="col-md-6">
        <h6 class="text-muted">Equipment</h6>
        ${slots.map(s => slotBox(s, gear[s])).join('')}
      </div>
      <div class="col-md-6">
        <h6 class="text-muted">Bags</h6>
        <div class="list-group" id="bag-list">
          ${ch.bag.map(bagItem).join('') || '<div class="text-muted">No items</div>'}
        </div>
      </div>
    </div>`;
    return html;
  }
```

- [ ] **Step 2: Add an `encumbranceBarHtml` helper function**

Insert this new function immediately above `function renderCharPanel(ch) {` (i.e. right after the closing `}` of `buildTooltip` at line 87):

```javascript
  function encumbranceBarHtml(enc) {
    if (!enc || typeof enc.weight !== 'number' || typeof enc.capacity !== 'number') return '';
    const pct = enc.capacity > 0 ? Math.min(100, (enc.weight / enc.capacity) * 100) : 0;
    const barClass = enc.status === 'blocked' ? 'bg-danger' : (enc.status === 'encumbered' ? 'bg-warning' : 'bg-success');
    const textClass = enc.status === 'blocked' ? 'text-danger' : (enc.status === 'encumbered' ? 'text-warning' : '');
    const statusLabel = enc.status === 'blocked' ? 'Overloaded — cannot carry more' : (enc.status === 'encumbered' ? 'Encumbered' : '');
    const penaltyNote = (enc.status !== 'normal' && enc.dex_penalty) ? ` (-${enc.dex_penalty} DEX)` : '';
    return `
      <div class="encumbrance-bar mb-2" data-status="${esc(enc.status)}">
        <div class="d-flex justify-content-between small">
          <span>Carry Weight</span>
          <span>${enc.weight.toFixed(1)} / ${enc.capacity.toFixed(1)}</span>
        </div>
        <div class="progress" style="height:6px;">
          <div class="progress-bar ${barClass}" style="width:${pct}%"></div>
        </div>
        ${statusLabel ? `<div class="small ${textClass} mt-1">${statusLabel}${penaltyNote}</div>` : ''}
      </div>`;
  }
```

- [ ] **Step 3: Wire the helper into `renderCharPanel` and add the gear-bonus summary line**

Replace the `renderCharPanel` function found in Step 1 with:
```javascript
  function gearBonusSummary(gear) {
    const totals = {};
    Object.values(gear || {}).forEach(inst => {
      if (!inst) return;
      const affixes = Array.isArray(inst.affixes) ? inst.affixes
        : (inst.effects && typeof inst.effects === 'object'
            ? Object.entries(inst.effects).map(([stat, val]) => ({ stat, val }))
            : []);
      affixes.forEach(a => {
        if (!a || !a.stat || typeof a.val !== 'number') return;
        totals[a.stat] = (totals[a.stat] || 0) + a.val;
      });
    });
    const parts = Object.entries(totals)
      .filter(([, v]) => v !== 0)
      .map(([stat, v]) => {
        const num = Number.isInteger(v) ? v : Math.round(v * 10) / 10;
        return `${num >= 0 ? '+' : ''}${num} ${stat.toUpperCase()}`;
      });
    return parts.join(', ');
  }

  function renderCharPanel(ch) {
    const gear = ch.gear || {};
    const slots = ['weapon', 'offhand', 'head', 'chest', 'legs', 'boots', 'gloves', 'ring1', 'ring2', 'amulet'];
    const bonusSummary = gearBonusSummary(gear);
    let html = `<div class="row g-3" data-char-id="${ch.id}">
      <div class="col-md-6">
        <h6 class="text-muted">Equipment</h6>
        ${bonusSummary ? `<div class="small text-info mb-2">Gear bonus: ${esc(bonusSummary)}</div>` : ''}
        ${encumbranceBarHtml(ch.encumbrance)}
        ${slots.map(s => slotBox(s, gear[s])).join('')}
      </div>
      <div class="col-md-6">
        <h6 class="text-muted">Bags</h6>
        <div class="list-group" id="bag-list">
          ${ch.bag.map(bagItem).join('') || '<div class="text-muted">No items</div>'}
        </div>
      </div>
    </div>`;
    return html;
  }
```

- [ ] **Step 4: Append CSS for `.encumbrance-bar`**

Append to `app/static/css/equipment.css` (after the Durability Indicator block, e.g. after the closing rule around line 479 — check with `tail -20 app/static/css/equipment.css` first to confirm you're appending at end of file, not mid-file):

```css

/* Encumbrance Indicator */
.encumbrance-bar {
    font-size: 0.8rem;
}

.encumbrance-bar .progress {
    background: rgba(100, 100, 120, 0.3);
}
```

- [ ] **Step 5: Smoke-check the file parses (no syntax errors)**

Run: `node --check app/static/js/equipment.js`
Expected: no output (exit code 0 means valid syntax).

- [ ] **Step 6: Commit**

```bash
git add app/static/js/equipment.js app/static/css/equipment.css
git commit -m "feat(equipment): show encumbrance bar and equipped gear-bonus summary"
```

---

### Task 3: Manual verification in a live browser

**Files:** none (verification only, no code changes)

**Interfaces:**
- Consumes: the running app (dev server), a logged-in user with at least one character that has bag/gear contents (procedural gear instances ideally, to exercise both the affix-tooltip fix and the gear-bonus summary).

- [ ] **Step 1: Start the app via the `run` skill and log in**

Use the `run` skill to launch the Flask dev server. Log in as a test user with at least one character.

- [ ] **Step 2: Verify the encumbrance bar renders correctly**

Open the Equipment modal for a character. Confirm:
- A "Carry Weight" bar appears above the gear slots showing `weight / capacity`.
- If the character is under capacity, the bar is green (`bg-success`) with no status text below it.
- If you don't have an over-capacity character handy, add enough bag items (via existing dev/admin tooling or by picking up floor loot in a dungeon run) to push weight past capacity; confirm the bar turns yellow ("Encumbered") past `capacity`, and red ("Overloaded — cannot carry more") past `capacity * hard_cap_pct`, each showing the `-N DEX` penalty note.

- [ ] **Step 3: Verify real-affix tooltips**

Equip or carry a procedural gear instance (uid-bearing item, e.g. from dungeon floor loot or hoard withdrawal). Hover/focus it in the bag list and in its equipped slot. Confirm the tooltip's effects line shows the item's actual `affixes` values (cross-check by fetching `GET /api/characters/<id>` in a second tab or via browser devtools network panel and comparing the `affixes` array to what's displayed) — not a generic `+1 STR`-style guess.

- [ ] **Step 4: Verify the gear-bonus summary line**

With at least one affix-bearing item equipped, confirm "Gear bonus: ..." appears above the encumbrance bar in the Equipment column, and its values match the sum of all currently equipped items' affixes. Unequip everything and confirm the line disappears (no "Gear bonus: " with empty content).

- [ ] **Step 5: Regression-check legacy items**

If any legacy (non-procedural, plain `Item`-row) gear is equippable in this save (e.g. a basic starter weapon), equip it and confirm its tooltip and the gear-bonus summary still reflect its `effects` correctly (this exercises the `it.effects` fallback branch in both Task 1 and Task 2's code).

- [ ] **Step 6: Report results**

Note in the SDD progress ledger (or directly to the user if running inline) whether all four UI behaviors (bar color states, real-affix tooltips, summary line, legacy fallback) verified correctly, with any screenshots/observations.
