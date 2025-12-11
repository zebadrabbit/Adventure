// Admin fog modal logic extracted to external file (no inline scripts)
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    // Check if we're in a modal or tab context
    const modalEl = document.getElementById('fogAdminModal');
    const tabEl = document.getElementById('tab-fog');
    const fogTabButton = document.querySelector('[data-bs-target="#tab-fog"]');

    if (!modalEl && !tabEl) return;

    function loadFogInputs() {
      // Load current fog config into input fields
      if (!window.dungeonDev || !window.dungeonDev.getFogConfig) return;
      const cfg = window.dungeonDev.getFogConfig();

      const inputs = {
        'fog-inner-radius': cfg.innerRadius,
        'fog-full-radius': cfg.fullRadius,
        'fog-min-opacity': cfg.minOpacity,
        'fog-max-opacity': cfg.maxOpacity,
        'fog-noise': cfg.noise,
        'fog-memory-opacity': cfg.memoryOpacity
      };

      for (const [id, value] of Object.entries(inputs)) {
        const el = document.getElementById(id);
        if (el) el.value = value;
      }
    }

    function refreshConfig() {
      const cfgEl = document.getElementById('fog-admin-config');
      if (cfgEl && window.dungeonDev && window.dungeonDev.getFogConfig) {
        cfgEl.textContent = JSON.stringify(window.dungeonDev.getFogConfig(), null, 2);
      } else if (cfgEl) {
        cfgEl.textContent = 'Fog config not available (navigate to /adventure first)';
      }

      loadFogInputs();
    }

    // Handle both modal and tab contexts
    if (modalEl) {
      modalEl.addEventListener('shown.bs.modal', refreshConfig);
    }
    if (fogTabButton) {
      fogTabButton.addEventListener('shown.bs.tab', refreshConfig);
    }

    // Also try to load on initial page load if tab is already active
    setTimeout(() => {
      if (tabEl && tabEl.classList.contains('active')) {
        refreshConfig();
      }
    }, 500);

    // Toast notification helper
    function showToast(message, type = 'success') {
      const toast = document.createElement('div');
      toast.className = `toast align-items-center text-bg-${type} border-0`;
      toast.setAttribute('role', 'alert');
      toast.setAttribute('aria-live', 'assertive');
      toast.setAttribute('aria-atomic', 'true');

      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">
            ${message}
          </div>
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

    // Apply fog config button
    const applyBtn = document.getElementById('fog-apply-config');
    if (applyBtn) applyBtn.addEventListener('click', () => {
      try {
        const config = {
          innerRadius: parseFloat(document.getElementById('fog-inner-radius').value),
          fullRadius: parseFloat(document.getElementById('fog-full-radius').value),
          minOpacity: parseFloat(document.getElementById('fog-min-opacity').value),
          maxOpacity: parseFloat(document.getElementById('fog-max-opacity').value),
          noise: parseFloat(document.getElementById('fog-noise').value),
          memoryOpacity: parseFloat(document.getElementById('fog-memory-opacity').value)
        };

        if (window.dungeonDev && window.dungeonDev.setFogConfig) {
          window.dungeonDev.setFogConfig(config);
          console.log('[Fog Admin] Applied new fog configuration:', config);
          showToast('Fog settings applied successfully', 'success');
          setTimeout(refreshConfig, 100);
        } else {
          showToast('Fog config not available (visit /adventure first)', 'warning');
        }
      } catch (e) {
        console.error('[Fog Admin] Failed to apply config:', e);
        showToast('Failed to apply fog settings', 'danger');
      }
    });

    // Reset fog config button
    const resetBtn = document.getElementById('fog-reset-config');
    if (resetBtn) resetBtn.addEventListener('click', () => {
      try {
        if (window.dungeonDev && window.dungeonDev.resetFogConfig) {
          window.dungeonDev.resetFogConfig();
          console.log('[Fog Admin] Reset fog configuration to defaults');
          showToast('Fog settings reset to defaults', 'info');
          setTimeout(() => {
            loadFogInputs();
            refreshConfig();
          }, 100);
        } else {
          showToast('Fog config not available (visit /adventure first)', 'warning');
        }
      } catch (e) {
        console.error('[Fog Admin] Failed to reset config:', e);
        showToast('Failed to reset fog settings', 'danger');
      }
    });
  });
})();
