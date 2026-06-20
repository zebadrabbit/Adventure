// Initialize tooltips
document.addEventListener('DOMContentLoaded', function () {
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(el => new bootstrap.Tooltip(el));

    // Update preview on input change
    const inputs = document.querySelectorAll('#progressionSettingsForm input, #progressionSettingsForm select');
    inputs.forEach(input => {
        input.addEventListener('change', updatePreview);
    });

    updatePreview();
});

function showToast(message, type = 'info') {
    const toast = document.getElementById('progressionToast');
    const toastBody = document.getElementById('progressionToastBody');
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
        max_level: parseInt(document.getElementById('max_level').value),
        xp_curve_type: document.getElementById('xp_curve_type').value,
        base_xp_mult: parseFloat(document.getElementById('base_xp_mult').value),
        death_xp_penalty: parseInt(document.getElementById('death_xp_penalty').value),
        xp_sources: {
            monster_kills: parseFloat(document.getElementById('monster_xp_mult').value),
            exploration: parseFloat(document.getElementById('exploration_xp_mult').value),
            quests: parseFloat(document.getElementById('quest_xp_mult').value),
            skill_usage: parseFloat(document.getElementById('skill_xp_mult').value),
            dungeon_clear: parseFloat(document.getElementById('dungeon_xp_mult').value)
        },
        talent_frequency: parseInt(document.getElementById('talent_frequency').value),
        starting_talent_points: parseInt(document.getElementById('starting_talent_points').value),
        respec_cost: parseInt(document.getElementById('respec_cost').value),
        stat_points_per_level: parseInt(document.getElementById('stat_points_per_level').value),
        starting_stat_total: parseInt(document.getElementById('starting_stat_total').value),
        max_stat: parseInt(document.getElementById('max_stat').value),
        tier_bonuses: {
            early_loot: parseFloat(document.getElementById('early_loot_tier').value),
            mid_loot: parseFloat(document.getElementById('mid_loot_tier').value),
            late_loot: parseFloat(document.getElementById('late_loot_tier').value)
        },
        level_scaling_enemies: document.getElementById('level_scaling_enemies').checked,
        party_xp_sharing: document.getElementById('party_xp_sharing').checked,
        rest_xp_bonus: document.getElementById('rest_xp_bonus').checked,
        allow_deleveling: document.getElementById('allow_deleveling').checked
    };
}

function updatePreview() {
    const config = getCurrentConfig();
    document.getElementById('configPreview').textContent = JSON.stringify(config, null, 2);
}

function saveProgressionSettings() {
    const config = getCurrentConfig();

    fetch('/admin/v2/settings/progression/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Progression settings saved successfully', 'success');
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function resetProgressionSettings() {
    if (!confirm('Reset all progression settings to defaults?')) return;

    fetch('/admin/v2/settings/progression/reset', {
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
