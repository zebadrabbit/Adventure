(function () {
    // Config API prefetch (used by equipment/character panels)
    let config = {};
    async function fetchConfig() {
        const [namePools, starterItems, baseStats, classMap] = await Promise.all([
            fetch('/api/config/name_pools').then(r => r.json()),
            fetch('/api/config/starter_items').then(r => r.json()),
            fetch('/api/config/base_stats').then(r => r.json()),
            fetch('/api/config/class_map').then(r => r.json()),
        ]);
        config.namePools = namePools;
        config.starterItems = starterItems;
        config.baseStats = baseStats;
        config.classMap = classMap;
    }
    fetchConfig();

    // Apply server-rendered XP bar fill percentages
    document.querySelectorAll('.xp-fill[data-xp-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.xpPct + '%';
    });

    // Apply server-rendered HP/MP bar fill percentages
    document.querySelectorAll('.bar-fill[data-bar-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.barPct + '%';
    });
})();
