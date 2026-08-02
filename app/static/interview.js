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

  async function jdel(p) {
    const r = await fetch(p, { method: 'DELETE' });
    return r.json();
  }

  const S = { view: 'catalog', session: null, polling: null, catalog: null, filter: '',
              shapes: [], subjects: [], excluded: new Set(), tab: 'loops', history: [], weak: [],
              progress: {}, topicFilter: 'all' };

  // ------------------------------------------------------------------ entry
  async function render() {
    const host = $('interview-inner');
    if (!host) return;
    if (S.session) { renderSession(); return; }
    host.innerHTML = '<p class="spinner">Loading…</p>';
    let status = { online: false, rubrics: 0 }, cat = { items: [] },
        shapes = { shapes: [], subjects: [] }, hist = { sessions: [] }, weak = { topics: [] };
    try {
      [status, cat, shapes, hist, weak] = await Promise.all([
        jget('/api/interview/status'), jget('/api/interview/catalog'),
        jget('/api/interview/shapes'), jget('/api/interview/history'),
        jget('/api/interview/weak')]);
    } catch (e) { host.innerHTML = '<p class="placeholder">Could not load interviews.</p>'; return; }
    S.catalog = cat.items || [];
    S.progress = cat.progress || {};
    S.shapes = shapes.shapes || [];
    S.subjects = shapes.subjects || [];
    S.history = hist.sessions || [];
    S.weak = weak.topics || [];
    S.status = status;
    // Landing on an empty tab reads as a broken feature, so a tab that has nothing to show is not
    // where you start.
    if (S.tab === 'weak' && !S.weak.length) S.tab = 'loops';
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

    const tabs = [['loops', 'Interview loops'],
                  ['weak', `Weak spots${S.weak.length ? ' (' + S.weak.length + ')' : ''}`],
                  ['topics', 'By topic'],
                  ['history', `Past interviews${S.history.length ? ' (' + S.history.length + ')' : ''}`]];
    const tabBar = `<div class="iv-tabs">` + tabs.map(([k, l]) =>
      `<button class="iv-tab ${S.tab === k ? 'active' : ''}" data-tab="${k}">${esc(l)}</button>`).join('') + `</div>`;

    let body = '';
    if (S.tab === 'loops') body = renderLoops();
    else if (S.tab === 'weak') body = renderWeak();
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
    wireWeak();
    wireHistory();
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
  /* Every card carries its own completion state. Without it a 322-item list is undifferentiated —
     you cannot tell what you have covered, so you re-do familiar topics and never notice the gaps.
     SOLID_AT matches the server's WEAK_MAX (0.7): above it a topic is done, below it you have been
     through it but it still needs work, and that distinction is the whole point of the badge. */
  const SOLID_AT = 0.7;

  function progressOf(id) { return (S.progress && S.progress[id]) || null; }

  function topicState(id) {
    const p = progressOf(id);
    if (!p) return 'new';
    return p.mastery >= SOLID_AT ? 'solid' : 'shaky';
  }

  function badge(id) {
    const p = progressOf(id);
    if (!p) return '';
    const pct = Math.round(p.mastery * 100);
    const st = topicState(id);
    const times = p.sessions === 1 ? 'once' : p.sessions + ' times';
    // Built on one line on purpose: whitespace inside an attribute value is NOT collapsed, so a
    // tooltip broken across source lines renders with the source indentation inside it.
    const tip = `${st === 'solid' ? 'Solid' : 'Attempted, still shaky'} — ${p.solid} of ${p.points} points solid, interviewed ${times}`;
    return `<span class="iv-done-badge ${st}" title="${esc(tip)}">` +
           `${st === 'solid' ? '✓' : '↻'} ${pct}%</span>`;
  }

  function renderTopics() {
    const q = S.filter.toLowerCase();
    const groups = new Map();
    let shown = 0;
    S.catalog.forEach((it) => {
      if (q && !it.title.toLowerCase().includes(q) && !it.subject_label.toLowerCase().includes(q)) return;
      if (S.topicFilter !== 'all' && topicState(it.id) !== S.topicFilter) return;
      if (!groups.has(it.subject_label)) groups.set(it.subject_label, []);
      groups.get(it.subject_label).push(it);
      shown++;
    });

    // Counted over the whole catalog, not the filtered view — this is the standing picture.
    const total = S.catalog.length;
    let solid = 0, shaky = 0;
    S.catalog.forEach((it) => {
      const st = topicState(it.id);
      if (st === 'solid') solid++; else if (st === 'shaky') shaky++;
    });
    const attempted = solid + shaky;

    const chips = [['all', `All ${total}`], ['new', `Not started ${total - attempted}`],
                   ['shaky', `Needs work ${shaky}`], ['solid', `Solid ${solid}`]];
    const bar = `<div class="iv-topbar">
        <span class="iv-progress-line">
          <b>${attempted}</b> of ${total} topics attempted${attempted ? ` · <b>${solid}</b> solid` : ''}
        </span>
        <span class="iv-filters">` + chips.map(([k, l]) =>
          `<button class="iv-chip ${S.topicFilter === k ? '' : 'off'}" data-tf="${k}">${esc(l)}</button>`
        ).join('') + `</span>
      </div>`;

    let body = bar + `<input class="iv-search" id="iv-search" type="text" placeholder="Search topics…"
                  autocomplete="off" spellcheck="false" value="${esc(S.filter)}">`;
    if (!shown) return body + '<p class="placeholder">No topics match.</p>';
    groups.forEach((items, label) => {
      body += `<h2 class="iv-group">${esc(label)} <span class="iv-count">${items.length}</span></h2>
               <div class="iv-cards">` + items.map((i) => `
          <button class="iv-card ${topicState(i.id)}" data-id="${esc(i.id)}" title="${esc(i.relevance || '')}">
            <span class="iv-card-t">${esc(i.title)}</span>
            <span class="iv-card-m">
              ${badge(i.id)}
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
    host.querySelectorAll('[data-tf]').forEach((el) =>
      el.addEventListener('click', () => { S.topicFilter = el.dataset.tf; renderCatalog(status); }));
    const search = $('iv-search');
    if (search) search.addEventListener('input', () => {
      S.filter = search.value;
      const pos = search.selectionStart;
      renderCatalog(status);
      const s2 = $('iv-search'); if (s2) { s2.focus(); s2.setSelectionRange(pos, pos); }
    });
  }

  // --- tab 3: weak spots ------------------------------------------------------
  /* The evidence from past interviews, made visible and actionable. It already drove loop
     composition invisibly (mixed.compose sorts weakness-first) — which meant the feature existed
     but nobody could SEE it, so it may as well not have. */
  function renderWeak() {
    if (!S.weak.length) {
      return `<p class="placeholder">Nothing here yet — weak spots are built from what you miss in
              interviews. Finish a loop or two and the topics you struggled with will collect here,
              worst first, ready to drill.</p>`;
    }
    const rows = S.weak.map((t) => {
      const pct = Math.round(t.mastery * 100);
      const when = t.last_tested_at ? ' · last tested ' + esc((t.last_tested_at || '').slice(0, 10)) : '';
      return `<button class="iv-weak-row" data-id="${esc(t.id)}" title="Drill this topic now">
                <span class="iv-weak-main">
                  <span class="iv-weak-t">${esc(t.title)}</span>
                  <span class="iv-weak-sub">${esc(t.subject_label)} · ${t.weak_points} of ${t.points}
                    points still shaky${when}</span>
                </span>
                <span class="iv-meter iv-weak-meter"><div style="width:${pct}%"></div></span>
                <b class="iv-weak-pct">${pct}%</b>
              </button>`;
    }).join('');
    return `<div class="iv-weak-head">
              <p class="iv-sub">Built from the rubric points you actually missed — worst first.</p>
              <button class="btn btn-primary" id="iv-weak-drill">Drill the top ${
                Math.min(4, S.weak.length)} in one loop</button>
            </div>
            <div class="iv-weak">${rows}</div>`;
  }

  function wireWeak() {
    const host = $('interview-inner');
    host.querySelectorAll('.iv-weak-row').forEach((el) =>
      el.addEventListener('click', () => start(el.dataset.id)));
    const drill = $('iv-weak-drill');
    if (drill) drill.addEventListener('click', () =>
      start(null, null, null, S.weak.slice(0, 4).map((t) => t.id)));
  }

  // --- tab 4: past interviews -------------------------------------------------
  function renderHistory() {
    if (!S.history.length) {
      return '<p class="placeholder">No interviews yet. Your sessions, scores and every point you missed will appear here.</p>';
    }
    return '<div class="iv-hist">' + S.history.map((h) => {
      // `live` must be declared before the template literals that read it — a const used above its
      // declaration throws a TDZ ReferenceError, which killed the whole history list silently.
      const live = h.status === 'active';
      const pct = h.overall == null ? '—' : Math.round(h.overall * 100) + '%';
      // Sorted by last interaction, so the timestamp shown must be the same one it sorted on —
      // showing "started 12 Jul" at the top of the list looks like the sort is broken.
      const when = ago(h.last_at || h.started_at);
      const state = h.status === 'done' ? '' :
        `<span class="iv-hist-state">${live ? '▸ continue' : esc(h.status)}</span>`;
      return `<div class="iv-hist-item">
                <button class="iv-hist-row" data-sid="${h.id}" data-active="${live ? 1 : 0}"
                  title="${live ? 'Continue this interview' : 'See the report'}">
                  <span class="iv-hist-main">
                    <span class="iv-hist-t">${esc(h.title || h.kind)}${h.mixed ? ' <span class="iv-hist-mix">loop</span>' : ''}</span>
                    <span class="iv-hist-sub">${esc(when)} · ${h.answers} answers${h.summary ? ' · ' + esc(h.summary) : ''}</span>
                  </span>
                  ${state}<span class="iv-hist-score">${pct}</span>
                </button>
                <button class="icon-btn iv-hist-del" data-sid="${h.id}"
                  data-title="${esc(h.title || h.kind)}"
                  title="Delete this interview and everything it taught the interviewer about you"
                  aria-label="Delete interview">✕</button>
              </div>`;
    }).join('') + '</div>';
  }

  /* "3 hours ago" beats "2026-08-01 14:20" for a list whose whole point is recency — you can see
     the order is right without doing date arithmetic. */
  function ago(ts) {
    if (!ts) return '';
    // Stored timestamps carry MICROseconds; the ES date format defines exactly three fractional
    // digits, and engines differ on whether they tolerate six. Truncate rather than rely on that.
    let s = String(ts).replace(/(\.\d{3})\d+/, '$1');
    if (!/Z$|[+-]\d\d:?\d\d$/.test(s)) s += 'Z';         // naive string means UTC here
    const t = Date.parse(s);
    if (isNaN(t)) return String(ts).slice(0, 16).replace('T', ' ');
    const mins = Math.round((Date.now() - t) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + ' min ago';
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + (hrs === 1 ? ' hour ago' : ' hours ago');
    const days = Math.round(hrs / 24);
    if (days < 30) return days + (days === 1 ? ' day ago' : ' days ago');
    return new Date(t).toISOString().slice(0, 10);
  }

  function wireHistory() {
    const host = $('interview-inner');
    host.querySelectorAll('.iv-hist-row').forEach((el) =>
      el.addEventListener('click', () =>
        el.dataset.active === '1' ? resume(+el.dataset.sid) : showReport(+el.dataset.sid)));
    host.querySelectorAll('.iv-hist-del').forEach((el) =>
      el.addEventListener('click', async (e) => {
        e.stopPropagation();                       // never open the interview you meant to delete
        const sid = +el.dataset.sid;
        if (!window.confirm(
          `Delete “${el.dataset.title}”?\n\nThe transcript, its score and everything it contributed ` +
          `to your weak spots are removed for good. The interviewer will no longer remember it.`)) return;
        el.disabled = true;
        const r = await jdel('/api/interview/session/' + sid);
        if (r && r.error) { el.disabled = false; alert(r.error); return; }
        // Weak spots are recomputed server-side by the delete, so reload rather than splicing
        // locally — otherwise the two tabs disagree about what you know.
        await render();
      }));
  }

  // ------------------------------------------------------------------ session
  async function start(rubricId, shape, exclude, rubricIds) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Starting the interview…</p>';
    const payload = rubricIds ? { rubric_ids: rubricIds }
      : shape ? { shape }
      : exclude ? { exclude, segments: 4 }
      : { rubric_id: rubricId };
    const r = await jpost('/api/interview/start', payload);
    if (r.error) { host.innerHTML = `<p class="placeholder">${esc(r.error)}</p>`; return; }
    S.session = { id: r.session_id, title: r.title, type: r.type, phases: r.phases,
                  phase: r.phase, step: r.step || 0, turns: [], thinking: true,
                  hintTier: 0, done: false };
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
  const TTS_VOICE_KEY = 'oaj_iv_voice';
  let voicesReady = false;

  function ttsSupported() { return 'speechSynthesis' in window; }
  function ttsOn() { try { return localStorage.getItem(TTS_KEY) === '1'; } catch (e) { return false; } }
  function setTts(v) { try { localStorage.setItem(TTS_KEY, v ? '1' : '0'); } catch (e) { } }
  function stopSpeaking() { if (ttsSupported()) window.speechSynthesis.cancel(); }

  /* Voice quality is the whole difference between "a robot is reading at me" and something you can
     listen to for 45 minutes. Browsers ship a mix: modern NEURAL voices (Microsoft "… Online
     (Natural)" on Edge/Chrome-Windows, Google's network voices) alongside decades-old formant
     synths (David, Zira, eSpeak) — and the DEFAULT pick is very often one of the bad ones.
     So rank explicitly rather than accepting voice[0]. */
  function scoreVoice(v) {
    const n = (v.name || '').toLowerCase();
    const lang = (v.lang || '').toLowerCase();
    let sc = 0;
    if (/natural|neural/.test(n)) sc += 100;      // Microsoft neural — the best free option
    if (/online/.test(n)) sc += 40;               // network voices beat local formant synths
    if (/google/.test(n)) sc += 45;               // Google network voices are good
    if (/siri|samantha|premium|enhanced/.test(n)) sc += 60;   // Apple's good ones
    if (/^en-in/.test(lang)) sc += 22;            // familiar accent for an Indian candidate
    else if (/^en-gb/.test(lang)) sc += 14;
    else if (/^en-us/.test(lang)) sc += 12;
    else if (/^en/.test(lang)) sc += 8;
    else sc -= 60;                                // non-English voice reading English is unlistenable
    if (/david|zira|mark|hazel|espeak|festival|pico|compact/.test(n)) sc -= 45;  // legacy synths
    if (v.localService && !/natural|neural/.test(n)) sc -= 8;
    return sc;
  }

  function voiceList() {
    if (!ttsSupported()) return [];
    return window.speechSynthesis.getVoices()
      .filter((v) => /^en/i.test(v.lang || ''))
      .sort((a, b) => scoreVoice(b) - scoreVoice(a));
  }

  function pickVoice() {
    const list = voiceList();
    if (!list.length) return null;
    try {
      const saved = localStorage.getItem(TTS_VOICE_KEY);
      if (saved) {
        const hit = list.find((v) => v.voiceURI === saved || v.name === saved);
        if (hit) return hit;
      }
    } catch (e) { }
    return list[0];                                // best-ranked available
  }

  // getVoices() is empty until the engine loads them; without this the first question of a session
  // would speak in the default (usually worst) voice.
  if (ttsSupported()) {
    const markReady = () => { voicesReady = true; };
    if (window.speechSynthesis.getVoices().length) markReady();
    window.speechSynthesis.addEventListener('voiceschanged', markReady);
  }

  function speakable(text) {
    return String(text || '')
      .replace(/```[\s\S]*?```/g, ' — code on screen — ')   // never read code aloud
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/^[-*]\s+/gm, '')
      .replace(/#{1,6}\s*/g, '')
      .replace(/\bO\(([^)]+)\)/g, 'order $1')              // "O(n log n)" -> "order n log n"
      .replace(/\s*\n{2,}\s*/g, '. ')                       // paragraph breaks become pauses
      .trim();
  }

  function speak(text) {
    if (!ttsSupported() || !ttsOn()) return;
    const t = speakable(text);
    if (!t) return;
    stopSpeaking();                       // never let two turns talk over each other
    const u = new SpeechSynthesisUtterance(t);
    const v = pickVoice();
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = 1.0;                         // neural voices sound unnatural when sped up
    u.pitch = 1;
    try { window.speechSynthesis.speak(u); } catch (e) { }
  }

  function voicePickerHtml() {
    const list = voiceList();
    if (list.length < 2) return '';
    let cur = '';
    try { cur = localStorage.getItem(TTS_VOICE_KEY) || ''; } catch (e) { }
    const best = list[0];
    return `<select class="iv-voice" id="iv-voice" title="Voice">` +
      list.slice(0, 12).map((v) => {
        const sel = (cur ? (v.voiceURI === cur || v.name === cur) : v === best) ? ' selected' : '';
        const nice = /natural|neural|google|premium|enhanced/i.test(v.name) ? ' ★' : '';
        return `<option value="${esc(v.voiceURI || v.name)}"${sel}>${esc(v.name)}${nice}</option>`;
      }).join('') + `</select>`;
  }

  async function resume(sid) {
    const host = $('interview-inner');
    host.innerHTML = '<p class="spinner">Picking up where you left off…</p>';
    const r = await jpost('/api/interview/resume/' + sid, {});
    if (r.error) { host.innerHTML = `<p class="placeholder">${esc(r.error)}</p>`; return; }
    S.session = {
      id: r.session_id, title: r.title, type: r.type, phases: r.phases || [],
      phase: r.phase, step: r.step || 0, hintTier: r.hint_tier || 0, done: false,
      // Rebuild the visible transcript from the server, which renders interviewer turns for us.
      // Only the raw markdown is stored, so without carrying `html` through here a reopened
      // interview showed every past turn as literal **markdown**, fences and all.
      turns: (r.turns || []).filter((t) => t.role !== 'system')
                            .map((t) => ({ role: t.role, content: t.content, html: t.html || '' })),
      thinking: !!r.job_id,
    };
    renderSession();
    if (r.job_id) poll(r.job_id);
  }

  function renderSession() {
    const s = S.session, host = $('interview-inner');
    // The server hands over the absolute step. Looking the phase name up in the rail instead is
    // wrong for a mixed loop, where several segments repeat the same phase names — indexOf finds
    // the first match, so being in segment 3's "approach" would light up segment 1's.
    const idx = (typeof s.step === 'number' && s.step >= 0) ? s.step : s.phases.indexOf(s.phase);
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

    // The headline number belongs ON the completion panel, not one click away behind "see report".
    // Finishing an interview and being told only "complete" is the moment you most want the score.
    const finalPct = s.finalScore == null ? null : Math.round(s.finalScore * 100);
    const composer = s.done
      ? `<div class="iv-done">
           <p><b>Interview complete.</b></p>
           ${finalPct == null
             ? '<p class="iv-sub">Scoring…</p>'
             : `<div class="iv-final">
                  <span class="iv-final-pct">${finalPct}%</span>
                  <span class="iv-final-sub">${esc(s.finalSummary || '')}</span>
                </div>`}
           <div class="iv-done-actions">
             <button class="btn btn-primary" id="iv-report">See the full report</button>
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
         <span class="iv-voice-wrap">
           ${ttsOn() ? voicePickerHtml() : ''}
           <button class="icon-btn iv-speak ${ttsOn() ? 'on' : ''}" id="iv-tts"
             title="${ttsOn() ? 'Interviewer is reading aloud — click to mute' : 'Have the interviewer read questions aloud'}"
             >${ttsOn() ? '🔊' : '🔇'}</button>
         </span>
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
    const vsel = $('iv-voice');
    if (vsel) {
      vsel.addEventListener('change', () => {
        try { localStorage.setItem(TTS_VOICE_KEY, vsel.value); } catch (e) { }
        stopSpeaking();
        speak('Voice set. I will read the questions in this voice.');   // hear it immediately
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
        if (typeof r.step === 'number') s.step = r.step;
        s.hintTier = r.hint_tier || 0;
        s.done = !!r.done;
        renderSession();
        if (s.done) loadFinalScore(s.id);
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

  /* The overall score is computed server-side when the session closes, so it is fetched rather than
     accumulated client-side — the app owns every number, and a browser must never be able to tell
     itself how it did. Failure is silent: the panel keeps its button, which still works. */
  async function loadFinalScore(sid) {
    try {
      const rep = await jget('/api/interview/report/' + sid);
      if (!S.session || S.session.id !== sid) return;     // they navigated away mid-fetch
      S.session.finalScore = (rep.scores && rep.scores.overall) || 0;
      const misses = (rep.misses || []).length;
      S.session.finalSummary = misses
        ? `${misses} point${misses === 1 ? '' : 's'} to review`
        : 'clean run — nothing missed';
      renderSession();
    } catch (e) { }
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
