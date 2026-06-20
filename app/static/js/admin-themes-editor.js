document.addEventListener('DOMContentLoaded', function () {
    let currentThemeId = null;
    let isPreviewMode = false;
    let currentBackgroundImage = null;

    // Initialize Dropzone
    const bgDropzone = new Dropzone("#backgroundImageDropzone", {
        url: "/api/admin/themes/upload-background",
        maxFiles: 1,
        maxFilesize: 5, // MB
        acceptedFiles: "image/*",
        addRemoveLinks: true,
        dictDefaultMessage: "Drop image here or click to upload",
        init: function () {
            this.on("success", function (file, response) {
                if (response.url) {
                    currentBackgroundImage = response.url;
                    document.getElementById('backgroundImage').value = response.url;
                    updateBackgroundPreview();
                    document.getElementById('removeBackgroundBtn').style.display = 'block';
                }
            });
            this.on("removedfile", function (file) {
                currentBackgroundImage = null;
                document.getElementById('backgroundImage').value = '';
                updateBackgroundPreview();
                document.getElementById('removeBackgroundBtn').style.display = 'none';
            });
        }
    });

    // Remove background button
    document.getElementById('removeBackgroundBtn').addEventListener('click', function () {
        bgDropzone.removeAllFiles(true);
        currentBackgroundImage = null;
        document.getElementById('backgroundImage').value = '';
        updateBackgroundPreview();
        this.style.display = 'none';
    });

    // Background property change handlers
    ['bgPosition', 'bgSize', 'bgRepeat', 'bgAttachment'].forEach(id => {
        document.getElementById(id).addEventListener('change', updateBackgroundPreview);
    });

    function updateBackgroundPreview() {
        const preview = document.getElementById('bgImagePreview');
        const imageUrl = currentBackgroundImage || document.getElementById('backgroundImage').value;

        if (imageUrl) {
            preview.style.backgroundImage = `url(${imageUrl})`;
            preview.style.backgroundPosition = document.getElementById('bgPosition').value;
            preview.style.backgroundSize = document.getElementById('bgSize').value;
            preview.style.backgroundRepeat = document.getElementById('bgRepeat').value;
            preview.classList.add('active');
        } else {
            preview.style.backgroundImage = '';
            preview.classList.remove('active');
        }
    }

    // Load all themes into selector
    function loadThemes() {
        fetch('/api/admin/themes')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Themes loaded:', data);
                const selector = document.getElementById('themeSelector');
                // Keep "Create New" option
                selector.innerHTML = '<option value="new">+ Create New Theme</option>';

                if (!data.themes || !Array.isArray(data.themes)) {
                    console.error('Invalid themes data:', data);
                    showNotification('Invalid theme data received', 'error');
                    return;
                }

                let activeThemeId = null;
                data.themes.forEach(theme => {
                    const option = document.createElement('option');
                    option.value = theme.id;
                    option.textContent = theme.name + (theme.is_active ? ' (Active)' : '');
                    selector.appendChild(option);

                    // Track the active theme
                    if (theme.is_active) {
                        activeThemeId = theme.id;
                    }
                });

                // Auto-load the active theme
                if (activeThemeId) {
                    selector.value = activeThemeId;
                    loadThemeData(activeThemeId);
                }
            })
            .catch(error => {
                console.error('Error loading themes:', error);
                showNotification('Failed to load themes: ' + error.message, 'error');
            });
    }

    // Load theme data into form
    function loadThemeData(themeId) {
        fetch(`/api/admin/themes/${themeId}`)
            .then(response => response.json())
            .then(theme => {
                currentThemeId = theme.id;

                // Basic info
                document.getElementById('themeName').value = theme.name || '';
                document.getElementById('themeDescription').value = theme.description || '';

                // Gradient (if stored)
                if (theme.gradient) {
                    document.getElementById('gradientAngle').value = theme.gradient.angle || 135;
                    document.getElementById('gradientStart').value = theme.gradient.start || '#4c5270';
                    document.getElementById('gradientStart_hex').value = theme.gradient.start || '#4c5270';
                    document.getElementById('gradientEnd').value = theme.gradient.end || '#5a3a52';
                    document.getElementById('gradientEnd_hex').value = theme.gradient.end || '#5a3a52';
                }

                // Colors
                const colorFields = [
                    'primary', 'secondary', 'success', 'danger', 'warning', 'info',
                    'light', 'dark', 'body_bg', 'body_color',
                    'link_color', 'link_hover_color', 'border_color', 'card_bg'
                ];

                colorFields.forEach(field => {
                    if (theme[field]) {
                        document.getElementById(field).value = theme[field];
                        document.getElementById(field + '_hex').value = theme[field].toUpperCase();
                    }
                });

                // Card opacity
                if (theme.card_opacity !== undefined) {
                    const opacityPercent = Math.round(theme.card_opacity * 100);
                    document.getElementById('cardOpacity').value = opacityPercent;
                    document.getElementById('cardOpacityValue').textContent = opacityPercent + '%';
                }

                // Background image
                if (theme.background_image) {
                    currentBackgroundImage = theme.background_image;
                    document.getElementById('backgroundImage').value = theme.background_image;
                    document.getElementById('bgPosition').value = theme.bg_position || 'center';
                    document.getElementById('bgSize').value = theme.bg_size || 'cover';
                    document.getElementById('bgRepeat').value = theme.bg_repeat || 'no-repeat';
                    document.getElementById('bgAttachment').value = theme.bg_attachment || 'scroll';
                    updateBackgroundPreview();
                    document.getElementById('removeBackgroundBtn').style.display = 'block';
                } else {
                    currentBackgroundImage = null;
                    document.getElementById('backgroundImage').value = '';
                    document.getElementById('removeBackgroundBtn').style.display = 'none';
                }

                // Update gradient preview
                updateGradientPreview();

                // Show/hide buttons
                document.getElementById('deleteThemeBtn').style.display = 'inline-block';
                document.getElementById('previewThemeBtn').style.display = 'inline-block';
                document.getElementById('applyThemeBtn').style.display = theme.is_active ? 'none' : 'inline-block';
            })
            .catch(error => {
                console.error('Error loading theme:', error);
                showNotification('Failed to load theme', 'error');
            });
    }

    // Clear form for new theme
    function resetForm() {
        currentThemeId = null;
        document.getElementById('themeForm').reset();
        document.getElementById('themeName').value = '';
        document.getElementById('themeDescription').value = '';

        // Reset to defaults
        document.getElementById('gradientAngle').value = 135;
        document.getElementById('gradientStart').value = '#4c5270';
        document.getElementById('gradientStart_hex').value = '#4c5270';
        document.getElementById('gradientEnd').value = '#5a3a52';
        document.getElementById('gradientEnd_hex').value = '#5a3a52';

        updateGradientPreview();

        // Hide action buttons
        document.getElementById('deleteThemeBtn').style.display = 'none';
        document.getElementById('previewThemeBtn').style.display = 'none';
        document.getElementById('applyThemeBtn').style.display = 'none';
    }

    // Gradient preview update
    function updateGradientPreview() {
        const angle = document.getElementById('gradientAngle').value;
        const start = document.getElementById('gradientStart').value;
        const end = document.getElementById('gradientEnd').value;

        const preview = document.getElementById('gradientPreview');
        preview.style.background = `linear-gradient(${angle}deg, ${start}, ${end})`;

        document.getElementById('angleValue').textContent = angle + '°';
    }

    // Sync color picker with hex input
    function syncColorInputs(pickerId) {
        const picker = document.getElementById(pickerId);
        const hexInput = document.getElementById(pickerId + '_hex');

        picker.addEventListener('input', (e) => {
            hexInput.value = e.target.value.toUpperCase();
            if (pickerId.startsWith('gradient')) {
                updateGradientPreview();
            }
        });

        hexInput.addEventListener('input', (e) => {
            const value = e.target.value;
            if (/^#[0-9A-Fa-f]{6}$/.test(value)) {
                picker.value = value;
                if (pickerId.startsWith('gradient')) {
                    updateGradientPreview();
                }
            }
        });
    }

    // Initialize all color inputs
    const colorInputs = [
        'gradientStart', 'gradientEnd', 'primary', 'secondary',
        'success', 'danger', 'warning', 'info',
        'light', 'dark', 'body_bg', 'body_color',
        'link_color', 'link_hover_color', 'border_color', 'card_bg'
    ];

    colorInputs.forEach(syncColorInputs);

    // Gradient angle slider
    document.getElementById('gradientAngle').addEventListener('input', updateGradientPreview);

    // Card opacity slider
    document.getElementById('cardOpacity').addEventListener('input', function (e) {
        document.getElementById('cardOpacityValue').textContent = e.target.value + '%';
    });

    // Initialize preview
    updateGradientPreview();

    // Theme selector change
    document.getElementById('themeSelector').addEventListener('change', function (e) {
        const value = e.target.value;
        if (value === 'new') {
            resetForm();
        } else {
            loadThemeData(parseInt(value));
        }
    });

    // Save theme button
    document.getElementById('saveThemeBtn').addEventListener('click', function () {
        const themeName = document.getElementById('themeName').value;
        if (!themeName) {
            showNotification('Please enter a theme name', 'error');
            return;
        }

        const themeData = {
            name: themeName,
            description: document.getElementById('themeDescription').value,
            card_opacity: parseFloat(document.getElementById('cardOpacity').value) / 100,
            gradient: {
                angle: document.getElementById('gradientAngle').value,
                start: document.getElementById('gradientStart').value,
                end: document.getElementById('gradientEnd').value
            },
            background_image: document.getElementById('backgroundImage').value || null,
            bg_position: document.getElementById('bgPosition').value,
            bg_size: document.getElementById('bgSize').value,
            bg_repeat: document.getElementById('bgRepeat').value,
            bg_attachment: document.getElementById('bgAttachment').value
        };

        // Add all color fields
        colorInputs.forEach(id => {
            if (!id.startsWith('gradient')) {
                themeData[id] = document.getElementById(id).value;
            }
        });

        console.log('Saving theme data:', themeData);

        const url = currentThemeId ? `/api/admin/themes/${currentThemeId}` : '/api/admin/themes';
        const method = currentThemeId ? 'PUT' : 'POST';

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(themeData)
        })
            .then(response => response.json())
            .then(data => {
                console.log('Save response:', data);
                if (data.error) {
                    showNotification(data.error, 'error');
                } else {
                    showNotification(`Theme "${data.name}" saved successfully!`, 'success');
                    currentThemeId = data.id;

                    // If this is the active theme, reload the page to show changes
                    if (data.is_active) {
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        loadThemes();
                        document.getElementById('themeSelector').value = data.id;
                        document.getElementById('deleteThemeBtn').style.display = 'inline-block';
                        document.getElementById('previewThemeBtn').style.display = 'inline-block';
                        document.getElementById('applyThemeBtn').style.display = 'inline-block';
                    }
                }
            })
            .catch(error => {
                console.error('Error saving theme:', error);
                showNotification('Failed to save theme', 'error');
            });
    });

    // Delete theme button
    document.getElementById('deleteThemeBtn').addEventListener('click', function () {
        if (!currentThemeId) return;

        if (!confirm('Are you sure you want to delete this theme?')) {
            return;
        }

        fetch(`/api/admin/themes/${currentThemeId}`, {
            method: 'DELETE'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showNotification(data.error, 'error');
                } else {
                    showNotification('Theme deleted successfully', 'success');
                    loadThemes();
                    resetForm();
                    document.getElementById('themeSelector').value = 'new';
                }
            })
            .catch(error => {
                console.error('Error deleting theme:', error);
                showNotification('Failed to delete theme', 'error');
            });
    });

    // Helper function to convert hex to rgba
    function hexToRgba(hex, opacity) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }

    // Preview theme button
    document.getElementById('previewThemeBtn').addEventListener('click', function () {
        if (!currentThemeId) return;

        // Get current theme data from form
        const previewData = {
            primary: document.getElementById('primary').value,
            secondary: document.getElementById('secondary').value,
            success: document.getElementById('success').value,
            danger: document.getElementById('danger').value,
            warning: document.getElementById('warning').value,
            info: document.getElementById('info').value,
            light: document.getElementById('light').value,
            dark: document.getElementById('dark').value,
            body_bg: document.getElementById('body_bg').value,
            body_color: document.getElementById('body_color').value,
            link_color: document.getElementById('link_color').value,
            link_hover_color: document.getElementById('link_hover_color').value,
            border_color: document.getElementById('border_color').value,
            card_bg: document.getElementById('card_bg').value
        };

        // Get card opacity (convert from 0-100 to 0.0-1.0)
        const cardOpacity = parseFloat(document.getElementById('cardOpacity').value) / 100;

        // Apply preview styles
        const root = document.documentElement;
        Object.keys(previewData).forEach(key => {
            const cssVar = '--bs-' + key.replace('_', '-');
            root.style.setProperty(cssVar, previewData[key]);
        });

        // Apply gradient background
        const angle = document.getElementById('gradientAngle').value;
        const gradientStart = document.getElementById('gradientStart').value;
        const gradientEnd = document.getElementById('gradientEnd').value;
        document.body.style.background = `linear-gradient(${angle}deg, ${gradientStart}, ${gradientEnd})`;
        document.body.style.backgroundAttachment = 'fixed';

        // Apply card opacity with glass effect
        const cardBgRgba = hexToRgba(previewData.card_bg, cardOpacity);
        const cardElements = document.querySelectorAll('.card, .glass-panel, .section-card, .content-card');
        cardElements.forEach(card => {
            card.style.background = cardBgRgba;
            card.style.backdropFilter = 'blur(16px)';
            card.style.webkitBackdropFilter = 'blur(16px)';
            card.style.border = `1px solid ${hexToRgba(previewData.border_color, 0.2)}`;
        });

        isPreviewMode = true;
        showNotification('Theme preview applied (reload to reset)', 'success');
    });

    // Apply theme button (set as active)
    document.getElementById('applyThemeBtn').addEventListener('click', function () {
        if (!currentThemeId) {
            showNotification('Please select a theme first', 'error');
            return;
        }

        if (!confirm('Set this theme as the active theme for all users?')) {
            return;
        }

        fetch(`/api/admin/themes/${currentThemeId}/activate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showNotification(data.error, 'error');
                } else {
                    showNotification(`Theme "${data.name}" is now active! Reloading...`, 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                }
            })
            .catch(error => {
                console.error('Error activating theme:', error);
                showNotification('Failed to activate theme: ' + error.message, 'error');
            });
    });

    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `<i class="bi bi-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>${message}`;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Load themes on page load
    loadThemes();
});
