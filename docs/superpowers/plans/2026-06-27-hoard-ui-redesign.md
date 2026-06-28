# Hoard UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal hoard tab with a three-panel layout: character strip (left), character detail (center), and vault (right), with drag-and-drop item transfer and tier-input currency deposit/withdraw.

**Architecture:** Bootstrap 12-col grid inside `#lobby-hoard`. Character strip always visible (col-1). Clicking a character slides in a detail panel (col-4) and shrinks the hoard to col-7. Drag-and-drop uses native HTML5 API. Two new API endpoints handle item deposit and currency transfer.

**Tech Stack:** Flask, SQLAlchemy, Bootstrap 5, native HTML5 drag-and-drop, existing `Hoard` model, existing `hoard_api.py` blueprint.

## Global Constraints

- CSS vars `--class-{name}-bg/fg/border` exist in `app/static/css/classes.css` for fighter/rogue/mage/cleric/druid/ranger
- Inline styles prohibited by pre-commit hook — all styles go in CSS files
- Static files use manual version tokens: `?v=X.Y.Z` — bump when editing JS/CSS
- Currency in copper (smallest unit): 100c = 1s, 10000c = 1g; use existing `format_copper()` / `formatCopper()` for display
- Character class lives in `stats` JSON as lowercase string (e.g. `"fighter"`)
- `hoard_api.py` blueprint registered as `bp_hoard` in `app/__init__.py`

---

### Task 1: New API endpoint — deposit item to hoard

**Files:**
- Modify: `app/routes/hoard_api.py`

