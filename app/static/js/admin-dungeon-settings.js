// Initialize tooltips
document.addEventListener('DOMContentLoaded', function () {
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(el => new bootstrap.Tooltip(el));

    // Update preview on input change
    const inputs = document.querySelectorAll('#dungeonSettingsForm input');
    inputs.forEach(input => {
        input.addEventListener('change', updatePreview);
    });

    updatePreview();
});

function showToast(message, type = 'info') {
    const toast = document.getElementById('dungeonToast');
    const toastBody = document.getElementById('dungeonToastBody');
    toastBody.textContent = message;

    toast.classList.remove('bg-success', 'bg-danger', 'bg-warning');
    if (type === 'success') toast.classList.add('bg-success');
    else if (type === 'error') toast.classList.add('bg-danger');
    else if (type === 'warning') toast.classList.add('bg-warning');

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function getCurrentConfig() {
    return {
        map_size: parseInt(document.getElementById('map_size').value),
        room_density: parseFloat(document.getElementById('room_density').value),
        monster_density: parseFloat(document.getElementById('monster_density').value),
        elite_spawn_rate: parseFloat(document.getElementById('elite_spawn_rate').value),
        boss_count: parseInt(document.getElementById('boss_count').value),
        loot_density: parseFloat(document.getElementById('loot_density').value),
        hp_mult_per_tier: parseFloat(document.getElementById('hp_mult_per_tier').value),
        dmg_mult_per_tier: parseFloat(document.getElementById('dmg_mult_per_tier').value),
        xp_mult_per_tier: parseFloat(document.getElementById('xp_mult_per_tier').value),
        loot_mult_per_tier: parseFloat(document.getElementById('loot_mult_per_tier').value),
        early_exit_xp_penalty: parseInt(document.getElementById('early_exit_xp_penalty').value),
        early_exit_loot_penalty: parseInt(document.getElementById('early_exit_loot_penalty').value),
        full_clear_bonus: parseInt(document.getElementById('full_clear_bonus').value),
        flawless_xp_bonus: parseInt(document.getElementById('flawless_xp_bonus').value),
        speed_clear_time: parseInt(document.getElementById('speed_clear_time').value),
        speed_clear_bonus: parseInt(document.getElementById('speed_clear_bonus').value),
        affixes: {
            frenzied: document.getElementById('affix_frenzied').checked,
            bolstered: document.getElementById('affix_bolstered').checked,
            volcanic: document.getElementById('affix_volcanic').checked,
            necrotic: document.getElementById('affix_necrotic').checked,
            arcane: document.getElementById('affix_arcane').checked,
            cursed: document.getElementById('affix_cursed').checked
        }
    };
}

function updatePreview() {
    const config = getCurrentConfig();
    document.getElementById('configPreview').textContent = JSON.stringify(config, null, 2);
}

function saveDungeonSettings() {
    const config = getCurrentConfig();

    fetch('/admin/v2/settings/dungeon/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Dungeon settings saved successfully', 'success');
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function resetDungeonSettings() {
    if (!confirm('Reset all dungeon settings to defaults?')) return;

    fetch('/admin/v2/settings/dungeon/reset', {
        method: 'POST'
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Settings reset to defaults', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}
