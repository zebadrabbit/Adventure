document.addEventListener('DOMContentLoaded', function () {
    // Wire static Search, Camp & Hearth buttons (now left of log)
    (function bindActionButtons() {
        const searchBtn = document.getElementById('btn-search');
        const partyInventoryBtn = document.getElementById('btn-party-inventory');
        const campBtn = document.getElementById('btn-camp');
        const hearthBtn = document.getElementById('btn-hearth');
        function appendLog(msg, cls) {
            try { const out = document.getElementById('dungeon-output'); if (!out) return; const div = document.createElement('div'); div.textContent = msg; if (cls) div.className = cls; out.appendChild(div); div.scrollIntoView({ block: 'nearest' }); } catch (e) { }
        }
        if (searchBtn) {
            searchBtn.addEventListener('click', () => {
                // Use the global doSearchTile function
                if (window.doSearchTile) {
                    window.doSearchTile(searchBtn);
                } else {
                    // Fallback if function not loaded yet
                    searchBtn.disabled = true;
                    fetch('/api/dungeon/search_tile', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                        .then(r => r.json().catch(() => ({ error: 'bad json' })))
                        .then(j => {
                            if (j && j.message) appendLog(j.message);
                            if (j && j.revealed_caches > 0) {
                                appendLog(`Revealed ${j.revealed_caches} hidden cache(s)!`, 'text-success');
                                if (window.refreshEntities) window.refreshEntities();
                            }
                            if (j && j.encounter && j.encounter.combat_id) { window.location.href = '/combat/' + j.encounter.combat_id; }
                        })
                        .catch(() => appendLog('Search failed (network error)', 'text-danger'))
                        .finally(() => { searchBtn.disabled = false; });
                }
            });
        }
        if (campBtn) {
            campBtn.addEventListener('click', () => {
                campBtn.disabled = true;
                fetch('/api/dungeon/camp', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                    .then(r => r.json().catch(() => ({ error: 'bad json' })))
                    .then(j => {
                        if (j && j.message) appendLog(j.message);
                        if (j && j.restored_hp_total) appendLog(`Party recovers ${j.restored_hp_total} HP collectively.`, `text-success small`);
                        if (j && j.encounter && j.encounter.combat_id) { window.location.href = '/combat/' + j.encounter.combat_id; }
                    })
                    .catch(() => appendLog('Camp failed (network error)', 'text-danger'))
                    .finally(() => { campBtn.disabled = false; });
            });
        }
        if (hearthBtn) {
            hearthBtn.addEventListener('click', () => {
                if (!confirm('Hearth and abandon this dungeon run? Penalties will apply.')) return;
                hearthBtn.disabled = true;
                fetch('/api/dungeon/hearth', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                    .then(r => r.json().catch(() => ({ error: 'bad json' })))
                    .then(j => {
                        if (j && j.message) appendLog(j.message, 'text-warning');
                        setTimeout(() => { window.location.href = '/dashboard'; }, 1200);
                    })
                    .catch(() => appendLog('Hearth failed (network error)', 'text-danger'))
                    .finally(() => { hearthBtn.disabled = false; });
            });
        }
        if (partyInventoryBtn) {
            partyInventoryBtn.addEventListener('click', () => {
                // Show party stash modal (simplified for now - can be expanded)
                alert('Party Stash feature coming soon! This will show shared gold and items that party members can contribute to and withdraw from.');
            });
        }
    })();

    // Toggle map controls visibility
    (function bindMapControlsToggle() {
        const toggleBtn = document.getElementById('btn-toggle-controls');
        const controlsPanel = document.getElementById('map-controls-panel');
        if (toggleBtn && controlsPanel) {
            toggleBtn.addEventListener('click', () => {
                const isHidden = controlsPanel.style.display === 'none';
                controlsPanel.style.display = isHidden ? '' : 'none';
                toggleBtn.classList.toggle('active', isHidden);
            });
        }
    })();

    // Hotkeys panel toggle
    (function bindHotkeysPanel() {
        const showBtn = document.getElementById('btn-show-hotkeys');
        const closeBtn = document.getElementById('btn-close-hotkeys');
        const panel = document.getElementById('hotkeys-panel');
        if (showBtn && panel) {
            showBtn.addEventListener('click', () => {
                panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            });
        }
        if (closeBtn && panel) {
            closeBtn.addEventListener('click', () => {
                panel.style.display = 'none';
            });
        }
    })();

    // Keyboard shortcuts
    (function bindKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            const key = e.key.toLowerCase();

            // Movement
            if (key === 'w' || key === 'arrowup') {
                e.preventDefault();
                const btn = document.querySelector('[data-dir="n"]');
                if (btn && !btn.disabled) btn.click();
            } else if (key === 's' || key === 'arrowdown') {
                e.preventDefault();
                const btn = document.querySelector('[data-dir="s"]');
                if (btn && !btn.disabled) btn.click();
            } else if (key === 'a' || key === 'arrowleft') {
                e.preventDefault();
                const btn = document.querySelector('[data-dir="w"]');
                if (btn && !btn.disabled) btn.click();
            } else if (key === 'd' || key === 'arrowright') {
                e.preventDefault();
                const btn = document.querySelector('[data-dir="e"]');
                if (btn && !btn.disabled) btn.click();
            }
            // Actions
            else if (key === ' ') {
                e.preventDefault();
                const searchBtn = document.getElementById('btn-search');
                if (searchBtn && !searchBtn.disabled) searchBtn.click();
            } else if (key === 'c') {
                const campBtn = document.getElementById('btn-camp');
                if (campBtn && !campBtn.disabled) campBtn.click();
            } else if (key === 'h') {
                const hearthBtn = document.getElementById('btn-hearth');
                if (hearthBtn && !hearthBtn.disabled) hearthBtn.click();
            } else if (key === 'i') {
                // Open first character's bag panel
                const bagBtn = document.querySelector('.btn-bag-panel');
                if (bagBtn) bagBtn.click();
            } else if (key === 'escape') {
                // Close hotkeys panel
                const panel = document.getElementById('hotkeys-panel');
                if (panel && panel.style.display !== 'none') {
                    panel.style.display = 'none';
                }
            }
        });
    })();

    function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }
    document.querySelectorAll('.hp-bar').forEach(w => {
        const hp = parseFloat(w.getAttribute('data-hp')) || 0;
        const max = parseFloat(w.getAttribute('data-hp-max')) || 0;
        const pct = max > 0 ? clamp((hp / max) * 100, 0, 100) : 0;
        const hue = Math.floor(120 * (pct / 100)); // 120 green -> 0 red
        const fill = w.querySelector('[data-bar="hp"]');
        if (fill) {
            fill.style.width = pct.toFixed(1) + '%';
            fill.style.backgroundColor = 'hsl(' + hue + ',70%,45%)';
            fill.style.transition = 'width 0.3s ease-in-out, background-color 0.3s ease-in-out';
        }
    });
    document.querySelectorAll('.mana-bar').forEach(w => {
        const mana = parseFloat(w.getAttribute('data-mana')) || 0;
        const max = parseFloat(w.getAttribute('data-mana-max')) || 0;
        const pct = max > 0 ? clamp((mana / max) * 100, 0, 100) : 0;
        const fill = w.querySelector('[data-bar="mana"]');
        if (fill) {
            fill.style.width = pct.toFixed(1) + '%';
            fill.style.backgroundColor = '#3b82f6'; // Consistent blue color
            fill.style.transition = 'width 0.3s ease-in-out';
        }
    });

    // Equipment/Bags buttons now handled by equipment.js (same as dashboard)
});
