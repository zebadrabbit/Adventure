// Shared by the load-time paint below and partyCardRefresh()'s paint() --
// HP colour is state-carrying (green -> red as a character nears death), so
// it needs recomputing every time the bar's percentage changes, not just
// once on page load.
function hpFillColor(pct) {
    const hue = Math.floor(120 * (pct / 100)); // 120 green -> 0 red
    return 'hsl(' + hue + ',70%,45%)';
}

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
                        if (!j) return;
                        // Camping costs a campfire kit and has a cooldown; both
                        // refusals come back as 400s with an explanatory message.
                        if (j.error === 'no_supplies') {
                            appendLog('No one is carrying a campfire kit. Buy one before you descend.', 'text-warning');
                            return;
                        }
                        if (j.error === 'camp_cooldown') {
                            appendLog(`Too soon to rest again (${j.remaining_ticks} ticks).`, 'text-warning');
                            return;
                        }
                        if (j.message) appendLog(j.message);
                        if (j.restored_hp_total) appendLog(`Party recovers ${j.restored_hp_total} HP collectively.`, 'text-success small');
                        if (j.restored_mana_total) appendLog(`Party recovers ${j.restored_mana_total} MP collectively.`, 'text-info small');
                        if (typeof j.supplies_remaining === 'number') {
                            appendLog(`Campfire kits remaining: ${j.supplies_remaining}`, 'text-muted small');
                        }
                        if (j.ambush && j.ambush.count) {
                            appendLog(`${j.ambush.count} shapes close in on the firelight!`, 'text-danger');
                            if (window.refreshEntities) window.refreshEntities();
                        }
                        if (window.refreshPartyCards) window.refreshPartyCards();
                        if (j.encounter && j.encounter.combat_id) { window.location.href = '/combat/' + j.encounter.combat_id; }
                    })
                    .catch(() => appendLog('Camp failed (network error)', 'text-danger'))
                    .finally(() => { campBtn.disabled = false; });
            });
        }
        if (hearthBtn) {
            hearthBtn.addEventListener('click', () => {
                if (!confirm('Hearth and abandon this dungeon run? You keep what you found, but this dungeon is gone.')) return;
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
            // Don't trigger if user is typing/selecting in a form control --
            // every hotkey is suspect here, not just Space, so this stays a
            // blanket bail regardless of which key was pressed.
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

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
                // Space is special, unlike every other hotkey here: the
                // browser natively activates a focused <button>/<a> on
                // Space, and a focused .adv-frame-open activates itself the
                // same way (its own keydown handler below -- role="button"
                // gets no native Space handling, which is why that handler
                // exists). Bail here, scoped to Space only, so Search
                // doesn't ALSO fire on top of whatever the focused control
                // just did. Movement and the letter hotkeys below have no
                // such native collision and must keep working even when
                // focus is merely resting on a button -- e.g. right after a
                // mouse click, since browsers leave a clicked <button>
                // focused. (An earlier version of this guard bailed on ANY
                // key whenever ANY button/link/frame had focus, which broke
                // WASD/C/E/H/I for the rest of the session after a single
                // button click -- verified in a live session, not a
                // hypothetical.)
                //
                // <summary> (the log's collapse header, .adv-log-head) is
                // the same class of native-Space-activation element: focused
                // and tabbable, and the browser toggles the parent <details>
                // on Space with no handler of its own needed -- exactly like
                // button/a. Missing it here meant tabbing to the log header
                // and pressing Space fired Search (2 turns, can roll an
                // encounter) instead of, or in addition to, the native
                // toggle.
                if (e.target.closest?.('.adv-frame-open, button, a, summary')) return;
                e.preventDefault();
                const searchBtn = document.getElementById('btn-search');
                if (searchBtn && !searchBtn.disabled) searchBtn.click();
            } else if (key === 'c') {
                const campBtn = document.getElementById('btn-camp');
                if (campBtn && !campBtn.disabled) campBtn.click();
            } else if (key === 'e') {
                const extractBtn = document.getElementById('btn-extract');
                if (extractBtn && !extractBtn.disabled) extractBtn.click();
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
        const fill = w.querySelector('[data-bar="hp"]');
        if (fill) {
            fill.style.width = pct.toFixed(1) + '%';
            fill.style.backgroundColor = hpFillColor(pct);
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
            // No inline colour here -- adventure-hud.css's
            // .mana-bar .party-stat-bar-fill { background: var(--mp); }
            // owns it. (Previously hardcoded to '#3b82f6', a near-duplicate
            // of --mp that didn't match it.)
            fill.style.transition = 'width 0.3s ease-in-out';
        }
    });

    // Clicking anywhere on a party frame opens that character, same as the
    // frame's equip button. The paper doll itself is the next chunk
    // (specs/2026-07-28-character-panel-redesign.md); this is the hook it
    // will reuse.
    document.addEventListener('click', (e) => {
        const frame = e.target.closest('.adv-frame-open');
        if (!frame) return;
        // Let the frame's own buttons handle their own clicks.
        if (e.target.closest('button')) return;
        const equipBtn = frame.querySelector('.btn-equip-panel');
        if (equipBtn) equipBtn.click();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const frame = e.target.closest?.('.adv-frame-open');
        if (!frame || e.target !== frame) return;
        e.preventDefault();
        const equipBtn = frame.querySelector('.btn-equip-panel');
        if (equipBtn) equipBtn.click();
    });
});

