// Dashboard and party logic extracted from dashboard.html
(function() {
    // Party selection logic with limit enforcement and card click
    const selects = Array.from(document.querySelectorAll('.party-select'));
    const partyTable = document.getElementById('party-table');
    const autofillBtn = document.getElementById('autofill-party-btn');
    const beginBtn = document.getElementById('begin-adventure-btn');
    const partyCount = document.getElementById('party-count');
    const hiddenInputs = document.getElementById('party-hidden-inputs');
    const cards = Array.from(document.querySelectorAll('.character-card'));

    function getClassInfo(id) {
        const card = document.querySelector(`.character-card[data-id="${id}"]`);
        if (card) {
            const badge = card.querySelector('.class-badge');
            if (badge) {
                return {
                    name: badge.textContent.trim(),
                    className: badge.className
                };
            }
        }
        return { name: '', className: '' };
    }

    function getSelected() {
        return selects.filter(cb => cb.checked).map(cb => {
            const id = cb.getAttribute('data-id');
            const name = cb.getAttribute('data-name');
            const card = document.querySelector(`.character-card[data-id="${id}"]`);
            let level = '';
            let classInfo = getClassInfo(id);
            if (card) {
                const badge = card.querySelector('.badge.bg-info');
                if (badge) {
                    const m = badge.textContent.match(/\d+/);
                    if (m) level = m[0];
                }
            }
            return { id, name, level, classInfo };
        });
    }

    function updatePartyUI() {
        const sel = getSelected();
        // Update party table
        if (sel.length === 0) {
            partyTable.innerHTML = '';
        } else {
            let html = `<div class="table-responsive"><table class="table table-sm table-dark table-striped table-bordered mb-0 party-table-compact" style="border-radius: 0.5rem; overflow: hidden; font-size: 0.95rem;">\n`;
            html += `<thead class="table-warning text-dark"><tr><th class="ps-2" style="padding: 0.25rem 0.5rem;">Name</th><th style="padding: 0.25rem 0.5rem;">Level</th><th style="padding: 0.25rem 0.5rem;">Class</th></tr></thead><tbody>`;
            sel.forEach(s => {
                html += `<tr><td class="ps-2 fw-semibold" style="padding: 0.25rem 0.5rem;">${s.name}</td><td class="text-center" style="padding: 0.25rem 0.5rem;">${s.level}</td><td class="text-center" style="padding: 0.25rem 0.5rem;"><span class='badge ${s.classInfo.className}'>${s.classInfo.name}</span></td></tr>`;
            });
            html += '</tbody></table></div>';
            partyTable.innerHTML = html;
        }
        // Update party count
        if (partyCount) partyCount.textContent = sel.length;
        // Enable/disable Begin Adventure button
        if (beginBtn) beginBtn.disabled = !(sel.length >= 1 && sel.length <= 4);
        // Update hidden inputs for form submission
        if (hiddenInputs) {
            hiddenInputs.innerHTML = '';
            sel.forEach(s => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'party_ids';
                input.value = s.id;
                hiddenInputs.appendChild(input);
            });
        }
        // Enforce max 4 selection
        if (sel.length >= 4) {
            selects.forEach(cb => {
                if (!cb.checked) cb.disabled = true;
            });
        } else {
            selects.forEach(cb => { cb.disabled = false; });
        }
        // Sync card selected class
        selects.forEach(cb => {
            const card = document.querySelector(`.character-card[data-id="${cb.getAttribute('data-id')}"]`);
            if (card) card.classList.toggle('selected', cb.checked);
        });
    }

    selects.forEach(cb => {
        cb.addEventListener('change', updatePartyUI);
    });

    // Card click toggles checkbox
    cards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Prevent click on delete/manage buttons from toggling
            if (e.target.closest('button') || e.target.closest('form') || e.target.closest('a')) return;
            const cb = card.querySelector('.party-select');
            if (cb && !cb.disabled) {
                cb.checked = !cb.checked;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });

    updatePartyUI();

    if (autofillBtn) {
        autofillBtn.addEventListener('click', function(e) {
            e.preventDefault();
            selects.forEach(cb => { cb.checked = false; });
            const pool = selects.slice();
            for (let i = pool.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [pool[i], pool[j]] = [pool[j], pool[i]];
            }
            let filled = 0;
            for (let i = 0; i < pool.length && filled < 4; i++) {
                pool[i].checked = true;
                filled++;
            }
            if (filled < 4) {
                fetch('/autofill_characters', { method: 'POST' })
                    .then(resp => resp.json())
                    .then(data => {
                        if (data && data.created) {
                            window.location.reload();
                        }
                    });
            } else {
                selects.forEach(cb => cb.dispatchEvent(new Event('change', { bubbles: true })));
            }
        });
    }

    // Dungeon seed randomizer
    const seedInput = document.getElementById('dungeon-seed');
    const seedBtn = document.getElementById('generate-seed-btn');
    if (seedInput && seedBtn) {
        seedBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // Generate a random 8-character alphanumeric seed
            const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
            let seed = '';
            for (let i = 0; i < 8; i++) {
                seed += charset.charAt(Math.floor(Math.random() * charset.length));
            }
            seedInput.value = seed;
        });
    }
})();