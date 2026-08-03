/* Mock OA — a timed paper of 2-4 problems under one clock.

   The whole feature exists for the skill the judge could not previously exercise: TRIAGE. Solving
   one problem with no deadline is a different activity from choosing, with 47 minutes left, whether
   to finish Q2 or open Q3. So:

   - The clock is drawn here but OWNED by the server (`ends_at`, written once at start). A reload,
     a closed tab, or a second device cannot buy time, and the countdown re-syncs rather than
     free-running.
   - The running bar lives OUTSIDE the mock view, above the workspace, because you spend the paper
     in the judge — a status bar you have to navigate away from your code to see is not a status bar.
   - Questions are cards with title / difficulty / company and nothing else. No tags, no topic: the
     rest of the app already hides them so as not to name the technique, and that matters most here.
   - Polling is deliberately slow (60s). The per-question state changes only when YOU submit, and we
     already know when that happens — so the poll is a safety net for expiry, not a data feed, and
     an idle paper does not keep the host machine awake.
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
  async function jdel(p) { const r = await fetch(p, { method: 'DELETE' }); return r.json(); }

  const S = {
    data: null,            // catalogue payload
    filter: 'all',         // duration filter on the set grid
    running: null,         // live paper state from the server
    left: 0,               // seconds remaining, ticked locally between syncs
    tick: null, poll: null,
    randMinutes: 120, random: null,   // random-paper builder
    report: null,          // a finished paper being shown
    busy: false,
  };

  const currentPid = () => { try { return state.currentProblemId; } catch (e) { return null; } };

  const DUR_LABEL = (m) => (m % 60 === 0 ? `${m / 60} hour${m > 60 ? 's' : ''}` : `${m} min`);
  const hhmmss = (s) => {
    s = Math.max(0, Math.floor(s));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    const p = (n) => String(n).padStart(2, '0');
    return h ? `${h}:${p(m)}:${p(x)}` : `${p(m)}:${p(x)}`;
  };
  const ago = (iso) => {
    if (!iso) return '';
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 90) return 'just now';
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} hours ago`;
    const d = Math.round(s / 86400);
    return d === 1 ? 'yesterday' : `${d} days ago`;
  };

  // ------------------------------------------------------------------ landing
  async function render() {
    const host = $('mock-inner');
    if (!host) return;
    if (S.report) { renderReport(); return; }
    host.innerHTML = '<p class="spinner">Loading…</p>';
    try { S.data = await jget('/api/mock-oa'); }
    catch (e) { host.innerHTML = '<p class="placeholder">Could not load mock OAs.</p>'; return; }
    S.running = S.data.running;
    if (S.running) startClock(S.running.seconds_left);
    renderBar();
    renderLanding();
  }

  function renderLanding() {
    const host = $('mock-inner');
    const durs = [...new Set((S.data.sets || []).map((s) => s.minutes))].sort((a, b) => a - b);
    const chips = ['all', ...durs].map((d) =>
      `<button class="mk-chip ${String(S.filter) === String(d) ? 'active' : ''}" data-dur="${d}">
         ${d === 'all' ? 'All papers' : esc(DUR_LABEL(d))}</button>`).join('');

    const sets = (S.data.sets || []).filter((s) => S.filter === 'all' || String(s.minutes) === String(S.filter));
    const best = {};
    for (const h of (S.data.history || [])) {
      if (h.score && (best[h.set_id] === undefined || h.score.score > best[h.set_id])) best[h.set_id] = h.score.score;
    }

    const cards = sets.map((s) => {
      const ramp = s.difficulties.map((d) => `<span class="pill pill-${esc(d)}">${esc(d[0])}</span>`).join('');
      const done = best[s.id] !== undefined
        ? `<span class="mk-best" title="Your best score on this paper">best ${best[s.id]}%</span>` : '';
      return `<div class="mk-card" data-set="${esc(s.id)}">
          <div class="mk-card-top">
            <span class="mk-card-t">${esc(s.title)}</span>
            ${s.themed ? '<span class="mk-themed" title="A themed drill — the family is named on purpose">themed</span>' : ''}
          </div>
          <div class="mk-card-m">
            <span class="mk-mins">${esc(DUR_LABEL(s.minutes))}</span>
            <span class="mk-dot">·</span><span>${s.questions} questions</span>
            <span class="mk-ramp">${ramp}</span>${done}
          </div>
          <p class="mk-blurb">${esc(s.blurb)}</p>
          <div class="mk-qlist">${s.cards.map((c, i) => `
            <span class="mk-qrow"><b>Q${i + 1}</b> ${esc(c.title)}
              <span class="pill pill-${esc(c.difficulty)}">${esc(c.difficulty)}</span>
              ${c.solved_ever ? '<span class="mk-seen" title="You have solved this one before — outside this paper">seen</span>' : ''}
            </span>`).join('')}</div>
          <div class="mk-card-foot">
            <span class="mk-est">≈ ${s.estimate} min of solving</span>
            <button class="btn btn-primary mk-start" data-set="${esc(s.id)}">Start paper</button>
          </div>
        </div>`;
    }).join('');

    const hist = (S.data.history || []).length ? `
      <h2 class="iv-group">Past papers</h2>
      <div class="mk-hist">${S.data.history.map((h) => `
        <div class="mk-hrow" data-id="${h.id}">
          <div class="mk-hmain">
            <span class="mk-htitle">${esc(h.title)}</span>
            <span class="mk-hsub">${esc(ago(h.started_at))} · ${esc(DUR_LABEL(h.minutes))}
              ${h.status === 'abandoned' ? ' · abandoned' : ''}</span>
          </div>
          <span class="mk-hscore ${h.score && h.score.score >= 60 ? 'good' : ''}">${h.score ? h.score.score : 0}%</span>
          <span class="mk-hsolved">${h.score ? h.score.solved : 0}/${h.score ? h.score.questions : (h.problems || []).length} solved</span>
          <button class="mk-hview" data-view-id="${h.id}">Report</button>
          <button class="mk-hdel" data-del-id="${h.id}" title="Delete this paper">×</button>
        </div>`).join('')}</div>` : '';

    host.innerHTML = `
      <div class="iv-head">
        <div>
          <h1 class="iv-title">Mock OA</h1>
          <p class="iv-sub">A real paper: two to four questions, one clock, and no way to buy more time.</p>
        </div>
      </div>
      ${S.running ? `
        <div class="mk-resume">
          <div><b>${esc(S.running.title)}</b> is running — ${hhmmss(S.left)} left.</div>
          <div class="mk-resume-a">
            <button class="btn btn-primary" id="mk-resume-go">Back to Q1</button>
            <button class="btn btn-subtle" id="mk-resume-fin">Finish &amp; score</button>
          </div>
        </div>` : ''}
      <div class="mk-chips">${chips}</div>
      <div class="mk-grid">${cards || '<p class="placeholder">No papers at this length.</p>'}</div>
      ${renderRandomBuilder()}
      ${hist}`;

    host.querySelectorAll('.mk-chip').forEach((el) => el.addEventListener('click', () => {
      S.filter = el.dataset.dur === 'all' ? 'all' : Number(el.dataset.dur); renderLanding();
    }));
    host.querySelectorAll('.mk-start').forEach((el) =>
      el.addEventListener('click', (e) => { e.stopPropagation(); startSet(el.dataset.set); }));
    host.querySelectorAll('.mk-hview').forEach((el) =>
      el.addEventListener('click', () => showReport(Number(el.dataset.viewId))));
    host.querySelectorAll('.mk-hdel').forEach((el) =>
      el.addEventListener('click', async () => {
        if (!confirm('Delete this paper from your history?')) return;
        await jdel('/api/mock-oa/attempt/' + el.dataset.delId); render();
      }));
    const go = $('mk-resume-go'), fin = $('mk-resume-fin');
    if (go) go.addEventListener('click', () => openQuestion(S.running.problems[0]));
    if (fin) fin.addEventListener('click', () => finish());
    wireRandom();
  }

  // --- random paper builder ---------------------------------------------------
  function renderRandomBuilder() {
    const opts = (S.data.durations || [60, 90, 120, 180]).map((m) =>
      `<button class="mk-chip small ${S.randMinutes === m ? 'active' : ''}" data-rm="${m}">${esc(DUR_LABEL(m))}</button>`).join('');
    const preview = S.random ? `
      <div class="mk-qlist mk-rand-preview">${S.random.cards.map((c, i) => `
        <span class="mk-qrow"><b>Q${i + 1}</b> ${esc(c.title)}
          <span class="pill pill-${esc(c.difficulty)}">${esc(c.difficulty)}</span>
          <span class="mk-co">${esc(c.company || '')}</span>
        </span>`).join('')}
        <span class="mk-est">≈ ${S.random.estimate} min of solving in a ${S.random.minutes}-minute paper</span>
      </div>` : '';
    return `
      <h2 class="iv-group">Or build one <span class="iv-count">questions are picked to fill the time, hardest last, favouring ones you have not solved</span></h2>
      <div class="mk-rand">
        <div class="mk-chips">${opts}</div>
        ${preview}
        <div class="mk-rand-foot">
          <button class="btn btn-subtle" id="mk-shuffle">${S.random ? 'Shuffle again' : 'Pick questions'}</button>
          <button class="btn btn-primary" id="mk-rand-start" ${S.random ? '' : 'disabled'}>Start this paper</button>
        </div>
      </div>`;
  }

  function wireRandom() {
    const host = $('mock-inner');
    host.querySelectorAll('[data-rm]').forEach((el) => el.addEventListener('click', () => {
      S.randMinutes = Number(el.dataset.rm); S.random = null; renderLanding();
    }));
    const sh = $('mk-shuffle');
    if (sh) sh.addEventListener('click', async () => {
      sh.disabled = true; sh.textContent = 'Picking…';
      const r = await jpost('/api/mock-oa/random', { minutes: S.randMinutes });
      S.random = r.ok ? r : null;
      if (!r.ok) alert(r.error || 'Could not build a paper this long.');
      renderLanding();
    });
    const st = $('mk-rand-start');
    if (st) st.addEventListener('click', () => {
      if (S.random) startPaper({ minutes: S.random.minutes, problems: S.random.problems });
    });
  }

  // ------------------------------------------------------------------ lifecycle
  function startSet(setId) {
    const s = (S.data.sets || []).find((x) => x.id === setId);
    if (S.running && !confirm(`"${S.running.title}" is still running. Starting this one abandons it. Continue?`)) return;
    if (s && !confirm(`Start "${s.title}"? The clock runs for ${DUR_LABEL(s.minutes)} from now and cannot be paused.`)) return;
    startPaper({ set_id: setId });
  }

  async function startPaper(body) {
    if (S.busy) return;
    S.busy = true;
    try {
      const r = await jpost('/api/mock-oa/start', body);
      if (!r.ok) { alert(r.error || 'Could not start.'); return; }
      S.running = r.attempt;
      S.random = null;
      startClock(S.running.seconds_left);
      renderBar();
      openQuestion(S.running.problems[0]);
    } finally { S.busy = false; }
  }

  async function finish() {
    const id = S.running && S.running.id;
    stopClock();
    const r = await jpost('/api/mock-oa/finish', id ? { attempt_id: id } : {});
    S.running = null;
    renderBar();
    // Handing in is the end of the exercise, so the report is where you land — including when the
    // clock ran out while you were mid-keystroke in the judge. That is what a real OA does.
    if (r.ok) { S.report = r.attempt; switchToMock(); renderReport(); }
    else render();
  }

  // ------------------------------------------------------------------ the clock
  function startClock(seconds) {
    stopClock();
    S.left = Math.max(0, seconds || 0);
    S.tick = setInterval(() => {
      S.left -= 1;
      paintClock();
      if (S.left <= 0) { stopClock(); finish(); }
    }, 1000);
    // Slow poll: the only thing it can tell us that we don't already know is that the paper ran out
    // while this tab was asleep. Per-question state is refreshed on submit, not on a timer.
    S.poll = setInterval(sync, 60000);
    document.addEventListener('visibilitychange', onVisible);
    paintClock();
  }

  function stopClock() {
    clearInterval(S.tick); clearInterval(S.poll);
    S.tick = S.poll = null;
    document.removeEventListener('visibilitychange', onVisible);
  }

  function onVisible() { if (!document.hidden) sync(); }

  async function sync() {
    let r;
    try { r = await jget('/api/mock-oa/active'); } catch (e) { return; }
    if (!r.running) {
      stopClock();
      S.running = null;
      renderBar();
      if (r.just_finished) { S.report = r.just_finished; switchToMock(); renderReport(); }
      return;
    }
    S.running = r.running;
    S.left = r.running.seconds_left;   // the server's clock wins over ours, always
    renderBar();
  }

  /* Called by the judge after a submit: the question you just judged may have changed colour. */
  async function refresh() { if (S.running) await sync(); }

  // ------------------------------------------------------------------ the running bar
  function renderBar() {
    const bar = $('mock-bar');
    if (!bar) return;
    if (!S.running) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
    const live = S.running.live || { per_problem: [] };
    const chips = (S.running.cards || []).map((c, i) => {
      const st = (live.per_problem || [])[i] || {};
      const cls = st.solved ? 'done' : (st.submissions ? 'tried' : '');
      // `state` is app.js's top-level const: a script-scope global binding, NOT a window property.
      const on = currentPid() === c.id ? ' here' : '';
      const label = st.solved ? 'solved' : (st.submissions ? `${st.points}%` : 'not attempted');
      return `<button class="mk-q ${cls}${on}" data-pid="${esc(c.id)}"
                title="Q${i + 1} · ${esc(c.title)} · ${esc(c.difficulty)} · ${label}">
                Q${i + 1}<span class="mk-q-d">${esc((c.difficulty || '?')[0])}</span></button>`;
    }).join('');
    bar.innerHTML = `
      <span class="mk-bar-t" title="${esc(S.running.title)}">${esc(S.running.title)}</span>
      <div class="mk-qs">${chips}</div>
      <span class="mk-clock" id="mk-clock">${hhmmss(S.left)}</span>
      <button class="mk-bar-fin" id="mk-bar-fin" title="End the paper now and see your score">Finish</button>`;
    bar.style.display = 'flex';
    bar.querySelectorAll('.mk-q').forEach((el) =>
      el.addEventListener('click', () => openQuestion(el.dataset.pid)));
    const f = $('mk-bar-fin');
    if (f) f.addEventListener('click', () => {
      if (confirm('End the paper now and score it? Submissions after this do not count.')) finish();
    });
    paintClock();
  }

  function paintClock() {
    const el = $('mk-clock');
    if (!el) return;
    el.textContent = hhmmss(S.left);
    el.classList.toggle('warn', S.left <= 600 && S.left > 120);
    el.classList.toggle('danger', S.left <= 120);
  }

  // ------------------------------------------------------------------ navigation
  function switchToMock() {
    const nav = document.querySelector('.topnav-item[data-view="mock"]');
    if (nav) nav.click();
  }

  /* Open one of the paper's questions in the judge, in OA mode.

     OA mode is forced because hidden tests are the point of an OA — but its one-submission rule is
     a practice rule, not an OA rule, so app.js keeps Submit enabled while a paper is running. */
  async function openQuestion(pid) {
    const nav = document.querySelector('.topnav-item[data-view="judge"]');
    if (nav) nav.click();
    try { await window.loadProblem(pid); } catch (e) { /* the judge reports its own failures */ }
    const radios = document.getElementsByName('mode');
    for (const r of radios) {
      if (r.value === 'oa' && !r.checked) { r.checked = true; r.dispatchEvent(new Event('change')); }
    }
    renderBar();
  }

  // ------------------------------------------------------------------ report
  async function showReport(id) {
    try { const r = await jget('/api/mock-oa/attempt/' + id); S.report = r.attempt; }
    catch (e) { return; }
    renderReport();
  }

  function renderReport() {
    const host = $('mock-inner');
    const a = S.report, sc = a.score || { per_problem: [], score: 0, solved: 0, questions: 0 };
    const used = a.ended_at && a.started_at
      ? Math.round((new Date(a.ended_at) - new Date(a.started_at)) / 60000) : a.minutes;
    const rows = (a.cards || []).map((c, i) => {
      const p = (sc.per_problem || [])[i] || {};
      const cls = p.solved ? 'ok' : (p.submissions ? 'part' : 'none');
      const verdict = p.solved ? 'Solved'
        : p.submissions ? `${p.verdict || 'WA'} · ${p.passed || 0}/${p.total || 0} tests`
        : 'Not attempted';
      return `<div class="mk-rrow ${cls}">
          <span class="mk-rq">Q${i + 1}</span>
          <button class="mk-rtitle" data-pid="${esc(c.id)}">${esc(c.title)}</button>
          <span class="pill pill-${esc(c.difficulty)}">${esc(c.difficulty)}</span>
          <span class="mk-rverdict">${esc(verdict)}</span>
          <span class="mk-rsubs">${p.submissions || 0} submission${p.submissions === 1 ? '' : 's'}</span>
          <span class="mk-rpts">${p.points || 0}%</span>
        </div>`;
    }).join('');

    // Say what the score MEANS. A bare percentage is the least useful thing a report can show.
    const verdictLine = sc.solved === sc.questions
      ? 'Full marks — every question solved inside the window.'
      : sc.solved === 0 && sc.attempted === 0 ? 'Nothing was submitted before the clock ran out.'
      : sc.solved === 0 ? 'Partial credit only. Look at which question you spent the most time on and whether it was the right one.'
      : `${sc.solved} of ${sc.questions} solved. On a real OA that is usually enough to advance when the unsolved one is the hardest.`;

    host.innerHTML = `
      <div class="iv-head">
        <div>
          <h1 class="iv-title">${esc(a.title)}</h1>
          <p class="iv-sub">${esc(ago(a.started_at))} · ${esc(DUR_LABEL(a.minutes))} paper · ${used} min used
            ${a.status === 'abandoned' ? ' · abandoned' : ''}</p>
        </div>
        <div class="mk-bigscore ${sc.score >= 60 ? 'good' : ''}">${sc.score}<span>%</span></div>
      </div>
      <p class="mk-verdict">${esc(verdictLine)}</p>
      <div class="mk-report">${rows}</div>
      <div class="mk-rfoot">
        <button class="btn btn-subtle" id="mk-back">Back to papers</button>
        <span class="mk-note">The questions stay open in the judge — the clock only decides what counted.</span>
      </div>`;
    host.querySelectorAll('.mk-rtitle').forEach((el) =>
      el.addEventListener('click', async () => {
        const nav = document.querySelector('.topnav-item[data-view="judge"]');
        if (nav) nav.click();
        try { await window.loadProblem(el.dataset.pid); } catch (e) {}
      }));
    const b = $('mk-back');
    if (b) b.addEventListener('click', () => { S.report = null; render(); });
  }

  // ------------------------------------------------------------------ boot
  /* The bar has to come back after a reload even if the user never opens the Mock OA tab — they
     might reload straight into the judge mid-paper, and a paper with no visible clock is worse
     than no paper at all. */
  async function boot() {
    try {
      const r = await jget('/api/mock-oa/active');
      if (r.running) { S.running = r.running; startClock(r.running.seconds_left); renderBar(); }
    } catch (e) { /* not signed in, or offline — the tab will load it later */ }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();

  window.OAMockOA = { render, refresh, running: () => !!S.running };
})();
