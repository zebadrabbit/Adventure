let configModal;

document.addEventListener('DOMContentLoaded', function () {
    configModal = new bootstrap.Modal(document.getElementById('configModal'));
});

function showToast(message, type = 'info') {
    const toast = document.getElementById('dbToast');
    const toastBody = document.getElementById('dbToastBody');
    toastBody.textContent = message;

    toast.classList.remove('bg-success', 'bg-danger', 'bg-warning');
    if (type === 'success') toast.classList.add('bg-success');
    else if (type === 'error') toast.classList.add('bg-danger');
    else if (type === 'warning') toast.classList.add('bg-warning');

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function addConfig() {
    document.getElementById('configModalTitle').textContent = 'Add Configuration';
    document.getElementById('configKey').value = '';
    document.getElementById('configValue').value = '';
    document.getElementById('configKey').disabled = false;
    configModal.show();
}

function editConfig(key, value) {
    document.getElementById('configModalTitle').textContent = 'Edit Configuration';
    document.getElementById('configKey').value = key;
    document.getElementById('configValue').value = value;
    document.getElementById('configKey').disabled = true;
    configModal.show();
}

function saveConfig() {
    const key = document.getElementById('configKey').value.trim();
    const value = document.getElementById('configValue').value.trim();

    if (!key || !value) {
        showToast('Key and value are required', 'error');
        return;
    }

    fetch('/admin/v2/database/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Configuration saved', 'success');
                configModal.hide();
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function deleteConfig(key) {
    if (!confirm(`Delete configuration "${key}"?`)) return;

    fetch(`/admin/v2/database/config/${encodeURIComponent(key)}`, {
        method: 'DELETE'
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Configuration deleted', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}
