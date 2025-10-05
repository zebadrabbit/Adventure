// time-widget.js
// Listens for time_update events from the server and updates any tick spans.
(function () {
    function updateAll(tick) {
        const ids = ['dashboard-time-tick', 'time-tick-value'];
        ids.forEach(id => { const el = document.getElementById(id); if (el) { el.textContent = tick; } });
    }
    // If Socket.IO isn't loaded yet, defer slightly
    function init() {
        if (typeof io === 'undefined') { setTimeout(init, 500); return; }
        try {
            // Reuse existing adventure/combat socket if available to avoid extra connections
            let socket = window.combatSocket || window.adventureSocket || window.entitySocket || null;
            if (!socket) {
                if (window._timeWidgetSocketInit) return; // avoid spawning new connection repeatedly
                window._timeWidgetSocketInit = true;
                socket = io('/adventure', { transports: ['websocket', 'polling'] });
                window.adventureSocket = socket; // unify reference
            }
            if (socket._timeWidgetBound) return; // idempotent
            socket._timeWidgetBound = true;
            socket.on('time_update', (data) => {
                if (data && typeof data.tick !== 'undefined') {
                    updateAll(data.tick);
                }
            });
            try {
                window._socketDebug = window._socketDebug || { namespaces: new Set(), engineId: null };
                if (socket && socket.io && socket.io.engine) window._socketDebug.engineId = socket.io.engine.id || socket.id;
                if (socket && socket.nsp) window._socketDebug.namespaces.add(socket.nsp);
            } catch (e) { /* ignore */ }
        } catch (e) { /* non-fatal */ }
    }
    document.addEventListener('DOMContentLoaded', init);
})();
