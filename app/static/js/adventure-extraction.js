// Extraction Modal Handler
document.addEventListener('DOMContentLoaded', () => {
    const hearthBtn = document.getElementById('btn-hearth');
    const extractionModal = new bootstrap.Modal(document.getElementById('extractionModal'));

    if (hearthBtn) {
        hearthBtn.addEventListener('click', async () => {
            // Load extraction status
            try {
                const resp = await fetch('/api/dungeon/extraction/status');
                const data = await resp.json();

                const statusDiv = document.getElementById('extraction-status');
                const charactersDiv = document.getElementById('extraction-characters');
                const confirmBtn = document.getElementById('btn-confirm-extraction');
                const penaltiesDiv = document.getElementById('extraction-penalties');

                if (data.characters && data.characters.length > 0) {
                    statusDiv.classList.add('d-none');
                    charactersDiv.classList.remove('d-none');

                    // Show penalties if early extraction
                    if (!data.all_bosses_defeated && data.penalties) {
                        penaltiesDiv.style.display = 'block';
                        const xpPenalty = Math.round((1 - data.penalties.xp_multiplier) * 100);
                        const lootPenalty = Math.round((1 - data.penalties.loot_quality_multiplier) * 100);
                        document.getElementById('xp-penalty').textContent = xpPenalty + '%';
                        document.getElementById('loot-penalty').textContent = lootPenalty + '%';
                    }

                    // Build character selection list
                    const charList = document.getElementById('character-selection-list');
                    charList.innerHTML = '';

                    const livingChars = data.characters.filter(c => !c.is_dead);

                    data.characters.forEach(char => {
                        const div = document.createElement('div');
                        div.className = 'form-check d-flex align-items-center justify-content-between';

                        const labelHtml = `
              <div>
                <input class="form-check-input extraction-char-check" type="checkbox"
                       value="${char.id}" id="extract-char-${char.id}" checked>
                <label class="form-check-label" for="extract-char-${char.id}">
                  ${char.name} (Level ${char.level})
                  ${char.is_dead ? '<span class="badge bg-danger ms-1">DEAD</span>' : ''}
                  ${char.permadeath ? '<span class="badge bg-dark ms-1">PERMADEATH</span>' : ''}
                </label>
              </div>`;

                        let lootBodyHtml = '';
                        if (char.is_dead && livingChars.length > 0) {
                            lootBodyHtml = `
              <div class="dropdown">
                <button class="btn btn-sm btn-outline-warning dropdown-toggle" type="button"
                        data-bs-toggle="dropdown" id="loot-body-btn-${char.id}">
                  Loot Body
                </button>
                <ul class="dropdown-menu">
                  ${livingChars.map(lc => `<li><a class="dropdown-item loot-body-target"
                      href="#" data-downed-id="${char.id}" data-survivor-id="${lc.id}">${lc.name}</a></li>`).join('')}
                </ul>
              </div>`;
                        }

                        div.innerHTML = labelHtml + lootBodyHtml;
                        charList.appendChild(div);
                    });

                    charList.querySelectorAll('.loot-body-target').forEach(link => {
                        link.addEventListener('click', async (ev) => {
                            ev.preventDefault();
                            const downedId = parseInt(link.getAttribute('data-downed-id'), 10);
                            const survivorId = parseInt(link.getAttribute('data-survivor-id'), 10);
                            const btn = document.getElementById(`loot-body-btn-${downedId}`);
                            try {
                                const r = await fetch('/api/dungeon/loot-body', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ downed_id: downedId, survivor_id: survivorId })
                                });
                                const res = await r.json();
                                if (r.ok && res.success) {
                                    btn.outerHTML = '<span class="badge bg-secondary">Looted</span>';
                                    document.dispatchEvent(new CustomEvent('mud-characters-state-invalidated', { detail: { character_id: survivorId } }));
                                } else {
                                    alert(res.error || 'Loot failed');
                                }
                            } catch (err) {
                                console.error('Loot body failed:', err);
                                alert('Loot failed (network error)');
                            }
                        });
                    });

                    confirmBtn.disabled = false;
                } else {
                    statusDiv.innerHTML = '<p class="text-warning">No characters in dungeon.</p>';
                }

                extractionModal.show();
            } catch (err) {
                console.error('Failed to load extraction status:', err);
                alert('Failed to load extraction status');
            }
        });
    }

    // Handle extraction confirmation
    const confirmBtn = document.getElementById('btn-confirm-extraction');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            const selectedChars = Array.from(document.querySelectorAll('.extraction-char-check:checked'))
                .map(cb => parseInt(cb.value));

            if (selectedChars.length === 0) {
                alert('You must select at least one character to extract');
                return;
            }

            try {
                const resp = await fetch('/api/dungeon/extraction/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ character_ids: selectedChars })
                });

                const data = await resp.json();

                if (data.success) {
                    const secured = data.result && data.result.secured;
                    const summary = secured
                        ? `Secured ${secured.copper_display} and ${secured.items} item(s) to the Hoard.`
                        : '';
                    const statusDiv = document.getElementById('extraction-status');
                    statusDiv.classList.remove('d-none');
                    document.getElementById('extraction-characters').classList.add('d-none');
                    // data.message and the secured.* summary fields are all server-built from integer
                    // counts/format_copper output (extraction_service.extract_party) -- safe to interpolate
                    // raw today. If any of them ever incorporate a player-chosen string, escape it first.
                    statusDiv.innerHTML = `
                <div class="alert alert-success">
                  <strong>${data.message}</strong>
                  ${summary ? `<div class="mt-1">${summary}</div>` : ''}
                </div>`;
                    document.getElementById('btn-confirm-extraction').classList.add('d-none');
                    setTimeout(() => { window.location.href = '/dashboard'; }, 1800);
                } else {
                    alert(data.error || 'Extraction failed');
                }
            } catch (err) {
                console.error('Extraction failed:', err);
                alert('Extraction failed');
            }
        });
    }
});
