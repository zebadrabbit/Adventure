// Initialize tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Get current configuration from form
function getCurrentConfig() {
    const form = document.getElementById('combat-form');
    const formData = new FormData(form);

    return {
        crit_multiplier: parseFloat(formData.get('crit_multiplier')),
        base_evasion: parseInt(formData.get('base_evasion')),
        damage_variance_pct: parseInt(formData.get('damage_variance_pct')),
        min_damage: parseInt(formData.get('min_damage')),
        defend_reduction_pct: parseInt(formData.get('defend_reduction_pct')),
        flee_base_chance: parseInt(formData.get('flee_base_chance')),
        spell_costs: {
            firebolt: parseInt(formData.get('spell_firebolt_cost')),
            ice_shard: parseInt(formData.get('spell_ice_shard_cost')),
            lightning: parseInt(formData.get('spell_lightning_cost'))
        },
        spell_int_scaling: parseFloat(formData.get('spell_int_scaling')),
        initiative_bonus: parseInt(formData.get('initiative_bonus')),
        ambush_chance: parseInt(formData.get('ambush_chance')),
        monster_spell_chance: parseInt(formData.get('monster_spell_chance')),
        monster_flee_hp_threshold: parseInt(formData.get('monster_flee_hp_threshold')),
        monster_help_chance: parseInt(formData.get('monster_help_chance')),
        victory_xp_mult: parseFloat(formData.get('victory_xp_mult')),
        flee_xp_penalty_pct: parseInt(formData.get('flee_xp_penalty_pct')),
        party_xp_split: formData.get('party_xp_split'),
        allow_friendly_fire: formData.get('allow_friendly_fire') === 'on',
        death_saves: formData.get('death_saves') === 'on',
        auto_monster_turns: formData.get('auto_monster_turns') === 'on',
        resistance_system: formData.get('resistance_system') === 'on'
    };
}

// Update preview
function updatePreview() {
    const config = getCurrentConfig();
    document.getElementById('config-preview').textContent = JSON.stringify(config, null, 2);
}

// Update preview on any input change
document.getElementById('combat-form').addEventListener('input', updatePreview);
document.getElementById('combat-form').addEventListener('change', updatePreview);

// Initial preview
updatePreview();

// Save settings
document.getElementById('combat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const config = getCurrentConfig();

    try {
        const response = await fetch('/admin/v2/settings/combat/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (result.success) {
            const toast = new bootstrap.Toast(document.getElementById('save-toast'));
            toast.show();
        } else {
            throw new Error(result.error || 'Save failed');
        }
    } catch (error) {
        document.getElementById('error-message').textContent = error.message;
        const toast = new bootstrap.Toast(document.getElementById('error-toast'));
        toast.show();
    }
});

// Reset to defaults
document.getElementById('reset-btn').addEventListener('click', async () => {
    if (!confirm('Reset all combat settings to defaults?')) return;

    try {
        const response = await fetch('/admin/v2/settings/combat/reset', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            window.location.reload();
        } else {
            throw new Error(result.error || 'Reset failed');
        }
    } catch (error) {
        document.getElementById('error-message').textContent = error.message;
        const toast = new bootstrap.Toast(document.getElementById('error-toast'));
        toast.show();
    }
});
