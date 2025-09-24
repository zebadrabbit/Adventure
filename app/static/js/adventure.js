// Adventure page dungeon logic extracted from adventure.html
(function(){
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
  document.addEventListener('DOMContentLoaded', function() {
    const output = document.getElementById('dungeon-output');
    // ------------------------------------------------------------------
    // Dynamic class color theming
    // Fetch centralized class color config from /api/config/class_colors
    // and apply as CSS variables. This allows future runtime palette tweaks
    // or adding new classes without editing static CSS files. If new class
    // slugs are returned that we don't have predefined .class-*/.border-* rules
    // for, we inject them dynamically.
    // ------------------------------------------------------------------
    (function fetchAndApplyClassColors(){
      const endpoint = '/api/config/class_colors';
      fetch(endpoint, { headers: { 'Accept': 'application/json' }})
        .then(r => { if(!r.ok) throw new Error('status '+r.status); return r.json(); })
        .then(map => {
          if (!map || typeof map !== 'object') return;
          const root = document.documentElement;
          const predefined = new Set(['fighter','rogue','mage','cleric','druid','ranger']);
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
            styleEl.setAttribute('data-generated','class-colors');
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
      } catch(e) { /* ignore parse/storage errors */ }
      return new Set();
    }

    function saveSeenTiles(seenSet) {
      try {
        const arr = Array.from(seenSet);
        localStorage.setItem(seenStorageKey(), JSON.stringify(arr));
      } catch(e) { /* ignore quota or storage errors */ }
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
      } catch(e) { return null; }
    }
    function saveFogConfig(cfg) {
      try { localStorage.setItem(FOG_CFG_KEY, JSON.stringify(cfg)); } catch(e) {}
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
    (function initFogConfig(){
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
  const searchBtn = document.getElementById('btn-search');
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

    function processNextMove() {
      if (moveInFlight) return;
      const next = moveQueue.shift();
      if (!next && next !== '') return; // allow empty string init
      executeMove(next);
    }

    function queueMove(dir) {
      moveQueue.push(dir);
      processNextMove();
    }

    // Persistent discovered/notice markers
    let noticeMarkers = {}; // key: "x,y" -> L.marker

    function keyFor(x,y){ return `${x},${y}`; }

    function addNoticeMarker(x, y) {
      if (!window.dungeonMap) return;
      const k = keyFor(x,y);
      if (noticeMarkers[k]) return; // already present
      const iconHtml = `<img src="/static/iconography/search-question.svg" alt="Searchable" style="width:28px;height:28px;filter: drop-shadow(0 0 2px #000);">`;
      const divIcon = L.divIcon({ html: iconHtml, className: 'notice-marker-div', iconSize: [28,28], iconAnchor: [14,14] });
      const m = L.marker([ (y + 0.5) * TILE_SIZE, (x + 0.5) * TILE_SIZE ], { icon: divIcon, interactive: false });
      m.addTo(window.dungeonMap);
      noticeMarkers[k] = m;
      if (searchBtn && window.currentPos && keyFor(window.currentPos[0], window.currentPos[1]) === k) {
        searchBtn.disabled = false;
      }
    }

    function removeNoticeMarker(x, y) {
      const k = keyFor(x,y);
      const m = noticeMarkers[k];
      if (m && window.dungeonMap) {
        try { window.dungeonMap.removeLayer(m); } catch(e) {}
      }
      delete noticeMarkers[k];
    }

    async function refreshNoticeMarkers() {
      try {
        const r = await fetch(`/api/dungeon/notices?ts=${Date.now()}`, { cache: 'no-store' });
        if (!r.ok) return;
        const data = await r.json();
        const set = new Set((data.notices || []).map(p => keyFor(p[0], p[1])));
        // remove stale
        Object.keys(noticeMarkers).forEach(k => { if (!set.has(k)) {
          const [x,y] = k.split(',').map(n=>parseInt(n,10));
          removeNoticeMarker(x,y);
        }});
        // add present
        (data.notices || []).forEach(p => addNoticeMarker(p[0], p[1]));
        // update Search button state for current tile
        if (searchBtn && window.currentPos) {
          const k = keyFor(window.currentPos[0], window.currentPos[1]);
          searchBtn.disabled = !noticeMarkers[k];
        }
      } catch(e) { /* ignore */ }
    }

    function executeMove(dir) {
      moveInFlight = true;
      fetch('/api/dungeon/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir })
      })
      .then(r => { if (!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
      .then(data => {
        if (data && data.desc && output) {
          // Treat newlines as log line breaks
          output.innerHTML = '';
          const parts = String(data.desc).split(/\n+/);
          parts.forEach((p, idx) => {
            const div = document.createElement('div');
            div.textContent = p;
            output.appendChild(div);
          });
          liveRegion.textContent = data.desc.replace(/Exits:.*$/i,'').trim();
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
                try { updateDungeonVisibility(data.pos[0], data.pos[1]); } catch(e) { /* noop */ }
              }
              // If newly noticed, add marker persistently
              if (data.noticed_loot) {
                addNoticeMarker(data.pos[0], data.pos[1]);
              }
              // Enable/disable search button based on whether current tile has notice
              if (searchBtn) {
                const k = keyFor(data.pos[0], data.pos[1]);
                searchBtn.disabled = !noticeMarkers[k];
              }
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
      if (moveEastBtn)  moveEastBtn.disabled  = !normalized.includes('e') && !normalized.includes('east');
      if (moveWestBtn)  moveWestBtn.disabled  = !normalized.includes('w') && !normalized.includes('west');
    }

    // Wire dedicated movement buttons if they exist (add ARIA labels)
  if (moveNorthBtn) { moveNorthBtn.setAttribute('aria-label','Move North'); moveNorthBtn.addEventListener('click', () => !moveNorthBtn.disabled && queueMove('n')); }
  if (moveSouthBtn) { moveSouthBtn.setAttribute('aria-label','Move South'); moveSouthBtn.addEventListener('click', () => !moveSouthBtn.disabled && queueMove('s')); }
  if (moveEastBtn)  { moveEastBtn.setAttribute('aria-label','Move East'); moveEastBtn.addEventListener('click', () => !moveEastBtn.disabled && queueMove('e')); }
  if (moveWestBtn)  { moveWestBtn.setAttribute('aria-label','Move West'); moveWestBtn.addEventListener('click', () => !moveWestBtn.disabled && queueMove('w')); }

    if (searchBtn) {
      searchBtn.addEventListener('click', () => {
        if (searchBtn.disabled) return;
        fetch('/api/dungeon/search', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
          .then(r => r.json())
          .then(data => {
            if (!output) return;
            const foundWithItems = data && data.found && Array.isArray(data.items) && data.items.length;
            // When items are found, replace the plain message with a header and linked items to avoid duplicates
              if (foundWithItems) {
              const hdr = document.createElement('div');
              hdr.textContent = 'You search the area and discover:';
              output.appendChild(hdr);
              const list = document.createElement('div');
              list.className = 'loot-list mt-1';
              data.items.forEach(it => {
                const a = document.createElement('a');
                a.href = '#';
                a.className = 'loot-link me-2';
                a.textContent = it.name || it.slug || 'Unknown Item';
                const rarity = it.rarity || 'common';
                a.setAttribute('data-tooltip', `${it.name} (Lv ${it.level || 0}, ${rarity})\n${it.type || ''} — ${it.value_copper || 0}c\n${(it.description || '').trim()}`);
                a.addEventListener('mouseenter', showTooltip);
                a.addEventListener('mouseleave', hideTooltip);
                   a.addEventListener('click', (ev) => {
                  ev.preventDefault();
                  hideTooltip();
                  // Claim this loot id
                  fetch(`/api/dungeon/loot/claim/${it.id}`, { method: 'POST' })
                    .then(r => r.json())
                    .then(res => {
                      const line = document.createElement('div');
                      if (res && res.claimed) {
                        line.textContent = `Added ${res.item?.name || 'item'} to your inventory.`;
                        // remove link
                        a.remove();
                          // after claim, refresh markers and update Search
                          refreshNoticeMarkers();
                          if (searchBtn && window.currentPos) {
                            const k = keyFor(window.currentPos[0], window.currentPos[1]);
                            searchBtn.disabled = !noticeMarkers[k];
                          }
                           // If no more loot links remain in this list, optimistically drop marker
                           const remaining = list.querySelectorAll('.loot-link');
                           if (!remaining || remaining.length === 0) {
                             if (window.currentPos) removeNoticeMarker(window.currentPos[0], window.currentPos[1]);
                             if (searchBtn) searchBtn.disabled = true;
                           }
                      } else {
                        line.textContent = 'Unable to claim item.';
                      }
                      output.appendChild(line);
                      hideTooltip();
                    })
                    .catch(err => console.error('[loot] claim error', err));
                });
                list.appendChild(a);
              });
              output.appendChild(list);
              // After reveal, refresh from server to keep only those with unclaimed loot
              refreshNoticeMarkers();
            } else if (data && data.message) {
              // If no items found, or generic response, show the server message
              const div = document.createElement('div');
              div.textContent = data.message;
              output.appendChild(div);
                // If nothing here, ensure markers/buttons reflect it
              refreshNoticeMarkers();
              if (/nothing here|there is nothing here/i.test(data.message) && window.currentPos) {
                removeNoticeMarker(window.currentPos[0], window.currentPos[1]);
                if (searchBtn) searchBtn.disabled = true;
              }
            }
          })
          .catch(err => console.error('[dungeon] search error', err));
      });
    }

    // Simple tooltip implementation for loot links
    let tooltipEl = null;
    function showTooltip(e) {
      const text = e.currentTarget.getAttribute('data-tooltip');
      if (!text) return;
      if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.className = 'adventure-tooltip';
        document.body.appendChild(tooltipEl);
      }
      tooltipEl.textContent = text;
      tooltipEl.style.display = 'block';
      const rect = e.currentTarget.getBoundingClientRect();
      tooltipEl.style.position = 'fixed';
      tooltipEl.style.left = `${rect.left}px`;
      tooltipEl.style.top = `${rect.top - 8 - (tooltipEl.offsetHeight || 0)}px`;
      tooltipEl.style.background = 'rgba(0,0,0,0.85)';
      tooltipEl.style.color = '#eee';
      tooltipEl.style.padding = '6px 8px';
      tooltipEl.style.border = '1px solid #444';
      tooltipEl.style.borderRadius = '4px';
      tooltipEl.style.pointerEvents = 'none';
      tooltipEl.style.whiteSpace = 'pre';
      tooltipEl.style.zIndex = 9999;
      // Adjust top now that size is known
      const h = tooltipEl.offsetHeight;
      tooltipEl.style.top = `${rect.top - 8 - h}px`;
    }
    function hideTooltip() {
      if (tooltipEl) tooltipEl.style.display = 'none';
    }
    // Dismiss tooltip on any document click to avoid lingering when elements are removed
    document.addEventListener('click', () => { try { hideTooltip(); } catch(e){} }, true);

    // Keyboard movement (arrows + WASD). Ignore when typing in input/textarea.
    document.addEventListener('keydown', (e) => {
      if (!keyboardEnabled) return;
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || e.metaKey || e.ctrlKey || e.altKey) return;
      let dir = null;
      switch(e.key.toLowerCase()) {
        case 'arrowup': case 'w': dir = 'n'; break;
        case 'arrowdown': case 's': dir = 's'; break;
        case 'arrowleft': case 'a': dir = 'w'; break;
        case 'arrowright': case 'd': dir = 'e'; break;
      }
      if (dir) {
        if (dir === 'n' && moveNorthBtn && moveNorthBtn.disabled) return;
        if (dir === 's' && moveSouthBtn && moveSouthBtn.disabled) return;
        if (dir === 'e' && moveEastBtn  && moveEastBtn.disabled)  return;
        if (dir === 'w' && moveWestBtn  && moveWestBtn.disabled)  return;
        e.preventDefault();
        queueMove(dir);
      }
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
        const dist = Math.sqrt(dx*dx + dy*dy); // Euclidean for circular falloff

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
            layer.bindTooltip(layer._dungeon.tooltip, {permanent: false, direction: 'top', offset: [0, -8]});
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
            try { layer.unbindTooltip(); } catch(e) {}
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
          try { layer.unbindTooltip(); } catch(e) {}
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
              let tooltip = `(${x+1},${y+1}): `;
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
            try { updateDungeonVisibility(playerPos[0], playerPos[1]); } catch(e) { /* noop */ }
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
            .catch(()=>{});

          // --------------------------------------------------------
          // Developer console helpers (namespaced under window.dungeonDev)
          // --------------------------------------------------------
          if (!window.dungeonDev) window.dungeonDev = {};
          window.dungeonDev.coverage = function() {
            if (!window.dungeonTileLayers || !window.dungeonSeenTiles) return 0;
            const total = Object.keys(window.dungeonTileLayers).length;
            const seen = window.dungeonSeenTiles.size;
            const pct = total ? (seen/total*100) : 0;
            console.log(`[dungeonDev] Seen tiles: ${seen}/${total} (${pct.toFixed(2)}%)`);
            return { seen, total, pct };
          };
          window.dungeonDev.clearSeen = function() {
            if (window.dungeonSeenTiles) {
              window.dungeonSeenTiles.clear();
              saveSeenTiles(window.dungeonSeenTiles);
              updateDungeonVisibility(playerPos ? playerPos[0] : 0, playerPos ? playerPos[1] : 0);
              console.log('[dungeonDev] Cleared seen tiles');
            }
          };
          window.dungeonDev.getFogConfig = function() {
            const cfg = currentFogConfig();
            console.log('[dungeonDev] Fog config', cfg);
            return cfg;
          };
          window.dungeonDev.saveFogConfig = function(partial) {
            if (!partial || typeof partial !== 'object') { console.warn('[dungeonDev] supply an object with fog keys'); return; }
            const merged = { ...currentFogConfig(), ...partial };
            saveFogConfig(merged);
            console.log('[dungeonDev] Persisted fog config (note: runtime constants not hot-applied yet).', merged);
            return merged;
          };
          window.dungeonDev.dump = function() {
            return {
              coverage: window.dungeonDev.coverage(),
              fog: currentFogConfig(),
              seed: window.currentDungeonSeed
            };
          };
          // Throttled server sync for seen tiles
          let lastServerSync = 0;
          const SERVER_SYNC_INTERVAL = 4000; // ms
          function syncSeenToServer(force=false) {
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
            }).catch(()=>{});
          }
          window.dungeonDev.forceSync = () => syncSeenToServer(true);

          // Hook into existing throttled local save by wrapping saveSeenTilesThrottled
          const _oldSaveSeenTilesThrottled = saveSeenTilesThrottled;
          saveSeenTilesThrottled = function(seenSet) {
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
              iconAnchor: [baseSize/2, baseSize/2]
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
          setTimeout(() => { try { map.invalidateSize(false); } catch(e) {} }, 50);
          // Recalculate on window resize for responsive horizontal expansion
          window.addEventListener('resize', () => {
            if (window.dungeonMap) {
              try { window.dungeonMap.invalidateSize(false); } catch(e) {}
            }
          }, { passive: true });

          // After map fully initialized, fetch current cell description & exits via state endpoint
          fetch('/api/dungeon/state')
            .then(r => r.json())
            .then(data => {
              if (data && data.desc && output) {
                output.textContent = data.desc;
                liveRegion.textContent = data.desc.replace(/Exits:.*$/i,'').trim();
              }
              if (data && Array.isArray(data.exits)) {
                availableExits = data.exits.map(e => e.toLowerCase());
                renderExitButtons();
              }
              // If position returned differs (e.g., server corrected), update fog
              if (data && Array.isArray(data.pos) && data.pos.length >= 2) {
                try { updateDungeonVisibility(data.pos[0], data.pos[1]); } catch(e) {}
              }
            })
            .catch(err => console.error('[dungeon] state error', err));
        });
    }

    function requestNewSeed(seedValue, regenerate=false) {
      const body = {};
      if (seedValue !== undefined && seedValue !== null) body.seed = seedValue;
      if (regenerate) body.regenerate = true;
      return fetch('/api/dungeon/seed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).then(r => { if(!r.ok) throw new Error('Seed HTTP '+r.status); return r.json(); });
    }

    // Example hook: expose to global for a future UI control (not yet wired in templates)
    window.dungeonNewSeed = function(seedValue) {
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
