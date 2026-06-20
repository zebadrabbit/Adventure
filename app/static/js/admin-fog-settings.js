document.addEventListener('DOMContentLoaded', function () {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const form = document.getElementById('fog-settings-form');
    const resetBtn = document.getElementById('reset-defaults');
    const preview = document.getElementById('fog-config-preview');

    // Update preview when inputs change
    function updatePreview() {
        const config = {
            innerRadius: parseFloat(document.getElementById('inner_radius').value),
            fullRadius: parseFloat(document.getElementById('full_radius').value),
            minOpacity: parseFloat(document.getElementById('min_opacity').value),
            maxOpacity: parseFloat(document.getElementById('max_opacity').value),
            noise: parseFloat(document.getElementById('noise').value),
            memoryOpacity: parseFloat(document.getElementById('memory_opacity').value)
        };
        preview.textContent = JSON.stringify(config, null, 2);
    }

    form.querySelectorAll('input').forEach(input => {
        input.addEventListener('input', updatePreview);
    });

    // Save settings
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        // Convert to proper types
        for (let key in data) {
            data[key] = parseFloat(data[key]);
        }

        try {
            const response = await fetch(form.dataset.saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                showToast('Fog settings saved successfully', 'success');

                // Update global fog config if available
                if (window.globalFogConfig) {
                    window.globalFogConfig.set(data);
                }
            } else {
                showToast(result.error || 'Failed to save settings', 'danger');
            }
        } catch (error) {
            console.error('Save error:', error);
            showToast('Failed to save settings', 'danger');
        }
    });

    // Reset to defaults
    resetBtn.addEventListener('click', async function () {
        if (!confirm('Reset all fog settings to default values?')) return;

        try {
            const response = await fetch(form.dataset.resetUrl, {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                // Update form with defaults
                for (let key in result.config) {
                    const input = document.querySelector(`[name="${key}"]`);
                    if (input) input.value = result.config[key];
                }
                updatePreview();
                showToast('Fog settings reset to defaults', 'info');

                // Update global fog config if available
                if (window.globalFogConfig) {
                    window.globalFogConfig.reset();
                }
            } else {
                showToast(result.error || 'Failed to reset settings', 'danger');
            }
        } catch (error) {
            console.error('Reset error:', error);
            showToast('Failed to reset settings', 'danger');
        }
    });

    // Toast notification helper
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }

        container.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 3000 });
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }
});
