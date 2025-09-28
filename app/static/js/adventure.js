// Adventure page dungeon logic extracted from adventure.html
(function () {
  const TILE_SIZE = 64;
  // Fog-of-war configuration:
  // INNER_VIS_RADIUS: tiles within this Manhattan distance are fully visible (original colors).
  // FOG_FULL_RADIUS: outer limit where fog reaches maximum darkness. Tiles beyond this still rendered
  // but nearly opaque black (kept so map shape perception is limited). Increase for larger explored area preview.
  // Opacity scales from MIN_FOG_OPACITY at inner edge to MAX_FOG_OPACITY at outer edge.
  // Fog parameters (smooth radial gradient + noise + memory)
  const INNER_VIS_RADIUS = 8;       // fully visible radius (Euclidean)
  const FOG_FULL_RADIUS = 26;       // where fog reaches max opacity
  const MIN_FOG_OPACITY = 0.18;     // minimum fog opacity just outside inner radius
  const MAX_FOG_OPACITY = 0.82;     // maximum fog opacity at/after full radius
  const FOG_NOISE_AMPLITUDE = 0.08; // max +/- added to opacity per tile for irregularity
  const MEMORY_DIM_OPACITY = 0.35;  // opacity for previously seen but currently out-of-range tiles
  const MEMORY_STROKE = false;      // memory tiles get no stroke edge
  const MEMORY_FILL_COLOR = '#060606'; // dim color base for memory tiles
  // Fog config persistence keys (user tunable in console)
  const FOG_CFG_KEY = 'adventureFogConfig';
  document.addEventListener('DOMContentLoaded', function () {
    const output = document.getElementById('dungeon-output');
    // Load party characters from data element injected by template (no inline scripts)
    (function loadPartyCharacters() {
      try {
        const el = document.getElementById('party-characters-data');
        if (!el) { window.partyCharacters = window.partyCharacters || []; return; }
        const raw = el.getAttribute('data-json') || '[]';
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          window.partyCharacters = parsed.map(p => ({ id: p.id, name: p.name, class: p.class || p.class_name || '' }));
        }
      } catch (e) { window.partyCharacters = window.partyCharacters || []; }
    })();
    // ------------------------------------------------------------------
    // Dynamic class color theming
    // Fetch centralized class color config from /api/config/class_colors
    // and apply as CSS variables. This allows future runtime palette tweaks
    // or adding new classes without editing static CSS files. If new class
    // slugs are returned that we don't have predefined .class-*/.border-* rules
    // for, we inject them dynamically.
    // ------------------------------------------------------------------
    (function fetchAndApplyClassColors() {
      const endpoint = '/api/config/class_colors';
      fetch(endpoint, { headers: { 'Accept': 'application/json' } })
        .then(r => { if (!r.ok) throw new Error('status ' + r.status); return r.json(); })
        .then(map => {
          if (!map || typeof map !== 'object') return;
          const root = document.documentElement;
          const predefined = new Set(['fighter', 'rogue', 'mage', 'cleric', 'druid', 'ranger']);
          const dynamicRules = [];
          for (const [slug, cfg] of Object.entries(map)) {
            if (!cfg || typeof cfg !== 'object') continue;
            const bg = cfg.bg || cfg.background || '#333';
            const fg = cfg.fg || cfg.color || '#eee';
            const border = cfg.border || cfg.accent || '#555';
            root.style.setProperty(`--class-${slug}-bg`, bg);
            root.style.setProperty(`--class-${slug}-fg`, fg);
            root.style.setProperty(`--class-${slug}-border`, border);
            if (!predefined.has(slug)) {
              dynamicRules.push(`.class-${slug}{background:var(--class-${slug}-bg)!important;color:var(--class-${slug}-fg)!important;}`);
              dynamicRules.push(`.border-${slug}{border:2px solid var(--class-${slug}-border)!important;}`);
              dynamicRules.push(`.class-badge.${slug}-badge{background:var(--class-${slug}-bg);color:var(--class-${slug}-fg);border:1px solid var(--class-${slug}-border);}`);
            }
          }
          if (dynamicRules.length) {
            const styleEl = document.createElement('style');
            styleEl.setAttribute('data-generated', 'class-colors');
            styleEl.textContent = dynamicRules.join('\n');
            document.head.appendChild(styleEl);
          }
        })
        .catch(err => {
          // Non-fatal: keep existing static palette. Silent in production; log compact info for debugging.
          if (window && window.console) {
            console.debug('[class-colors] fetch skipped/fallback:', err.message);
          }
        });
    })();
    // ------------------------------------------------------------
    // Seen tile persistence + throttled save (localStorage)
    // ------------------------------------------------------------
    const SEEN_STORAGE_PREFIX = 'adventureSeenTiles:';
    const SEEN_SAVE_THROTTLE_MS = 1500;
    let lastSeenSave = 0;

    function seenStorageKey() {
      return SEEN_STORAGE_PREFIX + (window.currentDungeonSeed != null ? window.currentDungeonSeed : 'default');
    }

    function loadSeenTilesFromStorage() {
      try {
        const raw = localStorage.getItem(seenStorageKey());
        if (!raw) return new Set();
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) return new Set(arr);
      } catch (e) { /* ignore parse/storage errors */ }
      return new Set();
    }

    function saveSeenTiles(seenSet) {
      try {
        const arr = Array.from(seenSet);
        localStorage.setItem(seenStorageKey(), JSON.stringify(arr));
      } catch (e) { /* ignore quota or storage errors */ }
    }

    function saveSeenTilesThrottled(seenSet) {
      const now = performance.now();
      if (now - lastSeenSave < SEEN_SAVE_THROTTLE_MS) return;
      lastSeenSave = now;
      saveSeenTiles(seenSet);
    }

    // ------------------------------------------------------------
    // Fog configuration persistence (radius/opacity). Exposed via console commands.
    // ------------------------------------------------------------
    function loadFogConfig() {
      try {
        const raw = localStorage.getItem(FOG_CFG_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
      } catch (e) { return null; }
    }
    function saveFogConfig(cfg) {
      try { localStorage.setItem(FOG_CFG_KEY, JSON.stringify(cfg)); } catch (e) { }
    }
    // Only reading current constants (immutable) – for future dynamic tuning we could reassign globals.
    function currentFogConfig() {
      return {
        innerRadius: INNER_VIS_RADIUS,
        fullRadius: FOG_FULL_RADIUS,
        minOpacity: MIN_FOG_OPACITY,
        maxOpacity: MAX_FOG_OPACITY,
        noise: FOG_NOISE_AMPLITUDE,
        memoryOpacity: MEMORY_DIM_OPACITY
      };
    }
    // If persisted config differs in future when we allow dynamic adjusting, we'd apply here.
    (function initFogConfig() {
      const cfg = loadFogConfig();
      if (cfg) {
        // Placeholder: accepting persisted values later when we allow overrides.
        // We intentionally do not mutate constants now to keep code simple.
      }
    })();
    // Position element removed per design update (compass + log only)
    // Legacy exits button container removed
    const moveNorthBtn = document.getElementById('btn-move-n');
    const moveSouthBtn = document.getElementById('btn-move-s');
    const moveEastBtn = document.getElementById('btn-move-e');
    const moveWestBtn = document.getElementById('btn-move-w');
    let availableExits = [];
    let keyboardEnabled = true;
    const keyboardToggle = document.getElementById('toggle-keyboard-move');
    if (keyboardToggle) {
      keyboardEnabled = keyboardToggle.checked;
      keyboardToggle.addEventListener('change', () => { keyboardEnabled = keyboardToggle.checked; });
    }
    // Movement throttling & queue
    let moveInFlight = false;
    const moveQueue = [];
    const liveRegionId = 'dungeon-live-region';
    let liveRegion = document.getElementById(liveRegionId);
    if (!liveRegion) {
      liveRegion = document.createElement('div');
      liveRegion.id = liveRegionId;
      liveRegion.setAttribute('aria-live', 'polite');
      liveRegion.setAttribute('aria-atomic', 'true');
      liveRegion.className = 'visually-hidden';
      document.body.appendChild(liveRegion);
    }

    // Shared tooltip system now provided by tooltips.js (MUDTooltips)
    function showTooltip() { /* retained for legacy listeners; actual logic handled by Bootstrap */ }
    function hideTooltip() { /* retained for legacy listeners */ }

    // Movement queue helpers (restored after refactor)
    function queueMove(dir) {
      moveQueue.push(dir);
      if (!moveInFlight) processNextMove();
    }
    function processNextMove() {
      if (moveInFlight) return;
      const next = moveQueue.shift();
      if (!next) return;
      executeMove(next);
    }

    // ------------------------------------------------------------
    // Notice markers (spots with recalled / potential loot/search)
    // Lightweight recreation after refactor that removed originals.
    // ------------------------------------------------------------
    const noticeMarkers = window.noticeMarkers || (window.noticeMarkers = {});
    function keyFor(x, y) { return x + ',' + y; }
    function addNoticeMarker(x, y) {
      try {
        if (!window.dungeonMap) return;
        const k = keyFor(x, y);
        if (noticeMarkers[k]) return; // already present
        const lat = (y + 0.5) * TILE_SIZE;
        const lng = (x + 0.5) * TILE_SIZE;
        const marker = L.circleMarker([lat, lng], {
          radius: 6,
          color: '#ffc107',
          weight: 2,
          fillColor: '#ffc107',
          fillOpacity: 0.9
        }).addTo(window.dungeonMap);
        noticeMarkers[k] = { marker, x, y };
      } catch (e) { /* noop */ }
    }
    function removeNoticeMarker(x, y) {
      try {
        const k = keyFor(x, y);
        const entry = noticeMarkers[k];
        if (entry) {
          try { window.dungeonMap && window.dungeonMap.removeLayer(entry.marker); } catch (e) { }
          delete noticeMarkers[k];
        }
      } catch (e) { /* noop */ }
    }
    function refreshNoticeMarkers() {
      // Optional server-driven refresh; if endpoint missing, fails silently.
      fetch('/api/dungeon/notices')
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data) return;
          if (Array.isArray(data.positions)) {
            data.positions.forEach(p => {
              if (Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1])) {
                addNoticeMarker(p[0], p[1]);
              }
            });
          }
        })
        .catch(() => { });
    }

    function canSearchHere() {
      if (!window.currentPos) return false;
      const k = keyFor(window.currentPos[0], window.currentPos[1]);
      return !!noticeMarkers[k];
    }

    function renderInlineSearch(container) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-outline-warning btn-sm ms-1 inline-search-btn';
      btn.textContent = 'Search';
      btn.disabled = !canSearchHere();
      btn.dataset.clicked = '0';
      btn.addEventListener('click', (ev) => {
        ev.preventDefault();
        if (btn.disabled) return;
        // Deactivate this specific Search button immediately after click
        btn.dataset.clicked = '1';
        btn.disabled = true;
        doSearch(btn);
      });
      container.appendChild(btn);
      return btn;
    }

    function updateInlineSearchButtons() {
      const nodes = document.querySelectorAll('.dungeon-output .inline-search-btn');
      nodes.forEach(n => {
        try {
          const alreadyClicked = (n.dataset && n.dataset.clicked === '1');
          n.disabled = alreadyClicked || !canSearchHere();
        } catch (e) { }
      });
    }

    function executeMove(dir) {
      moveInFlight = true;
      fetch('/api/dungeon/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir })
      })
        .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(data => {
          if (data && data.desc && output) {
            renderLogFromDesc(String(data.desc));
            if (data.last_roll) {
              try { updateLastRollUI(data.last_roll); } catch (e) { }
            }
          }
          if (data && data.pos) {
            const pxY = (data.pos[1] + 0.5) * TILE_SIZE;
            const pxX = (data.pos[0] + 0.5) * TILE_SIZE;
            if (window.dungeonPlayerMarker && window.dungeonMap && Number.isFinite(pxY) && Number.isFinite(pxX)) {
              window.dungeonPlayerMarker.setLatLng([pxY, pxX]);
              window.dungeonMap.panTo([pxY, pxX], { animate: true });
              window.currentPos = data.pos;
              // Update fog-of-war visibility after movement
              if (Array.isArray(data.pos)) {
                try { updateDungeonVisibility(data.pos[0], data.pos[1]); } catch (e) { /* noop */ }
              }
              // If newly noticed, add marker persistently
              if (data.noticed_loot) {
                addNoticeMarker(data.pos[0], data.pos[1]);
              }
              // Update inline search buttons based on current tile
              updateInlineSearchButtons();
            }
          }
          if (data && Array.isArray(data.exits)) {
            availableExits = data.exits.map(e => e.toLowerCase());
          } else if (data && data.desc) {
            const match = data.desc.match(/Exits: ([^.]*)\./);
            if (match && match[1]) {
              availableExits = match[1].split(',').map(e => e.trim().toLowerCase()).filter(Boolean);
            }
          } else {
            availableExits = [];
          }
        })
        .catch(err => {
          console.error('[dungeon] move error', err);
        })
        .finally(() => {
          renderExitButtons();
          moveInFlight = false;
          setTimeout(processNextMove, 120);
        });
    }

    function renderExitButtons() {
      const normalized = availableExits;
      if (moveNorthBtn) moveNorthBtn.disabled = !normalized.includes('n') && !normalized.includes('north');
      if (moveSouthBtn) moveSouthBtn.disabled = !normalized.includes('s') && !normalized.includes('south');
      if (moveEastBtn) moveEastBtn.disabled = !normalized.includes('e') && !normalized.includes('east');
      if (moveWestBtn) moveWestBtn.disabled = !normalized.includes('w') && !normalized.includes('west');
    }

    // Wire dedicated movement buttons if they exist (add ARIA labels)
    if (moveNorthBtn) { moveNorthBtn.setAttribute('aria-label', 'Move North'); moveNorthBtn.addEventListener('click', () => !moveNorthBtn.disabled && queueMove('n')); }
    if (moveSouthBtn) { moveSouthBtn.setAttribute('aria-label', 'Move South'); moveSouthBtn.addEventListener('click', () => !moveSouthBtn.disabled && queueMove('s')); }
    if (moveEastBtn) { moveEastBtn.setAttribute('aria-label', 'Move East'); moveEastBtn.addEventListener('click', () => !moveEastBtn.disabled && queueMove('e')); }
    if (moveWestBtn) { moveWestBtn.setAttribute('aria-label', 'Move West'); moveWestBtn.addEventListener('click', () => !moveWestBtn.disabled && queueMove('w')); }

    // Unified search action used by inline Search buttons
    let searchInFlight = false;
    function doSearch(invokingBtn) {
      if (searchInFlight) { console.debug('[search] skipped: already in-flight'); return; }
      // Only allow when current tile is noticed (prevents spam). Important: check BEFORE setting in-flight flag.
      const allowed = canSearchHere();
      if (!allowed) { console.debug('[search] blocked: cannot search here (no notice marker at current pos?)'); return; }
      searchInFlight = true;
      console.debug('[search] starting search request');
      fetch('/api/dungeon/search', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
        .then(r => r.json())
        .then(data => {
          console.debug('[search] response payload', data);
          if (!output) return;
          // Prevent duplicates: remove any existing loot list before appending a new one
          try {
            const existingLists = output.querySelectorAll('.loot-list');
            existingLists.forEach(el => el.remove());
          } catch (e) { }
          const foundWithItems = data && data.found && Array.isArray(data.items) && data.items.length;
          if (foundWithItems) {
            const hdr = document.createElement('div');
            hdr.textContent = 'You search the area and discover:';
            output.appendChild(hdr);
            const list = document.createElement('div');
            list.className = 'loot-list mt-1';
            const partyChars = (window.partyCharacters || []).filter(c => c && c.id && c.name);
            data.items.forEach(it => {
              try { console.debug('[search] render loot item', { id: it && it.id, name: it && it.name, rarity: it && it.rarity }); } catch (_e) { }
              const wrapper = document.createElement('div');
              wrapper.className = 'loot-entry d-inline-block me-3 mb-2';
              const label = document.createElement('span');
              label.className = 'loot-label me-1';
              label.textContent = (it.name || it.slug || 'Unknown Item') + ':';
              const rarity = it.rarity || 'common';
              const dropdownDiv = document.createElement('div');
              dropdownDiv.className = 'dropdown d-inline-block';
              const btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'btn btn-sm btn-outline-warning dropdown-toggle';
              btn.setAttribute('data-bs-toggle', 'dropdown');
              btn.setAttribute('aria-expanded', 'false');
              btn.textContent = (it.name || it.slug || 'Item');
              // Debug hook: mark loot id for diagnostics
              btn.setAttribute('data-loot-id', it.id);
              // Ensure a Bootstrap dropdown instance is created (some pages might not auto-init)
              // Fallback manual toggler if Bootstrap dropdown fails to show
              // (Deferred init added later after DOM insertion)
              // Move tooltip to the dropdown button so hovering the button (not just the label) shows details
              if (window.MUDTooltips) {
                try {
                  btn.setAttribute('tabindex', '0');
                  btn.setAttribute('aria-label', `${it.name}`);
                  btn.setAttribute('role', 'button');
                  const attrStr = window.MUDTooltips.attrForItem(it);
                  if (attrStr) {
                    const regex = /([a-zA-Z-]+)="([^"]*)"/g; let m;
                    while ((m = regex.exec(attrStr))) { btn.setAttribute(m[1], m[2]); }
                  }
                } catch (e) { }
              }
              const menu = document.createElement('ul');
              menu.className = 'dropdown-menu';
              menu.setAttribute('data-parent-loot-id', it.id);
              if (!partyChars.length) {
                const li = document.createElement('li');
                li.innerHTML = '<span class="dropdown-item disabled">No party</span>';
                menu.appendChild(li);
              } else {
                partyChars.forEach(pc => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.className = 'dropdown-item';
                  a.textContent = pc.name;
                  a.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    hideTooltip();
                    btn.disabled = true;
                    fetch(`/api/dungeon/loot/claim/${it.id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ character_id: pc.id }) })
                      .then(async r => {
                        const status = r.status;
                        let payload = null; let text = null;
                        try { payload = await r.json(); } catch (e) { try { text = await r.text(); } catch (_) { } }
                        return { status, ok: r.ok, body: payload, rawText: text };
                      })
                      .then(resWrap => {
                        const line = document.createElement('div');
                        line.className = 'small';
                        const res = resWrap.body || {};
                        if (resWrap.ok && res && res.claimed) {
                          line.textContent = `Assigned ${res.item?.name || 'item'} to ${pc.name}.`;
                          wrapper.remove();
                          try { refreshNoticeMarkers(); } catch (e) { }
                          // Notify other UI (equipment modal) that character inventories changed
                          try { document.dispatchEvent(new CustomEvent('mud-characters-state-invalidated', { detail: { character_id: pc.id } })); } catch (e) { }
                          const remaining = list.querySelectorAll('.loot-entry');
                          if (!remaining || remaining.length === 0) {
                            if (window.currentPos) removeNoticeMarker(window.currentPos[0], window.currentPos[1]);
                            updateInlineSearchButtons();
                          }
                        } else {
                          // Build detailed error message
                          const errCore = res?.error || resWrap.rawText || 'unknown error';
                          const detailParts = [];
                          if (res?.message) detailParts.push(res.message);
                          if (res?.where) detailParts.push('where=' + res.where);
                          if (res?.character) detailParts.push('character=' + res.character);
                          if (res?.party) detailParts.push('party=' + JSON.stringify(res.party));
                          if (res?.expected_seed) detailParts.push('expected_seed=' + res.expected_seed);
                          if (res?.row_seed) detailParts.push('row_seed=' + res.row_seed);
                          line.textContent = `Unable to claim (${resWrap.status}): ${errCore}${detailParts.length ? ' [' + detailParts.join('; ') + ']' : ''}`;
                          btn.disabled = false;
                        }
                        output.appendChild(line);
                        try { line.scrollIntoView({ block: 'nearest' }); } catch (e) { }
                        console.debug('[loot] claim response', resWrap);
                      })
                      .catch(err => {
                        console.error('[loot] claim network/parse error', err);
                        const line = document.createElement('div');
                        line.className = 'small text-danger';
                        line.textContent = 'Unable to claim item (network error)';
                        output.appendChild(line);
                        btn.disabled = false;
                      });
                  });
                  li.appendChild(a);
                  menu.appendChild(li);
                });
              }
              dropdownDiv.appendChild(btn);
              dropdownDiv.appendChild(menu);
              wrapper.appendChild(label);
              wrapper.appendChild(dropdownDiv);
              list.appendChild(wrapper);
              // Defer dropdown init until after element & menu are in DOM so Bootstrap can find the menu sibling
              setTimeout(() => {
                try {
                  if (!document.body.contains(btn)) return; // removed meanwhile
                  if (window.bootstrap && bootstrap.Dropdown) {
                    if (bootstrap.Dropdown.getOrCreateInstance) {
                      btn.__mudDropdown = bootstrap.Dropdown.getOrCreateInstance(btn, { autoClose: true, popperConfig: { strategy: 'absolute' } });
                    } else {
                      let existing = bootstrap.Dropdown.getInstance(btn);
                      if (!existing) existing = new bootstrap.Dropdown(btn, { autoClose: true, popperConfig: { strategy: 'absolute' } });
                      btn.__mudDropdown = existing;
                    }
                  } else {
                    // Fallback manual toggle if Bootstrap not present (shouldn't happen now)
                    btn.addEventListener('click', () => {
                      const m = btn.nextElementSibling;
                      if (!m) return;
                      const shown = m.classList.contains('show');
                      m.classList.toggle('show', !shown);
                      if (!shown) {
                        m.style.position = 'absolute';
                        const r = btn.getBoundingClientRect();
                        m.style.top = (r.bottom + 4) + 'px';
                        m.style.left = r.left + 'px';
                      }
                    }, { once: false });
                  }
                } catch (e) { console.debug('[loot] deferred dropdown init failed', e); }
              }, 0);
            });
            output.appendChild(list);
            try {
              const entries = list.querySelectorAll('.loot-entry');
              console.debug('[search] loot list appended', { count: entries.length });
              if (!entries.length) {
                console.warn('[search] expected loot items but none rendered');
              }
            } catch (_e) { }
            // Re-apply tooltips for newly inserted loot buttons
            // Re-apply tooltips without forced reinit to avoid duplicate bootstrap instance churn
            try { if (window.MUDTooltips) window.MUDTooltips.apply(list, false); } catch (e) { }
          } else {
            const line = document.createElement('div');
            line.textContent = data && data.message ? data.message : 'You search the area but find nothing.';
            output.appendChild(line);
            console.debug('[search] no loot found', { found: data && data.found, itemsLength: data && data.items && data.items.length });
          }
        })
        .catch(err => console.error('[dungeon] search error', err))
        .finally(() => {
          searchInFlight = false;
          // Ensure the invoking button stays disabled after click
          try { if (invokingBtn) { invokingBtn.dataset.clicked = '1'; invokingBtn.disabled = true; } } catch (e) { }
          // Failsafe: clear flag after short delay in case of unexpected early return paths
          setTimeout(() => { if (searchInFlight) { console.warn('[search] failsafe clearing stuck in-flight flag'); searchInFlight = false; } }, 4000);
        });
    }

    // No global Search button anymore; inline buttons call doSearch()

    function updateLastRollUI(roll) {
      if (!roll || typeof roll !== 'object') return;
      const ch = roll.character || null;
      const who = ch && (ch.id != null) ? document.querySelector(`.character-card .last-roll-line[data-char-id="${ch.id}"]`) : null;
      const text = (function () {
        const parts = [];
        if (roll.skill) parts.push(String(roll.skill).charAt(0).toUpperCase() + String(roll.skill).slice(1));
        const detail = `${roll.roll ?? '?'}${roll.die ? '' : ''}${typeof roll.mod === 'number' ? (roll.mod >= 0 ? ' +' + roll.mod : ' ' + roll.mod) : ''}`;
        const total = (typeof roll.total === 'number') ? ` = ${roll.total}` : '';
        const expr = roll.expr ? ` (${roll.expr})` : '';
        return `Last roll: ${parts.join(' ')} ${detail}${total}${expr}`.trim();
      })();
      if (who) {
        who.textContent = text;
      } else {
        // Fallback: show above the log
        const line = document.createElement('div');
        line.className = 'text-warning small';
        line.textContent = text;
        if (output) output.appendChild(line);
      }
    }

    function renderLogFromDesc(desc) {
      if (!output) return;
      output.innerHTML = '';
      const parts = String(desc).split(/\n+/);
      parts.forEach((p) => {
        const div = document.createElement('div');
        const isRecallMsg = /You recall a suspicious spot here\.?$/.test(p);
        const isCanSearchMsg = /You can Search this area\.?$/.test(p);
        if (isRecallMsg || isCanSearchMsg) {
          const span = document.createElement('span');
          span.textContent = p.replace(/\.?$/, '.');
          div.appendChild(span);
          div.appendChild(document.createTextNode(' '));
          renderInlineSearch(div);
        } else {
          div.textContent = p;
        }
        output.appendChild(div);
      });
      try { liveRegion.textContent = desc.replace(/Exits:.*$/i, '').trim(); } catch (e) { }
      updateInlineSearchButtons();
    }

    // Dismiss tooltip on any document click to avoid lingering when elements are removed
    document.addEventListener('click', () => { try { hideTooltip(); } catch (e) { } }, true);
    // After dynamic loot list updates, apply Bootstrap tooltips
    const observer = new MutationObserver(() => { if (window.MUDTooltips) window.MUDTooltips.apply(output || document); });
    if (output) { observer.observe(output, { childList: true, subtree: true }); }
    if (window.MUDTooltips) window.MUDTooltips.apply(output || document);

    // Keyboard movement (arrows + WASD). Ignore when typing in input/textarea.
    document.addEventListener('keydown', (e) => {
      if (!keyboardEnabled) return;
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return; // except we allow Shift as a movement override only
      let dir = null;
      switch (e.key.toLowerCase()) {
        case 'arrowup': case 'w': dir = 'n'; break;
        case 'arrowdown': case 's': dir = 's'; break;
        case 'arrowleft': case 'a': dir = 'w'; break;
        case 'arrowright': case 'd': dir = 'e'; break;
      }
      if (!dir) return;
      // Allow Shift to bypass disabled button checks (useful if buttons not in DOM or stale)
      const bypass = e.shiftKey;
      const blocked = !bypass && (
        (dir === 'n' && moveNorthBtn && moveNorthBtn.disabled) ||
        (dir === 's' && moveSouthBtn && moveSouthBtn.disabled) ||
        (dir === 'e' && moveEastBtn && moveEastBtn.disabled) ||
        (dir === 'w' && moveWestBtn && moveWestBtn.disabled)
      );
      if (blocked) {
        if (window && window.console && !e._mudLoggedBlock) {
          e._mudLoggedBlock = true;
          console.debug('[movement] suppressed key press', { dir, reason: 'button-disabled', hint: 'Hold Shift to force movement if map loaded.' });
        }
        return;
      }
      e.preventDefault();
      queueMove(dir);
    });

    // Initial exits fetched after map load (see loadDungeonMap)

    // Applies visibility rules to all stored tile layers based on player (px,py).
    function updateDungeonVisibility(px, py) {
      if (!window.dungeonTileLayers) return;
      if (!window.dungeonSeenTiles) window.dungeonSeenTiles = new Set();
      if (!window.dungeonTileRenderState) window.dungeonTileRenderState = {}; // per-tile cached style classification
      const seen = window.dungeonSeenTiles;
      const renderState = window.dungeonTileRenderState;
      const layers = window.dungeonTileLayers;
      let seenChanged = false;
      for (const key in layers) {
        const layer = layers[key];
        if (!layer || !layer._dungeon) continue;
        const dx = layer._dungeon.x - px;
        const dy = layer._dungeon.y - py;
        const dist = Math.sqrt(dx * dx + dy * dy); // Euclidean for circular falloff

        if (dist <= INNER_VIS_RADIUS) {
          // Mark as seen
          if (!seen.has(key)) { seen.add(key); seenChanged = true; }
          const prev = renderState[key];
          if (!prev || prev.mode !== 'visible') {
            layer.setStyle({
              fillOpacity: 0.72,
              weight: 1,
              color: '#2e2e2e',
              stroke: true,
              fillColor: layer._dungeon.color
            });
            renderState[key] = { mode: 'visible' };
          }
          if (layer._dungeon.tooltip && !layer._dungeon.tooltipBound) {
            layer.bindTooltip(layer._dungeon.tooltip, { permanent: false, direction: 'top', offset: [0, -8] });
            layer._dungeon.tooltipBound = true;
          }
          continue;
        }

        const span = FOG_FULL_RADIUS - INNER_VIS_RADIUS;
        if (dist <= FOG_FULL_RADIUS) {
          const rel = span > 0 ? (dist - INNER_VIS_RADIUS) / span : 1;
          let fogOpacity = MIN_FOG_OPACITY + (MAX_FOG_OPACITY - MIN_FOG_OPACITY) * rel;
          // Noise (deterministic) per tile + mild radial attenuation (less noise near center)
          const ix = layer._dungeon.x;
          const iy = layer._dungeon.y;
          let h = (ix * 73856093) ^ (iy * 19349663) ^ (FOG_FULL_RADIUS * 83492791);
          h = (h >>> 0) % 104729;
          const noise = ((h / 104729) - 0.5) * 2; // [-1,1]
          const attenuation = 1 - Math.max(0, (INNER_VIS_RADIUS - dist) / INNER_VIS_RADIUS);
          fogOpacity += noise * FOG_NOISE_AMPLITUDE * attenuation;
          if (fogOpacity < MIN_FOG_OPACITY) fogOpacity = MIN_FOG_OPACITY;
          else if (fogOpacity > MAX_FOG_OPACITY) fogOpacity = MAX_FOG_OPACITY;
          // If previously seen, blend toward memory dim color slightly
          const wasSeen = seen.has(key);
          if (wasSeen) {
            fogOpacity = Math.min(fogOpacity, MEMORY_DIM_OPACITY + 0.15); // memory slightly lighter than fresh fog
          }
          const roundedOpacity = Math.round(fogOpacity * 100) / 100; // reduce churn from tiny float deltas
          const prev = renderState[key];
          if (!prev || prev.mode !== 'fog' || prev.o !== roundedOpacity) {
            layer.setStyle({
              fillOpacity: fogOpacity,
              weight: 0,
              stroke: false,
              fillColor: '#000000',
              color: '#000000'
            });
            renderState[key] = { mode: 'fog', o: roundedOpacity };
          }
          if (layer._dungeon.tooltipBound) {
            try { layer.unbindTooltip(); } catch (e) { }
            layer._dungeon.tooltipBound = false;
          }
          // Mark tiles moderately close (inside fog region) as seen so they persist when you move away
          if (dist <= INNER_VIS_RADIUS + 2 && !seen.has(key)) { seen.add(key); seenChanged = true; }
          continue;
        }

        // Outside fog full radius. If seen before, render memory; else dark.
        const wasSeen = seen.has(key);
        if (wasSeen) {
          const prev = renderState[key];
          if (!prev || prev.mode !== 'memory') {
            layer.setStyle({
              fillOpacity: MEMORY_DIM_OPACITY,
              weight: MEMORY_STROKE ? 0.3 : 0,
              stroke: MEMORY_STROKE,
              color: '#0a0a0a',
              fillColor: MEMORY_FILL_COLOR
            });
            renderState[key] = { mode: 'memory' };
          }
        } else {
          const prev = renderState[key];
          if (!prev || prev.mode !== 'dark') {
            layer.setStyle({
              fillOpacity: 0.94,
              weight: 0,
              stroke: false,
              fillColor: '#000000',
              color: '#000000'
            });
            renderState[key] = { mode: 'dark' };
          }
        }
        if (layer._dungeon.tooltipBound) {
          try { layer.unbindTooltip(); } catch (e) { }
          layer._dungeon.tooltipBound = false;
        }
      }
      if (seenChanged) saveSeenTilesThrottled(seen);
    }

    function loadDungeonMap() {
      const mapDiv = document.getElementById('dungeon-map');
      if (!mapDiv) return;
      fetch('/api/dungeon/map')
        .then(r => r.json())
        .then(data => {
          if (data.seed !== undefined) {
            const badge = document.getElementById('dungeon-seed-badge');
            if (badge) badge.textContent = 'seed: ' + data.seed;
            window.currentDungeonSeed = data.seed;
            // Load persisted seen tiles now that seed known
            window.dungeonSeenTiles = loadSeenTilesFromStorage();
          }
          const grid = data.grid; // row-major: grid[y][x]
          const height = data.height;
          const width = data.width;
          const validHeight = Number.isFinite(height) && height > 0;
          const validWidth = Number.isFinite(width) && width > 0;
          if (window.dungeonMap) {
            window.dungeonMap.remove();
          }
          const map = L.map('dungeon-map', {
            crs: L.CRS.Simple,
            // Reduced zoom span: drop extreme most-zoomed-out (-2) and most-zoomed-in (+2) levels.
            // New allowed discrete zoom levels: -1, 0, 1
            minZoom: -1,
            maxZoom: 1,
            zoomSnap: 1,
            zoomDelta: 1,
            zoomControl: true,
            attributionControl: false
          });
          window.dungeonMap = map;

          let playerPos = null;
          if (Array.isArray(data.player_pos) && data.player_pos.length >= 2 &&
            Number.isFinite(data.player_pos[0]) && Number.isFinite(data.player_pos[1])) {
            playerPos = data.player_pos;
          }

          if (playerPos) {
            const centerY = (playerPos[1] + 0.5) * TILE_SIZE; // y first
            const centerX = (playerPos[0] + 0.5) * TILE_SIZE; // x second
            if (Number.isFinite(centerY) && Number.isFinite(centerX)) {
              map.setView([centerY, centerX], 0);
            } else if (validHeight && validWidth) {
              map.setView([(height * TILE_SIZE) / 2, (width * TILE_SIZE) / 2], 0);
            } else {
              map.setView([0, 0], 0);
            }
          } else if (validHeight && validWidth) {
            map.setView([(height * TILE_SIZE) / 2, (width * TILE_SIZE) / 2], 0);
          } else {
            map.setView([0, 0], 0);
          }

          if (validHeight && validWidth) {
            map.setMaxBounds([[0, 0], [height * TILE_SIZE, width * TILE_SIZE]]);
          }

          // Load persisted notices and render markers
          refreshNoticeMarkers();

          for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
              const cell = grid[y][x]; // y row, x column
              let tooltip = `(${x + 1},${y + 1}): `;
              if (typeof cell === 'object' && cell !== null && cell.cell_type) {
                tooltip += cell.cell_type;
                if (cell.features && cell.features.length > 0) {
                  tooltip += ' [' + cell.features.join(', ') + ']';
                }
              } else {
                tooltip += cell;
              }
              // Dark mode palette
              // Original colors replaced with deeper, desaturated tones for reduced glare
              // Brighter & slightly more saturated palette (v2)
              const color = (typeof cell === 'object' && cell !== null && cell.cell_type) ?
                (cell.cell_type === 'room' ? '#256535' :          // brighter moss green
                  cell.cell_type === 'tunnel' ? '#155067' :        // richer teal/blue
                    cell.cell_type === 'wall' ? '#523727' :          // warmer brown
                      cell.cell_type === 'door' ? '#551455' :          // more vivid purple
                        cell.cell_type === 'cave' ? '#121212' : '#232323') :
                (cell === 'room' ? '#256535' :
                  cell === 'tunnel' ? '#155067' :
                    cell === 'wall' ? '#523727' :
                      cell === 'door' ? '#551455' :
                        cell === 'cave' ? '#121212' : '#232323');
              const rect = L.rectangle(
                [[y * TILE_SIZE, x * TILE_SIZE], [(y + 1) * TILE_SIZE, (x + 1) * TILE_SIZE]],
                { color: '#303030', weight: 1, fillColor: color, fillOpacity: 0.85, interactive: true }
              ).addTo(map);
              rect.setStyle({ pane: 'tilePane', stroke: true, weight: 1, fillOpacity: 0.7 });
              rect._path.setAttribute('width', TILE_SIZE);
              rect._path.setAttribute('height', TILE_SIZE);
              // Store tile layer reference for fog-of-war updates
              if (!window.dungeonTileLayers) window.dungeonTileLayers = {};
              rect._dungeon = { x, y, color, tooltip, tooltipBound: false };
              window.dungeonTileLayers[`${x},${y}`] = rect;
            }
          }

          // After all tiles added, apply initial visibility based on player position
          if (playerPos) {
            try { updateDungeonVisibility(playerPos[0], playerPos[1]); } catch (e) { /* noop */ }
          }

          // Attempt to merge server-side seen tiles (if any) after local vis applied
          fetch('/api/dungeon/seen')
            .then(r => r.ok ? r.json() : null)
            .then(sdata => {
              if (!sdata || !sdata.tiles) return;
              const parts = sdata.tiles.split(';').filter(Boolean);
              if (!window.dungeonSeenTiles) window.dungeonSeenTiles = new Set();
              let merged = false;
              for (const p of parts) {
                if (!window.dungeonSeenTiles.has(p)) { window.dungeonSeenTiles.add(p); merged = true; }
              }
              if (merged && playerPos) {
                updateDungeonVisibility(playerPos[0], playerPos[1]);
              }
            })
            .catch(() => { });

          // --------------------------------------------------------
          // Developer console helpers (namespaced under window.dungeonDev)
          // --------------------------------------------------------
          if (!window.dungeonDev) window.dungeonDev = {};
          window.dungeonDev.coverage = function () {
            if (!window.dungeonTileLayers || !window.dungeonSeenTiles) return 0;
            const total = Object.keys(window.dungeonTileLayers).length;
            const seen = window.dungeonSeenTiles.size;
            const pct = total ? (seen / total * 100) : 0;
            console.log(`[dungeonDev] Seen tiles: ${seen}/${total} (${pct.toFixed(2)}%)`);
            return { seen, total, pct };
          };
          window.dungeonDev.clearSeen = function () {
            if (window.dungeonSeenTiles) {
              window.dungeonSeenTiles.clear();
              saveSeenTiles(window.dungeonSeenTiles);
              updateDungeonVisibility(playerPos ? playerPos[0] : 0, playerPos ? playerPos[1] : 0);
              console.log('[dungeonDev] Cleared seen tiles');
            }
          };
          window.dungeonDev.getFogConfig = function () {
            const cfg = currentFogConfig();
            console.log('[dungeonDev] Fog config', cfg);
            return cfg;
          };
          window.dungeonDev.saveFogConfig = function (partial) {
            if (!partial || typeof partial !== 'object') { console.warn('[dungeonDev] supply an object with fog keys'); return; }
            const merged = { ...currentFogConfig(), ...partial };
            saveFogConfig(merged);
            console.log('[dungeonDev] Persisted fog config (note: runtime constants not hot-applied yet).', merged);
            return merged;
          };
          window.dungeonDev.dump = function () {
            return {
              coverage: window.dungeonDev.coverage(),
              fog: currentFogConfig(),
              seed: window.currentDungeonSeed
            };
          };
          // Throttled server sync for seen tiles
          let lastServerSync = 0;
          const SERVER_SYNC_INTERVAL = 4000; // ms
          function syncSeenToServer(force = false) {
            const now = performance.now();
            if (!force && now - lastServerSync < SERVER_SYNC_INTERVAL) return;
            if (!window.dungeonSeenTiles || !window.currentDungeonSeed) return;
            lastServerSync = now;
            // Compress to semicolon list
            const tiles = Array.from(window.dungeonSeenTiles).slice(0, 50000).join(';');
            fetch('/api/dungeon/seen', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ tiles })
            }).catch(() => { });
          }
          window.dungeonDev.forceSync = () => syncSeenToServer(true);

          // Hook into existing throttled local save by wrapping saveSeenTilesThrottled
          const _oldSaveSeenTilesThrottled = saveSeenTilesThrottled;
          saveSeenTilesThrottled = function (seenSet) {
            _oldSaveSeenTilesThrottled(seenSet);
            syncSeenToServer(false);
          };

          if (playerPos) {
            if (window.dungeonPlayerMarker) {
              window.dungeonMap.removeLayer(window.dungeonPlayerMarker);
            }
            // Use original sword/shield icon again; scale with zoom via CSS transform.
            const baseSize = 40; // px at zoom 0 (matches CSS width/height)
            const wrapper = document.createElement('div');
            wrapper.className = 'player-marker-wrapper';
            wrapper.innerHTML = `<img src="/static/iconography/axe-sword.svg" alt="Player" class="player-marker-img" />`;
            const playerDivIcon = L.divIcon({
              html: wrapper,
              className: 'player-marker-div', // keep Leaflet from adding default img styles
              iconSize: [baseSize, baseSize],
              iconAnchor: [baseSize / 2, baseSize / 2]
            });
            window.dungeonPlayerMarker = L.marker([
              (playerPos[1] + 0.5) * TILE_SIZE, // y
              (playerPos[0] + 0.5) * TILE_SIZE  // x
            ], { icon: playerDivIcon, interactive: false }).addTo(map);

            function scalePlayerMarker() {
              const z = map.getZoom(); // expected integer in [-1,1]
              // Exponential scaling feels more natural than linear at extremes.
              // scale = 1.2^z, clamped to [0.45, 2.0]
              let scale = Math.pow(1.2, z);
              if (scale < 0.45) scale = 0.45; else if (scale > 2.0) scale = 2.0;
              const imgEl = wrapper.querySelector('.player-marker-img');
              if (imgEl) {
                imgEl.style.transform = `translate(-50%, -50%) scale(${scale})`;
              }
            }
            map.on('zoomend', scalePlayerMarker);
            // initial
            setTimeout(scalePlayerMarker, 0);
          }

          // Defer invalidateSize to allow layout (fluid width) to settle
          setTimeout(() => { try { map.invalidateSize(false); } catch (e) { } }, 50);
          // Recalculate on window resize for responsive horizontal expansion
          window.addEventListener('resize', () => {
            if (window.dungeonMap) {
              try { window.dungeonMap.invalidateSize(false); } catch (e) { }
            }
          }, { passive: true });

          // After map fully initialized, fetch current cell description & exits via state endpoint
          fetch('/api/dungeon/state')
            .then(r => r.json())
            .then(data => {
              if (data && data.desc && output) {
                renderLogFromDesc(String(data.desc));
                if (data.last_roll) {
                  try { updateLastRollUI(data.last_roll); } catch (e) { }
                }
              }
              if (data && Array.isArray(data.exits)) {
                availableExits = data.exits.map(e => e.toLowerCase());
                renderExitButtons();
              }
              // If position returned differs (e.g., server corrected), update fog
              if (data && Array.isArray(data.pos) && data.pos.length >= 2) {
                try { updateDungeonVisibility(data.pos[0], data.pos[1]); } catch (e) { }
              }
            })
            .catch(err => console.error('[dungeon] state error', err));
        });
    }

    function requestNewSeed(seedValue, regenerate = false) {
      const body = {};
      if (seedValue !== undefined && seedValue !== null) body.seed = seedValue;
      if (regenerate) body.regenerate = true;
      return fetch('/api/dungeon/seed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).then(r => { if (!r.ok) throw new Error('Seed HTTP ' + r.status); return r.json(); });
    }

    // Example hook: expose to global for a future UI control (not yet wired in templates)
    window.dungeonNewSeed = function (seedValue) {
      return requestNewSeed(seedValue, !seedValue)
        .then(data => {
          // After changing seed, reload map
          loadDungeonMap();
          return data;
        })
        .catch(err => console.error('[dungeon] seed error', err));
    };

    // Seed controls removed from adventure page; centralized on dashboard.

    loadDungeonMap();
  });
})();
