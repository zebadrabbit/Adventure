(function () {
    // --- Config API Fetch ---
    let config = {};
    async function fetchConfig() {
        const [namePools, starterItems, baseStats, classMap] = await Promise.all([
            fetch('/api/config/name_pools').then(r => r.json()),
            fetch('/api/config/starter_items').then(r => r.json()),
            fetch('/api/config/base_stats').then(r => r.json()),
            fetch('/api/config/class_map').then(r => r.json()),
        ]);
        config.namePools = namePools;
        config.starterItems = starterItems;
        config.baseStats = baseStats;
        config.classMap = classMap;
    }
    fetchConfig();

    // Dashboard and party logic extracted from dashboard.html
    (function () {
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

        // Initial render: if some checkboxes are already checked (e.g., autofill just created party)
        // populate party table & hidden inputs immediately.
        updatePartyUI();

        // Card click toggles checkbox and keeps visual state in sync
        cards.forEach(card => {
            card.addEventListener('click', function (e) {
                // Prevent click on delete/manage buttons from toggling
                if (e.target.closest('button') || e.target.closest('form') || e.target.closest('a')) return;
                const cb = card.querySelector('.party-select');
                if (cb && !cb.disabled) {
                    cb.checked = !cb.checked;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
            // Keep card visual state in sync with checkbox (for keyboard, autofill, etc.)
            const cb = card.querySelector('.party-select');
        });

        // Add form submission validation and logging
        const adventureForm = document.getElementById('begin-adventure-form');
        if (adventureForm) {
            adventureForm.addEventListener('submit', function (e) {
                const formData = new FormData(adventureForm);
                const partyIds = formData.getAll('party_ids');
                console.log('[dashboard] Form submission - party_ids:', partyIds);

                if (partyIds.length === 0) {
                    e.preventDefault();
                    alert('No party members selected. Please select 1-4 characters or click Autofill Party.');
                    return false;
                }
                if (partyIds.length > 4) {
                    e.preventDefault();
                    alert('Too many party members selected. Maximum is 4.');
                    return false;
                }
                console.log('[dashboard] Form validation passed, submitting...');
            });
        }

    })();

    // Apply server-rendered XP bar fill percentages (kept out of inline
    // style attrs so templates stay free of style=).
    document.querySelectorAll('.xp-fill[data-xp-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.xpPct + '%';
    });
})();
