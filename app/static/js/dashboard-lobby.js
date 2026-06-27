/* dashboard-lobby.js — Lobby tab state + party/barracks/recruit interactions */
(function () {
  'use strict';

  // ── Tab state persistence ────────────────────────────────────────────────
  const NAV_KEY = 'lobby_active_tab';

  function activateTab(targetId) {
    const btn = document.querySelector(`#lobbyTabNav [data-bs-target="#${targetId}"]`);
    if (!btn) return;
    const tab = bootstrap.Tab.getOrCreateInstance(btn);
    tab.show();
  }

  const savedTab = sessionStorage.getItem(NAV_KEY);
  if (savedTab) activateTab(savedTab);

  document.querySelectorAll('#lobbyTabNav .nav-link').forEach(btn => {
    btn.addEventListener('shown.bs.tab', e => {
      const target = e.target.getAttribute('data-bs-target');
      if (target) sessionStorage.setItem(NAV_KEY, target.replace('#', ''));
      // Fetch candidates when Recruit tab opens
      if (target === '#lobby-recruit') loadCandidates();
    });
  });

  // ── Switch tab helper (used by buttons with data-lobby-switch) ───────────
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-lobby-switch]');
    if (btn) activateTab(btn.dataset.lobbySwitch);
  });

  // ── Party tab — empty slot clicks go to Barracks ─────────────────────────
  document.querySelectorAll('.party-slot-empty').forEach(slot => {
    slot.addEventListener('click', () => activateTab('lobby-barracks'));
  });

  // ── Party tab — REMOVE button ─────────────────────────────────────────────
  document.addEventListener('click', async e => {
    const btn = e.target.closest('.btn-party-remove');
    if (!btn) return;
    const charId = btn.dataset.charId;
    if (!charId) return;
    btn.disabled = true;
    try {
      const resp = await fetch(`/api/party/remove/${charId}`, { method: 'POST' });
      if (resp.ok) { sessionStorage.setItem('lobby_active_tab', 'lobby-party'); location.reload(); }
      else btn.disabled = false;
    } catch (_) { btn.disabled = false; }
  });

  // ── Party tab — GO DUNGEON button ─────────────────────────────────────────
  const goDungeonBtn = document.getElementById('lobby-go-dungeon-btn');
  if (goDungeonBtn) {
    goDungeonBtn.addEventListener('click', () => activateTab('lobby-dungeon'));
  }

  // ── Party tab — AUTO-FILL ─────────────────────────────────────────────────
  const autofillBtn = document.getElementById('lobby-autofill-btn');
  if (autofillBtn) {
    autofillBtn.addEventListener('click', async () => {
      autofillBtn.disabled = true;
      autofillBtn.textContent = 'Filling…';
      try {
        const resp = await fetch('/autofill_characters', {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
        });
        if (resp.ok) { sessionStorage.setItem('lobby_active_tab', 'lobby-party'); location.reload(); }
        else { autofillBtn.disabled = false; autofillBtn.textContent = 'AUTO-FILL'; }
      } catch (_) { autofillBtn.disabled = false; autofillBtn.textContent = 'AUTO-FILL'; }
    });
  }

  // ── Barracks tab — card selection ────────────────────────────────────────
  const barracksGrid = document.getElementById('barracks-grid');
  const addPartyBtn = document.getElementById('barracks-add-party-btn');

  function selectedBarracksIds() {
    return Array.from(document.querySelectorAll('.barracks-card.selected')).map(c => parseInt(c.dataset.id));
  }

  function updateAddPartyBtn() {
    if (!addPartyBtn) return;
    const count = selectedBarracksIds().length;
    addPartyBtn.disabled = count === 0;
    addPartyBtn.textContent = count > 0 ? `ADD TO PARTY (${count})` : 'ADD TO PARTY';
  }

  if (barracksGrid) {
    barracksGrid.addEventListener('click', e => {
      const card = e.target.closest('.barracks-card');
      if (!card || card.dataset.inParty === 'true') return;
      if (e.target.closest('form') || e.target.closest('button')) return;
      card.classList.toggle('selected');
      updateAddPartyBtn();
    });
  }

  if (addPartyBtn) {
    addPartyBtn.addEventListener('click', async () => {
      const ids = selectedBarracksIds();
      if (!ids.length) return;
      addPartyBtn.disabled = true;
      try {
        const resp = await fetch('/api/party/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ char_ids: ids }),
        });
        if (resp.ok) { sessionStorage.setItem(NAV_KEY, 'lobby-party'); location.reload(); }
        else addPartyBtn.disabled = false;
      } catch (_) { addPartyBtn.disabled = false; }
    });
  }

  // Barracks "RECRUIT MORE →" button
  const barracksRecruitBtn = document.getElementById('barracks-recruit-btn');
  const barracksRecruitEmptyBtn = document.getElementById('barracks-recruit-empty-btn');
  if (barracksRecruitBtn) barracksRecruitBtn.addEventListener('click', () => activateTab('lobby-recruit'));
  if (barracksRecruitEmptyBtn) barracksRecruitEmptyBtn.addEventListener('click', () => activateTab('lobby-recruit'));

  // ── Barracks tab — sort controls ─────────────────────────────────────────
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      sortBarracks(btn.dataset.sort);
    });
  });

  function sortBarracks(by) {
    if (!barracksGrid) return;
    const cols = Array.from(barracksGrid.querySelectorAll(':scope > .col-12, :scope > [class*="col-"]'));
    cols.sort((a, b) => {
      const ca = a.querySelector('.barracks-card');
      const cb = b.querySelector('.barracks-card');
      if (!ca || !cb) return 0;
      if (by === 'level') return parseInt(cb.dataset.level || 0) - parseInt(ca.dataset.level || 0);
      if (by === 'class') return (ca.dataset.class || '').localeCompare(cb.dataset.class || '');
      if (by === 'name')  return (ca.dataset.name || '').localeCompare(cb.dataset.name || '');
      return 0;
    });
    cols.forEach(col => barracksGrid.appendChild(col));
  }

  // ── Recruit tab ──────────────────────────────────────────────────────────
  let candidates = [];
  let loaded = false;

  async function loadCandidates() {
    const grid = document.getElementById('recruit-candidates-grid');
    if (!grid) return;
    if (loaded) return;
    loaded = false;
    grid.innerHTML = '<div class="col-12 text-center py-4 text-muted small"><span class="spinner-border spinner-border-sm me-2"></span>Loading candidates…</div>';
    try {
      const resp = await fetch('/api/recruit/candidates');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      candidates = await resp.json();
      renderCandidates(grid);
      loaded = true;
    } catch (err) {
      grid.innerHTML = `<div class="col-12 text-center py-4 text-danger small">Failed to load candidates. <button class="tactical-btn-secondary btn-sm ms-2" id="recruit-retry-btn">Retry</button></div>`;
      document.getElementById('recruit-retry-btn')?.addEventListener('click', () => { loaded = false; loadCandidates(); });
    }
  }

  function renderCandidates(grid) {
    const STAT_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
    const tweaks = candidates.map(() => ({}));

    function totalTweaks(i) {
      return Object.values(tweaks[i]).reduce((s, v) => s + v, 0);
    }

    function buildCard(i, c) {
      const t = tweaks[i];
      const remaining = 2 - totalTweaks(i);
      return `
        <div class="col-12 col-md-6 col-xl-3">
          <div class="tactical-panel candidate-card" data-candidate="${i}">
            <div class="panel-header">
              <h5><span class="class-badge ${c.cls}-badge me-2">${c.cls.toUpperCase()}</span>${c.name}</h5>
            </div>
            <div class="panel-body">
              <div class="candidate-stats-grid">
                ${STAT_KEYS.map(k => `
                  <div class="candidate-stat-row" data-stat="${k}" data-idx="${i}">
                    <span class="stat-label">${k.toUpperCase()}</span>
                    <span class="stat-val">${(c.stats[k] || 0) + (t[k] || 0)}</span>
                    <button class="tactical-btn-secondary stat-tweak-btn" data-dir="-1"
                      ${(t[k] || 0) <= 0 ? 'disabled' : ''}>−</button>
                    <button class="tactical-btn-secondary stat-tweak-btn" data-dir="1"
                      ${remaining <= 0 ? 'disabled' : ''}>+</button>
                  </div>`).join('')}
              </div>
              <div class="stat-points-counter mb-2">STAT POINTS: ${remaining} remaining</div>
              <div class="small text-muted mb-2">
                HP ${c.stats.hp} · MP ${c.stats.mana}
              </div>
              <button class="deploy-btn btn-full-width btn-hire" data-idx="${i}">HIRE</button>
            </div>
          </div>
        </div>`;
    }

    function rerender() {
      grid.innerHTML = candidates.map((c, i) => buildCard(i, c)).join('');
      attachCandidateEvents();
    }

    function attachCandidateEvents() {
      // Stat tweak buttons
      grid.querySelectorAll('.stat-tweak-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          const row = btn.closest('[data-stat]');
          if (!row) return;
          const stat = row.dataset.stat;
          const idx = parseInt(row.dataset.idx);
          const dir = parseInt(btn.dataset.dir);
          const t = tweaks[idx];
          const cur = t[stat] || 0;
          if (dir < 0 && cur <= 0) return;
          if (dir > 0 && totalTweaks(idx) >= 2) return;
          t[stat] = cur + dir;
          if (t[stat] === 0) delete t[stat];
          rerender();
        });
      });

      // Hire buttons
      grid.querySelectorAll('.btn-hire').forEach(btn => {
        btn.addEventListener('click', async () => {
          const idx = parseInt(btn.dataset.idx);
          const c = candidates[idx];
          btn.disabled = true;
          btn.textContent = 'Hiring…';
          try {
            const resp = await fetch('/api/recruit/hire', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: c.name,
                cls: c.cls,
                stats: c.stats,
                gear_slugs: c.gear_slugs,
                stat_tweaks: tweaks[idx],
              }),
            });
            if (resp.ok) {
              sessionStorage.setItem(NAV_KEY, 'lobby-barracks');
              location.reload();
            } else {
              const err = await resp.json().catch(() => ({}));
              btn.disabled = false;
              btn.textContent = 'HIRE';
              alert(err.error || 'Hire failed');
            }
          } catch (_) { btn.disabled = false; btn.textContent = 'HIRE'; }
        });
      });
    }

    rerender();
  }

  // Reroll button
  const rerollBtn = document.getElementById('recruit-reroll-btn');
  if (rerollBtn) {
    rerollBtn.addEventListener('click', () => { loaded = false; loadCandidates(); });
  }

  // Auto-load if Recruit tab is already active on page load
  const activeTab = document.querySelector('#lobbyTabNav .nav-link.active');
  if (activeTab && activeTab.getAttribute('data-bs-target') === '#lobby-recruit') {
    loadCandidates();
  }

})();
