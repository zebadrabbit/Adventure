/* Basic combat UI logic */
(function () {
    const root = document.getElementById('combat-root');
    if (!root) { return; }
    const combatId = parseInt(root.getAttribute('data-combat-id'), 10);
    const logEl = document.getElementById('combat-log');
    const monsterNameEl = document.getElementById('monster-name');
    const monsterLevelEl = document.getElementById('monster-level');
    const monsterHpBar = document.getElementById('monster-hp-bar');
    const partyContainer = document.getElementById('party-panels');
    let latestVersion = null;
    let socket = null;
    let pollingInterval = null; // fallback

    let lastLogSignature = null;
    let lastLogNode = null;
    let lastLogCount = 1;
    function classifyAndTransform(msg) {
        let cls = '';
        // Order matters: more specific patterns first
        if (/Turn \d+:/.test(msg)) cls = 'log-turn';
        else if (/defeated!/i.test(msg)) cls = 'log-system';
        else if (/Loot:/i.test(msg)) cls = 'log-loot';
        else if (/(casts|hits|attack)/i.test(msg)) cls = 'log-damage';
        else if (/(heals?|regains|restores)/i.test(msg)) cls = 'log-heal';
        else if (/Encounter starts/i.test(msg)) cls = 'log-system';
        return { cls, msg };
    }
    function formatMessage(l) {
        let rawMsg = l.m || '';
        if (/Loot:\s*{/.test(rawMsg)) {
            try {
                const idx = rawMsg.indexOf('Loot:');
                const raw = rawMsg.slice(idx + 5).trim();
                const itemMatches = [...raw.matchAll(/'([A-Za-z0-9_-]+)'/g)].map(m => m[1]).filter(k => !['items', 'items_list', 'rolls', 'base_pool', 'weights', 'special'].includes(k));
                if (itemMatches.length === 0) rawMsg = rawMsg.replace(/Loot:.*/, 'Loot: (no items)');
                else rawMsg = rawMsg.replace(/Loot:.*/, 'Loot: ' + itemMatches.join(', '));
            } catch (e) { /* ignore */ }
        }
        const ts = (l.ts ? '[' + l.ts.split('T')[1].split('.')[0] + '] ' : '');
        return { text: ts + rawMsg, bare: rawMsg };
    }
    let processedLogCount = 0;
    function appendLog(lines) {
        if (!Array.isArray(lines)) return;
        // If the incoming log shrank (e.g., server truncated) rebuild from scratch
        if (lines.length < processedLogCount) {
            logEl.innerHTML = '';
            lastLogSignature = null;
            lastLogNode = null;
            lastLogCount = 1;
            processedLogCount = 0;
        }
        // Process only new lines beyond processedLogCount
        for (let i = processedLogCount; i < lines.length; i++) {
            const l = lines[i];
            const formattedObj = formatMessage(l);
            const formatted = formattedObj.text;
            const signature = formatted.replace(/\[[0-9:]+\]\s*/, '');
            const { cls } = classifyAndTransform(formattedObj.bare);
            if (signature === lastLogSignature && lastLogNode) {
                lastLogCount += 1;
                // Update existing node text to include (xN)
                const baseText = lastLogNode.getAttribute('data-base') || lastLogNode.textContent;
                lastLogNode.setAttribute('data-base', baseText.replace(/ \(x\d+\)$/, ''));
                lastLogNode.textContent = baseText.replace(/ \(x\d+\)$/, '') + ' (x' + lastLogCount + ')';
                lastLogNode.classList.add('log-duplicate');
            } else {
                lastLogSignature = signature;
                lastLogCount = 1;
                const div = document.createElement('div');
                div.textContent = formatted;
                if (cls) div.classList.add(cls);
                lastLogNode = div;
                logEl.appendChild(div);
            }
        }
        processedLogCount = lines.length;
        logEl.scrollTop = logEl.scrollHeight;
    }

    function render(state) {
        if (!state) return;
        const m = state.monster || {};
        monsterNameEl.textContent = m.name || 'Monster';
        monsterLevelEl.textContent = 'Lv ' + (m.level || '?');
        const maxHp = state.monster_max_hp || m.hp || 0;
        const curHp = state.monster_hp ?? maxHp;
        const pct = maxHp > 0 ? Math.max(0, Math.min(100, (curHp / maxHp) * 100)) : 0;
        monsterHpBar.style.width = pct + '%';
        monsterHpBar.textContent = curHp + ' / ' + maxHp;
        // Party panels
        partyContainer.innerHTML = '';
        const initiative = state.initiative || [];
        const activeIndex = state.active_index;
        const party = (state.party && state.party.members) || [];
        // Build quick lookup of actor id -> initiative slot index
        const active = initiative[activeIndex];
        const itemCounts = (state.party && state.party.item_counts) || {};
        party.forEach(mem => {
            const col = document.createElement('div');
            // Full-width inside the dedicated party column
            col.className = 'col-md-12 col-lg-12 mb-3';
            const card = document.createElement('div');
            card.className = 'card h-100 party-member' + (active && active.type === 'player' && active.id === mem.char_id ? ' border-warning shadow' : '');
            card.setAttribute('role', 'listitem');
            if (active && active.type === 'player' && active.id === mem.char_id) {
                card.setAttribute('aria-current', 'true');
            }
            const header = document.createElement('div');
            header.className = 'card-header d-flex justify-content-between align-items-center';
            header.innerHTML = '<span>' + (mem.name || 'Hero') + '</span>' +
                '<span class="small text-muted">HP ' + mem.hp + '/' + mem.max_hp + ' | MP ' + mem.mana + '/' + mem.mana_max + '</span>';
            const body = document.createElement('div');
            body.className = 'card-body p-2';
            const btnRow = document.createElement('div');
            const canAct = active && active.type === 'player' && active.id === mem.char_id && state.status === 'active';
            btnRow.className = 'd-flex flex-wrap gap-2';
            const actions = [
                { k: 'attack', label: 'Attack', cls: 'btn-outline-danger' },
                { k: 'defend', label: 'Defend', cls: 'btn-outline-warning' },
                { k: 'cast_firebolt', label: 'Firebolt', cls: 'btn-outline-primary', manaCost: 5 },
                { k: 'use_potion', label: 'Potion', cls: 'btn-outline-success', needsPotion: true },
                { k: 'flee', label: 'Flee', cls: 'btn-outline-secondary' },
                { k: 'end_turn', label: 'End Turn', cls: 'btn-outline-dark' }
            ];
            actions.forEach(a => {
                const b = document.createElement('button');
                b.type = 'button';
                b.className = 'btn btn-sm ' + a.cls;
                b.textContent = a.label;
                if (!canAct) {
                    b.disabled = true;
                }
                if (a.needsPotion) {
                    const potCount = itemCounts['potion-healing'] || 0;
                    if (potCount <= 0) {
                        b.disabled = true;
                        b.title = 'No potions available';
                    } else {
                        b.title = potCount + ' potion' + (potCount === 1 ? '' : 's') + ' remaining';
                    }
                }
                // Mana gating for Firebolt
                if (canAct && a.k === 'cast_firebolt' && typeof mem.mana === 'number') {
                    if (mem.mana < (a.manaCost || 0)) {
                        b.disabled = true;
                        b.title = 'Not enough mana';
                    }
                }
                b.addEventListener('click', () => doAction(a.k, state.version, mem.char_id));
                btnRow.appendChild(b);
            });
            body.appendChild(btnRow);
            card.appendChild(header);
            card.appendChild(body);
            col.appendChild(card);
            partyContainer.appendChild(col);
        });
        // If combat complete, show a return to dungeon action area (once)
        if (state.status === 'complete') {
            let existing = document.getElementById('combat-return-container');
            if (!existing) {
                existing = document.createElement('div');
                existing.id = 'combat-return-container';
                existing.className = 'mt-3';
                const snap = state.dungeon_snapshot || {};
                const btn = document.createElement('button');
                btn.className = 'btn btn-primary';
                btn.textContent = 'Return to Dungeon';
                btn.addEventListener('click', () => {
                    // Simple redirect – parameters could be used by server to restore context later
                    const inst = snap.instance_id || '';
                    window.location.href = '/adventure' + (inst ? ('?instance=' + inst) : '');
                });
                existing.appendChild(btn);
                root.appendChild(existing);
            }
        }
        appendLog(state.log);
        // Live region update for active turn
        try {
            const turnLive = document.getElementById('combat-turn-live');
            if (turnLive && active && active.type === 'player') {
                const actor = party.find(p => p.char_id === active.id);
                if (actor) {
                    turnLive.textContent = 'It is ' + actor.name + "'s turn.";
                }
            } else if (turnLive && active && active.type === 'monster') {
                turnLive.textContent = 'Monster turn.';
            }
        } catch (e) { /* ignore */ }
        // Rewards panel (render only once when complete and rewards exist)
        if (state.status === 'complete' && state.rewards) {
            let panel = document.getElementById('combat-rewards-panel');
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'combat-rewards-panel';
                panel.className = 'card mt-3';
                const header = document.createElement('div');
                header.className = 'card-header';
                header.textContent = 'Rewards';
                const body = document.createElement('div');
                body.className = 'card-body';
                const r = state.rewards || {};
                const items = r.items || r.items_list || r.loot || {};
                let itemsHtml = '';
                if (Array.isArray(items)) {
                    itemsHtml = items.map(i => '<span class="badge bg-success me-1">' + i + '</span>').join('');
                } else if (typeof items === 'object') {
                    itemsHtml = Object.entries(items).map(([k, v]) => '<span class="badge bg-success me-1">' + k + (v > 1 ? ' x' + v : '') + '</span>').join('');
                }
                const xp = (r.xp && r.xp.total) ? r.xp.total : null;
                body.innerHTML = '<div>' + (itemsHtml || '<em>No items</em>') + '</div>' + (xp ? ('<div class="mt-2">XP: ' + xp + '</div>') : '');
                panel.appendChild(header);
                panel.appendChild(body);
                root.appendChild(panel);
            }
        }
    }

    async function fetchState() {
        try {
            const r = await fetch('/api/combat/' + combatId + '/state');
            const j = await r.json();
            if (j && j.ok) {
                render(j.state);
            }
        } catch (e) { /* ignore */ }
    }

    async function doAction(action, version, actorId) {
        let endpoint;
        let payload = { version: version, actor_id: actorId };
        if (action === 'attack') endpoint = '/api/combat/' + combatId + '/attack';
        else if (action === 'defend') endpoint = '/api/combat/' + combatId + '/defend';
        else if (action === 'cast_firebolt') { endpoint = '/api/combat/' + combatId + '/cast'; payload.spell = 'firebolt'; }
        else if (action === 'use_potion') { endpoint = '/api/combat/' + combatId + '/use_item'; payload.slug = 'potion-healing'; }
        else if (action === 'flee') endpoint = '/api/combat/' + combatId + '/flee';
        else if (action === 'end_turn') endpoint = '/api/combat/' + combatId + '/end_turn';
        else return;
        try {
            const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const j = await r.json();
            if (j.state) {
                render(j.state);
            }
        } catch (e) { /* ignore */ }
    }

    function initSocket() {
        if (typeof io === 'undefined') {
            // No socket.io client loaded; rely on polling
            fetchState();
            pollingInterval = setInterval(fetchState, 2000);
            return;
        }
        // Server emits to namespace '/adventure'; ensure we connect there (default root would miss events)
        socket = (window.adventureSocket && window.adventureSocket.connected && window.adventureSocket) || window.adventureSocket || io('/adventure', { path: '/socket.io', transports: ['websocket', 'polling'] });
        window.adventureSocket = socket; // unify reference
        // Listen for combat updates on shared namespace; server emits event with full state dict
        socket.on('connect', () => {
            // Initial snapshot
            fetchState();
        });
        socket.on('combat_update', (state) => {
            // Only process relevant combat id
            if (!state || state.id !== combatId) return;
            latestVersion = state.version;
            render(state);
        });
        socket.on('combat_end', (state) => {
            if (state && state.id === combatId) {
                render(state);
            }
        });
        socket.on('combat_complete', (state) => {
            if (state && state.id === combatId) {
                render(state);
            }
        });
        socket.on('disconnect', () => {
            // Start polling fallback while disconnected
            if (!pollingInterval) {
                pollingInterval = setInterval(fetchState, 3000);
            }
        });
    }

    initSocket();

    // Client error reporting (lazy best-effort)
    if (!window.__adventureErrorPatched) {
        window.__adventureErrorPatched = true;
        const report = (payload) => {
            try {
                fetch('/api/client/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).catch(() => { });
            } catch (e) { /* ignore */ }
        };
        window.addEventListener('error', (ev) => {
            report({ type: 'error', msg: ev.message, stack: ev.error && ev.error.stack, src: ev.filename, line: ev.lineno, col: ev.colno });
        });
        window.addEventListener('unhandledrejection', (ev) => {
            report({ type: 'unhandledrejection', reason: (ev.reason && (ev.reason.message || ev.reason.toString())) });
        });
    }
})();
