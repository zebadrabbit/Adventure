// tooltips.js - shared tooltip builder for items (adventure + equipment)
(function(){
  if (window.MUDTooltips) return; // idempotent
  const STORAGE_KEY = 'mudTooltipMode'; // 'rich' | 'plain' | 'off'
  function esc(s){ return (s||'').toString().replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c])); }
  const rarityOrder = ['common','uncommon','rare','epic','legendary','mythic'];
  function rarityClass(r){
    const idx = rarityOrder.indexOf((r||'').toLowerCase());
    return idx === -1 ? 'rarity-common' : 'rarity-' + rarityOrder[idx];
  }
  function getMode(){
    try { return localStorage.getItem(STORAGE_KEY) || 'rich'; } catch(e){ return 'rich'; }
  }
  function setMode(m){
    try { localStorage.setItem(STORAGE_KEY, m); } catch(e){}
    // Persist server-side (best effort)
    fetch('/api/prefs/tooltip_mode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: m }) }).catch(()=>{});
    document.dispatchEvent(new CustomEvent('mud-tooltips-mode-change',{ detail:{ mode:m }}));
    // Reinitialize after mode change
    apply(document, true);
    updateToggleLabel();
  }
  function cycleMode(){
    const cur = getMode();
    const next = cur === 'rich' ? 'plain' : (cur === 'plain' ? 'off' : 'rich');
    setMode(next);
  }
  function itemPlainText(it){
    const rarity = (it.rarity || 'common').toLowerCase();
    const level = it.level != null ? it.level : 0;
    const weight = it.weight != null ? it.weight : 1;
    const value = it.value_copper != null ? it.value_copper : 0;
    const type = it.type || 'item';
    const desc = (it.description||'').trim();
    return `${it.name} | ${type} | L${level} | ${rarity} | ${weight} wt | ${value}c${desc? ' | '+desc : ''}`;
  }
  function itemHtml(it){
    if (getMode() === 'plain') {
      return `<div class='mud-item-tip rarity-common'>${esc(itemPlainText(it))}</div>`;
    }
    const name = esc(it.name || 'Unknown');
    const rarity = (it.rarity || 'common').toLowerCase();
    const level = it.level != null ? it.level : 0;
    const weight = it.weight != null ? it.weight : 1;
    const value = it.value_copper != null ? it.value_copper : 0;
    const type = esc(it.type || 'item');
    let desc = esc((it.description||'').trim());
    if (desc.length > 260) desc = desc.slice(0,257) + '…';
    const effectsLine = effectsText(it);
    return `<div class='mud-item-tip ${rarityClass(rarity)}'>`+
      `<div class='mud-item-name ${rarityClass(rarity)} fw-semibold'>${name}</div>`+
      `<div class='mud-item-meta small text-muted'>${type} • L${level} • ${rarity} • ${weight} wt • ${value}c</div>`+
      (effectsLine?`<div class='mud-item-effects small text-info mt-1'>${esc(effectsLine)}</div>`:'')+
      (desc?`<div class='mud-item-desc small mt-1'>${desc}</div>`:'')+
      `</div>`;
  }
  function attrForItem(it){
    if (getMode() === 'off') return '';
    const html = itemHtml(it);
    // Store original HTML in a custom attribute (base64) to avoid quoting/escaping issues inside data attributes.
    const b64 = btoa(unescape(encodeURIComponent(html)));
    return `data-mud-tooltip="1" data-mud-tip="${b64}"`;
  }
  // Live region for screen reader announcement
  let liveRegion = null;
  function ensureLiveRegion(){
    if (liveRegion) return liveRegion;
    liveRegion = document.createElement('div');
    liveRegion.id = 'mud-tooltips-live';
    liveRegion.setAttribute('aria-live','polite');
    liveRegion.setAttribute('aria-atomic','true');
    liveRegion.className = 'visually-hidden';
    document.body.appendChild(liveRegion);
    return liveRegion;
  }
  let announceTimer = null;
  function announce(html){
    if (getMode()==='off') return; // don't announce when disabled
    if (announceTimer) clearTimeout(announceTimer);
    announceTimer = setTimeout(()=>{
      const lr = ensureLiveRegion();
      const txt = html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
      lr.textContent = txt;
    }, 150);
  }
  function apply(container, forceReinit){
    if (getMode() === 'off') {
      if (window.bootstrap && bootstrap.Tooltip) {
        document.querySelectorAll('[data-mud-tooltip],[data-bs-toggle="tooltip"]').forEach(el=>{
          if (el.__mudTooltip) { try { el.__mudTooltip.dispose(); } catch(e){}; delete el.__mudTooltip; }
        });
      }
      return;
    }
    // If Bootstrap loaded but Popper missing, its tooltip won't render content -> use fallback.
    if (window.bootstrap && bootstrap.Tooltip && window.Popper) {
      // proceed
    } else {
      // Ensure fallback engages even if some partial bootstrap artifact present (like CSS arrow w/o JS)
      enablePureJsFallback();
      return;
    }
    container = container || document;
    container.querySelectorAll('[data-mud-tooltip],[data-bs-toggle="tooltip"]').forEach(el=>{
      let existing = null;
      try { existing = bootstrap.Tooltip.getInstance(el); } catch(e) { existing = null; }
      // Hard short-circuit: if already has a tooltip and not forcing reinit, skip entirely.
      if (!forceReinit && existing) {
        el.__mudTooltip = existing;
        if (!el.__mudAriaBound) {
          // Minimal ensure ARIA listeners (tipHtml resolved below if needed later)
          el.__mudAriaBound = true;
          el.addEventListener('focus', ()=>{ try { el.__mudTooltip && el.__mudTooltip.show(); } catch(e){} });
          el.addEventListener('blur', ()=>{ try { el.__mudTooltip && el.__mudTooltip.hide(); } catch(e){} });
          el.addEventListener('mouseenter', ()=>{ /* announcement handled on full init */ });
        }
        return; // prevents multi-instance path
      }
      if (forceReinit && existing) {
        try { existing.dispose(); } catch(e){}
        existing = null;
        el.__mudTooltip = null;
      }
      let tipHtml = null;
      try {
        const raw = el.getAttribute('data-mud-tip');
        if (raw) tipHtml = decodeURIComponent(escape(atob(raw)));
      } catch(e) { tipHtml = null; }
      const opts = {
        html: true,
        trigger: 'hover focus',
        title: tipHtml || el.getAttribute('data-bs-title'),
        sanitize: false,
        customClass: 'mud-item-tooltip',
        container: 'body',
        boundary: 'viewport',
        placement: el.getAttribute('data-placement') || 'auto'
      };
      if (!existing) {
        try {
          // Bootstrap 5.3+: getOrCreateInstance avoids multi-instance error
          if (bootstrap.Tooltip.getOrCreateInstance) {
            existing = bootstrap.Tooltip.getOrCreateInstance(el, opts);
          } else {
            existing = new bootstrap.Tooltip(el, opts);
          }
          el.setAttribute('data-mud-tooltip-init','1');
        } catch(e) {
          // Suppress "doesn't allow more than one instance" noise: reuse existing if retrievable
          if (/more than one instance/i.test(e.message || '')) {
            try { existing = bootstrap.Tooltip.getInstance(el); } catch(_) {}
          }
        }
      } else {
        el.setAttribute('data-mud-tooltip-reused','1');
      }
      // Update content when we have an instance and decoded HTML
      if (tipHtml && existing && typeof existing.setContent === 'function') {
        try { existing.setContent({ '.tooltip-inner': tipHtml }); } catch(e){}
      }
      if (existing) el.__mudTooltip = existing;
      if (!el.__mudAriaBound) {
        el.__mudAriaBound = true;
        el.addEventListener('focus', ()=>{ try { el.__mudTooltip && el.__mudTooltip.show(); announce(tipHtml || el.getAttribute('data-bs-title')||''); } catch(e){} });
        el.addEventListener('blur', ()=>{ try { el.__mudTooltip && el.__mudTooltip.hide(); } catch(e){} });
        el.addEventListener('mouseenter', ()=>{ announce(tipHtml || el.getAttribute('data-bs-title')||''); });
      }
    });
  }
  // Toggle UI
  let toggleBtn = null;
  function updateToggleLabel(){
    if (!toggleBtn) return; const m = getMode();
    toggleBtn.textContent = `Tooltips: ${m}`;
    toggleBtn.setAttribute('aria-label', `Tooltip mode ${m}`);
  }
  function ensureToggle(){
    if (toggleBtn) return toggleBtn;
    toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'mud-tooltips-toggle btn btn-sm btn-secondary';
    toggleBtn.style.position = 'fixed';
    toggleBtn.style.right = '0.5rem';
    toggleBtn.style.bottom = '0.5rem';
    toggleBtn.style.zIndex = 1055;
    toggleBtn.addEventListener('click', cycleMode);
    document.addEventListener('keydown', (e)=>{
      if (e.altKey && e.shiftKey && e.key.toLowerCase()==='t') { e.preventDefault(); cycleMode(); }
    });
    document.body.appendChild(toggleBtn);
    updateToggleLabel();
    return toggleBtn;
  }
  // Public API
  window.MUDTooltips = { attrForItem, apply, itemHtml, getMode, setMode, cycleMode };
  // Initial setup after DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ()=>{ ensureToggle(); bootstrapServerMode(); delayedBootstrapApply(); });
  } else {
    ensureToggle(); bootstrapServerMode(); delayedBootstrapApply();
  }
  // Fetch server-side persisted mode (if logged in) and override local value once at startup
  function bootstrapServerMode(){
    fetch('/api/prefs/tooltip_mode', { headers: { 'Accept': 'application/json' }})
      .then(r => { if(!r.ok) throw new Error('skip'); return r.json(); })
      .then(data => { if (data && data.value) { try { localStorage.setItem(STORAGE_KEY, data.value); } catch(e){} updateToggleLabel(); apply(document, true); } })
      .catch(()=>{});
  }

  // Attempt re-applying until Bootstrap is actually loaded; fall back to a custom tooltip implementation
  let _bootstrapApplyAttempts = 0;
  function delayedBootstrapApply(){
    if (getMode()==='off') return; // nothing to do when disabled
    if (window.bootstrap && bootstrap.Tooltip && window.Popper) {
      apply(document, true);
      return;
    }
    _bootstrapApplyAttempts++;
    if (_bootstrapApplyAttempts < 40) { // ~10s @ 250ms
      setTimeout(delayedBootstrapApply, 250);
    } else {
      // Fallback: minimal custom tooltip for accessibility & info
      enablePureJsFallback();
    }
  }

  // Pure JS fallback (only if Bootstrap never loaded)
  let _fallbackBound = false;
  function enablePureJsFallback(){
    if (_fallbackBound) return; _fallbackBound = true;
    const tooltipEl = document.createElement('div');
    tooltipEl.className = 'mud-fallback-tooltip';
    tooltipEl.style.position = 'fixed';
    tooltipEl.style.zIndex = 2050;
    tooltipEl.style.pointerEvents = 'none';
    tooltipEl.style.background = 'rgba(20,20,25,0.95)';
    tooltipEl.style.color = '#eee';
    tooltipEl.style.fontSize = '0.75rem';
    tooltipEl.style.padding = '6px 8px';
    tooltipEl.style.borderRadius = '4px';
    tooltipEl.style.boxShadow = '0 2px 6px rgba(0,0,0,0.4)';
    tooltipEl.style.maxWidth = '260px';
    tooltipEl.style.display = 'none';
    document.body.appendChild(tooltipEl);
    function showFallback(el){
      if (getMode()==='off') return;
      const html = el.getAttribute('data-bs-title');
      if (!html) return; tooltipEl.innerHTML = html; tooltipEl.style.display='block';
      const r = el.getBoundingClientRect();
      const pad = 6;
      let top = r.top - tooltipEl.offsetHeight - 8; if (top < 4) top = r.bottom + 8;
      let left = r.left + (r.width/2) - (tooltipEl.offsetWidth/2); if (left < 4) left = 4; const max = window.innerWidth - tooltipEl.offsetWidth - 4; if (left > max) left = max;
      tooltipEl.style.top = Math.round(top)+ 'px';
      tooltipEl.style.left = Math.round(left)+ 'px';
      announce(html);
    }
    function hideFallback(){ tooltipEl.style.display='none'; }
    function bind(el){
      if (el.__mudFallbackBound) return; el.__mudFallbackBound = true;
      el.addEventListener('mouseenter', ()=>showFallback(el));
      el.addEventListener('mouseleave', hideFallback);
      el.addEventListener('focus', ()=>showFallback(el));
      el.addEventListener('blur', hideFallback);
    }
    const scan = ()=>{ document.querySelectorAll('[data-mud-tooltip]').forEach(bind); };
    scan();
    const mo = new MutationObserver(scan); mo.observe(document.documentElement,{subtree:true,childList:true});
  }

  // --- Effects inference helpers ---
  function effectsText(it){
    if (it && it.effects && typeof it.effects === 'object' && Object.keys(it.effects).length) {
      return Object.entries(it.effects).map(([k,v])=> formatEffect(k,v)).join(' ');
    }
    // Fallback inference (mirror server logic heuristics)
    return inferEffects(it).map(e=>formatEffect(e.stat, e.delta)).join(' ');
  }
  function formatEffect(stat, delta){
    const sign = delta >= 0 ? '+' : '';
    return `${sign}${delta} ${stat.toUpperCase()}`;
  }
  function inferEffects(it){
    if (!it || !it.type) return [];
    const slug = (it.slug||'').toLowerCase();
    const t = (it.type||'').toLowerCase();
    const out = [];
    if (t === 'weapon') {
      if (slug.includes('bow')) out.push({stat:'dex', delta:1});
      else if (slug.includes('staff')) out.push({stat:'int', delta:1});
      else if (slug.includes('dagger')) out.push({stat:'dex', delta:1});
      else out.push({stat:'str', delta:1});
    } else if (t === 'armor') {
      if (slug.includes('shield')) out.push({stat:'con', delta:1});
      else if (slug.includes('leather')) out.push({stat:'con', delta:1});
      else out.push({stat:'con', delta:1});
    } else if (t === 'ring') {
      out.push({stat:'wis', delta:1});
    } else if (['amulet','necklace','talisman'].includes(t)) {
      out.push({stat:'cha', delta:1});
    }
    return out;
  }
})();
