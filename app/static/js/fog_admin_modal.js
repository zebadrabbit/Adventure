// Admin fog modal logic extracted to external file (no inline scripts)
(function(){
  document.addEventListener('DOMContentLoaded', function(){
    const modalEl = document.getElementById('fogAdminModal');
    if (!modalEl) return;
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
