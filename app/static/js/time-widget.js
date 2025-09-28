// time-widget.js
// Listens for time_update events from the server and updates any tick spans.
(function(){
  function updateAll(tick){
    const ids = ['dashboard-time-tick','time-tick-value'];
    ids.forEach(id=>{ const el = document.getElementById(id); if(el){ el.textContent = tick; }});
  }
  // If Socket.IO isn't loaded yet, defer slightly
  function init(){
    if(typeof io === 'undefined'){ setTimeout(init, 500); return; }
    try {
      const socket = io('/adventure', { transports: ['websocket','polling'] });
      socket.on('time_update', (data)=>{
        if(data && typeof data.tick !== 'undefined'){
          updateAll(data.tick);
        }
      });
    } catch(e){ /* non-fatal */ }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
