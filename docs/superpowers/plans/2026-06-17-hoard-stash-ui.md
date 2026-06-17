# Hoard / Stash Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Hoard" screen — a modal reachable from the dashboard that shows the
per-user Hoard's copper and items, and lets the player withdraw any item to a chosen
character.

**Architecture:** One new vanilla-JS IIFE module (`app/static/js/hoard.js`), following the
existing `app/static/js/equipment.js` pattern (single Bootstrap modal, a state-fetch +
re-render-on-change loop, no class). One small `dashboard.html` edit adds the trigger
button and the `<script>` tag. No backend or CSS changes — reuses Bootstrap utility classes
plus the rarity/durability CSS classes already loaded via `equipment.css`.

**Tech Stack:** Vanilla JS, Bootstrap 5 modal, Flask JSON APIs already in place
(`GET /api/hoard`, `GET /api/characters/state`, `POST /api/hoard/withdraw`).

## Global Constraints

- No backend or template changes beyond the one `dashboard.html` edit in Task 2 — frontend-only.
- All money must render through the backend's `*_display` strings (`copper_display`), never
  a hand-rolled number.
- Reuse existing CSS conventions: rarity classes (`.rarity-common`…`.rarity-mythic`) and
  durability bar classes (`.durability-bar`/`.durability-fill.high|medium|low`), both already
  defined in `app/static/css/equipment.css` and already loaded on the dashboard page. Do not
  invent new selectors for these.
- No manual deposit-into-hoard feature — out of scope (no backend support exists).
- The dungeon's stubbed "Party Stash" button/alert (`app/templates/adventure.html`) is a
  separate, unbuilt feature and must not be touched or repurposed by this plan.
