// project: Adventure MUD
// module: dashboard-autofill.js
// Adds client-side wiring for the Autofill party button calling /autofill_characters
// License: MIT

(function () {
  const btn = document.getElementById('autofill-party-btn');
  if (!btn) return;
  const partyTable = document.getElementById('party-table');
  const partyCount = document.getElementById('party-count');
  const hiddenInputs = document.getElementById('party-hidden-inputs');
  const beginBtn = document.getElementById('begin-adventure-btn');

  let busy = false;
  function flash(msg, cls = 'info', ttl = 2200) {
    try {
      let container = document.getElementById('autofill-flash');
      if (!container) {
        container = document.createElement('div');
        container.id = 'autofill-flash';
        container.className = 'mt-2';
        btn.parentElement.appendChild(container);
      }
      container.innerHTML = `<div class="alert alert-${cls} py-1 px-2 mb-0 small">${msg}</div>`;
      setTimeout(() => { if (container) container.innerHTML = ''; }, ttl);
    } catch (_) { }
  }

  function renderParty(party) {
    if (!Array.isArray(party) || party.length === 0) {
      partyTable.innerHTML = '';
      if (partyCount) partyCount.textContent = '0';
      if (beginBtn) beginBtn.disabled = true;
      if (hiddenInputs) hiddenInputs.innerHTML = '';
      return;
    }
    let html = `<div class="table-responsive"><table class="table table-sm table-dark table-striped table-bordered mb-0 party-table-compact" style="border-radius:.5rem;overflow:hidden;font-size:.95rem;">`;
    html += `<thead class=\"table-warning text-dark\"><tr><th class='ps-2'>Name</th><th>HP</th><th>Mana</th><th>Class</th></tr></thead><tbody>`;
    party.forEach(p => {
      html += `<tr><td class='ps-2 fw-semibold'>${p.name}</td><td class='text-center'>${p.hp}</td><td class='text-center'>${p.mana}</td><td class='text-center'>${p.class}</td></tr>`;
    });
    html += '</tbody></table></div>';
    partyTable.innerHTML = html;
    if (partyCount) partyCount.textContent = party.length;
    if (beginBtn) beginBtn.disabled = !(party.length >= 1 && party.length <= 4);
    if (hiddenInputs) {
      hiddenInputs.innerHTML = '';
      party.forEach(p => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'party_ids';
        input.value = p.id;
        hiddenInputs.appendChild(input);
      });
    }
  }

  async function autofill() {
    if (busy) return; busy = true; btn.disabled = true; btn.classList.add('disabled');
    btn.dataset.originalText = btn.dataset.originalText || btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Building…';
    try {
      const resp = await fetch('/autofill_characters', {
        method: 'POST',
        headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
      });
      if (!resp.ok) { flash('Autofill failed (' + resp.status + ')', 'danger'); return; }
      const data = await resp.json();
      renderParty(data.party);
      flash((data.created > 0 ? 'Added ' + data.created + ' new; ' : '') + 'Party ready (' + data.party_size + ')', 'success');
      // Also mark the corresponding character cards as selected visually (if they exist)
      const ids = new Set(data.party.map(p => String(p.id)));
      document.querySelectorAll('.party-select').forEach(cb => {
        const id = cb.getAttribute('data-id');
        cb.checked = ids.has(id);
        cb.dispatchEvent(new Event('change', { bubbles: true }));
      });
    } catch (err) {
      console.error('[autofill] error', err);
      flash('Error – check console', 'danger');
    } finally {
      busy = false; btn.disabled = false; btn.classList.remove('disabled');
      btn.innerHTML = btn.dataset.originalText || 'Autofill';
    }
  }

  btn.addEventListener('click', autofill);
  console.debug('[dashboard-autofill] simplified autofill ready');
})();
