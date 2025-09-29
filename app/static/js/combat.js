/* Basic combat UI logic */
(function(){
  const root = document.getElementById('combat-root');
  if(!root){ return; }
  const combatId = parseInt(root.getAttribute('data-combat-id'), 10);
  const logEl = document.getElementById('combat-log');
  const monsterNameEl = document.getElementById('monster-name');
  const monsterLevelEl = document.getElementById('monster-level');
  const monsterHpBar = document.getElementById('monster-hp-bar');
  const partyContainer = document.getElementById('party-panels');

  function appendLog(lines){
    if(!Array.isArray(lines)) return;
    lines.forEach(l => {
      const div = document.createElement('div');
      div.textContent = (l.ts ? '['+l.ts.split('T')[1].split('.')[0]+'] ' : '') + l.m;
      logEl.appendChild(div);
    });
    logEl.scrollTop = logEl.scrollHeight;
  }

  function render(state){
    if(!state) return;
    const m = state.monster || {};
    monsterNameEl.textContent = m.name || 'Monster';
    monsterLevelEl.textContent = 'Lv ' + (m.level || '?');
    const maxHp = state.monster_max_hp || m.hp || 0;
    const curHp = state.monster_hp ?? maxHp;
    const pct = maxHp > 0 ? Math.max(0, Math.min(100, (curHp / maxHp) * 100)) : 0;
    monsterHpBar.style.width = pct + '%';
    monsterHpBar.textContent = curHp + ' / ' + maxHp;
    // Party panels
    partyContainer.innerHTML = '';
    const initiative = state.initiative || [];
    const activeIndex = state.active_index;
    const party = (state.party && state.party.members) || [];
    // Build quick lookup of actor id -> initiative slot index
    const active = initiative[activeIndex];
    party.forEach(mem => {
      const col = document.createElement('div');
      col.className = 'col-md-6 col-lg-4 mb-3';
      const card = document.createElement('div');
      card.className = 'card h-100 party-member' + (active && active.type==='player' && active.id === mem.char_id ? ' border-warning shadow' : '');
      const header = document.createElement('div');
      header.className = 'card-header d-flex justify-content-between align-items-center';
      header.innerHTML = '<span>'+ (mem.name || 'Hero') + '</span>' +
        '<span class="small text-muted">HP ' + mem.hp + '/' + mem.max_hp + ' | MP ' + mem.mana + '/' + mem.mana_max + '</span>';
      const body = document.createElement('div');
      body.className = 'card-body p-2';
      const btnRow = document.createElement('div');
      const canAct = active && active.type==='player' && active.id === mem.char_id && state.status==='active';
      btnRow.className = 'd-flex flex-wrap gap-2';
      const actions = [
        {k:'attack', label:'Attack', cls:'btn-outline-danger'},
        {k:'flee', label:'Flee', cls:'btn-outline-secondary'},
        {k:'end_turn', label:'End Turn', cls:'btn-outline-dark'}
      ];
      actions.forEach(a => {
        const b = document.createElement('button');
        b.type='button';
        b.className='btn btn-sm '+a.cls;
        b.textContent=a.label;
        if(!canAct) b.disabled = true;
        b.addEventListener('click', () => doAction(a.k, state.version, mem.char_id));
        btnRow.appendChild(b);
      });
      body.appendChild(btnRow);
      card.appendChild(header);
      card.appendChild(body);
      col.appendChild(card);
      partyContainer.appendChild(col);
    });
    appendLog(state.log);
  }

  async function fetchState(){
    try{
      const r = await fetch('/api/combat/'+combatId+'/state');
      const j = await r.json();
      if(j && j.ok){
        render(j.state);
      }
    }catch(e){ /* ignore */ }
  }

  async function doAction(action, version, actorId){
    let endpoint;
    let payload = {version: version, actor_id: actorId};
    if(action==='attack') endpoint = '/api/combat/'+combatId+'/attack';
    else if(action==='flee') endpoint = '/api/combat/'+combatId+'/flee';
    else if(action==='end_turn') endpoint = '/api/combat/'+combatId+'/end_turn';
    else return;
    try{
      const r = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      const j = await r.json();
      if(j.state){
        render(j.state);
      }
    }catch(e){ /* ignore */ }
  }

  // Initial fetch and poll fallback (2s) until websockets integrated
  fetchState();
  setInterval(fetchState, 2000);
})();
