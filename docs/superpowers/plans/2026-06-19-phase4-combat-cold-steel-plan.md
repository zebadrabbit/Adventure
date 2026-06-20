# Phase 4 — Combat Cold Steel Theming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recolor combat's leftover glassmorphism/ANSI-log skin onto the existing Cold Steel `--ui-*` tokens, with no markup, behavior, or test-relevant changes.

**Architecture:** Pure CSS/JS color substitution. Every hardcoded `rgba()`/hex literal in `app/static/css/combat.css` and `app/static/css/combat-effects.css` becomes a `color-mix()` expression against one of the 8 existing `--ui-*` tokens defined in `app/static/css/theme.css:27-37`. `app/static/js/combat-effects.js`'s generic damage/heal/crit/miss colors switch to a `getComputedStyle`-based lookup of those same tokens, so CSS and JS share one source of truth. Elemental spell-particle colors (fire/ice/lightning) in the JS file are explicitly NOT touched.

**Tech Stack:** Plain CSS (`color-mix(in srgb, ...)`), vanilla JS (`getComputedStyle`). No build step, no new dependencies.

## Global Constraints

- Reuse only the 8 existing tokens: `--ui-bg`, `--ui-panel`, `--ui-elevated`, `--ui-accent`, `--ui-accent-hover`, `--ui-danger`, `--ui-success`, `--ui-warning`, `--ui-text`, `--ui-text-dim` (defined `app/static/css/theme.css:27-37`).
- No new CSS variables, no markup/class renames in `app/templates/combat.html`, no JS logic/behavior changes.
- Elemental particle colors (fire/ice/lightning gradients, shield-spawn purple, generic sparkle tint) in `combat-effects.js` are out of scope — leave every literal there untouched.
- No automated tests apply (pure color change) — verification is a live browser check via the `run`/`verify` skill at the end.

---

### Task 1: Flatten the glass-card components in `combat.css`

**Files:**
- Modify: `app/static/css/combat.css:29-83` (`.card-glass`, `.card-header-glass`, `.card-body-glass`, `.badge-glass`, `.badge-glass-sm`)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by later tasks (these classes are visually independent of buttons/bars/log).

- [ ] **Step 1: Replace the glass card block**

Replace lines 25-83 of `app/static/css/combat.css` (the `GLASS CARD COMPONENTS` section, from `.card-glass {` through the end of `.badge-glass-sm {...}`) with:

```css
/* ========================================
   COLD STEEL CARD COMPONENTS
   ======================================== */

.card-glass {
    background: var(--ui-panel);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 25%, transparent);
    border-radius: 16px;
    box-shadow: 0 8px 24px 0 color-mix(in srgb, var(--ui-bg) 60%, transparent);
    transition: all 0.3s ease;
}

.card-glass:hover {
    border-color: color-mix(in srgb, var(--ui-accent) 45%, transparent);
    box-shadow: 0 12px 32px 0 color-mix(in srgb, var(--ui-bg) 70%, transparent);
}

.card-header-glass {
    background: linear-gradient(135deg,
            color-mix(in srgb, var(--ui-accent) 30%, var(--ui-elevated)),
            color-mix(in srgb, var(--ui-elevated) 70%, var(--ui-bg)));
    border-bottom: 1px solid color-mix(in srgb, var(--ui-accent) 25%, transparent);
    padding: 1rem 1.25rem;
    border-radius: 16px 16px 0 0;
    color: var(--ui-text);
    font-weight: 600;
    font-size: 1rem;
}

.card-body-glass {
    padding: 1.25rem;
    color: var(--ui-text);
}

/* Badge styling */
.badge-glass {
    background: var(--ui-elevated);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 35%, transparent);
    color: var(--ui-text);
    padding: 0.35rem 0.65rem;
    font-size: 0.75rem;
    border-radius: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-glass-sm {
    background: var(--ui-elevated);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 35%, transparent);
    color: var(--ui-text);
    padding: 0.25rem 0.6rem;
    font-size: 0.7rem;
    border-radius: 6px;
    font-weight: 600;
}
```

- [ ] **Step 2: Visually sanity-check the diff**

Run: `git diff app/static/css/combat.css`
Expected: only the `GLASS CARD COMPONENTS` section changed; no `rgba(255, 255, 255` or `backdrop-filter` lines remain in that block.

