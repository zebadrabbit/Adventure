/**
 * Global Fog Configuration
 * Manages fog-of-war settings across all pages
 */
(function () {
    'use strict';

    const FOG_CFG_KEY = 'adventureFogConfig';

    // Default fog parameters
    const DEFAULT_FOG_CONFIG = {
        innerRadius: 8,       // fully visible radius (Euclidean)
        fullRadius: 26,       // where fog reaches max opacity
        minOpacity: 0.18,     // minimum fog opacity just outside inner radius
        maxOpacity: 0.92,     // maximum fog opacity at/after full radius
        noise: 0.08,          // max +/- added to opacity per tile for irregularity
        memoryOpacity: 0.35   // opacity for previously seen but currently out-of-range tiles
    };

    // Active fog config (mutable)
    let activeFogConfig = { ...DEFAULT_FOG_CONFIG };

    // Load config from localStorage
    function loadFogConfig() {
        try {
            const raw = localStorage.getItem(FOG_CFG_KEY);
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    // Save config to localStorage
    function saveFogConfig(cfg) {
        try {
            localStorage.setItem(FOG_CFG_KEY, JSON.stringify(cfg));
        } catch (e) {
            console.error('Failed to save fog config:', e);
        }
    }

    // Get current fog config
    function currentFogConfig() {
        return { ...activeFogConfig };
    }

    // Apply new fog config
    function applyFogConfig(cfg) {
        activeFogConfig = {
            innerRadius: cfg.innerRadius ?? activeFogConfig.innerRadius,
            fullRadius: cfg.fullRadius ?? activeFogConfig.fullRadius,
            minOpacity: cfg.minOpacity ?? activeFogConfig.minOpacity,
            maxOpacity: cfg.maxOpacity ?? activeFogConfig.maxOpacity,
            noise: cfg.noise ?? activeFogConfig.noise,
            memoryOpacity: cfg.memoryOpacity ?? activeFogConfig.memoryOpacity
        };
        saveFogConfig(activeFogConfig);

        // Update canvas fog settings if available
        if (window.updateCanvasFogConfig) {
            window.updateCanvasFogConfig(activeFogConfig);
        }

        return activeFogConfig;
    }

    // Reset to defaults
    function resetFogConfig() {
        return applyFogConfig(DEFAULT_FOG_CONFIG);
    }

    // Fetch fog config from server
    async function fetchServerConfig() {
        try {
            const response = await fetch('/admin/v2/api/fog-config');
            if (!response.ok) return null;
            const data = await response.json();
            if (data.success && data.config) {
                return data.config;
            }
        } catch (e) {
            console.warn('Failed to fetch server fog config:', e);
        }
        return null;
    }

    // Load config on init - prioritize server config over localStorage
    (async function initFogConfig() {
        const serverConfig = await fetchServerConfig();
        if (serverConfig) {
            applyFogConfig(serverConfig);
        } else {
            const persistedConfig = loadFogConfig();
            if (persistedConfig) {
                applyFogConfig(persistedConfig);
            }
        }
    })();

    // Expose global API
    window.globalFogConfig = {
        get: currentFogConfig,
        set: applyFogConfig,
        reset: resetFogConfig,
        getDefaults: () => ({ ...DEFAULT_FOG_CONFIG })
    };

    // Legacy compatibility - expose on dungeonDev namespace
    if (!window.dungeonDev) window.dungeonDev = {};
    window.dungeonDev.getFogConfig = currentFogConfig;
    window.dungeonDev.setFogConfig = applyFogConfig;
    window.dungeonDev.resetFogConfig = resetFogConfig;
})();
