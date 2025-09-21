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
          output.textContent = data.desc;
          liveRegion.textContent = data.desc.replace(/Exits:.*$/i,'').trim();
        }
        if (data && data.pos) {
          const pxY = (data.pos[1] + 0.5) * TILE_SIZE;
          const pxX = (data.pos[0] + 0.5) * TILE_SIZE;
            if (window.dungeonPlayerMarker && window.dungeonMap && Number.isFinite(pxY) && Number.isFinite(pxX)) {
              window.dungeonPlayerMarker.setLatLng([pxY, pxX]);
              window.dungeonMap.panTo([pxY, pxX], { animate: true });
              // Update fog-of-war visibility after movement
              if (Array.isArray(data.pos)) {
                try { updateDungeonVisibility(data.pos[0], data.pos[1]); } catch(e) { /* noop */ }
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
            minZoom: -2,
            maxZoom: 2,
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
              const z = map.getZoom(); // expected integer in [-2,2]
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
