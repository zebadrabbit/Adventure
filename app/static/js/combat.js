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
    // Stable home for the action panel — it gets re-parented into whichever
    // character card is active each render, so it must be moved back out
    // here before partyContainer.innerHTML is wiped, or the wipe destroys
    // it permanently (document.getElementById would return null forever
    // after, since the node itself is gone, not just its position).
    const combatLeft = document.getElementById('combat-left');
    let latestVersion = null;
    let socket = null;
    let pollingInterval = null; // fallback

    let lastLogSignature = null;
    let lastLogNode = null;
    let lastLogCount = 1;
    let latestHighlightNode = null;
    function classifyAndTransform(msg) {
        let cls = '';
        // Order matters: more specific patterns first
        if (/Turn \d+:/.test(msg)) cls = 'log-turn';
        else if (/(critical|crit)/i.test(msg)) cls = 'log-crit';
        else if (/(dies|death|slain|killed|defeated)/i.test(msg)) cls = 'log-death';
        else if (/victory|victorious|wins?|won/i.test(msg)) cls = 'log-victory';
        else if (/Loot:/i.test(msg)) cls = 'log-loot';
        else if (/(curse|cursed|hex)/i.test(msg)) cls = 'log-curse';
        else if (/(poison|poisoned|venom)/i.test(msg)) cls = 'log-poison';
        else if (/(buff|blessed|enchant|strengthen)/i.test(msg)) cls = 'log-buff';
        else if (/(debuff|weaken|vulnerability|vulnerable)/i.test(msg)) cls = 'log-debuff';
        else if (/(stun|stunned|daze|dazed)/i.test(msg)) cls = 'log-stun';
        else if (/(bleed|bleeding|hemorrhage)/i.test(msg)) cls = 'log-bleed';
        else if (/(burn|burning|ignite|fire)/i.test(msg)) cls = 'log-burn';
        else if (/(freeze|frozen|frost|ice)/i.test(msg)) cls = 'log-freeze';
        else if (/(miss|misses|whiff)/i.test(msg)) cls = 'log-miss';
        else if (/(block|blocked|parry|parried)/i.test(msg)) cls = 'log-block';
        else if (/(dodge|dodges|evade|evaded)/i.test(msg)) cls = 'log-dodge';
        else if (/(shield|armor|absorb)/i.test(msg)) cls = 'log-shield';
        else if (/(flee|flees|retreat|escape)/i.test(msg)) cls = 'log-flee';
        else if (/(heals?|regains|restores|recovery|regenerate)/i.test(msg)) cls = 'log-heal';
        else if (/(casts?|hits?|attacks?|strikes?|damage|deals)/i.test(msg)) cls = 'log-damage';
        else if (/(Encounter starts|defeated!)/i.test(msg)) cls = 'log-system';
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
        return { text: rawMsg, bare: rawMsg };
    }
    let processedLogCount = 0;
    let typewriterQueue = [];
    let isTyping = false;

    function typewriterEffect(element, text, speed = 5) {
        return new Promise((resolve) => {
            let i = 0;
            element.textContent = '';
            const cursor = document.createElement('span');
            cursor.className = 'terminal-cursor';

            function type() {
                if (i < text.length) {
                    cursor.remove();
                    element.textContent += text.charAt(i);
                    element.appendChild(cursor);
                    i++;
                    setTimeout(type, speed + Math.random() * 3); // Variable speed like modem
                } else {
                    // Keep cursor at end of line
                    resolve();
                }
            }
            type();
        });
    }

    async function processTypewriterQueue() {
        if (isTyping || typewriterQueue.length === 0) return;
        isTyping = true;

        while (typewriterQueue.length > 0) {
            const { element, text } = typewriterQueue.shift();

            // Remove cursor from previous log entry
            const existingCursor = logEl.querySelector('.terminal-cursor');
            if (existingCursor) {
                existingCursor.remove();
            }

            await typewriterEffect(element, text);
            logEl.scrollTop = logEl.scrollHeight;
        }

        isTyping = false;
    }

    function appendLog(lines) {
        if (!Array.isArray(lines)) return;
        // If the incoming log shrank (e.g., server truncated) rebuild from scratch
        if (lines.length < processedLogCount) {
            logEl.innerHTML = '';
            lastLogSignature = null;
            lastLogNode = null;
            lastLogCount = 1;
            processedLogCount = 0;
            typewriterQueue = [];
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
                setLatestHighlight(lastLogNode);
            } else {
                lastLogSignature = signature;
                lastLogCount = 1;
                const div = document.createElement('div');
                if (cls) div.classList.add(cls);
                lastLogNode = div;
                logEl.appendChild(div);
                setLatestHighlight(div);

                // Add to typewriter queue
                typewriterQueue.push({ element: div, text: formatted });
            }
        }
        processedLogCount = lines.length;
        processTypewriterQueue();
    }

    function setLatestHighlight(node) {
        if (latestHighlightNode && latestHighlightNode !== node) {
            latestHighlightNode.classList.remove('log-latest');
        }
        node.classList.add('log-latest');
        latestHighlightNode = node;
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

        // Show damage if HP changed
        if (window.combatEffects && state.last_damage_to_monster) {
            const dmg = state.last_damage_to_monster;
            const panel = document.getElementById('monster-panel');
            if (panel && dmg.amount) {
                window.combatEffects.showDamage(panel, dmg.amount, {
                    isCritical: dmg.is_critical,
                    isMiss: dmg.is_miss
                });
            }
        }
        // Party panels
        const actionPanel = document.getElementById('combat-action-panel');
        if (actionPanel && combatLeft) {
            // Move it back to its stable home BEFORE wiping partyContainer —
            // see comment at combatLeft's declaration.
            combatLeft.appendChild(actionPanel);
        }
        partyContainer.innerHTML = '';
        const initiative = state.initiative || [];
        const activeIndex = state.active_index;
        const party = (state.party && state.party.members) || [];
        const active = initiative[activeIndex];
        const itemCounts = (state.party && state.party.item_counts) || {};
        const template = document.getElementById('party-member-template');

        let activeCharId = null;
        let activeMember = null;
        let activeContainer = null;

        party.forEach(mem => {
            // Clone template
            const clone = template.content.cloneNode(true);
            const container = clone.querySelector('.party-member-wrapper');
            const card = clone.querySelector('.tactical-panel');

            // Set char id for click handling
            card.dataset.charId = mem.char_id;

            // Set active state
            const isActive = active && active.type === 'player' && active.id === mem.char_id;
            if (isActive) {
                card.classList.add('border-warning', 'shadow', 'active-turn');
                card.setAttribute('aria-current', 'true');
                activeCharId = mem.char_id;
                activeMember = mem;
                activeContainer = container;
            }

            // Update data fields
            clone.querySelector('[data-field="name"]').textContent = mem.name || 'Hero';
            clone.querySelector('[data-field="level"]').textContent = 'Lv ' + (mem.level || 1);

            // Update class badge
            const classBadge = clone.querySelector('[data-field="class-badge"]');
            const charClass = (mem.char_class || 'fighter').toLowerCase();
            if (classBadge) {
                classBadge.textContent = (mem.char_class || 'Fighter').charAt(0).toUpperCase() + (mem.char_class || 'Fighter').slice(1);
                classBadge.className = `badge class-badge ${charClass}-badge`;
            }

            // Update HP
            const hpText = clone.querySelector('[data-field="hp-text"]');
            const hpBar = clone.querySelector('[data-field="hp-bar"]');
            if (hpText) hpText.textContent = `${mem.hp}/${mem.max_hp}`;
            if (hpBar) {
                const hpPct = mem.max_hp > 0 ? (mem.hp / mem.max_hp * 100) : 0;
                hpBar.style.width = hpPct + '%';
            }

            // Show damage/heal if character HP changed
            if (window.combatEffects && state.last_damage_to_party) {
                const charDmg = state.last_damage_to_party[mem.char_id];
                if (charDmg && charDmg.amount) {
                    // Delay slightly to let DOM update
                    setTimeout(() => {
                        const charCard = partyContainer.querySelector(`[data-char-id="${mem.char_id}"]`);
                        if (charCard) {
                            window.combatEffects.showDamage(charCard, charDmg.amount, {
                                isCritical: charDmg.is_critical,
                                isMiss: charDmg.is_miss,
                                isHeal: charDmg.is_heal
                            });
                        }
                    }, 50);
                }
            }

            // Update Mana
            const manaText = clone.querySelector('[data-field="mana-text"]');
            const manaBar = clone.querySelector('[data-field="mana-bar"]');
            if (manaText) manaText.textContent = `${mem.mana}/${mem.mana_max}`;
            if (manaBar) {
                const manaPct = mem.mana_max > 0 ? (mem.mana / mem.mana_max * 100) : 0;
                manaBar.style.width = manaPct + '%';
            }

            partyContainer.appendChild(clone);
        });

        // Setup centralized action panel — attach it directly under whichever
        // character card is currently active, instead of leaving it as a
        // static block below the whole party list.
        if (actionPanel && activeCharId && activeMember) {
            const canAct = state.status === 'active';
            if (activeContainer) {
                activeContainer.appendChild(actionPanel);
            }
            actionPanel.style.display = 'block';

            const charClass = (activeMember.char_class || 'fighter').toLowerCase();
            const intStat = activeMember.int_stat || 10;
            const strStat = activeMember.str_stat || 10;
            const dexStat = activeMember.dex_stat || 10;

            // Define which classes can use spells
            const spellcastingClasses = ['mage', 'cleric', 'druid', 'sorcerer', 'warlock', 'bard', 'paladin', 'ranger'];
            const canCastSpells = spellcastingClasses.includes(charClass) || intStat >= 12;

            // Define melee-focused classes
            const meleeFocused = ['fighter', 'barbarian', 'paladin', 'monk', 'ranger'];
            const isPhysical = meleeFocused.includes(charClass) || strStat >= 14;

            // Update action buttons
            actionPanel.querySelectorAll('button[data-action]').forEach(btn => {
                const action = btn.dataset.action;
                let shouldHide = false;

                // Hide spell buttons for non-casters
                if (action.startsWith('cast_') && !canCastSpells) {
                    shouldHide = true;
                }

                if (shouldHide) {
                    btn.style.display = 'none';
                    return;
                }
                btn.style.display = '';

                if (!canAct) {
                    btn.disabled = true;
                } else {
                    btn.disabled = false;
                }

                // Potion availability
                if (btn.dataset.needsPotion) {
                    const potCount = itemCounts['potion-healing'] || 0;
                    if (potCount <= 0) {
                        btn.disabled = true;
                        btn.title = 'No potions available';
                    } else {
                        btn.title = potCount + ' potion' + (potCount === 1 ? '' : 's') + ' remaining';
                    }
                }

                // Mana gating
                if (canAct && btn.dataset.manaCost) {
                    const manaCost = parseInt(btn.dataset.manaCost);
                    if (activeMember.mana < manaCost) {
                        btn.disabled = true;
                        btn.title = 'Not enough mana (' + manaCost + ' required)';
                    }
                }

                // Remove old listeners and add new one
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
                newBtn.addEventListener('click', () => doAction(action, state.version, activeCharId));
            });
        } else if (actionPanel) {
            actionPanel.style.display = 'none';
        }
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
        let spellType = null;

        if (action === 'attack') endpoint = '/api/combat/' + combatId + '/attack';
        else if (action === 'defend') endpoint = '/api/combat/' + combatId + '/defend';
        else if (action === 'cast_firebolt') {
            endpoint = '/api/combat/' + combatId + '/cast';
            payload.spell = 'firebolt';
            spellType = 'firebolt';
        }
        else if (action === 'cast_ice_shard') {
            endpoint = '/api/combat/' + combatId + '/cast';
            payload.spell = 'ice_shard';
            spellType = 'ice_shard';
        }
        else if (action === 'cast_lightning') {
            endpoint = '/api/combat/' + combatId + '/cast';
            payload.spell = 'lightning';
            spellType = 'lightning';
        }
        else if (action === 'use_potion') {
            endpoint = '/api/combat/' + combatId + '/use_item';
            payload.slug = 'potion-healing';
            spellType = 'heal';
        }
        else if (action === 'flee') endpoint = '/api/combat/' + combatId + '/flee';
        else if (action === 'end_turn') endpoint = '/api/combat/' + combatId + '/end_turn';
        else return;

        // Show visual effect for spells
        if (window.combatEffects && spellType) {
            const casterCard = partyContainer.querySelector(`[data-char-id="${actorId}"]`);
            const targetPanel = spellType === 'heal' ? casterCard : document.getElementById('monster-panel');
            if (casterCard && targetPanel) {
                window.combatEffects.createParticles(casterCard, targetPanel, spellType);

                // Add casting glow to button
                const btn = document.querySelector(`[data-action="${action}"]`);
                if (btn) {
                    btn.classList.add('casting');
                    setTimeout(() => btn.classList.remove('casting'), 800);
                }
            }
        }
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

                // Check for XP rewards and trigger progression updates
                if (state.rewards && state.rewards.xp && state.rewards.xp.per_member) {
                    const xpRewards = state.rewards.xp.per_member;

                    // Notify character progression system if available
                    if (window.characterProgression) {
                        Object.keys(xpRewards).forEach(charId => {
                            const xpGained = xpRewards[charId];
                            if (xpGained > 0) {
                                // Update XP bar and check for level-up
                                window.characterProgression.updateXPBar(charId, true);
                            }
                        });
                    }
                }

                // Trigger loot distribution modal if items were awarded
                if (state.rewards && (state.rewards.items || state.rewards.items_list)) {
                    // Fire event for loot distribution system
                    document.dispatchEvent(new CustomEvent('combat-complete', {
                        detail: { combatId: state.id, rewards: state.rewards }
                    }));

                    // Auto-show loot modal after brief delay
                    if (window.lootDistribution) {
                        setTimeout(() => {
                            window.lootDistribution.checkForLoot(state.id);
                        }, 1500);
                    }
                }
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
