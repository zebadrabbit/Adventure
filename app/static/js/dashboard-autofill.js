// project: Adventure MUD
// module: dashboard-autofill.js
// Adds client-side wiring for the Autofill party button calling /autofill_characters
// License: MIT

(function() {
  const btn = document.getElementById('autofill-party-btn');
  if(!btn) return;
  let busy = false;
  async function autofill() {
    if(busy) return; busy = true; btn.disabled = true;
    btn.classList.add('disabled');
    try {
      const resp = await fetch('/autofill_characters', {method:'POST', headers:{'X-Requested-With':'fetch'}});
      if(!resp.ok) {
        console.warn('Autofill failed', resp.status);
        return;
      }
      const data = await resp.json();
      // If new characters were created, reload to render them (simple approach)
      if(data.created > 0) {
        window.location.reload();
      } else {
        // No creation needed; provide a subtle visual cue
        btn.classList.add('btn-success');
        setTimeout(()=>btn.classList.remove('btn-success'), 1200);
      }
    } catch(err) {
      console.error('Error autofilling characters', err);
    } finally {
      busy = false; btn.disabled = false; btn.classList.remove('disabled');
    }
  }
  btn.addEventListener('click', autofill);
})();
