// Admin server settings modal extracted logic
// Date: 2025-09-21
(function () {
  // Reuse a shared root socket if already created; otherwise create once.
  if (!window._rootSocket) {
    if (window._rootSocketInit) {
      // Another script attempted initialization but socket missing (maybe race); retry shortly
      setTimeout(() => { if (!window._rootSocket && window.io) { window._rootSocket = window.io('/', { transports: ['websocket', 'polling'] }); } }, 400);
    } else if (window.io) {
      window._rootSocketInit = true;
      window._rootSocket = window.io('/', { transports: ['websocket', 'polling'] });
    }
  }
  const socket = window._rootSocket;
  const onlineList = document.getElementById('online-users');
  const form = document.getElementById('admin-broadcast-form');
  const targetSel = document.getElementById('broadcast-target');
  const msgInput = document.getElementById('broadcast-message');
  const log = document.getElementById('admin-broadcast-log');
  const refreshBtn = document.getElementById('admin-refresh-status');
  let autoInterval = null;
  let autoEnabled = false;
  const statsRoot = document.getElementById('admin-system-stats');
  const gamesList = document.getElementById('admin-active-games');
  const intervalSel = document.getElementById('admin-refresh-interval');
  // Moderation panel elements
  const modPanel = document.getElementById('moderation-panel');
  const modUserList = document.getElementById('mod-user-list');
  const modSearch = document.getElementById('mod-search');
  const modFilterButtons = modPanel ? modPanel.querySelectorAll('[data-mod-filter]') : [];
  let modFilter = 'all';
  let modSnapshot = []; // cached augmented list
  if (!socket || !form) return;

  function addLog(line) {
    const div = document.createElement('div');
    div.textContent = line;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function renderUsers(users) {
    if (!onlineList) return;
    onlineList.innerHTML = '';
    const template = document.getElementById('user-list-item-template');
    (users || []).forEach(u => {
      const li = template ? template.content.cloneNode(true).querySelector('li') : document.createElement('li');
      if (!template) { li.className = 'd-flex justify-content-between align-items-center mb-1'; }
      li.setAttribute('data-user-id', u.username);

      const left = li.querySelector('[data-field="username"]') || li.querySelector('.user-name') || document.createElement('span');
      let badges = `<span class="badge bg-${u.role === 'admin' ? 'danger' : (u.role === 'mod' ? 'warning text-dark' : 'secondary')} me-1">${u.role}</span>`;
      if (window.ADMIN_MODERATION && window.ADMIN_MODERATION.muted?.includes(u.username)) {
        badges += '<span class="badge bg-secondary me-1">muted</span>';
      }
      if (window.ADMIN_MODERATION && window.ADMIN_MODERATION.banned?.includes(u.username)) {
        badges += '<span class="badge bg-dark me-1">banned</span>';
      }
      left.innerHTML = `${badges}${u.username}`;

      if (u.role !== 'admin') { // avoid self-kick or admin->admin by default
        const isBanned = window.ADMIN_MODERATION?.banned?.includes(u.username);
        const isMuted = window.ADMIN_MODERATION?.muted?.includes(u.username);

        const msgBtn = li.querySelector('[data-action="message"]');
        if (msgBtn) {
          msgBtn.addEventListener('click', () => {
            const m = prompt(`Message to ${u.username}`);
            if (m && m.trim()) {
              socket.emit('admin_direct_message', { to: u.username, message: m.trim() });
            }
          });
        }

        const kickBtn = li.querySelector('[data-action="kick"]');
        if (kickBtn) {
          kickBtn.addEventListener('click', () => {
            if (confirm(`Disconnect ${u.username}?`)) {
              socket.emit('admin_kick_user', { user: u.username });
            }
          });
        }

        const banBtn = li.querySelector('[data-action="ban"]');
        if (banBtn) {
          banBtn.className = 'btn btn-sm ' + (isBanned ? 'btn-dark' : 'btn-outline-dark') + ' me-1';
          banBtn.innerHTML = isBanned ? '<i class="bi bi-check-circle"></i>' : '<i class="bi bi-slash-circle"></i>';
          banBtn.title = isBanned ? 'Unban' : 'Ban';
          banBtn.addEventListener('click', () => {
            if (isBanned) {
              socket.emit('admin_unban_user', { user: u.username });
            } else if (confirm(`Ban ${u.username}? They will be disconnected and blocked.`)) {
              socket.emit('admin_ban_user', { user: u.username });
            }
          });
        }

        const muteBtn = li.querySelector('[data-action="mute"]');
        if (muteBtn) {
          muteBtn.className = 'btn btn-sm ' + (isMuted ? 'btn-secondary' : 'btn-outline-secondary');
          muteBtn.innerHTML = isMuted ? '<i class="bi bi-mic"></i>' : '<i class="bi bi-mic-mute"></i>';
          muteBtn.title = isMuted ? 'Unmute' : 'Mute';
          muteBtn.addEventListener('click', () => {
            if (isMuted) {
              socket.emit('admin_unmute_user', { user: u.username });
            } else {
              socket.emit('admin_mute_user', { user: u.username });
            }
          });
        }
      } else {
        // Remove action buttons for admins
        const btnGroup = li.querySelector('.btn-group');
        if (btnGroup) btnGroup.remove();
      }
      onlineList.appendChild(li);
    });
  }

  function buildModSnapshot(users) {
    modSnapshot = (users || []).map(u => {
      const isBanned = window.ADMIN_MODERATION?.banned?.includes(u.username) || false;
      const isMuted = window.ADMIN_MODERATION?.muted?.includes(u.username) || false;
      return Object.assign({}, u, { isBanned, isMuted });
    });
  }

  function renderModerationList() {
    if (!modUserList) return;
    modUserList.innerHTML = '';
    let list = modSnapshot.slice();
    if (modFilter === 'banned') list = list.filter(u => u.isBanned);
    if (modFilter === 'muted') list = list.filter(u => u.isMuted);
    const term = (modSearch?.value || '').trim().toLowerCase();
    if (term) list = list.filter(u => u.username.toLowerCase().includes(term));
    if (!list.length) {
      const li = document.createElement('li');
      li.className = 'text-muted';
      li.textContent = 'No users match';
      modUserList.appendChild(li); return;
    }
    list.sort((a, b) => a.username.localeCompare(b.username));
    const userTemplate = document.getElementById('user-list-item-template');
    const bannedTemplate = document.getElementById('banned-user-item-template');
    const mutedTemplate = document.getElementById('muted-user-item-template');

    list.forEach(u => {
      let template = userTemplate;
      if (u.isBanned && bannedTemplate) template = bannedTemplate;
      else if (u.isMuted && mutedTemplate) template = mutedTemplate;

      const li = template ? template.content.cloneNode(true).querySelector('li') : document.createElement('li');
      if (!template) { li.className = 'd-flex justify-content-between align-items-center mb-1'; }
      li.setAttribute('data-user-id', u.username);

      const left = li.querySelector('[data-field="username"]') || li.querySelector('.user-name') || document.createElement('span');
      let badges = '';
      if (u.isBanned) badges += '<span class="badge bg-dark me-1">banned</span>';
      if (u.isMuted) badges += '<span class="badge bg-secondary me-1">muted</span>';
      badges += `<span class="badge bg-${u.role === 'admin' ? 'danger' : (u.role === 'mod' ? 'warning text-dark' : 'info')} me-1">${u.role}</span>`;
      left.innerHTML = `${badges}${u.username}`;

      if (u.role !== 'admin') {
        const banBtn = li.querySelector('[data-action="ban"]') || li.querySelector('[data-action="unban"]');
        if (banBtn) {
          banBtn.className = 'btn btn-sm ' + (u.isBanned ? 'btn-dark' : 'btn-outline-dark') + ' me-1';
          banBtn.innerHTML = u.isBanned ? '<i class="bi bi-check-circle"></i>' : '<i class="bi bi-slash-circle"></i>';
          banBtn.title = u.isBanned ? 'Unban' : 'Ban';
          banBtn.setAttribute('data-action', u.isBanned ? 'unban' : 'ban');
          banBtn.addEventListener('click', () => {
            socket.emit(u.isBanned ? 'admin_unban_user' : 'admin_ban_user', { user: u.username });
          });
        }

        const muteBtn = li.querySelector('[data-action="mute"]') || li.querySelector('[data-action="unmute"]');
        if (muteBtn) {
          muteBtn.className = 'btn btn-sm ' + (u.isMuted ? 'btn-secondary' : 'btn-outline-secondary');
          muteBtn.innerHTML = u.isMuted ? '<i class="bi bi-mic"></i>' : '<i class="bi bi-mic-mute"></i>';
          muteBtn.title = u.isMuted ? 'Unmute' : 'Mute';
          muteBtn.setAttribute('data-action', u.isMuted ? 'unmute' : 'mute');
          muteBtn.addEventListener('click', () => {
            socket.emit(u.isMuted ? 'admin_unmute_user' : 'admin_mute_user', { user: u.username });
          });
        }
      } else {
        // Remove action buttons for admins
        const btnGroup = li.querySelector('.btn-group');
        if (btnGroup) btnGroup.remove();
      }
      modUserList.appendChild(li);
    });
  }

  function refreshModeration(users) {
    buildModSnapshot(users);
    renderModerationList();
  }

  modFilterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      modFilterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      modFilter = btn.getAttribute('data-mod-filter');
      renderModerationList();
    });
  });
  modSearch?.addEventListener('input', () => { renderModerationList(); });

  function renderStats(counts, server) {
    if (!statsRoot) return;
    const map = {};
    statsRoot.querySelectorAll('[data-stat]').forEach(span => {
      map[span.getAttribute('data-stat')] = span;
    });
    const merged = Object.assign({}, counts || {}, server || {});
    Object.entries(merged).forEach(([k, v]) => {
      if (map[k]) map[k].textContent = v;
    });
  }

  function renderGames(games) {
    if (!gamesList) return;
    gamesList.innerHTML = '';
    (games || []).forEach(g => {
      const li = document.createElement('li');
      const created = g.created ? new Date(g.created * 1000).toLocaleTimeString() : '';
      li.textContent = `${g.room} (${g.member_count}) ${created}`;
      gamesList.appendChild(li);
    });
    if (!games || games.length === 0) {
      const li = document.createElement('li');
      li.className = 'text-muted';
      li.textContent = 'No active games';
      gamesList.appendChild(li);
    }
  }

  function requestStatus() {
    socket.emit('admin_status');
    // fallback legacy for older servers
    socket.emit('admin_online_users');
  }

  document.getElementById('serverSettingsModal')?.addEventListener('shown.bs.modal', () => {
    requestStatus();
  });
  function toggleAuto() {
    autoEnabled = !autoEnabled;
    if (autoEnabled) {
      refreshBtn.classList.add('btn-primary');
      refreshBtn.classList.remove('btn-outline-secondary');
      refreshBtn.innerHTML = '<i class="bi bi-pause-circle"></i>';
      const period = parseInt(intervalSel?.value || '20000', 10);
      autoInterval = setInterval(requestStatus, period);
    } else {
      refreshBtn.classList.remove('btn-primary');
      refreshBtn.classList.add('btn-outline-secondary');
      refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
      if (autoInterval) { clearInterval(autoInterval); autoInterval = null; }
    }
  }
  refreshBtn?.addEventListener('click', (e) => { e.preventDefault(); if (e.shiftKey) { toggleAuto(); } else { requestStatus(); } });

  // Legacy events: keep for backward compatibility
  socket.on('admin_online_users', (users) => {
    renderUsers(users);
  });
  socket.on('admin_online_users_response', (users) => {
    renderUsers(users);
  });

  // New comprehensive status event
  socket.on('admin_status', (payload) => {
    if (payload.moderation) {
      window.ADMIN_MODERATION = {
        banned: payload.moderation.banned_usernames || [],
        muted: payload.moderation.muted_usernames || []
      };
    }
    renderUsers(payload.users);
    renderStats(payload.counts, payload.server);
    renderGames(payload.active_games);
    if (payload.moderation) {
      addLog(`Moderation: banned=${payload.server?.banned || 0} muted=${payload.server?.muted || 0}`);
      refreshModeration(payload.users);
    }
  });

  socket.on('admin_direct_message', (payload) => {
    addLog(`DM ${payload.from}→${payload.to}: ${payload.message}`);
  });

  socket.on('admin_notice', (payload) => {
    addLog(`NOTICE: ${payload.message}`);
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
