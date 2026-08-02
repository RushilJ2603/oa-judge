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

  const S = { view: 'catalog', session: null, polling: null, catalog: null, filter: '',
              shapes: [], subjects: [], excluded: new Set(), tab: 'loops', history: [] };

  // ------------------------------------------------------------------ entry
  async function render() {
    const host = $('interview-inner');
    if (!host) return;
    if (S.session) { renderSession(); return; }
    host.innerHTML = '<p class="spinner">Loading…</p>';
    let status = { online: false, rubrics: 0 }, cat = { items: [] },
        shapes = { shapes: [], subjects: [] }, hist = { sessions: [] };
    try {
      [status, cat, shapes, hist] = await Promise.all([
        jget('/api/interview/status'), jget('/api/interview/catalog'),
        jget('/api/interview/shapes'), jget('/api/interview/history')]);
    } catch (e) { host.innerHTML = '<p class="placeholder">Could not load interviews.</p>'; return; }
    S.catalog = cat.items || [];
    S.shapes = shapes.shapes || [];
    S.subjects = shapes.subjects || [];
    S.history = hist.sessions || [];
    S.status = status;
    renderCatalog(status);
  }

  function renderCatalog(status) {
    const host = $('interview-inner');
    const dot = status.online
      ? '<span class="iv-dot on"></span>Interviewer online'
      : '<span class="iv-dot"></span>Interviewer offline';
    const offlineNote = status.online ? '' :
      `<div class="iv-offline">The interviewer runs on a host machine that is not currently up.
       You can still browse — start a session once it is online.</div>`;

    const tabs = [['loops', 'Interview loops'], ['topics', 'By topic'],
                  ['history', `Past interviews${S.history.length ? ' (' + S.history.length + ')' : ''}`]];
    const tabBar = `<div class="iv-tabs">` + tabs.map(([k, l]) =>
      `<button class="iv-tab ${S.tab === k ? 'active' : ''}" data-tab="${k}">${esc(l)}</button>`).join('') + `</div>`;

    let body = '';
    if (S.tab === 'loops') body = renderLoops();
    else if (S.tab === 'topics') body = renderTopics();
    else body = renderHistory();

    host.innerHTML =
      `<div class="iv-head">
         <div>
           <h1 class="iv-title">Mock Interview</h1>
           <p class="iv-sub">Grounded in your own notes. It remembers what you missed last time.</p>
         </div>
         <div class="iv-status">${dot}</div>
       </div>
       ${offlineNote}
       ${tabBar}
       ${body}`;

    host.querySelectorAll('.iv-tab').forEach((el) =>
      el.addEventListener('click', () => { S.tab = el.dataset.tab; renderCatalog(status); }));
    wireLoops(status);
    wireTopics(status);
    host.querySelectorAll('.iv-hist-row').forEach((el) =>
      el.addEventListener('click', () =>
        el.dataset.active === '1' ? resume(+el.dataset.sid) : showReport(+el.dataset.sid)));
  }

  // --- tab 1: loops (the default — a real onsite spans subjects) ---------------
  function renderLoops() {
    const cards = S.shapes.map((s) => `
      <button class="iv-card iv-loop" data-shape="${esc(s.shape)}">
        <span class="iv-card-t">${esc(s.label || s.shape)}</span>
        <span class="iv-loop-sub">${esc(s.sub || '')}</span>
        <span class="iv-loop-prev">${esc(s.preview)}</span>
      </button>`).join('');

    const chips = S.subjects.map((sub) => {
      const off = S.excluded.has(sub.key);
      return `<button class="iv-chip ${off ? 'off' : ''}" data-sub="${esc(sub.key)}"
                title="${off ? 'Excluded — click to include' : 'Included — click to exclude'}">
                ${esc(sub.label)} <span class="iv-chip-n">${sub.count}</span></button>`;
    }).join('');

    return `
      <div class="iv-cards">${cards}</div>
      <h2 class="iv-group">Build your own <span class="iv-count">turn off anything you don't want asked</span></h2>
      <div class="iv-builder">
        <div class="iv-chips">${chips}</div>
        <div class="iv-builder-foot">
          <span class="iv-preview" id="iv-custom-preview">Pick your subjects, then start.</span>
          <button class="btn btn-primary" id="iv-custom-start">Start custom loop</button>
        </div>
      </div>`;
  }

  function wireLoops(status) {
    const host = $('interview-inner');
    host.querySelectorAll('.iv-loop').forEach((el) =>
      el.addEventListener('click', () => start(null, el.dataset.shape)));
    host.querySelectorAll('.iv-chip').forEach((el) =>
      el.addEventListener('click', async () => {
        const k = el.dataset.sub;
        if (S.excluded.has(k)) S.excluded.delete(k); else S.excluded.add(k);
        el.classList.toggle('off');
        await refreshPreview();
      }));
    const btn = $('iv-custom-start');
    if (btn) btn.addEventListener('click', () => start(null, null, [...S.excluded]));
    if ($('iv-custom-preview')) refreshPreview();
  }

  async function refreshPreview() {
    const el = $('iv-custom-preview');
    if (!el) return;
    el.textContent = 'Choosing topics…';
    try {
      const r = await jpost('/api/interview/preview', { exclude: [...S.excluded], segments: 4 });
      el.textContent = r.segments ? r.preview : 'Nothing left — re-enable a subject.';
    } catch (e) { el.textContent = ''; }
  }

  // --- tab 2: by topic, grouped by subject ------------------------------------
  function renderTopics() {
    const q = S.filter.toLowerCase();
    const groups = new Map();
    S.catalog.forEach((it) => {
      if (q && !it.title.toLowerCase().includes(q) && !it.subject_label.toLowerCase().includes(q)) return;
      if (!groups.has(it.subject_label)) groups.set(it.subject_label, []);
      groups.get(it.subject_label).push(it);
    });
    let body = `<input class="iv-search" id="iv-search" type="text" placeholder="Search topics…"
                  autocomplete="off" spellcheck="false" value="${esc(S.filter)}">`;
    if (!groups.size) return body + '<p class="placeholder">No topics match.</p>';
    groups.forEach((items, label) => {
      body += `<h2 class="iv-group">${esc(label)} <span class="iv-count">${items.length}</span></h2>
               <div class="iv-cards">` + items.map((i) => `
          <button class="iv-card" data-id="${esc(i.id)}" title="${esc(i.relevance || '')}">
            <span class="iv-card-t">${esc(i.title)}</span>
            <span class="iv-card-m">
              <span class="iv-w" title="How often interviews ask this">${'★'.repeat(i.weight)}</span>
              <span class="iv-diff ${esc(i.difficulty)}">${esc(i.difficulty || '')}</span>
            </span>
          </button>`).join('') + '</div>';
    });
    return body;
  }

  function wireTopics(status) {
    const host = $('interview-inner');
    host.querySelectorAll('.iv-card[data-id]').forEach((el) =>
      el.addEventListener('click', () => start(el.dataset.id)));
    const search = $('iv-search');
    if (search) search.addEventListener('input', () => {
      S.filter = search.value;
      const pos = search.selectionStart;
      renderCatalog(status);
      const s2 = $('iv-search'); if (s2) { s2.focus(); s2.setSelectionRange(pos, pos); }
    });
  }

  // --- tab 3: past interviews -------------------------------------------------
  function renderHistory() {
    if (!S.history.length) {
      return '<p class="placeholder">No interviews yet. Your sessions, scores and every point you missed will appear here.</p>';
    }
    return '<div class="iv-hist">' + S.history.map((h) => {
      const pct = h.overall == null ? '—' : Math.round(h.overall * 100) + '%';
      const when = (h.started_at || '').slice(0, 16).replace('T', ' ');
      const state = h.status === 'done' ? '' :
        `<span class="iv-hist-state">${live ? '▸ continue' : esc(h.status)}</span>`;
      const live = h.status === 'active';
      return `<button class="iv-hist-row" data-sid="${h.id}" data-active="${live ? 1 : 0}"
                title="${live ? 'Continue this interview' : 'See the report'}">
                <span class="iv-hist-main">
                  <span class="iv-hist-t">${esc(h.title || h.kind)}${h.mixed ? ' <span class="iv-hist-mix">loop</span>' : ''}</span>
                  <span class="iv-hist-sub">${esc(when)} · ${h.answers} answers${h.summary ? ' · ' + esc(h.summary) : ''}</span>
                </span>
                ${state}<span class="iv-hist-score">${pct}</span>
              </button>`;
    }).join('') + '</div>';
  }

  // ------------------------------------------------------------------ session
  async function start(rubricId, shape, exclude) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Starting the interview…</p>';
    const payload = shape ? { shape }
      : exclude ? { exclude, segments: 4 }
      : { rubric_id: rubricId };
    const r = await jpost('/api/interview/start', payload);
    if (r.error) { host.innerHTML = `<p class="placeholder">${esc(r.error)}</p>`; return; }
    S.session = { id: r.session_id, title: r.title, type: r.type, phases: r.phases,
                  phase: r.phase, turns: [], thinking: true, hintTier: 0, done: false };
    renderSession();
    poll(r.job_id);
  }

  // ------------------------------------------------------------------ text to speech
  /* The interviewer reads its questions aloud (Web Speech Synthesis — browser-native, free).
     Paired with dictation this becomes an actual spoken mock interview.
     Choices worth knowing:
       - CODE IS NOT READ OUT. Hearing "backtick vector less-than int greater-than" is useless, so
         fenced blocks are replaced with a short spoken marker and you read the code on screen.
       - speaking is cancelled when a new turn arrives or you leave, so answers never overlap;
       - the preference persists in localStorage, because re-enabling it every session is friction;
       - unsupported browsers hide the control instead of showing a dead one. */
  const TTS_KEY = 'oaj_iv_tts';
  function ttsSupported() { return 'speechSynthesis' in window; }
  function ttsOn() { try { return localStorage.getItem(TTS_KEY) === '1'; } catch (e) { return false; } }
  function setTts(v) { try { localStorage.setItem(TTS_KEY, v ? '1' : '0'); } catch (e) { } }
  function stopSpeaking() { if (ttsSupported()) window.speechSynthesis.cancel(); }

  function speakable(text) {
    return String(text || '')
      .replace(/```[\s\S]*?```/g, ' — code on screen — ')   // never read code aloud
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/^[-*]\s+/gm, '')
      .replace(/#{1,6}\s*/g, '')
      .trim();
  }

  function speak(text) {
    if (!ttsSupported() || !ttsOn()) return;
    const t = speakable(text);
    if (!t) return;
    stopSpeaking();                       // never let two turns talk over each other
    const u = new SpeechSynthesisUtterance(t);
    u.rate = 1.02;                        // conversational, not robotic-slow
    u.pitch = 1;
    u.lang = 'en-IN';
    try { window.speechSynthesis.speak(u); } catch (e) { }
  }

  async function resume(sid) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Picking up where you left off…</p>';
    const r = await jpost('/api/interview/resume/' + sid, {});
    if (r.error) { host.innerHTML = `<p class="placeholder">${esc(r.error)}</p>`; return; }
    S.session = {
      id: r.session_id, title: r.title, type: r.type, phases: r.phases || [],
      phase: r.phase, hintTier: r.hint_tier || 0, done: false,
      // Rebuild the visible transcript from the server; older interviewer turns were stored as
      // plain text, so they fall back to escaped text rather than rendered markdown.
      turns: (r.turns || []).filter((t) => t.role !== 'system')
                            .map((t) => ({ role: t.role, content: t.content })),
      thinking: !!r.job_id,
    };
    renderSession();
    if (r.job_id) poll(r.job_id);
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
      : `<div class="iv-row"><div class="iv-who">Interviewer</div><div class="iv-bubble${t.html ? ' md' : ''}">${t.html || esc(t.content)}</div></div>`
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
             <span class="iv-composer-actions">
               <button class="icon-btn iv-mic" id="iv-mic" title="Dictate your answer"
                 ${s.thinking ? 'disabled' : ''}>🎤 Speak</button>
               <button class="btn btn-primary" id="iv-send" ${s.thinking ? 'disabled' : ''}>Send</button>
             </span>
           </div>
         </div>`;

    host.innerHTML =
      `<div class="iv-shead">
         <button class="icon-btn" id="iv-back" title="Leave this interview">←</button>
         <div class="iv-shead-main">
           <h1 class="iv-stitle">${esc(s.title)}</h1>
           <div class="iv-rail">${rail}</div>
         </div>
         <button class="icon-btn iv-speak ${ttsOn() ? 'on' : ''}" id="iv-tts"
           title="${ttsOn() ? 'Interviewer is reading aloud — click to mute' : 'Have the interviewer read questions aloud'}"
           >${ttsOn() ? '🔊' : '🔇'}</button>
       </div>
       <div class="iv-thread" id="iv-thread">${rows}${thinking}</div>
       ${composer}`;

    $('iv-back').addEventListener('click', leave);
    const tts = $('iv-tts');
    if (tts) {
      if (!ttsSupported()) tts.style.display = 'none';
      tts.addEventListener('click', () => {
        setTts(!ttsOn());
        if (!ttsOn()) stopSpeaking();
        renderSession();
      });
    }
    if (s.done) {
      $('iv-report').addEventListener('click', showReport);
      $('iv-exit').addEventListener('click', leave);
    } else {
      const ta = $('iv-answer');
      $('iv-send').addEventListener('click', send);
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
      });
      wireMic(ta);
      // Keep the candidate in flow: focus returns the moment it is their turn again.
      if (!s.thinking) ta.focus();
    }
    const th = $('iv-thread');
    if (th) th.scrollTop = th.scrollHeight;
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }

  async function send() {
    const s = S.session, ta = $('iv-answer');
    stopMic();                       // a live mic would keep appending into the next turn
    stopSpeaking();                  // stop mid-question readout the moment they answer
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
    let waited = 0, inFlight = false;
    S.polling = setInterval(async () => {
      // A turn takes ~15s, so a naive 2s interval puts ~7 requests in flight at once. They would
      // all arrive as "done" together — hence the interviewer's message appearing many times.
      // One request at a time.
      if (inFlight) return;
      inFlight = true;
      waited += 1;
      let r;
      try { r = await jget('/api/interview/poll/' + jobId); }
      catch (e) { return; }
      finally { inFlight = false; }
      if (r.status === 'done') {
        clearInterval(S.polling);
        const s = S.session;
        s.thinking = false;
        s.turns.push({ role: 'interviewer', content: r.say || '…', html: r.say_html || '' });
        speak(r.say || '');
        if (r.phase) s.phase = r.phase;
        s.hintTier = r.hint_tier || 0;
        s.done = !!r.done;
        renderSession();
      } else if (r.error || waited > 300) {
        clearInterval(S.polling);
        const s = S.session;
        s.thinking = false;
        s.turns.push({ role: 'interviewer',
          content: '⚠ ' + (r.error || 'The interviewer did not respond. Is the host machine still running?') });
        renderSession();
      }
    }, 1000);   // 1s: the model floor is ~15s, so poll granularity should not add to it
  }

  async function showReport(sid) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Building your report…</p>';
    const id = sid || (S.session && S.session.id);
    const rep = await jget('/api/interview/report/' + id);
    if (rep.error) { host.innerHTML = `<p class="placeholder">${esc(rep.error)}</p>`; return; }
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

  // ------------------------------------------------------------------ speech to text
  /* Browser-native Web Speech API: no key, no server cost, and speaking your answer is what a real
     interview actually is. Notes on the design:
       - interim results are shown live but only the FINAL transcript is committed, so the textarea
         does not churn while you are mid-sentence;
       - dictation APPENDS to whatever you typed rather than replacing it, so the two mix freely;
       - Chrome ends recognition on its own after a pause — for an interview answer that is mid-
         thought, so it is restarted automatically until you switch it off.
     Chrome/Edge route audio through Google's servers; unsupported browsers simply never see the
     button rather than getting one that silently fails. */
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, recOn = false, recBase = '';

  function micSupported() { return !!SpeechRec; }

  function stopMic() {
    recOn = false;
    if (rec) { try { rec.stop(); } catch (e) { } rec = null; }
    const b = $('iv-mic');
    if (b) { b.classList.remove('on'); b.textContent = '🎤 Speak'; }
  }

  function wireMic(ta) {
    const btn = $('iv-mic');
    if (!btn) return;
    if (!micSupported()) { btn.style.display = 'none'; return; }
    btn.addEventListener('click', () => (recOn ? stopMic() : startMic(ta)));
  }

  function startMic(ta) {
    if (!SpeechRec) return;
    rec = new SpeechRec();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-IN';
    recOn = true;
    recBase = ta.value ? ta.value.replace(/\s*$/, '') + ' ' : '';
    const btn = $('iv-mic');
    if (btn) { btn.classList.add('on'); btn.textContent = '● Listening'; }

    rec.onresult = (e) => {
      let done = '', interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) done += t + ' '; else interim += t;
      }
      if (done) recBase += done;
      ta.value = recBase + interim;
      ta.scrollTop = ta.scrollHeight;
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        stopMic();
        const b = $('iv-mic');
        if (b) b.title = 'Microphone permission denied — allow it in the address bar';
      }
    };
    rec.onend = () => { if (recOn) { try { rec.start(); } catch (e) { } } };  // pause != finished
    try { rec.start(); } catch (e) { stopMic(); }
  }

  function leave() {
    stopMic();
    stopSpeaking();
    clearInterval(S.polling);
    S.session = null;
    render();
  }

  window.OAInterview = { render, leave };
})();