- [ ] **Step 3: Commit**

```bash
git add app/static/css/combat.css
git commit -m "feat(combat-ui): flatten glass cards/badges onto Cold Steel tokens"
```

---

### Task 2: Recolor progress bars and combat buttons in `combat.css`

**Files:**
- Modify: `app/static/css/combat.css:145-287` (`.progress-glass*`, `.progress-bar-*`, `.btn-combat*`)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replace the progress bar block**

Replace the `PROGRESS BARS` section (lines 145-188, from `.progress-glass {` through the end of `.progress-bar-success {...}`) with:

```css
/* ========================================
   PROGRESS BARS
   ======================================== */

.progress-glass {
    height: 18px;
    background: color-mix(in srgb, var(--ui-bg) 70%, var(--ui-elevated));
    border: 1px solid color-mix(in srgb, var(--ui-accent) 15%, transparent);
    border-radius: 10px;
    overflow: hidden;
    position: relative;
}

.progress-glass-sm {
    height: 8px;
    background: color-mix(in srgb, var(--ui-bg) 70%, var(--ui-elevated));
    border: 1px solid color-mix(in srgb, var(--ui-accent) 15%, transparent);
    border-radius: 6px;
    overflow: hidden;
    position: relative;
}

.progress-bar-danger {
    background: linear-gradient(90deg,
            var(--ui-danger),
            color-mix(in srgb, var(--ui-danger) 70%, black));
    height: 100%;
    transition: width 0.4s ease;
    box-shadow: inset 0 1px 2px color-mix(in srgb, var(--ui-text) 20%, transparent);
    border-radius: 10px;
}

.progress-bar-primary {
    background: linear-gradient(90deg,
            var(--ui-accent),
            color-mix(in srgb, var(--ui-accent) 70%, black));
    height: 100%;
    transition: width 0.4s ease;
    box-shadow: inset 0 1px 2px color-mix(in srgb, var(--ui-text) 20%, transparent);
    border-radius: 10px;
}

.progress-bar-success {
    background: linear-gradient(90deg,
            var(--ui-success),
            color-mix(in srgb, var(--ui-success) 70%, black));
    height: 100%;
    transition: width 0.4s ease;
    box-shadow: inset 0 1px 2px color-mix(in srgb, var(--ui-text) 20%, transparent);
}
```

- [ ] **Step 2: Replace the combat button block**

Replace the `COMBAT BUTTONS` section (lines 190-287, from `.btn-group-combat {` through the end of `.btn-combat-flee:hover...`) with:

```css
/* ========================================
   COMBAT BUTTONS
   ======================================== */

.btn-group-combat {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.btn-combat {
    background: var(--ui-elevated);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 25%, transparent);
    color: var(--ui-text);
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.2s ease;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
}

.btn-combat:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-elevated) 70%, var(--ui-accent));
    border-color: color-mix(in srgb, var(--ui-accent) 45%, transparent);
    color: var(--ui-text);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px color-mix(in srgb, var(--ui-bg) 60%, transparent);
}

.btn-combat:active:not(:disabled) {
    transform: translateY(0);
}

.btn-combat:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* Combat button variants */
.btn-combat-attack {
    border-color: color-mix(in srgb, var(--ui-danger) 50%, transparent);
    color: color-mix(in srgb, var(--ui-danger) 80%, var(--ui-text));
}

.btn-combat-attack:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-danger) 20%, var(--ui-elevated));
    border-color: color-mix(in srgb, var(--ui-danger) 70%, transparent);
    color: var(--ui-text);
}

.btn-combat-defend {
    border-color: color-mix(in srgb, var(--ui-warning) 50%, transparent);
    color: color-mix(in srgb, var(--ui-warning) 80%, var(--ui-text));
}

.btn-combat-defend:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-warning) 20%, var(--ui-elevated));
    border-color: color-mix(in srgb, var(--ui-warning) 70%, transparent);
    color: var(--ui-text);
}

.btn-combat-spell {
    border-color: color-mix(in srgb, var(--ui-accent) 50%, transparent);
    color: color-mix(in srgb, var(--ui-accent) 80%, var(--ui-text));
}

.btn-combat-spell:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-accent) 20%, var(--ui-elevated));
    border-color: color-mix(in srgb, var(--ui-accent) 70%, transparent);
    color: var(--ui-text);
}

.btn-combat-heal {
    border-color: color-mix(in srgb, var(--ui-success) 50%, transparent);
    color: color-mix(in srgb, var(--ui-success) 80%, var(--ui-text));
}

.btn-combat-heal:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-success) 20%, var(--ui-elevated));
    border-color: color-mix(in srgb, var(--ui-success) 70%, transparent);
    color: var(--ui-text);
}

.btn-combat-flee {
    border-color: color-mix(in srgb, var(--ui-text-dim) 50%, transparent);
    color: var(--ui-text-dim);
}

.btn-combat-flee:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ui-text-dim) 20%, var(--ui-elevated));
    border-color: color-mix(in srgb, var(--ui-text-dim) 70%, transparent);
    color: var(--ui-text);
}
```