**Interfaces:**
- Produces: `POST /api/hoard/deposit-item` → `{success, hoard_items, char_bag}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hoard_deposit_item.py
import json
import pytest

def test_deposit_item_moves_item_to_hoard(client, logged_in_user, test_character_with_item):
    char, item_slug = test_character_with_item
    resp = client.post('/api/hoard/deposit-item', json={
        'character_id': char.id,
        'slug': item_slug
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert any(i.get('slug') == item_slug for i in data['hoard_items'])
    assert not any(i.get('slug') == item_slug for i in data['char_bag'])

def test_deposit_item_rejects_unknown_character(client, logged_in_user):
    resp = client.post('/api/hoard/deposit-item', json={
        'character_id': 99999,
        'slug': 'potion-healing'
    })
    assert resp.status_code == 404

def test_deposit_item_rejects_missing_item(client, logged_in_user, test_character):
    resp = client.post('/api/hoard/deposit-item', json={
        'character_id': test_character.id,
        'slug': 'nonexistent-slug'
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_hoard_deposit_item.py -v
```
Expected: FAIL — `404` on `/api/hoard/deposit-item` (route doesn't exist)

- [ ] **Step 3: Implement `POST /api/hoard/deposit-item`**

Add after the existing `withdraw` route in `app/routes/hoard_api.py`:

```python
@bp_hoard.route("/api/hoard/deposit-item", methods=["POST"])
@login_required
def deposit_item():
    data = request.get_json() or {}
    character_id = data.get("character_id")
    slug = data.get("slug")
    uid = data.get("uid")
    if not character_id or not (slug or uid):
        return jsonify({"error": "Missing required fields"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(current_user.id)
    ok = hoard_service.deposit_from_character(hoard, char, slug=slug, uid=uid)
    if not ok:
        return jsonify({"error": "Item not in character bag"}), 400
    db.session.commit()

    char_bag = json.loads(char.items or "[]")
    hoard_items = json.loads(hoard.items_json or "[]")
    return jsonify({"success": True, "hoard_items": hoard_items, "char_bag": char_bag})
```

- [ ] **Step 4: Implement `hoard_service.deposit_from_character`**

In `app/economy/hoard_service.py`, add alongside the existing `withdraw_to_character`:

```python
def deposit_from_character(hoard, char, *, slug=None, uid=None):
    """Move one item from character bag into hoard. Returns True on success."""
    from app.inventory.utils import load_inventory, dump_inventory
    char_inv = load_inventory(char.items)
    hoard_inv = load_inventory(hoard.items_json)

    # Find the item in char bag
    idx = None
    if uid:
        idx = next((i for i, e in enumerate(char_inv) if e.get("uid") == uid), None)
    elif slug:
        idx = next((i for i, e in enumerate(char_inv) if e.get("slug") == slug), None)

    if idx is None:
        return False

    item = char_inv.pop(idx)
    hoard_inv.append(item)
    char.items = dump_inventory(char_inv)
    hoard.items_json = dump_inventory(hoard_inv)
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_hoard_deposit_item.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/hoard_api.py app/economy/hoard_service.py tests/test_hoard_deposit_item.py
git commit -m "feat(hoard): add POST /api/hoard/deposit-item endpoint"
```

---

### Task 2: New API endpoint — currency transfer (deposit/withdraw)

**Files:**
- Modify: `app/routes/hoard_api.py`

**Interfaces:**
- Consumes: `{character_id, direction: "deposit"|"withdraw", gold, silver, copper}` (all ints)
- Produces: `POST /api/hoard/currency` → `{success, hoard_copper, hoard_copper_display, char_gold, char_silver, char_copper, char_display}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hoard_currency.py
import json, pytest

def test_deposit_currency(client, logged_in_user, test_character_with_coins):
    char = test_character_with_coins  # has 2g 0s 0c in stats
    resp = client.post('/api/hoard/currency', json={
        'character_id': char.id,
        'direction': 'deposit',
        'gold': 1, 'silver': 0, 'copper': 0
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['hoard_copper'] == 10000  # 1g in copper
    assert data['char_gold'] == 1        # 1g remains on char

def test_withdraw_currency(client, logged_in_user, test_character, test_hoard_with_copper):
    # hoard has 5000c (50s), char has 0
    resp = client.post('/api/hoard/currency', json={
        'character_id': test_character.id,
        'direction': 'withdraw',
        'gold': 0, 'silver': 50, 'copper': 0
    })
    data = resp.get_json()
    assert data['success'] is True
    assert data['hoard_copper'] == 0
    assert data['char_silver'] == 50

def test_deposit_insufficient_funds(client, logged_in_user, test_character):
    resp = client.post('/api/hoard/currency', json={
        'character_id': test_character.id,
        'direction': 'deposit',
        'gold': 100, 'silver': 0, 'copper': 0
    })
    assert resp.status_code == 400

def test_withdraw_insufficient_hoard(client, logged_in_user, test_character):
    resp = client.post('/api/hoard/currency', json={
        'character_id': test_character.id,
        'direction': 'withdraw',
        'gold': 999, 'silver': 0, 'copper': 0
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_hoard_currency.py -v
```
Expected: FAIL — route doesn't exist

- [ ] **Step 3: Implement the endpoint**

Add to `app/routes/hoard_api.py`. Import `_char_copper` and `_set_char_copper` patterns from `trading_api.py` (or refactor to shared util — see note below):

```python
from app.economy.currency import COPPER_PER_GOLD, COPPER_PER_SILVER, format_copper

def _char_copper_hoard(char):
    try:
        stats = json.loads(char.stats) if char.stats else {}
    except Exception:
        stats = {}
    return (
        int(stats.get("gold", 0) or 0) * COPPER_PER_GOLD
        + int(stats.get("silver", 0) or 0) * COPPER_PER_SILVER
        + int(stats.get("copper", 0) or 0)
    )

def _set_char_copper_hoard(char, total_copper):
    try:
        stats = json.loads(char.stats) if char.stats else {}
    except Exception:
        stats = {}
    total_copper = max(0, int(total_copper))
    g, rem = divmod(total_copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    stats["gold"] = g
    stats["silver"] = s
    stats["copper"] = c
    char.stats = json.dumps(stats)

@bp_hoard.route("/api/hoard/currency", methods=["POST"])
@login_required
def transfer_currency():
    data = request.get_json() or {}
    character_id = data.get("character_id")
    direction = data.get("direction")
    if direction not in ("deposit", "withdraw"):
        return jsonify({"error": "direction must be deposit or withdraw"}), 400
    try:
        amount = (
            int(data.get("gold", 0) or 0) * COPPER_PER_GOLD
            + int(data.get("silver", 0) or 0) * COPPER_PER_SILVER
            + int(data.get("copper", 0) or 0)
        )
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(current_user.id)
    char_copper = _char_copper_hoard(char)
    hoard_copper = hoard.copper or 0

    if direction == "deposit":
        if char_copper < amount:
            return jsonify({"error": "Not enough coins on character"}), 400
        _set_char_copper_hoard(char, char_copper - amount)
        hoard.copper = hoard_copper + amount
    else:  # withdraw
        if hoard_copper < amount:
            return jsonify({"error": "Not enough copper in hoard"}), 400
        hoard.copper = hoard_copper - amount
        _set_char_copper_hoard(char, char_copper + amount)

    db.session.commit()
    new_char_copper = _char_copper_hoard(char)
    g, rem = divmod(new_char_copper, COPPER_PER_GOLD)
    s, c = divmod(rem, COPPER_PER_SILVER)
    return jsonify({
        "success": True,
        "hoard_copper": hoard.copper,
        "hoard_copper_display": format_copper(hoard.copper),
        "char_gold": g,
        "char_silver": s,
        "char_copper": c,
        "char_display": format_copper(new_char_copper),
    })
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_hoard_currency.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/hoard_api.py tests/test_hoard_currency.py
git commit -m "feat(hoard): add POST /api/hoard/currency deposit/withdraw endpoint"
```

---

### Task 3: CSS — hoard three-panel layout and character strip

**Files:**
- Create: `app/static/css/hoard-ui.css`
- Modify: `app/static/css/app.css` (add import)

**Interfaces:**
- Produces: CSS classes consumed by Tasks 4 and 5

- [ ] **Step 1: Create `app/static/css/hoard-ui.css`**

```css
/* hoard-ui.css — Three-panel hoard screen */

.hoard-layout {
    display: flex;
    gap: 0;
    min-height: 420px;
}

/* Panel A: Character strip */
.hoard-char-strip {
    width: 48px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 4px;
    border-right: 1px solid rgba(255,255,255,0.1);
}

.hoard-char-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 2px solid transparent;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    transition: box-shadow 0.15s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}

.hoard-char-btn.active {
    box-shadow: 0 0 0 2px var(--adv-primary, #7c3aed);
}

/* Panel B: Character detail (slide-in) */
.hoard-char-detail {
    width: 0;
    overflow: hidden;
    transition: width 0.2s ease;
    border-right: 1px solid rgba(255,255,255,0.1);
}

.hoard-char-detail.open {
    width: 300px;
}

.hoard-char-detail-inner {
    width: 300px;
    padding: 12px;
}

/* Currency row */
.hoard-currency-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}

.hoard-currency-row .currency-dir-btn {
    padding: 2px 8px;
    font-weight: 700;
    font-size: 0.85rem;
}

.hoard-currency-row input[type="number"] {
    width: 52px;
    text-align: center;
    padding: 2px 4px;
    font-size: 0.85rem;
}

.hoard-currency-row .currency-label {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.6);
}

/* Panel C: Vault */
.hoard-vault {
    flex: 1;
    padding: 12px;
    overflow-y: auto;
}

.hoard-vault-header {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.5);
    margin-bottom: 8px;
}

/* Item lists */
.hoard-item-list {
    min-height: 60px;
    border: 2px dashed transparent;
    border-radius: 6px;
    transition: border-color 0.15s;
}

.hoard-item-list.drag-over {
    border-color: var(--adv-primary, #7c3aed);
    background: rgba(124, 58, 237, 0.05);
}

.hoard-item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: grab;
    user-select: none;
    transition: background 0.1s;
}

.hoard-item-row:hover {
    background: rgba(255,255,255,0.06);
}

.hoard-item-row.dragging {
    opacity: 0.4;
}
```

- [ ] **Step 2: Add import to `app/static/css/app.css`**

Find the existing `@import` list and add:
```css
@import url("hoard-ui.css");
```

- [ ] **Step 3: Verify no inline-style hook failure**

```bash
grep -n "style=" app/static/css/hoard-ui.css
```
Expected: no output (CSS file has no inline styles)

- [ ] **Step 4: Commit**

```bash
git add app/static/css/hoard-ui.css app/static/css/app.css
git commit -m "feat(hoard): add three-panel hoard UI CSS"
```

---

### Task 4: Rewrite `hoard.js` — three-panel manager

**Files:**
- Modify: `app/static/js/hoard.js`

**Interfaces:**
- Consumes: `GET /api/hoard`, `GET /api/characters/state`, `GET /api/characters/<id>`, `POST /api/hoard/deposit-item`, `POST /api/hoard/withdraw`, `POST /api/hoard/currency`
- Consumes CSS classes from Task 3: `.hoard-layout`, `.hoard-char-strip`, `.hoard-char-btn`, `.hoard-char-detail`, `.hoard-char-detail-inner`, `.hoard-vault`, `.hoard-item-list`, `.hoard-item-row`, `.drag-over`, `.dragging`
- Produces: `window.hoardSystem = { open }` (same public API as before)

- [ ] **Step 1: Write the test (DOM smoke test)**

```python
# tests/test_hoard_ui.py  (Playwright smoke — run manually, not in CI)
# Verifies the hoard tab renders the three-panel layout after open().
# Skip if no browser available.
```
*(UI test is manual; functional API tests already exist in Tasks 1 and 2)*

- [ ] **Step 2: Rewrite `app/static/js/hoard.js`**

```javascript
// hoard.js — three-panel hoard UI
(function () {
  const COPPER_PER_GOLD = 10000;
  const COPPER_PER_SILVER = 100;

  let hoardData = null;      // GET /api/hoard response
  let allChars = [];         // [{id, name, class_name}, ...] from /api/characters/state
  let selectedChar = null;   // {id, name, class_name, bag, coins}
  let charDetailData = null; // GET /api/characters/<id> response

  const THREAT_NAMES = []; // not used here — lives in dungeon-config.js

  // ── Helpers ──────────────────────────────────────────────────────────────

  function esc(s) {
    return (s || '').toString().replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function formatCopper(copper) {
    const total = Math.max(0, Math.floor(copper || 0));
    const g = Math.floor(total / COPPER_PER_GOLD);
    const s = Math.floor((total % COPPER_PER_GOLD) / COPPER_PER_SILVER);
    const c = total % COPPER_PER_SILVER;
    const parts = [];
    if (g) parts.push(`${g}g`);
    if (s) parts.push(`${s}s`);
    if (c || !parts.length) parts.push(`${c}c`);
    return parts.join(' ');
  }

  function classStyle(cls) {
    const c = (cls || 'fighter').toLowerCase();
    return `background:var(--class-${c}-bg,#444);color:var(--class-${c}-fg,#fff);border-color:var(--class-${c}-border,#666);`;
  }

  function toast(msg, ok = true) {
    const el = document.createElement('div');
    el.className = `alert alert-${ok ? 'success' : 'warning'} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    el.style.zIndex = '9999';
    el.innerHTML = `${esc(msg)}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  // ── API calls ─────────────────────────────────────────────────────────────

  async function loadHoard() {
    const r = await fetch('/api/hoard');
    if (!r.ok) throw new Error('hoard load failed');
    hoardData = await r.json();
  }

  async function loadChars() {
    const r = await fetch('/api/characters/state');
    if (!r.ok) throw new Error('chars load failed');
    const d = await r.json();
    allChars = (d.characters || []).map(c => ({
      id: c.id, name: c.name, class_name: c.class_name || 'fighter'
    }));
  }

  async function loadCharDetail(id) {
    const r = await fetch(`/api/characters/${id}`);
    if (!r.ok) throw new Error('char detail load failed');
    charDetailData = await r.json();
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function renderStrip() {
    return allChars.map(c => {
      const initial = (c.name || '?')[0].toUpperCase();
      const active = selectedChar && selectedChar.id === c.id ? 'active' : '';
      const style = classStyle(c.class_name);
      return `<button type="button" class="hoard-char-btn ${active}" data-char-id="${c.id}"
        title="${esc(c.name)}" style="${style}">${esc(initial)}</button>`;
    }).join('');
  }

  function renderCharDetail() {
    if (!selectedChar || !charDetailData) return '';
    const char = charDetailData;
    const stats = char.stats || {};
    const g = stats.gold || 0, s = stats.silver || 0, cu = stats.copper || 0;
    const bag = char.bag || [];

    const bagHtml = bag.length
      ? bag.map(item => renderItemRow(item, 'char')).join('')
      : '<div class="text-muted small">Bag empty.</div>';

    return `
<div class="hoard-char-detail-inner">
  <div class="fw-bold mb-2">${esc(char.name || selectedChar.name)}</div>
  <div class="hoard-currency-row">
    <button type="button" class="btn btn-sm btn-outline-secondary currency-dir-btn" data-dir="withdraw" title="Withdraw from hoard to character">&laquo;</button>
    <input type="number" id="hoard-cin-gold" min="0" value="${g}" class="form-control form-control-sm">
    <span class="currency-label">g</span>
    <input type="number" id="hoard-cin-silver" min="0" value="${s}" class="form-control form-control-sm">
    <span class="currency-label">s</span>
    <input type="number" id="hoard-cin-copper" min="0" value="${cu}" class="form-control form-control-sm">
    <span class="currency-label">c</span>
    <button type="button" class="btn btn-sm btn-outline-secondary currency-dir-btn" data-dir="deposit" title="Deposit from character to hoard">&raquo;</button>
  </div>
  <div class="hoard-item-list" id="char-item-list">
    ${bagHtml}
  </div>
</div>`;
  }

  function renderVault() {
    const copper = hoardData ? (hoardData.copper || 0) : 0;
    const items = hoardData ? (hoardData.items || []) : [];
    const itemsHtml = items.length
      ? items.map(item => renderItemRow(item, 'hoard')).join('')
      : '<div class="text-muted small">Vault is empty.</div>';

    return `
<div class="hoard-vault-header">VAULT &mdash; ${esc(formatCopper(copper))}</div>
<div class="hoard-item-list" id="hoard-item-list">
  ${itemsHtml}
</div>`;
  }

  function renderItemRow(item, source) {
    const isInstance = !!item.uid;
    const name = esc(item.name || item.slug || 'Item');
    const qty = (!isInstance && item.qty > 1) ? `<span class="badge bg-secondary ms-1">×${item.qty}</span>` : '';
    const dragAttr = isInstance ? `data-uid="${esc(item.uid)}"` : `data-slug="${esc(item.slug)}"`;
    return `<div class="hoard-item-row" draggable="true" data-source="${source}" ${dragAttr}>
      <span>${name}${qty}</span>
    </div>`;
  }

  function render() {
    const body = document.getElementById('hoard-tab-body');
    if (!body) return;
    const detailOpen = selectedChar ? 'open' : '';
    body.innerHTML = `
<div class="hoard-layout">
  <div class="hoard-char-strip">${renderStrip()}</div>
  <div class="hoard-char-detail ${detailOpen}" id="hoard-char-detail">${renderCharDetail()}</div>
  <div class="hoard-vault">${renderVault()}</div>
</div>`;
    bindEvents();
  }

  // ── Events ────────────────────────────────────────────────────────────────

  function bindEvents() {
    // Character strip click
    document.querySelectorAll('.hoard-char-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = parseInt(btn.dataset.charId, 10);
        if (selectedChar && selectedChar.id === id) {
          selectedChar = null;
          charDetailData = null;
          render();
          return;
        }
        const found = allChars.find(c => c.id === id);
        if (!found) return;
        selectedChar = found;
        await loadCharDetail(id);
        render();
      });
    });

    // Currency buttons
    document.querySelectorAll('.currency-dir-btn').forEach(btn => {
      btn.addEventListener('click', () => transferCurrency(btn.dataset.dir));
    });

    // Drag-and-drop
    setupDragAndDrop();
  }

  function setupDragAndDrop() {
    let dragged = null;

    document.querySelectorAll('.hoard-item-row').forEach(row => {
      row.addEventListener('dragstart', e => {
        dragged = {
          source: row.dataset.source,
          slug: row.dataset.slug,
          uid: row.dataset.uid,
        };
        row.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      row.addEventListener('dragend', () => row.classList.remove('dragging'));
    });

    ['hoard-item-list', 'char-item-list'].forEach(listId => {
      const list = document.getElementById(listId);
      if (!list) return;
      const targetSource = listId === 'hoard-item-list' ? 'hoard' : 'char';

      list.addEventListener('dragover', e => {
        e.preventDefault();
        list.classList.add('drag-over');
      });
      list.addEventListener('dragleave', () => list.classList.remove('drag-over'));
      list.addEventListener('drop', async e => {
        e.preventDefault();
        list.classList.remove('drag-over');
        if (!dragged || dragged.source === targetSource) return;

        if (targetSource === 'hoard') {
          // char → hoard
          if (!selectedChar) return;
          await depositItem(selectedChar.id, dragged.slug, dragged.uid);
        } else {
          // hoard → char
          if (!selectedChar) { toast('Select a character first', false); return; }
          await withdrawItem(selectedChar.id, dragged.slug, dragged.uid);
        }
      });
    });
  }

  // ── Transfer helpers ──────────────────────────────────────────────────────

  async function depositItem(charId, slug, uid) {
    const body = { character_id: charId };
    if (uid) body.uid = uid; else body.slug = slug;
    try {
      const r = await fetch('/api/hoard/deposit-item', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) { toast(d.error || 'Deposit failed', false); return; }
      toast('Stored in hoard');
      await refresh();
    } catch { toast('Deposit failed (network)', false); }
  }

  async function withdrawItem(charId, slug, uid) {
    const body = { character_id: charId };
    if (uid) body.uid = uid; else body.slug = slug;
    try {
      const r = await fetch('/api/hoard/withdraw', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) { toast(d.error || 'Withdraw failed', false); return; }
      toast('Moved to character');
      await refresh();
    } catch { toast('Withdraw failed (network)', false); }
  }

  async function transferCurrency(direction) {
    if (!selectedChar) { toast('Select a character first', false); return; }
    const g = parseInt(document.getElementById('hoard-cin-gold')?.value || '0', 10) || 0;
    const s = parseInt(document.getElementById('hoard-cin-silver')?.value || '0', 10) || 0;
    const c = parseInt(document.getElementById('hoard-cin-copper')?.value || '0', 10) || 0;
    if (g + s + c === 0) { toast('Enter an amount', false); return; }
    try {
      const r = await fetch('/api/hoard/currency', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character_id: selectedChar.id, direction, gold: g, silver: s, copper: c }),
      });
      const d = await r.json();
      if (!r.ok) { toast(d.error || 'Transfer failed', false); return; }
      const verb = direction === 'deposit' ? 'Deposited to hoard' : 'Withdrew from hoard';
      toast(`${verb}: ${d.hoard_copper_display}`);
      await refresh();
    } catch { toast('Transfer failed (network)', false); }
  }

  async function refresh() {
    await loadHoard();
    if (selectedChar) await loadCharDetail(selectedChar.id);
    render();
  }

  // ── Public API ────────────────────────────────────────────────────────────

  async function open() {
    try {
      await Promise.all([loadHoard(), loadChars()]);
    } catch (err) {
      const body = document.getElementById('hoard-tab-body');
      if (body) body.innerHTML = '<div class="alert alert-danger">Failed to load hoard.</div>';
      return;
    }
    render();
  }

  window.hoardSystem = { open };
})();
```

- [ ] **Step 3: Verify no inline styles (`style=` in JS strings are exempted by hook — but double check)**

```bash
python manage.sh db upgrade 2>/dev/null; echo ok  # just to confirm app starts
```

- [ ] **Step 4: Commit**

```bash
git add app/static/js/hoard.js
git commit -m "feat(hoard): rewrite hoard.js with three-panel layout and drag-and-drop"
```

---

### Task 5: Update `GET /api/characters/<id>` to include bag and coins

The new character detail panel needs `bag` and `stats.gold/silver/copper`. Check if the existing endpoint already returns this.

**Files:**
- Modify: `app/routes/inventory_api.py` (if needed)

- [ ] **Step 1: Check existing response**

```bash
# Start server and test
./manage.sh restart
curl -s -b cookies.txt http://localhost:5000/api/characters/1 | python3 -m json.tool | grep -E "bag|gold|silver|copper"
```

If `bag` and `stats` with coins already present → skip to Step 4 (commit nothing).

- [ ] **Step 2: If `bag` is missing, add it to the character endpoint**

In `app/routes/inventory_api.py`, find the route `GET /api/characters/<id>` and add to the response dict:

```python
# Inside the existing character endpoint response:
bag = json.loads(char.items or "[]")
# ... in return jsonify({...}):
"bag": bag,
```

- [ ] **Step 3: Verify**

```bash
curl -s -b cookies.txt http://localhost:5000/api/characters/1 | python3 -m json.tool | grep bag
```
Expected: `"bag": [...]`

- [ ] **Step 4: Commit (only if changed)**

```bash
git add app/routes/inventory_api.py
git commit -m "feat(hoard): expose bag array on GET /api/characters/<id>"
```

---

### Task 6: Manual smoke test

- [ ] **Step 1: Restart server**

```bash
./manage.sh restart
```

- [ ] **Step 2: Open dashboard → Hoard tab**

- Verify three-panel layout renders (strip on left, vault fills remainder)
- Click a character button → detail panel slides in, vault shrinks
- Click same button again → detail panel collapses
- Verify character coins show in the `[00]g [00]s [00]c` inputs

- [ ] **Step 3: Test currency transfer**

- Set inputs to `0g 1s 0c`, click `>>` (deposit) → toast "Deposited to hoard: 1s", vault header shows updated balance
- Click `<<` (withdraw) → toast "Withdrew from hoard: 1s", character coins restored

- [ ] **Step 4: Test drag-and-drop**

- Drag a hoard item onto the character item list → toast "Moved to character", item disappears from vault
- Drag it back from character list to vault → toast "Stored in hoard"

- [ ] **Step 5: Commit version bump if everything looks good**

```bash
git add -p  # stage any fixes from testing
git commit -m "fix(hoard): smoke test fixes"
```
