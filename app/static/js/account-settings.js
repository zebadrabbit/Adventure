function confirmDeleteAccount() {
    if (confirm('Are you absolutely sure you want to delete your account? This action cannot be undone and all your characters, progress, and data will be permanently lost.')) {
        if (confirm('This is your last chance. Type "DELETE" in the prompt to confirm.\n\nAre you really sure?')) {
            // TODO: Implement account deletion endpoint
            alert('Account deletion is not yet implemented. Please contact an administrator.');
        }
    }
}
