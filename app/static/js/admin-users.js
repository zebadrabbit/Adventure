function showToast(message, type = 'info') {
    const toast = document.getElementById('userToast');
    const toastBody = document.getElementById('userToastBody');
    toastBody.textContent = message;

    // Update toast style based on type
    toast.classList.remove('bg-success', 'bg-danger', 'bg-warning');
    if (type === 'success') toast.classList.add('bg-success');
    else if (type === 'error') toast.classList.add('bg-danger');
    else if (type === 'warning') toast.classList.add('bg-warning');

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function updateUserRole(userId, newRole) {
    fetch(`/admin/v2/users/${userId}/role`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ role: newRole })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(`User role updated to ${newRole}`, 'success');
            } else {
                showToast('Failed to update role: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            showToast('Error updating role: ' + err.message, 'error');
        });
}

function banUser(userId) {
    const reason = prompt('Enter ban reason (optional):');
    if (reason === null) return; // User cancelled

    fetch(`/admin/v2/users/${userId}/ban`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'ban', reason: reason })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('User banned successfully', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showToast('Failed to ban user: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            showToast('Error banning user: ' + err.message, 'error');
        });
}

function unbanUser(userId) {
    if (!confirm('Unban this user?')) return;

    fetch(`/admin/v2/users/${userId}/ban`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'unban' })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('User unbanned successfully', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showToast('Failed to unban user: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            showToast('Error unbanning user: ' + err.message, 'error');
        });
}