- Verification is manual via a live browser (this repo's frontend has no JS test runner) —
  use the `run`/`verify` skills. Each task also gets a `node --check` syntax-validation step,
  which **is** automatable.
- Spec reference: `docs/superpowers/specs/2026-06-17-hoard-stash-ui-design.md`.

---

## File Structure

- **Create `app/static/js/hoard.js`** — the entire Hoard screen: modal markup, state
  fetch/render, withdraw action, character selector. Single responsibility: view + withdraw
  from the hoard. Does not touch equipping (that stays in `equipment.js`) or trading (stays
  in `trading-system.js`).
- **Modify `app/templates/dashboard.html`** — add a "HOARD" button section (mirroring the
  existing "MERCHANTS" section) and the new `<script src="{{ asset_url('js/hoard.js') }}">`
  tag.

---

### Task 1: Build the Hoard modal module

**Files:**
- Create: `app/static/js/hoard.js`

**Interfaces:**
- Produces: `window.hoardSystem.open()` (async, no args — loads hoard + character state,
  renders, and shows the modal). This is the only symbol other code needs; Task 2's button
  calls it via a `click` listener wired to elements with class `btn-hoard-open`.
- Consumes: `GET /api/hoard` → `{items: [...], copper, copper_display}`,
  `GET /api/characters/state` → `{characters: [{id, name, ...}]}`,
  `POST /api/hoard/withdraw` body `{character_id, slug}` or `{character_id, uid}` →
  `{success: true}` or `{error: "..."}`. Consumes `window.MUDTooltips.rarityClass(rarity)`
  (already exported globally by `app/static/js/tooltips.js`, loaded before this module on
  `dashboard.html`).

- [ ] **Step 1: Write the module**

Create `app/static/js/hoard.js`:

```javascript
// hoard.js - Hoard (per-user vault) viewer + withdraw-to-character
(function () {
  const modalId = 'hoardModal';
  let hoardState = null; // last GET /api/hoard response: {items, copper, copper_display}
  let characters = [];   // [{id, name}, ...] from /api/characters/state
  let selectedCharId = null;
  let loadError = null;

  function esc(s) { return (s || '').toString().replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c])); }

  function ensureModal() {
    if (document.getElementById(modalId)) return;
    const html = `
<div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-bank2 me-2"></i>Hoard</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div id="hoard-modal-body"></div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
      </div>
    </div>
  </div>
</div>`;
    document.body.insertAdjacentHTML('beforeend', html);
  }

  async function loadHoard() {
    const r = await fetch('/api/hoard');
    if (!r.ok) throw new Error('failed to load hoard');
    hoardState = await r.json();
  }

  async function loadCharacters() {
    const r = await fetch('/api/characters/state');
    if (!r.ok) throw new Error('failed to load characters');
    const data = await r.json();
    characters = (data.characters || []).map(c => ({ id: c.id, name: c.name }));
    if (characters.length > 0 && !characters.some(c => c.id === selectedCharId)) {
      selectedCharId = characters[0].id;
    }
  }

  function durabilityBarHtml(item) {
    if (item.durability == null || !item.max_durability) return '';
    const pct = Math.max(0, Math.min(100, (item.durability / item.max_durability) * 100));
    const tier = pct > 60 ? 'high' : pct > 25 ? 'medium' : 'low';
    return `<div class="durability-bar"><div class="durability-fill ${tier}" style="width: ${pct}%"></div></div>`;
  }

  function renderItemRow(item) {
    const isInstance = !!item.uid;
    const rarity = isInstance && window.MUDTooltips ? window.MUDTooltips.rarityClass(item.rarity) : '';
    const name = esc(item.name || item.slug || 'Item');
    const qtyBadge = (!isInstance && item.qty > 1) ? `<span class="badge bg-secondary ms-2">×${item.qty}</span>` : '';
    const withdrawAttr = isInstance ? `data-uid="${esc(item.uid)}"` : `data-slug="${esc(item.slug)}"`;
    return `
<div class="list-group-item d-flex justify-content-between align-items-center hoard-item-row">
  <div>
    <span class="${rarity}">${name}</span>${qtyBadge}
    ${durabilityBarHtml(item)}
  </div>
  <button type="button" class="btn btn-sm btn-outline-primary btn-hoard-withdraw" ${withdrawAttr}
    ${characters.length === 0 ? 'disabled' : ''}>Withdraw</button>
</div>`;
  }

  function render() {
    ensureModal();
    const body = document.getElementById('hoard-modal-body');
    if (loadError) {
      body.innerHTML = `<div class="alert alert-danger">${esc(loadError)}</div>`;
      return;
    }
    const copperDisplay = esc((hoardState && hoardState.copper_display) || '0c');
    const items = (hoardState && hoardState.items) || [];

    const selectorHtml = characters.length > 0
      ? `<select id="hoard-withdraw-target" class="form-select form-select-sm" style="max-width: 240px;">
           ${characters.map(c => `<option value="${c.id}" ${c.id === selectedCharId ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}
         </select>`
      : `<div class="text-muted small">Create a character first to withdraw items.</div>`;

    const itemsHtml = items.length > 0
      ? `<div class="list-group">${items.map(renderItemRow).join('')}</div>`
      : `<div class="text-muted">Your hoard is empty.</div>`;

    body.innerHTML = `
<div class="d-flex justify-content-between align-items-center mb-3">
  <div class="h5 mb-0"><i class="bi bi-coin me-1"></i>${copperDisplay}</div>
</div>
<div class="d-flex align-items-center gap-2 mb-3">
  <label class="small text-muted mb-0">Withdraw to:</label>
  ${selectorHtml}
</div>
<div id="hoard-withdraw-error"></div>
${itemsHtml}`;

    const select = document.getElementById('hoard-withdraw-target');
    if (select) {
      select.addEventListener('change', () => {
        selectedCharId = parseInt(select.value, 10);
      });
    }

    document.querySelectorAll('.btn-hoard-withdraw').forEach(btn => {
      btn.addEventListener('click', () => withdraw(btn));
    });
  }

  async function withdraw(btn) {
    const errorBox = document.getElementById('hoard-withdraw-error');
    errorBox.innerHTML = '';
    if (!selectedCharId) return;

    const body = { character_id: selectedCharId };
    const uid = btn.getAttribute('data-uid');
    const slug = btn.getAttribute('data-slug');
    if (uid) body.uid = uid; else body.slug = slug;

    btn.disabled = true;
    try {
      const r = await fetch('/api/hoard/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const result = await r.json();
      if (!r.ok) {
        errorBox.innerHTML = `<div class="alert alert-danger">${esc(result.error || 'Withdraw failed')}</div>`;
        btn.disabled = false;
        return;
      }
      document.dispatchEvent(new CustomEvent('mud-characters-state-invalidated'));
      await loadHoard();
      render();
    } catch (err) {
      console.error('[hoard] withdraw failed:', err);
      errorBox.innerHTML = `<div class="alert alert-danger">Withdraw failed (network error)</div>`;
      btn.disabled = false;
    }
  }

  async function open() {
    ensureModal();
    loadError = null;
    try {
      await Promise.all([loadHoard(), loadCharacters()]);
    } catch (err) {
      console.warn('[hoard] load failed:', err);
      loadError = 'Failed to load hoard.';
    }
    render();
    const modalEl = document.getElementById(modalId);
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
  }

  window.hoardSystem = { open };

  function wireButtons() {
    document.querySelectorAll('.btn-hoard-open').forEach(btn => {
      if (btn.__hoardWired) return;
      btn.__hoardWired = true;
      btn.addEventListener('click', open);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireButtons);
  } else {
    wireButtons();
  }
})();
```

- [ ] **Step 2: Syntax-check the file**

Run: `node --check app/static/js/hoard.js`
Expected: no output (exit code 0).

- [ ] **Step 3: Manual verification (module in isolation, no button yet)**

This module has no caller until Task 2 wires the dashboard button, but it's independently
testable via the devtools console. Use the `run` skill to start the app, log in, navigate to
`/dashboard`, open the browser devtools console, and run:

```javascript
window.hoardSystem.open()
```

Confirm:
- The modal opens showing the hoard's copper as a 3-tier display string (e.g. `"2g 14s 6c"`),
  not a bare integer.
- Items render: stackables show a quantity badge when `qty > 1`; gear instances show a
  rarity-colored name and a durability bar when applicable.
- The "Withdraw to" selector lists the user's characters.
- Clicking Withdraw on an item succeeds (the item disappears or its quantity decrements), and
  re-opening the Equipment modal for the destination character (`window.equipmentManager` or
  the existing bag-panel button) shows the item in their bag.
- With an empty hoard (a fresh user with no items), the modal shows "Your hoard is empty."
- With zero characters, the selector area shows "Create a character first to withdraw items."
  and Withdraw buttons are disabled.

If you cannot drive a real browser in this environment, do the `node --check` step
rigorously, read the code path carefully to confirm correctness, note in your report that
live-browser verification was not possible, and rely on the controller to do the live check
afterward — do not fabricate a browser verification you didn't perform.

- [ ] **Step 4: Commit**

```bash
git add app/static/js/hoard.js
git commit -m "feat(hoard-ui): add hoard viewer + withdraw-to-character modal"
```

---

### Task 2: Wire the Hoard button into the dashboard

**Files:**
- Modify: `app/templates/dashboard.html:132-158` (insert a new section after the existing
  "Merchant Shops" block), `app/templates/dashboard.html:386` (insert a new `<script>` tag
  after `trading-system.js`)

**Interfaces:**
- Consumes: `window.hoardSystem.open()` (Task 1) via a `click` listener on elements with
  class `btn-hoard-open` (already wired generically by `hoard.js`'s `wireButtons()` — this
  task only needs to add a button with that class, no new JS).

- [ ] **Step 1: Add the Hoard button section to the dashboard**

In `app/templates/dashboard.html`, insert immediately after the closing `</div>` of the
"Merchant Shops" block (the block ending at line 158, right before the `<!-- Party
Management -->` comment at line 160):

```html
                            <!-- Hoard -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('locked-chest', 16, 'me-2') }}HOARD</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary btn-hoard-open">
                                        <i class="bi bi-bank2 me-2"></i> View Hoard
                                    </button>
                                </div>
                            </div>
