// Seed widget logic (centralized on dashboard page)
(function(){
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('seed-widget');
    if (!container) return; // Not present
  const btnNew = document.getElementById('btn-new-seed');
  const btnApply = null; // removed button
    const input = document.getElementById('input-custom-seed');
    const status = document.getElementById('seed-status');

    function setStatus(msg, kind='info') {
      // Now minimized: we suppress success chatter per updated UX; only show errors.
      if (!status) return;
      if (kind === 'error') {
        status.textContent = msg;
        status.className = 'small text-danger';
      } else {
        status.textContent = '';
        status.className = 'small text-muted';
      }
    }

  let debounceTimer = null;
  const DEBOUNCE_MS = 450;

  async function postSeed(seedValue, regenerate=false) {
      try {
  // No verbose status on start per UX revision.
        const payload = {};
        if (seedValue !== undefined && seedValue !== null && seedValue !== '') payload.seed = seedValue;
        if (regenerate) payload.regenerate = true;
        const resp = await fetch('/api/dungeon/seed', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('HTTP '+resp.status);
        const data = await resp.json();
  // Write resulting seed into the input so user sees current value.
  if (input) input.value = data.seed;
        // Optionally update any global seed badge if present later
        const badge = document.getElementById('dungeon-seed-badge');
        if (badge) badge.textContent = 'seed: ' + data.seed;
        return data.seed;
      } catch (e) {
        console.error('[seed-widget] error', e);
        setStatus('Failed to set seed', 'error');
      }
    }

    if (btnNew) {
      btnNew.addEventListener('click', () => {
        postSeed(null, true);
      });
    }
    if (input) {
      input.addEventListener('input', () => {
        if (debounceTimer) clearTimeout(debounceTimer);
        const val = input.value.trim();
        debounceTimer = setTimeout(() => {
          if (val.length > 0) postSeed(val, false);
        }, DEBOUNCE_MS);
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (debounceTimer) clearTimeout(debounceTimer);
          const val = input.value.trim();
            if (val.length > 0) postSeed(val, false);
        }
      });
      input.addEventListener('blur', () => {
        if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
        const val = input.value.trim();
        if (val.length > 0) postSeed(val, false);
      });
    }

    // Initialize status with current seed if present
    const initial = container.getAttribute('data-initial-seed');
  if (initial && input) input.value = initial;
  });
})();
