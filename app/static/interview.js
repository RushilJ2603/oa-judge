/* Mock interview UI.

   Friction rules this file follows:
   - The answer box is focused after every interviewer turn, so you can just keep typing.
   - Enter sends; Shift+Enter is a newline. Nobody wants to reach for a Send button mid-thought.
   - The ~15s model wait is never a dead screen: a labelled thinking row appears immediately.
   - One natural page scroll. No nested scroll boxes (they were the "black boundaries" problem).
   - Worker offline is stated plainly, with what to do, instead of failing silently.
*/
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (window.escapeHTML ? window.escapeHTML(String(s == null ? '' : s))
    : String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])));

  async function jget(p) { const r = await fetch(p); if (!r.ok) throw new Error(r.status); return r.json(); }
  async function jpost(p, b) {
    const r = await fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) });
    return r.json();
  }

  const S = { view: 'catalog', session: null, polling: null, catalog: null, filter: '' };
  const TYPE_LABEL = { HLD: 'System Design', LLD: 'Low-Level Design', CONCEPT: 'Fundamentals', CP: 'DSA / CP' };

  // ------------------------------------------------------------------ entry
  async function render() {
    const host = $('interview-inner');
    if (!host) return;
    if (S.session) { renderSession(); return; }
    host.innerHTML = '<p class="spinner">Loading…</p>';
    let status = { online: false, rubrics: 0 }, cat = { items: [] };
    try { [status, cat] = await Promise.all([jget('/api/interview/status'), jget('/api/interview/catalog')]); }
    catch (e) { host.innerHTML = '<p class="placeholder">Could not load interviews.</p>'; return; }
    S.catalog = cat.items || [];
    renderCatalog(status);
  }

  function renderCatalog(status) {
    const host = $('interview-inner');
    const groups = {};
    S.catalog.forEach((it) => { (groups[it.type] = groups[it.type] || []).push(it); });
    const q = S.filter.toLowerCase();

    const dot = status.online
      ? '<span class="iv-dot on"></span>Interviewer online'
      : '<span class="iv-dot"></span>Interviewer offline';
    const offlineNote = status.online ? '' :
      `<div class="iv-offline">The interviewer runs on a host machine that is not currently up.
       You can still browse the list — start a session once it is online.</div>`;

    let body = '';
    ['HLD', 'LLD', 'CONCEPT', 'CP'].forEach((t) => {
      const items = (groups[t] || []).filter((i) =>
        !q || i.title.toLowerCase().includes(q) || i.id.toLowerCase().includes(q));
      if (!items.length) return;
      body += `<h2 class="iv-group">${esc(TYPE_LABEL[t] || t)} <span class="iv-count">${items.length}</span></h2>
               <div class="iv-cards">` +
        items.map((i) => `
          <button class="iv-card" data-id="${esc(i.id)}">
            <span class="iv-card-t">${esc(i.title)}</span>
            <span class="iv-card-m">
              <span class="iv-diff ${esc(i.difficulty)}">${esc(i.difficulty || '')}</span>
              <span class="iv-phases">${i.phases.length} phases</span>
            </span>
          </button>`).join('') + '</div>';
    });
    if (!body) body = '<p class="placeholder">No interviews match that search.</p>';

    host.innerHTML =
      `<div class="iv-head">
         <div>
           <h1 class="iv-title">Mock Interview</h1>
           <p class="iv-sub">Grounded in your own notes and research. It remembers what you missed last time.</p>
         </div>
         <div class="iv-status" title="${status.online ? 'A host machine is running the interviewer' : 'No host machine is running'}">${dot}</div>
       </div>
       ${offlineNote}
       <input class="iv-search" id="iv-search" type="text" placeholder="Search interviews…"
              autocomplete="off" spellcheck="false" value="${esc(S.filter)}">
       ${body}`;

    const search = $('iv-search');
    search.addEventListener('input', () => {
      S.filter = search.value;
      const pos = search.selectionStart;
      renderCatalog(status);
      const s2 = $('iv-search'); s2.focus(); s2.setSelectionRange(pos, pos);
    });
    host.querySelectorAll('.iv-card').forEach((el) =>
      el.addEventListener('click', () => start(el.dataset.id)));
  }

  // ------------------------------------------------------------------ session
  async function start(rubricId) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Starting the interview…</p>';
    const r = await jpost('/api/interview/start', { rubric_id: rubricId });
    if (r.error) { host.innerHTML = `<p class="placeholder">${esc(r.error)}</p>`; return; }
    S.session = { id: r.session_id, title: r.title, type: r.type, phases: r.phases,
                  phase: r.phase, turns: [], thinking: true, hintTier: 0, done: false };
    renderSession();
    poll(r.job_id);
  }

  function renderSession() {
    const s = S.session, host = $('interview-inner');
    const idx = s.phases.indexOf(s.phase);
    const rail = s.phases.map((p, i) => {
      const cls = s.done ? 'done' : (i < idx ? 'done' : i === idx ? 'now' : '');
      return `<span class="iv-step ${cls}" title="${esc(p)}">${esc(p.replace(/_/g, ' '))}</span>`;
    }).join('');

    const rows = s.turns.map((t) => t.role === 'candidate'
      ? `<div class="iv-row me"><div class="iv-bubble me">${esc(t.content)}</div></div>`
      : `<div class="iv-row"><div class="iv-who">Interviewer</div><div class="iv-bubble">${esc(t.content)}</div></div>`
    ).join('');

    const thinking = s.thinking
      ? `<div class="iv-row"><div class="iv-who">Interviewer</div>
           <div class="iv-bubble iv-thinking"><span></span><span></span><span></span>
           <em>thinking…</em></div></div>` : '';

    const composer = s.done
      ? `<div class="iv-done">
           <p><b>Interview complete.</b></p>
           <div class="iv-done-actions">
             <button class="btn btn-primary" id="iv-report">See your report</button>
             <button class="btn btn-subtle" id="iv-exit">Back to interviews</button>
           </div>
         </div>`
      : `<div class="iv-composer">
           <textarea id="iv-answer" class="iv-answer" rows="3" spellcheck="true"
             placeholder="Type your answer…  (Enter to send, Shift+Enter for a new line)"
             ${s.thinking ? 'disabled' : ''}></textarea>
           <div class="iv-composer-bar">
             <span class="iv-hint-state">${s.hintTier > 0
               ? `hint level ${s.hintTier} unlocked` : 'no hints yet — say if you are stuck'}</span>
             <button class="btn btn-primary" id="iv-send" ${s.thinking ? 'disabled' : ''}>Send</button>
           </div>
         </div>`;

    host.innerHTML =
      `<div class="iv-shead">
         <button class="icon-btn" id="iv-back" title="Leave this interview">←</button>
         <div class="iv-shead-main">
           <h1 class="iv-stitle">${esc(s.title)}</h1>
           <div class="iv-rail">${rail}</div>
         </div>
       </div>
       <div class="iv-thread" id="iv-thread">${rows}${thinking}</div>
       ${composer}`;

    $('iv-back').addEventListener('click', leave);
    if (s.done) {
      $('iv-report').addEventListener('click', showReport);
      $('iv-exit').addEventListener('click', leave);
    } else {
      const ta = $('iv-answer');
      $('iv-send').addEventListener('click', send);
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
      });
      // Keep the candidate in flow: focus returns the moment it is their turn again.
      if (!s.thinking) ta.focus();
    }
    const th = $('iv-thread');
    if (th) th.scrollTop = th.scrollHeight;
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }

  async function send() {
    const s = S.session, ta = $('iv-answer');
    const text = (ta.value || '').trim();
    if (!text || s.thinking) return;
    s.turns.push({ role: 'candidate', content: text });
    s.thinking = true;
    renderSession();
    const r = await jpost('/api/interview/answer', { session_id: s.id, answer: text });
    if (r.error) { s.thinking = false; s.turns.push({ role: 'interviewer', content: '⚠ ' + r.error }); renderSession(); return; }
    poll(r.job_id);
  }

  function poll(jobId) {
    clearInterval(S.polling);
    let waited = 0;
    S.polling = setInterval(async () => {
      waited += 2;
      let r;
      try { r = await jget('/api/interview/poll/' + jobId); } catch (e) { return; }
      if (r.status === 'done') {
        clearInterval(S.polling);
        const s = S.session;
        s.thinking = false;
        s.turns.push({ role: 'interviewer', content: r.say || '…' });
        if (r.phase) s.phase = r.phase;
        s.hintTier = r.hint_tier || 0;
        s.done = !!r.done;
        renderSession();
      } else if (r.error || waited > 240) {
        clearInterval(S.polling);
        const s = S.session;
        s.thinking = false;
        s.turns.push({ role: 'interviewer',
          content: '⚠ ' + (r.error || 'The interviewer did not respond. Is the host machine still running?') });
        renderSession();
      }
    }, 2000);
  }

  async function showReport() {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Building your report…</p>';
    const rep = await jget('/api/interview/report/' + S.session.id);
    const sc = rep.scores || {};
    const phases = (sc.phases || []).map((p) =>
      `<div class="iv-score"><span>${esc(p.phase.replace(/_/g, ' '))}</span>
         <div class="iv-meter"><div style="width:${Math.round(p.score * 100)}%"></div></div>
         <b>${Math.round(p.score * 100)}%</b></div>`).join('');
    const misses = (rep.misses || []).map((m) =>
      `<li><b>${esc(m.phase.replace(/_/g, ' '))}</b> — ${esc(m.point)}
        ${m.your_answer ? `<div class="iv-yours">you said: “${esc(m.your_answer)}”</div>` : ''}</li>`).join('');
    host.innerHTML =
      `<div class="iv-shead"><button class="icon-btn" id="iv-back">←</button>
         <div class="iv-shead-main"><h1 class="iv-stitle">${esc(rep.title || '')} — report</h1>
         <p class="iv-sub">Overall ${Math.round((sc.overall || 0) * 100)}%</p></div></div>
       <div class="iv-report">
         <h2 class="iv-group">By phase</h2>${phases}
         <h2 class="iv-group">What to review${misses ? '' : ' — nothing, clean run'}</h2>
         <ul class="iv-misses">${misses}</ul>
       </div>`;
    $('iv-back').addEventListener('click', leave);
  }

  function leave() {
    clearInterval(S.polling);
    S.session = null;
    render();
  }

  window.OAInterview = { render, leave };
})();
