// hoard.js - Hoard (per-user vault) viewer + withdraw-to-character
(function () {
  let hoardState = null; // last GET /api/hoard response: {items, copper, copper_display}
  let characters = [];   // [{id, name}, ...] from /api/characters/state
  let selectedCharId = null;
  let loadError = null;

  function esc(s) { return (s || '').toString().replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c])); }

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
    const body = document.getElementById('hoard-tab-body');
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
    loadError = null;
    try {
      await Promise.all([loadHoard(), loadCharacters()]);
    } catch (err) {
      console.warn('[hoard] load failed:', err);
      loadError = 'Failed to load hoard.';
    }
    render();
  }

  window.hoardSystem = { open };
})();
