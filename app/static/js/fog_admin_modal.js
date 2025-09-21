// Admin fog modal logic extracted to external file (no inline scripts)
(function(){
  document.addEventListener('DOMContentLoaded', function(){
    const modalEl = document.getElementById('fogAdminModal');
    if (!modalEl) return;
    function renderMetrics(metrics){
      const table = document.getElementById('fog-admin-metrics-table');
      if(!table) return;
      const tbody = table.querySelector('tbody');
      if(!tbody) return;
      if(!metrics || !metrics.seeds){
        tbody.innerHTML = '<tr><td colspan="7" class="text-danger">error</td></tr>';
        return;
      }
      if(metrics.seeds.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted">(none)</td></tr>';
      } else {
        tbody.innerHTML = '';
        metrics.seeds.forEach(s => {
          const tr = document.createElement('tr');
            tr.innerHTML = `<td>${s.seed}</td><td>${s.tiles}</td><td>${s.saved_pct}%</td><td>${s.raw_size}</td><td>${s.stored_size}</td><td>${s.last_update||''}</td><td><button data-seed="${s.seed}" class="btn btn-sm btn-outline-danger fog-admin-clear-seed">Clear</button></td>`;
          tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.fog-admin-clear-seed').forEach(btn => {
          btn.addEventListener('click', e => {
            const seed = e.currentTarget.getAttribute('data-seed');
            fetch('/api/dungeon/seen/clear', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({seed: Number(seed)})})
              .then(()=> setTimeout(refreshCounts, 400));
          });
        });
      }
      const totEl = document.getElementById('fog-admin-metrics-totals');
      if(totEl && metrics.totals){
        totEl.textContent = `Totals: ${metrics.totals.tiles} tiles; saved ${metrics.totals.saved_pct}% (${metrics.totals.raw_size} -> ${metrics.totals.stored_size} bytes)`;
      }
    }
    function refreshCounts() {
      const localCountEl = document.getElementById('fog-admin-local-count');
      const seen = window.dungeonSeenTiles ? window.dungeonSeenTiles.size : 0;
      if (localCountEl) localCountEl.textContent = seen + ' tiles';
      fetch('/api/dungeon/seen').then(r=> r.ok ? r.json():null).then(data => {
        const serverEl = document.getElementById('fog-admin-server-count');
        if (!serverEl) return;
        if (!data) { serverEl.textContent = 'error'; return; }
        const ct = data.tiles ? data.tiles.split(';').filter(Boolean).length : 0;
        serverEl.textContent = ct + ' tiles (seed ' + data.seed + ')';
      }).catch(()=>{
        const serverEl = document.getElementById('fog-admin-server-count');
        if (serverEl) serverEl.textContent = 'error';
      });
      // Metrics
      fetch('/api/dungeon/seen/metrics').then(r => r.ok ? r.json() : null).then(m => renderMetrics(m)).catch(()=>renderMetrics(null));
      const cfgEl = document.getElementById('fog-admin-config');
      if (cfgEl && window.dungeonDev && window.dungeonDev.getFogConfig) {
        cfgEl.textContent = JSON.stringify(window.dungeonDev.getFogConfig(), null, 2);
      }
    }
    modalEl.addEventListener('shown.bs.modal', refreshCounts);
    const dumpBtn = document.getElementById('fog-admin-dump');
    if (dumpBtn) dumpBtn.addEventListener('click', () => { if(window.dungeonDev) window.dungeonDev.coverage(); refreshCounts(); });
    const syncBtn = document.getElementById('fog-admin-force-sync');
    if (syncBtn) syncBtn.addEventListener('click', () => { if(window.dungeonDev && window.dungeonDev.forceSync) window.dungeonDev.forceSync(); setTimeout(refreshCounts, 700); });
    const clearLocalBtn = document.getElementById('fog-admin-clear-local');
    if (clearLocalBtn) clearLocalBtn.addEventListener('click', () => { if(window.dungeonDev) window.dungeonDev.clearSeen(); setTimeout(refreshCounts, 200); });
    const clearServerBtn = document.getElementById('fog-admin-clear-server');
    if (clearServerBtn) clearServerBtn.addEventListener('click', () => {
      fetch('/api/dungeon/seen', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ tiles: '' })})
        .then(()=> setTimeout(refreshCounts, 400));
    });
  });
})();
