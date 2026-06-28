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
