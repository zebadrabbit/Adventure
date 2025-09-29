// Admin fog modal logic extracted to external file (no inline scripts)
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('fogAdminModal');
    if (!modalEl) return;
    function renderMetrics() {
      // Legacy server metrics removed; show local coverage only.
      const table = document.getElementById('fog-admin-metrics-table');
      if (!table) return;
      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      const total = window.dungeonTileLayers ? Object.keys(window.dungeonTileLayers).length : 0;
      const seen = window.dungeonSeenTiles ? window.dungeonSeenTiles.size : 0;
      const pct = total ? ((seen / total) * 100).toFixed(2) : '0.00';
      tbody.innerHTML = `<tr><td colspan="7">Local coverage: ${seen}/${total} (${pct}%)</td></tr>`;
      const totEl = document.getElementById('fog-admin-metrics-totals');
      if (totEl) totEl.textContent = `Local coverage only`;
    }
    function refreshCounts() {
      const localCountEl = document.getElementById('fog-admin-local-count');
      const seen = window.dungeonSeenTiles ? window.dungeonSeenTiles.size : 0;
      if (localCountEl) localCountEl.textContent = seen + ' tiles';
      const serverEl = document.getElementById('fog-admin-server-count');
      if (serverEl) serverEl.textContent = '(deprecated)';
      renderMetrics();
      const cfgEl = document.getElementById('fog-admin-config');
      if (cfgEl && window.dungeonDev && window.dungeonDev.getFogConfig) {
        cfgEl.textContent = JSON.stringify(window.dungeonDev.getFogConfig(), null, 2);
      }
    }
    modalEl.addEventListener('shown.bs.modal', refreshCounts);
    const dumpBtn = document.getElementById('fog-admin-dump');
    if (dumpBtn) dumpBtn.addEventListener('click', () => { if (window.dungeonDev) window.dungeonDev.coverage(); refreshCounts(); });
    // forceSync removed (server persistence deprecated)
    const clearLocalBtn = document.getElementById('fog-admin-clear-local');
    if (clearLocalBtn) clearLocalBtn.addEventListener('click', () => { if (window.dungeonDev) window.dungeonDev.clearSeen(); setTimeout(refreshCounts, 200); });
    // clearServer removed (server persistence deprecated)
  });
})();
