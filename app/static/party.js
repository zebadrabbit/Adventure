// party.js - Manage party selection on dashboard
// Allows selecting up to 4 characters, updates summary and hidden inputs


(function() {
  const maxParty = 4;
  const selects = Array.from(document.querySelectorAll('.party-select'));
  const countEl = document.getElementById('party-count');
  const hiddenContainer = document.getElementById('party-hidden-inputs');
  const beginBtn = document.getElementById('begin-adventure-btn');
  const cards = Array.from(document.querySelectorAll('.character-card'));

  if (!countEl || !beginBtn) return;

  function getSelected() {
    return selects.filter(cb => cb.checked).map(cb => ({
      id: cb.getAttribute('data-id'),
      name: cb.getAttribute('data-name'),
      klass: cb.getAttribute('data-class')
    }));
  }

  function renderHiddenInputs(selected) {
    hiddenContainer.innerHTML = '';
    selected.forEach((s, idx) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'party_ids';
      input.value = s.id;
      hiddenContainer.appendChild(input);
    });
  }

  function updateUI() {
    const sel = getSelected();
    const n = sel.length;
    countEl.textContent = n.toString();
    beginBtn.disabled = n === 0 || n > maxParty;
    renderHiddenInputs(sel);

    // Enforce limit by disabling other unchecked boxes
    if (n >= maxParty) {
      selects.forEach(cb => {
        if (!cb.checked) cb.disabled = true;
      });
    } else {
      selects.forEach(cb => { cb.disabled = false; });
    }

    // Add/remove glow class
    cards.forEach(card => {
      const id = card.getAttribute('data-id');
      const cb = document.querySelector(`.party-select[data-id="${id}"]`);
      if (cb && cb.checked) {
        card.classList.add('selected');
      } else {
        card.classList.remove('selected');
      }
    });
  }

  selects.forEach(cb => cb.addEventListener('change', updateUI));

  // Toggle selection when clicking card area
  cards.forEach(card => {
    card.addEventListener('click', (e) => {
      // Ignore clicks on interactive elements inside the card to avoid double toggles
      const target = e.target;
      const ignore = target.closest('a, button, input, label, form');
      if (ignore) return;
      const id = card.getAttribute('data-id');
      const cb = document.querySelector(`.party-select[data-id="${id}"]`);
      if (!cb) return;
      if (cb.disabled && !cb.checked) return; // at limit and this one is unchecked
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });
  updateUI();
})();
