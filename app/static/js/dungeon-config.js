// dungeon-config.js — difficulty/affix selector for dungeon screen
(function () {
  const THREAT_NAMES = [
    [0,  0,  'Calm',         'threat-calm'],
    [1,  2,  'Troubled',     'threat-troubled'],
    [3,  5,  'Dire',         'threat-dire'],
    [6,  9,  'Harrowing',    'threat-harrowing'],
    [10, 14, 'Catastrophic', 'threat-catastrophic'],
    [15, Infinity, 'Doomed', 'threat-doomed'],
  ];

  let tier = 1;
  let selectedAffixes = new Set();
  let affixData = [];
  let initialized = false;

  function threatInfo(score) {
    for (const [lo, hi, name, cls] of THREAT_NAMES) {
      if (score >= lo && score <= hi) return { name, cls };
    }
    return { name: 'Doomed', cls: 'threat-doomed' };
  }

  function threatScore() {
    const affixWeight = affixData
      .filter(a => selectedAffixes.has(a.affix_id))
      .reduce((s, a) => s + (a.threat_weight || 1), 0);
    return affixWeight + (tier - 1) * 2;
  }

  function updateChecklist() {
    const tierNames = { 1: 'Normal', 2: 'Heroic', 3: 'Mythic' };
    const diffRow = document.getElementById('dungeon-check-difficulty');
    if (diffRow) diffRow.textContent = 'Difficulty: ' + (tierNames[tier] || 'Normal');

    const score = threatScore();
    const info = threatInfo(score);
    const affixRow = document.getElementById('dungeon-check-affixes');
    if (affixRow) {
      if (selectedAffixes.size === 0) {
        affixRow.innerHTML = '<span class="text-muted">No affixes selected</span>';
      } else {
        const names = affixData
          .filter(a => selectedAffixes.has(a.affix_id))
          .map(a => a.name)
          .join(', ');
        affixRow.innerHTML = names + ' <span class="threat-rating-display ' + info.cls + '">[' + info.name + ']</span>';
      }
    }

    // Sync hidden form fields
    const tierField = document.getElementById('hidden-difficulty-tier');
    if (tierField) tierField.value = tier;
    const affixField = document.getElementById('hidden-affix-ids');
    if (affixField) affixField.value = JSON.stringify([...selectedAffixes]);
  }

  function renderAffixGrid() {
    const grid = document.getElementById('affix-grid');
    if (!grid) return;
    grid.innerHTML = affixData.map(function (a) {
      const sel = selectedAffixes.has(a.affix_id) ? 'selected' : '';
      const color = a.color || '#888';
      return '<div class="affix-card ' + sel + '" data-affix-id="' + a.affix_id + '" data-affix-color="' + color + '">' +
        '<div class="affix-card-name" data-name-color="' + color + '">' + a.name +
          '<span class="badge bg-secondary affix-threat-badge">⚠' + a.threat_weight + '</span>' +
        '</div>' +
        '<div class="affix-card-desc">' + (a.description || '') + '</div>' +
        '</div>';
    }).join('');

    // Apply CSS custom property via JS (avoids inline style in HTML)
    grid.querySelectorAll('.affix-card').forEach(function (card) {
      const color = card.dataset.affixColor;
      if (color) card.style.setProperty('--affix-color', color);
      const nameEl = card.querySelector('.affix-card-name');
      if (nameEl) nameEl.style.color = color;

      card.addEventListener('click', function () {
        const id = card.dataset.affixId;
        if (selectedAffixes.has(id)) selectedAffixes.delete(id);
        else selectedAffixes.add(id);
        card.classList.toggle('selected');
        updateChecklist();
      });
    });
  }

  async function init() {
    if (initialized) return;
    initialized = true;

    // Difficulty buttons
    document.querySelectorAll('.difficulty-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.difficulty-btn').forEach(function (b) {
          b.classList.remove('active', 'btn-primary');
          b.classList.add('btn-outline-secondary');
        });
        btn.classList.remove('btn-outline-secondary');
        btn.classList.add('active', 'btn-primary');
        tier = parseInt(btn.dataset.tier, 10);
        updateChecklist();
      });
    });

    // Fetch affixes
    try {
      const resp = await fetch('/api/dungeon/affixes');
      if (resp.ok) {
        affixData = await resp.json();
        renderAffixGrid();
      }
    } catch (e) {
      console.warn('[dungeon-config] failed to load affixes', e);
    }

    updateChecklist();
  }

  // Init when dungeon tab becomes active
  document.addEventListener('DOMContentLoaded', function () {
    const dungeonTab = document.querySelector('[data-bs-target="#lobby-dungeon"]');
    if (dungeonTab) {
      dungeonTab.addEventListener('shown.bs.tab', init);
    } else {
      init();
    }
  });

  window.dungeonConfig = {
    open: init,
    getTier: function () { return tier; },
    getAffixes: function () { return [...selectedAffixes]; },
  };
})();
