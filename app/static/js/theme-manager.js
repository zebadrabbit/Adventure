/**
 * Theme Manager - ClippyFront-inspired theme CRUD interface
 */

class ThemeManager {
    constructor() {
        this.themes = [];
        this.currentTheme = null;
        this.editingTheme = null;
        this.init();
    }

    async init() {
        await this.loadThemes();
        this.setupEventListeners();
        this.renderThemeList();
    }

    async loadThemes() {
        try {
            const response = await fetch('/api/admin/themes');
            const data = await response.json();
            this.themes = data.themes || [];
        } catch (error) {
            console.error('Failed to load themes:', error);
            this.showNotification('Failed to load themes', 'danger');
        }
    }

    setupEventListeners() {
        // New theme button
        document.getElementById('newThemeBtn')?.addEventListener('click', () => {
            this.showThemeModal();
        });

        // Save theme button
        document.getElementById('saveThemeBtn')?.addEventListener('click', () => {
            this.saveTheme();
        });

        // Color pickers - sync with hex inputs
        const colorInputs = document.querySelectorAll('.color-picker');
        colorInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const hexInput = document.getElementById(e.target.id + '_hex');
                if (hexInput) {
                    hexInput.value = e.target.value;
                }
            });
        });

        // Hex inputs - sync with color pickers
        const hexInputs = document.querySelectorAll('.hex-input');
        hexInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const colorPicker = document.getElementById(e.target.id.replace('_hex', ''));
                if (colorPicker && this.isValidHex(e.target.value)) {
                    colorPicker.value = e.target.value;
                }
            });
        });
    }

    isValidHex(hex) {
        return /^#[0-9A-F]{6}$/i.test(hex);
    }

    renderThemeList() {
        const container = document.getElementById('themesList');
        if (!container) return;

        if (this.themes.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No themes created yet</p>
                    <button class="btn btn-primary" onclick="themeManager.showThemeModal()">
                        <i class="bi bi-plus-circle me-2"></i>Create First Theme
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = this.themes.map(theme => `
            <div class="theme-card ${theme.is_active ? 'active' : ''}" data-theme-id="${theme.id}">
                <div class="theme-header">
                    <div class="theme-info">
                        <h3 class="theme-name">${this.escapeHtml(theme.name)}</h3>
                        ${theme.description ? `<p class="theme-description">${this.escapeHtml(theme.description)}</p>` : ''}
                        ${theme.is_active ? '<span class="badge bg-success">Active</span>' : ''}
                    </div>
                    <div class="theme-actions">
                        ${!theme.is_active ? `
                            <button class="btn btn-sm btn-outline-success" onclick="themeManager.activateTheme(${theme.id})">
                                <i class="bi bi-check-circle me-1"></i>Activate
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-outline-primary" onclick="themeManager.editTheme(${theme.id})">
                            <i class="bi bi-pencil me-1"></i>Edit
                        </button>
                        ${!theme.is_active ? `
                            <button class="btn btn-sm btn-outline-danger" onclick="themeManager.deleteTheme(${theme.id})">
                                <i class="bi bi-trash me-1"></i>Delete
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="theme-colors">
                    <div class="color-swatch" style="background: ${theme.primary}" title="Primary"></div>
                    <div class="color-swatch" style="background: ${theme.secondary}" title="Secondary"></div>
                    <div class="color-swatch" style="background: ${theme.success}" title="Success"></div>
                    <div class="color-swatch" style="background: ${theme.danger}" title="Danger"></div>
                    <div class="color-swatch" style="background: ${theme.warning}" title="Warning"></div>
                    <div class="color-swatch" style="background: ${theme.info}" title="Info"></div>
                </div>
            </div>
        `).join('');
    }

    showThemeModal(theme = null) {
        this.editingTheme = theme;
        const modal = new bootstrap.Modal(document.getElementById('themeModal'));

        // Set form values
        document.getElementById('themeName').value = theme?.name || '';
        document.getElementById('themeDescription').value = theme?.description || '';

        // Set color values
        const colorFields = [
            'primary', 'secondary', 'success', 'danger', 'warning', 'info',
            'light', 'dark', 'body_bg', 'body_color', 'link_color',
            'link_hover_color', 'border_color', 'card_bg'
        ];

        colorFields.forEach(field => {
            const colorPicker = document.getElementById(field);
            const hexInput = document.getElementById(field + '_hex');
            const value = theme?.[field] || this.getDefaultColor(field);

            if (colorPicker) colorPicker.value = value;
            if (hexInput) hexInput.value = value;
        });

        modal.show();
    }

    getDefaultColor(field) {
        const defaults = {
            primary: '#6366f1',
            secondary: '#8b5cf6',
            success: '#22c55e',
            danger: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6',
            light: '#f8f9fa',
            dark: '#212529',
            body_bg: '#0f172a',
            body_color: '#f1f5f9',
            link_color: '#6366f1',
            link_hover_color: '#8b5cf6',
            border_color: '#334155',
            card_bg: '#1e293b'
        };
        return defaults[field] || '#000000';
    }

    async saveTheme() {
        const name = document.getElementById('themeName').value.trim();
        if (!name) {
            this.showNotification('Theme name is required', 'danger');
            return;
        }

        const themeData = {
            name,
            description: document.getElementById('themeDescription').value.trim(),
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

        try {
            const url = this.editingTheme
                ? `/api/admin/themes/${this.editingTheme.id}`
                : '/api/admin/themes';
            const method = this.editingTheme ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(themeData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save theme');
            }

            this.showNotification(
                this.editingTheme ? 'Theme updated successfully' : 'Theme created successfully',
                'success'
            );

            bootstrap.Modal.getInstance(document.getElementById('themeModal')).hide();
            await this.loadThemes();
            this.renderThemeList();
        } catch (error) {
            console.error('Failed to save theme:', error);
            this.showNotification(error.message, 'danger');
        }
    }

    async editTheme(themeId) {
        const theme = this.themes.find(t => t.id === themeId);
        if (theme) {
            this.showThemeModal(theme);
        }
    }

    async deleteTheme(themeId) {
        if (!confirm('Are you sure you want to delete this theme?')) {
            return;
        }

        try {
            const response = await fetch(`/api/admin/themes/${themeId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete theme');
            }

            this.showNotification('Theme deleted successfully', 'success');
            await this.loadThemes();
            this.renderThemeList();
        } catch (error) {
            console.error('Failed to delete theme:', error);
            this.showNotification(error.message, 'danger');
        }
    }

    async activateTheme(themeId) {
        try {
            const response = await fetch(`/api/admin/themes/${themeId}/activate`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to activate theme');
            }

            this.showNotification('Theme activated successfully', 'success');
            await this.loadThemes();
            this.renderThemeList();

            // Reload page to apply new theme
            setTimeout(() => window.location.reload(), 1000);
        } catch (error) {
            console.error('Failed to activate theme:', error);
            this.showNotification('Failed to activate theme', 'danger');
        }
    }

    showNotification(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show notification-toast`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        const container = document.getElementById('notificationContainer') || document.body;
        container.appendChild(alertDiv);

        setTimeout(() => alertDiv.remove(), 5000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize theme manager
let themeManager;
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('themesList')) {
        themeManager = new ThemeManager();
    }
});