```

So the surrounding structure reads:

```html
                            <!-- Merchant Shops -->
                            <div class="mt-4">
                                ...
                            </div>

                            <!-- Hoard -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('locked-chest', 16, 'me-2') }}HOARD</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary btn-hoard-open">
                                        <i class="bi bi-bank2 me-2"></i> View Hoard
                                    </button>
                                </div>
                            </div>

                            <!-- Party Management -->
                            <div class="mt-4">
                                ...
```

- [ ] **Step 2: Load the new script**

In `app/templates/dashboard.html`, replace:

```html
<script src="{{ asset_url('js/trading-system.js') }}"></script>
<script src="{{ asset_url('js/seed-widget.js') }}"></script>
```

with:

```html
<script src="{{ asset_url('js/trading-system.js') }}"></script>
<script src="{{ asset_url('js/hoard.js') }}"></script>
<script src="{{ asset_url('js/seed-widget.js') }}"></script>
```

- [ ] **Step 3: Confirm the icon asset exists**

Run: `ls app/static/iconography/locked-chest.svg`
Expected: the file is listed (no "No such file" error) — this confirms `svg_icon('locked-chest', ...)` will resolve to a real asset rather than a broken image.

- [ ] **Step 4: Syntax/template sanity check**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -c "
from app import create_app
app = create_app()
with app.test_request_context():
    from flask import render_template
    # Smoke-render is skipped here since dashboard.html requires a logged-in session and
    # character data; instead, confirm the template parses without a Jinja syntax error.
    app.jinja_env.get_template('dashboard.html')
    print('TEMPLATE_OK')
"`
Expected: `TEMPLATE_OK` printed, no `TemplateSyntaxError`.