// ---------------------------------------------------------------- party cards
// The character cards are server-rendered once. Before /api/dungeon/party
// existed they were built from a session snapshot taken when the party was
// picked, so every card showed full HP/MP for the whole run regardless of what
// combat, regeneration or camping did. They are now refreshed from the database
// after anything that can change those numbers.
(function partyCardRefresh() {
    function paint(member) {
        const card = document.querySelector(`[data-member-id="${member.id}"]`);
        if (!card) return;

        const set = (barSelector, cur, max, label) => {
            const track = card.querySelector(barSelector);
            if (!track) return;
            const fill = track.querySelector('.party-stat-bar-fill');
            const safeMax = Math.max(1, Number(max) || 1);
            const pct = Math.max(0, Math.min(100, (Number(cur) || 0) / safeMax * 100));
            if (fill) {
                fill.style.width = pct + '%';
                fill.textContent = `${label} ${cur}/${max}`;
                // Recompute the health hue on every refresh, not just page
                // load -- otherwise a character who drops to 10% keeps
                // whatever colour the bar had when the page was rendered
                // until the next full reload. Mana has no equivalent: its
                // colour is fixed (adventure-hud.css's --mp), never
                // inline-styled.
                if (label === 'HP') fill.style.backgroundColor = hpFillColor(pct);
            }
            track.setAttribute(label === 'HP' ? 'data-hp' : 'data-mana', cur);
            track.setAttribute(label === 'HP' ? 'data-hp-max' : 'data-mana-max', max);
        };

        set('.hp-bar', member.hp, member.hp_max, 'HP');
        set('.mana-bar', member.mana, member.mana_max, 'MP');
        // A downed character should be obvious at a glance.
        card.classList.toggle('is-downed', Number(member.hp) <= 0);
    }

    let inFlight = false;
    window.refreshPartyCards = function refreshPartyCards() {
        if (inFlight) return;
        inFlight = true;
        fetch('/api/dungeon/party', { headers: { Accept: 'application/json' } })
            .then(r => (r.ok ? r.json() : null))
            .then(data => {
                if (!data || !Array.isArray(data.party)) return;
                data.party.forEach(paint);
            })
            .catch(() => { /* a failed refresh must never break play */ })
            .finally(() => { inFlight = false; });
    };

    document.addEventListener('DOMContentLoaded', () => window.refreshPartyCards());
})();
