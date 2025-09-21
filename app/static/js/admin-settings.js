// Admin server settings modal extracted logic
// Date: 2025-09-21
(function(){
  const socket = window.io ? window.io() : null;
  const onlineList = document.getElementById('online-users');
  const form = document.getElementById('admin-broadcast-form');
  const targetSel = document.getElementById('broadcast-target');
  const msgInput = document.getElementById('broadcast-message');
  const log = document.getElementById('admin-broadcast-log');
  if (!socket || !form) return;

  function addLog(line){
    const div = document.createElement('div');
    div.textContent = line;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  document.getElementById('serverSettingsModal')?.addEventListener('shown.bs.modal', () => {
    socket.emit('admin_online_users');
  });

  socket.on('admin_online_users', (users) => {
    onlineList.innerHTML = '';
    (users || []).forEach(u => {
      const li = document.createElement('li');
      li.textContent = `${u.username} [${u.role}]`;
      onlineList.appendChild(li);
    });
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const target = targetSel.value;
    const message = msgInput.value.trim();
    if (!message) return;
    socket.emit('admin_broadcast', { target, message });
    addLog(`You → ${target}: ${message}`);
    msgInput.value = '';
  });

  socket.on('admin_broadcast', (payload) => {
    addLog(`${payload.from} → ${payload.target}: ${payload.message}`);
  });
})();
