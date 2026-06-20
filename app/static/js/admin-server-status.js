document.addEventListener('DOMContentLoaded', function () {
    // Get Python and Flask versions
    fetch('/admin/v2/api/server-info')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                document.getElementById('python-version').textContent = data.python_version;
                document.getElementById('flask-version').textContent = data.flask_version;
                document.getElementById('server-uptime').textContent = data.uptime;
            }
        })
        .catch(err => console.error('Failed to load server info:', err));
});
