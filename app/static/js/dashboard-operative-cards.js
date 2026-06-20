// Update select button text when party changes
document.addEventListener('DOMContentLoaded', function () {
    const updateSelectButtons = () => {
        document.querySelectorAll('.select-operative').forEach(btn => {
            const isSelected = btn.dataset.selected === 'true' || btn.classList.contains('selected');
            btn.querySelector('.select-text').textContent = isSelected ? 'SELECTED' : 'SELECT';
            if (isSelected) {
                btn.classList.add('selected');
                btn.closest('.operative-card').classList.add('selected');
            }
        });
    };

    // Hook into party selection
    document.querySelectorAll('.party-select').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectButtons);
    });

    updateSelectButtons();

    // Add equipped item badges
    if (window.equipmentManager) {
        document.querySelectorAll('.operative-card').forEach(card => {
            const charId = card.dataset.id;
            if (!charId) return;

            // Fetch character data to show equipped count
            fetch(`/api/characters/${charId}`)
                .then(r => r.json())
                .then(char => {
                    const gearCount = Object.keys(char.gear || {}).filter(slot => char.gear[slot]).length;
                    if (gearCount > 0) {
                        const equipBtn = card.querySelector('.btn-equip-panel');
                        if (equipBtn) {
                            equipBtn.style.position = 'relative';
                            const badge = document.createElement('span');
                            badge.className = 'position-absolute top-0 start-100 translate-middle badge rounded-pill bg-success';
                            badge.style.fontSize = '0.65rem';
                            badge.textContent = gearCount;
                            equipBtn.appendChild(badge);
                        }
                    }
                })
                .catch(() => { });
        });
    }
});