- [ ] **Step 3: Sanity-check the diff**

Run: `git diff app/static/css/combat.css`
Expected: only the `PROGRESS BARS` and `COMBAT BUTTONS` sections changed; no `#ef4444`, `#3b82f6`, `#10b981`, or `rgba(` literals remain in either block.

- [ ] **Step 4: Commit**

```bash
git add app/static/css/combat.css
git commit -m "feat(combat-ui): recolor progress bars and combat buttons onto Cold Steel"
```

---

### Task 3: Collapse the combat log palette onto 4 semantic tones

**Files:**
- Modify: `app/static/css/combat.css:289-539` (`COMBAT LOG` section, `.combat-container .btn/.progress/.badge`, all `.combat-log .log-*` rules)

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replace the terminal background/cursor colors**

In `app/static/css/combat.css`, find the `#combat-log` rule (around line 306-317) and the `flicker`/cursor rules below it. Replace from `#combat-log {` through the end of `.terminal-cursor {...}` (through line 375) with:

```css
#combat-log {
    flex: 1;
    overflow-y: auto;
    font-family: 'Courier New', 'Consolas', 'Monaco', monospace;
    font-size: 0.85rem;
    line-height: 1.4rem;
    background: color-mix(in srgb, var(--ui-bg) 90%, black);
    color: var(--ui-text-dim);
    padding: 1rem;
    border-radius: 0 0 16px 16px;
    position: relative;
}

/* CRT scanline effect */
#combat-log::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: repeating-linear-gradient(0deg,
            color-mix(in srgb, black 15%, transparent),
            color-mix(in srgb, black 15%, transparent) 1px,
            transparent 1px,
            transparent 2px);
    pointer-events: none;
    z-index: 1;
}

/* Subtle screen flicker */
@keyframes flicker {
    0% {
        opacity: 0.97;
    }

    50% {
        opacity: 1;
    }

    100% {
        opacity: 0.97;
    }
}

#combat-log::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: color-mix(in srgb, var(--ui-elevated) 10%, transparent);
    opacity: 0;
    animation: flicker 0.15s infinite;
    pointer-events: none;
    z-index: 2;
}

/* Terminal cursor */
.terminal-cursor {
    display: inline-block;
    width: 0.6em;
    height: 1em;
    background-color: var(--ui-text-dim);
    animation: blink 1s step-end infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
    margin-top: 0.5em;
}
```

- [ ] **Step 2: Replace the generic glass button/progress/badge overrides**

Find the block starting `/* Glass-morphism buttons */` through `.combat-container .badge {...}` (around line 390-425). Replace it with:

```css
/* Combat-container button/progress/badge overrides */
.combat-container .btn {
    background: var(--ui-elevated);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 25%, transparent);
    color: var(--ui-text);
    transition: all 0.2s ease;
}

.combat-container .btn:hover {
    background: color-mix(in srgb, var(--ui-elevated) 70%, var(--ui-accent));
    border-color: color-mix(in srgb, var(--ui-accent) 45%, transparent);
    color: var(--ui-text);
    transform: translateY(-1px);
}

/* Legacy button styles removed - using .btn-combat classes instead */

/* Progress bars */
.combat-container .progress {
    background: color-mix(in srgb, var(--ui-bg) 70%, var(--ui-elevated));
    border: 1px solid color-mix(in srgb, var(--ui-accent) 15%, transparent);
    border-radius: 10px;
}

.combat-container .progress-bar {
    background: linear-gradient(90deg,
            var(--ui-danger),
            color-mix(in srgb, var(--ui-danger) 70%, black));
    border-radius: 10px;
}

/* Badges */
.combat-container .badge {
    background: var(--ui-elevated);
    border: 1px solid color-mix(in srgb, var(--ui-accent) 35%, transparent);
    color: var(--ui-text);
    padding: 0.35rem 0.65rem;
}
```

