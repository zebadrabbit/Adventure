// equipment.js - Inventory & Equipment UI with drag-and-drop
(function(){
  const modalId = 'equipmentModal';
  let state = null; // loaded from /api/characters/state

  function ensureModal(){
    if (document.getElementById(modalId)) return;
    const html = `
<div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Character Equipment</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div id="equip-modal-body" class="container-fluid"></div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
      </div>
    </div>
  </div>
</div>`;
    document.body.insertAdjacentHTML('beforeend', html);
  }

  async function loadState(){
    const r = await fetch('/api/characters/state');
    if (!r.ok) throw new Error('failed to load character state');
    state = await r.json();
  }

  function slotBox(slot, item){
    const label = slot.replace(/\d+$/, '');
    const icon = iconForType(item?.type);
    const right = item
      ? `<div class="d-flex align-items-center gap-2">
           <div class="small">${icon} ${esc(item.name)} <span class="text-muted small">(${esc(item.type)})</span></div>
           <button class="btn btn-sm btn-outline-danger btn-unequip" data-slot="${slot}" title="Unequip from ${label}"><i class="bi bi-x-lg"></i></button>
         </div>`
      : `<span class="text-muted">Empty</span>`;
    return `
      <div class="equip-slot card p-2 mb-2" data-slot="${slot}" droppable="true" style="min-height:48px;">
        <div class="d-flex justify-content-between align-items-center">
          <div><strong class="text-uppercase small">${label}</strong></div>
          ${right}
        </div>
      </div>`;
  }

  function bagItem(it){
    const icon = iconForType(it.type);
    return `<div class="bag-item list-group-item d-flex justify-content-between align-items-center" draggable="true" data-slug="${esc(it.slug)}">
      <div>${icon} ${esc(it.name)} <span class="text-muted small">(${esc(it.type)})</span></div>
      <div class="btn-group btn-group-sm">
        ${it.type === 'potion' ? `<button class="btn btn-success btn-consume" data-slug="${esc(it.slug)}">Use</button>` : ''}
      </div>
    </div>`;
  }

  function iconForType(t){
    const m = {
      weapon: '<i class="bi bi-sword"></i>',
      armor: '<i class="bi bi-shield"></i>',
      potion: '<i class="bi bi-cup-straw"></i>',
      ring: '<i class="bi bi-gem"></i>',
      amulet: '<i class="bi bi-award"></i>',
      tool: '<i class="bi bi-wrench"></i>'
    };
    return m[t] || '<i class="bi bi-box"></i>';
  }

  function esc(s){ return (s||'').replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

  function renderCharPanel(ch){
    const gear = ch.gear || {};
    const slots = ['weapon','offhand','head','chest','legs','boots','gloves','ring1','ring2','amulet'];
    let html = `<div class="row g-3" data-char-id="${ch.id}">
      <div class="col-md-6">
        <h6 class="text-muted">Equipment</h6>
        ${slots.map(s=>slotBox(s, gear[s])).join('')}
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

  function findCharState(charId){
    if (!state || !state.characters) return null;
    return state.characters.find(c=>c.id===charId);
  }

  function wireDnD(modalEl, charId){
    const bag = modalEl.querySelector('#bag-list');
    let dragSlug = null;
    bag?.addEventListener('dragstart', (e)=>{
      const el = e.target.closest('.bag-item');
      if (!el) return;
      dragSlug = el.getAttribute('data-slug');
      e.dataTransfer.setData('text/plain', dragSlug);
    });
    modalEl.querySelectorAll('.equip-slot').forEach(slot => {
      slot.addEventListener('dragover', e=>{ e.preventDefault(); slot.classList.add('border','border-info'); });
      slot.addEventListener('dragleave', ()=> slot.classList.remove('border','border-info'));
      slot.addEventListener('drop', async (e)=>{
        e.preventDefault();
        slot.classList.remove('border','border-info');
        const slug = dragSlug || e.dataTransfer.getData('text/plain');
        const targetSlot = slot.getAttribute('data-slot');
        if (!slug || !targetSlot) return;
        const r = await fetch(`/api/characters/${charId}/equip`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug, slot: targetSlot })
        });
        if (r.ok) {
          await loadState();
          openForChar(charId); // re-render
        } else {
          console.warn('equip failed', await r.json().catch(()=>({})));
        }
      });
    });
    modalEl.querySelectorAll('.btn-consume').forEach(btn => {
      btn.addEventListener('click', async ()=>{
        const slug = btn.getAttribute('data-slug');
        const r = await fetch(`/api/characters/${charId}/consume`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug })
        });
        if (r.ok) {
          await loadState();
          openForChar(charId);
        }
      });
    });
    modalEl.querySelectorAll('.btn-unequip').forEach(btn => {
      btn.addEventListener('click', async ()=>{
        const slot = btn.getAttribute('data-slot');
        const r = await fetch(`/api/characters/${charId}/unequip`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slot })
        });
        if (r.ok) {
          await loadState();
          openForChar(charId);
        } else {
          console.warn('unequip failed', await r.json().catch(()=>({})))
        }
      });
    });
  }

  function openForChar(charId){
    ensureModal();
    const modalEl = document.getElementById(modalId);
    const target = findCharState(charId);
    if (!target) return;
    const body = modalEl.querySelector('#equip-modal-body');
    body.innerHTML = renderCharPanel(target);
    wireDnD(modalEl, charId);
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
  }

  async function init(){
    ensureModal();
    // Try to preload state, but don't block wiring if it fails (e.g., transient 401/redirect)
    try { await loadState(); } catch(e) { console.warn('equipment: initial state load failed, will lazy-load on click'); }
    // Bind click handlers even if state failed to load; we'll lazy load on demand
    document.querySelectorAll('.btn-equip-panel, .btn-bag-panel').forEach(btn => {
      // Avoid double-binding when navigating between pages with turbolinks-like behavior
      if (btn.__equipWired) return; btn.__equipWired = true;
      btn.addEventListener('click', async ()=>{
        const cid = parseInt(btn.getAttribute('data-char-id'), 10);
        if (!state) {
          try { await loadState(); } catch(e) { console.error('equipment: unable to load state', e); return; }
        }
        openForChar(cid);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
