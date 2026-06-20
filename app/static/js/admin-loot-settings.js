// Initialize tooltips
document.addEventListener('DOMContentLoaded', function () {
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(el => new bootstrap.Tooltip(el));

    // Update preview on input change
    const inputs = document.querySelectorAll('#lootSettingsForm input, #lootSettingsForm select');
    inputs.forEach(input => {
        input.addEventListener('change', updatePreview);
    });

    updatePreview();
});

function showToast(message, type = 'info') {
    const toast = document.getElementById('lootToast');
    const toastBody = document.getElementById('lootToastBody');
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
        base_drop_rate: parseFloat(document.getElementById('base_drop_rate').value),
        magic_find_mult: parseFloat(document.getElementById('magic_find_mult').value),
        gold_multiplier: parseFloat(document.getElementById('gold_multiplier').value),
        rarity_weights: {
            common: parseInt(document.getElementById('rarity_common').value),
            uncommon: parseInt(document.getElementById('rarity_uncommon').value),
            rare: parseInt(document.getElementById('rarity_rare').value),
            epic: parseInt(document.getElementById('rarity_epic').value),
            legendary: parseInt(document.getElementById('rarity_legendary').value),
            mythic: parseInt(document.getElementById('rarity_mythic').value)
        },
        category_weights: {
            weapons: parseInt(document.getElementById('category_weapons').value),
            armor: parseInt(document.getElementById('category_armor').value),
            consumables: parseInt(document.getElementById('category_consumables').value),
            jewelry: parseInt(document.getElementById('category_jewelry').value)
        },
        elite_loot_mult: parseFloat(document.getElementById('elite_loot_mult').value),
        boss_loot_mult: parseFloat(document.getElementById('boss_loot_mult').value),
        boss_min_rarity: document.getElementById('boss_min_rarity').value,
        boss_cache_size: parseInt(document.getElementById('boss_cache_size').value),
        smart_loot: document.getElementById('smart_loot').checked,
        unique_protection: document.getElementById('unique_protection').checked,
        level_scaling: document.getElementById('level_scaling').checked
    };
}

function updatePreview() {
    const config = getCurrentConfig();
    document.getElementById('configPreview').textContent = JSON.stringify(config, null, 2);
}

function saveLootSettings() {
    const config = getCurrentConfig();

    fetch('/admin/v2/settings/loot/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Loot settings saved successfully', 'success');
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function resetLootSettings() {
    if (!confirm('Reset all loot settings to defaults?')) return;

    fetch('/admin/v2/settings/loot/reset', {
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