- [ ] **Step 3: Replace the active party-member highlight colors**

Find `.party-member.border-warning` (appears twice — once around line 114-117 in the `PARTY MEMBER CARDS` section, once again near line 437-440 at the bottom). Replace **both** occurrences with:

```css
.party-member.border-warning {
    border-color: color-mix(in srgb, var(--ui-warning) 60%, transparent) !important;
    box-shadow: 0 0 15px color-mix(in srgb, var(--ui-warning) 40%, transparent);
}
```

(The `.party-member.active-turn` rule just above the first occurrence already uses `--adv-primary` via `color-mix` — leave it untouched, it's already token-based.)

- [ ] **Step 4: Replace the stat-label/stat-value colors**

Find `.stat-label` and `.stat-value` (around line 132-143). Replace with:

```css
.stat-label {
    font-size: 0.75rem;
    color: var(--ui-text-dim);
    font-weight: 500;
}

.stat-value {
    font-size: 0.75rem;
    color: var(--ui-text);
    font-weight: 600;
    font-family: 'Courier New', monospace;
}
```

- [ ] **Step 5: Replace all `.combat-log .log-*` rules**

Find the block from `.combat-log .log-duplicate {` (around line 443) through the end of the file (`.combat-log .log-victory {...}`, around line 539). Replace it with:

```css
/* Trim duplicate timestamp groups visually */
.combat-log .log-duplicate {
    opacity: 0.6;
}

/* Danger group: damage, crit, death, bleed, burn */
.combat-log .log-damage,
.combat-log .log-bleed,
.combat-log .log-burn {
    color: var(--ui-danger);
    font-weight: bold;
}

.combat-log .log-crit,
.combat-log .log-death {
    color: var(--ui-danger);
    font-weight: 700;
}

/* Success group: heal, buff, victory */
.combat-log .log-heal,
.combat-log .log-buff {
    color: var(--ui-success);
    font-weight: bold;
}

.combat-log .log-victory {
    color: var(--ui-success);
    font-weight: 700;
}

/* Warning group: debuff, stun, curse, poison, loot */
.combat-log .log-debuff,
.combat-log .log-stun,
.combat-log .log-curse,
.combat-log .log-poison {
    color: var(--ui-warning);
}

.combat-log .log-loot {
    color: var(--ui-warning);
    font-weight: 600;
}

/* Accent group: shield, block, dodge, freeze */
.combat-log .log-shield,
.combat-log .log-block,
.combat-log .log-dodge,
.combat-log .log-freeze {
    color: var(--ui-accent);
}

/* Informational marker */
.combat-log .log-turn {
    color: var(--ui-accent);
    font-weight: 600;
}

/* Neutral/dim group: system, miss, flee */
.combat-log .log-system,
.combat-log .log-flee {
    color: var(--ui-text-dim);
    font-style: italic;
}

.combat-log .log-miss {
    color: var(--ui-text-dim);
    font-style: italic;
}
```

- [ ] **Step 6: Sanity-check the diff for leftover literals**

Run: `grep -nE "rgba?\(|#[0-9a-fA-F]{3,6}\b" app/static/css/combat.css`
Expected: no output (zero matches) — every literal color in the file is now a `var(--ui-*)` or `color-mix()` expression.

- [ ] **Step 7: Commit**

```bash
git add app/static/css/combat.css
git commit -m "feat(combat-ui): collapse combat log palette onto 4 Cold Steel semantic tones"
```

---

### Task 4: Recolor status indicators in `combat-effects.css`

**Files:**
- Modify: `app/static/css/combat-effects.css:132-190` (`.status-indicator` base + 8 `.status-*` variants)

**Interfaces:**
- Consumes: nothing from Tasks 1-3.
- Produces: nothing consumed by Task 5 (Task 5 only touches `.js`).

- [ ] **Step 1: Replace the status-indicator block**

Replace from `.status-indicator {` (around line 132) through the end of `.status-blessed {...}` (around line 190) with:

```css
.status-indicator {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--ui-bg) 80%, black);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    border: 1px solid color-mix(in srgb, var(--ui-accent) 25%, transparent);
    animation: statusPulse 2s ease-in-out infinite;
}

@keyframes statusPulse {

    0%,
    100% {
        transform: scale(1);
        box-shadow: 0 0 0 0 color-mix(in srgb, var(--ui-accent) 40%, transparent);
    }

    50% {
        transform: scale(1.05);
        box-shadow: 0 0 8px 2px color-mix(in srgb, var(--ui-accent) 20%, transparent);
    }
}

/* Danger group */
.status-burn {
    border-color: color-mix(in srgb, var(--ui-danger) 50%, transparent);
}

/* Success group */
.status-regen {
    border-color: color-mix(in srgb, var(--ui-success) 50%, transparent);
}

/* Warning group */
.status-stun {
    border-color: color-mix(in srgb, var(--ui-warning) 50%, transparent);
}

.status-curse {
    border-color: color-mix(in srgb, var(--ui-warning) 50%, transparent);
}

.status-blessed {
    border-color: color-mix(in srgb, var(--ui-warning) 50%, transparent);
}

/* Accent group */
.status-freeze {
    border-color: color-mix(in srgb, var(--ui-accent) 50%, transparent);
}

.status-shield {
    border-color: color-mix(in srgb, var(--ui-accent) 50%, transparent);
}

/* Poison is its own DOT effect alongside burn/bleed -> danger group */
.status-poison {
    border-color: color-mix(in srgb, var(--ui-danger) 50%, transparent);
}
```

- [ ] **Step 2: Sanity-check the diff**

Run: `grep -nE "rgba?\(|#[0-9a-fA-F]{3,6}\b" app/static/css/combat-effects.css`
Expected: no output (zero matches) — `combat-effects.css` has no other literal colors outside this block (confirmed during design — the keyframes above it are pure transform animations).

- [ ] **Step 3: Commit**

```bash
git add app/static/css/combat-effects.css
git commit -m "feat(combat-ui): recolor status indicators onto Cold Steel semantic tones"
```

---

### Task 5: Re-key generic damage-number/flash colors in `combat-effects.js`

**Files:**
- Modify: `app/static/js/combat-effects.js:1-170` (top of file: add helper; lines ~99-102, ~108-109, ~141, ~162 use it)

**Interfaces:**
- Consumes: nothing from Tasks 1-4 directly, but relies on the `--ui-danger`/`--ui-success`/`--ui-warning`/`--ui-text-dim` tokens already existing in `theme.css` (unchanged by this plan).
- Produces: a `uiColor(name, fallback)` helper other combat JS could reuse later (not required by this plan).

- [ ] **Step 1: Add the `uiColor` helper near the top of the file**

Open `app/static/js/combat-effects.js`. After the top-of-file comment block (before the first class/function definition), add:

```js
function uiColor(name, fallback) {
    const v = getComputedStyle(document.documentElement)
        .getPropertyValue(`--ui-${name}`)
        .trim();
    return v || fallback;
}
```

- [ ] **Step 2: Replace the floating damage-number base colors**

Find (around line 99-102):

```js
            if (isHeal) baseColor = '#4ade80'; // Green
            else if (isCritical) baseColor = '#fbbf24'; // Yellow/Gold
            else if (isMiss) baseColor = '#94a3b8'; // Gray
            else baseColor = '#ef4444'; // Red
```

Replace with:

```js
            if (isHeal) baseColor = uiColor('success', '#4caf82');
            else if (isCritical) baseColor = uiColor('warning', '#d6a23a');
            else if (isMiss) baseColor = uiColor('text-dim', '#8d97a3');
            else baseColor = uiColor('danger', '#c0392b');
```

- [ ] **Step 3: Replace the `flashElement` default colors**

Find (around line 141):

```js
            this.flashElement(targetElement, isHeal ? '#4ade80' : '#ef4444');
```

Replace with:

```js
            this.flashElement(targetElement, isHeal ? uiColor('success', '#4caf82') : uiColor('danger', '#c0392b'));
```

Find the `flashElement` method signature (around line 162):

```js
    flashElement(element, color = '#ef4444') {
```

Replace with:

```js
    flashElement(element, color = uiColor('danger', '#c0392b')) {
```

And find its other heal-flash call site (around line 338):

```js
        this.flashElement(targetElement, '#4ade80');
```

Replace with:

```js
        this.flashElement(targetElement, uiColor('success', '#4caf82'));
```

- [ ] **Step 4: Confirm elemental colors are untouched**

Run: `grep -n "fire:\|ice:\|lightning:" app/static/js/combat-effects.js`
Expected: the three lines defining `fire: ['#ef4444', '#f97316', '#fbbf24']`, `ice: [...]`, `lightning: [...]` are still present verbatim — these are explicitly out of scope per the spec.

- [ ] **Step 5: Confirm no syntax errors**

Run: `node --check app/static/js/combat-effects.js`
Expected: no output (exit code 0). If `node` isn't available, instead run `python -c "import py_compile" 2>/dev/null; echo skip-if-no-node` and rely on Step 6's browser check to catch syntax errors via the console.

- [ ] **Step 6: Commit**

```bash
git add app/static/js/combat-effects.js
git commit -m "feat(combat-ui): re-key generic damage-number colors onto Cold Steel tokens"
```

---

### Task 6: Live verification in a browser

**Files:** none (verification only).

**Interfaces:**
- Consumes: all changes from Tasks 1-5.
- Produces: nothing (terminal task).

- [ ] **Step 1: Start the dev server using the project's `run` skill/script and log in**

Use whatever this repo's existing dev-server start mechanism is (check `docs/DEVELOPMENT.md` / `manage.sh` if unsure: `./manage.sh start` or equivalent). Log in with a test account and enter a dungeon run.

- [ ] **Step 2: Trigger a combat encounter and visually verify against the mapping table**

In the live browser:
- Confirm party-card panels are opaque slate/charcoal (no white blur), buttons show the 5 Cold Steel hues (attack=danger-red, defend=warning-amber, spell=accent-teal, heal=success-green, flee=dim-gray).
- Land at least one normal hit (damage=danger), one crit (danger, bold), one heal (success), one miss (text-dim, italic), and a turn announcement (accent) — confirm log colors match Task 3's table.
- If a poison/stun/curse/freeze/shield status is reachable in this encounter, trigger it and confirm the status-indicator badge border color matches Task 4's table.
- Win or lose the encounter and confirm `.log-victory`/`.log-death` render in success/danger respectively.
- Cast a fire, ice, and lightning spell (if reachable) and confirm their particle colors are unchanged (still red/orange/gold, blue, yellow — not flattened).

- [ ] **Step 3: Check browser console for errors**

Open devtools console. Expected: zero errors, specifically none referencing `uiColor`, `getComputedStyle`, or `getPropertyValue`.

- [ ] **Step 4: Report back**

No commit for this task (verification only) — report what you saw (pass/fail per bullet in Step 2) back in conversation so any visual mismatch can be fixed before considering Phase 4 done.

---

## Final step: update the roadmap doc

- [ ] **Step 1: Mark Phase 4 done in `docs/superpowers/TODO.md`**

Find `Next: Phase 4 (combat visuals), per the roadmap.` (in the Phase 5a entry) and the implicit absence of a "Phase 4" heading. Add a new `### UI Redesign Phase 4 — Combat Cold Steel theming ✅` section (following the exact format of the Phase 1/2/3a-3d/5a entries above it), summarizing: dropped the leftover glassmorphism skin from `combat.css`, collapsed 18 ANSI-style log colors onto 4 Cold Steel semantic tones, recolored `combat-effects.css` status indicators, re-keyed `combat-effects.js`'s generic damage-number colors onto the same tokens via `getComputedStyle`, left elemental fire/ice/lightning particle colors untouched as intentional flavor. Reference the design doc: `specs/2026-06-19-phase4-combat-cold-steel-design.md`. Note what's next per the roadmap (UI Redesign is now fully complete across Phases 1-5a, modulo the still-open `glass-theme.css` dead-code follow-up already noted under Phase 5a).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 4 (combat Cold Steel theming) done"
```
