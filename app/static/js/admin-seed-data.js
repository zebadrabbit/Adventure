function showToast(message, type = 'info') {
    const toast = document.getElementById('seedToast');
    const toastBody = document.getElementById('seedToastBody');
    toastBody.textContent = message;

    toast.classList.remove('bg-success', 'bg-danger', 'bg-warning');
    if (type === 'success') toast.classList.add('bg-success');
    else if (type === 'error') toast.classList.add('bg-danger');
    else if (type === 'warning') toast.classList.add('bg-warning');

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function showResults(data) {
    const resultsCard = document.getElementById('resultsCard');
    const resultsContent = document.getElementById('resultsContent');

    let html = '';
    if (data.errors && data.errors.length > 0) {
        html += '<div class="alert alert-danger">';
        html += '<h6>Errors:</h6><ul>';
        data.errors.forEach(err => {
            html += `<li>${err}</li>`;
        });
        html += '</ul></div>';
    }

    if (data.imported !== undefined && data.imported !== null) {
        html += `<div class="alert alert-success">Successfully imported ${data.imported} records</div>`;
    }

    if (data.message) {
        html += `<div class="alert alert-info">${data.message}</div>`;
    }

    resultsContent.innerHTML = html;
    resultsCard.classList.remove('d-none');
}

function uploadItems() {
    const fileInput = document.getElementById('itemsFile');
    if (!fileInput.files[0]) {
        showToast('Please select a file', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    showToast('Uploading items...', 'info');

    fetch('/admin/items', {
        method: 'POST',
        body: formData
    })
        .then(r => r.text())
        .then(html => {
            showToast('Items uploaded', 'success');
            // Parse the response HTML to extract results
            setTimeout(() => location.reload(), 1500);
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function uploadMonsters() {
    const fileInput = document.getElementById('monstersFile');
    if (!fileInput.files[0]) {
        showToast('Please select a file', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    showToast('Uploading monsters...', 'info');

    fetch('/admin/monsters', {
        method: 'POST',
        body: formData
    })
        .then(r => r.text())
        .then(html => {
            showToast('Monsters uploaded', 'success');
            setTimeout(() => location.reload(), 1500);
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}

function runSqlSeed(type) {
    if (!confirm(`Run SQL seed for ${type}?`)) return;

    showToast(`Running ${type} seed...`, 'info');

    fetch(`/admin/v2/tools/seed/${type}`, {
        method: 'POST'
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(data.message || 'Seed completed', 'success');
                if (data.details) showResults(data.details);
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
}