- [ ] **Step 5: Manual end-to-end verification**

Use the `run`/`verify` skills with a live browser, logged in on `/dashboard`:
- Confirm a "HOARD" section with a "View Hoard" button appears below "MERCHANTS".
- Click it; confirm the same modal behavior verified in Task 1 Step 3 now works via the
  button (no console command needed).
- Repeat the full Task 1 Step 3 checklist (copper display, item rendering, withdraw,
  empty-hoard state, zero-character state) end-to-end from the UI.

If live-browser verification isn't possible in your environment, perform Steps 3-4
rigorously, read the inserted markup carefully to confirm it matches the surrounding
template's structure, note in your report that live-browser verification was not performed,
and rely on the controller to do the live check afterward.

- [ ] **Step 6: Commit**

```bash
git add app/templates/dashboard.html
git commit -m "feat(hoard-ui): add dashboard entry point for the hoard viewer"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Hoard button + modal (Task 1+2) ✅, copper display via `*_display` ✅,
  stackable + gear-instance rendering with rarity/durability ✅, single character selector
  driving withdraw target ✅, withdraw via existing endpoint with success/error handling ✅,
  `mud-characters-state-invalidated` dispatch so the Equipment modal picks up withdrawn items
  ✅, empty-hoard and zero-character fallback states ✅. Out-of-scope items (manual deposit,
  the dungeon's Party Stash button) correctly untouched.
- **Type/name consistency check:** `window.hoardSystem.open()` is the only symbol Task 2
  depends on, and it's defined exactly that way in Task 1. The button class `btn-hoard-open`
  is referenced identically in both tasks (Task 1's `wireButtons()` query selector, Task 2's
  button markup). No mismatched names found.
- **No placeholders:** every step contains complete, runnable code or an exact command with
  expected output.
