/* CP + System Design sheets, and the contest tracker.
   Rides the existing OA Judge design system; loaded after app.js so it can reuse escapeHTML, but it
   keeps its own state + fetch so it never entangles with the judge. The judge workspace is only ever
   hidden/shown — never restyled. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (window.escapeHTML ? window.escapeHTML(String(s == null ? '' : s)) : String(s == null ? '' : s));
  async function jget(p) { const r = await fetch(p); if (!r.ok) throw new Error(r.status); return r.json(); }
  async function jpost(p, b) {
    const r = await fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) });
    return r.json();
  }

  const S = { view: 'judge', sheets: {}, current: null, activeSection: {} };

  // ---------------------------------------------------------------- view switching
  function switchView(view) {
    S.view = view;
    document.querySelectorAll('.topnav-item').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
    const ws = document.querySelector('.workspace');
    const sv = $('sheet-view'), tv = $('tracker-view'), cv = $('compiler-view'), bc = $('breadcrumb');
    if (ws) ws.style.display = view === 'judge' ? '' : 'none';
    if (sv) sv.style.display = (view === 'cp' || view === 'sd') ? 'flex' : 'none';
    if (tv) tv.style.display = view === 'tracker' ? 'block' : 'none';
    if (cv) cv.style.display = view === 'compiler' ? 'block' : 'none';
    if (bc) bc.style.display = view === 'judge' ? '' : 'none';
    try { history.replaceState(null, '', view === 'judge' ? location.pathname : '#' + view); } catch (e) {}
    if (view === 'cp') loadSheet('cp');
    else if (view === 'sd') loadSheet('sd');
    else if (view === 'tracker') loadTracker();
    else if (view === 'compiler') renderCompiler();
  }

  // ---------------------------------------------------------------- sheet
  async function loadSheet(sid) {
    if (S.current === sid && S.sheets[sid]) { renderSheet(sid); return; }
    S.current = sid;
    $('sheet-content').innerHTML = '<p class="spinner">Loading…</p>';
    try { S.sheets[sid] = await jget('/api/sheet/' + sid); }
    catch (e) { $('sheet-content').innerHTML = '<p class="placeholder">Could not load this sheet.</p>'; return; }
    renderSheet(sid);
  }

  function secProgress(sec, prog) {
    const done = sec.items.filter((i) => prog[i.id] === 'done').length;
    return { done, total: sec.items.length };
  }

  function renderSheet(sid) {
    const data = S.sheets[sid], sheet = data.sheet, prog = data.progress;
    $('sheet-title').textContent = sheet.title;
    $('sheet-sub').textContent = sheet.audience || sheet.subtitle || '';
    setMeter(data);
    $('sheet-roadmap').innerHTML = (sheet.roadmap || []).map((p) => `
      <div class="rm-phase">
        <div class="rm-badge"><span class="dot">${esc(p.phase)}</span>${esc(p.title)}</div>
        <div class="rm-span">${esc(p.span || '')}</div>
        <div class="rm-focus">${esc(p.focus || '')}</div>
        <div class="rm-milestone">◆ ${esc(p.milestone || '')}</div>
      </div>`).join('');
    const active = S.activeSection[sid] || 0;
    const grouped = sheet.sections.some((s) => s.group);
    let railHtml = grouped ? '<div class="rail-seq-hint">Follow top to bottom ↓</div>' : '';
    let lastGroup = null;
    sheet.sections.forEach((sec, i) => {
      const sp = secProgress(sec, prog), pc = sp.total ? Math.round(sp.done / sp.total * 100) : 0;
      const complete = sp.total && sp.done === sp.total;
      if (grouped && sec.group !== lastGroup) { railHtml += `<div class="rail-section-h">${esc(sec.group)}</div>`; lastGroup = sec.group; }
      const step = grouped ? `<span class="rail-step ${complete ? 'done' : ''}">${complete ? '✓' : i + 1}</span>` : '';
      railHtml += `<div class="rail-topic ${i === active ? 'active' : ''} ${complete ? 'complete' : ''}" data-idx="${i}">
        <div class="rail-trow">${step}<span class="rail-tname">${esc(sec.title)}</span><span class="rail-tcount">${sp.done}/${sp.total}</span></div>
        <div class="rail-tbar"><div class="rail-tfill" style="width:${pc}%"></div></div>
      </div>`;
    });
    $('sheet-rail').innerHTML = railHtml;
    $('sheet-rail').querySelectorAll('.rail-topic').forEach((el) =>
      el.addEventListener('click', () => { S.activeSection[sid] = +el.dataset.idx; renderSheet(sid); }));
    renderSection(sid);
  }

  function setMeter(data) {
    const prog = data.progress;
    let ct = 0, cd = 0, tt = 0, td = 0;
    data.sheet.sections.forEach((sec) => sec.items.forEach((it) => {
      tt++; const done = prog[it.id] === 'done'; if (done) td++;
      if (it.tier === 'core') { ct++; if (done) cd++; }
    }));
    const pct = ct ? Math.round(cd / ct * 100) : 0;
    const lead = ct ? `<b>${cd}</b> / ${ct} core` : `<b>${td}</b> / ${tt}`;
    $('sheet-meter').innerHTML =
      `<div class="m-num">${lead}${ct ? ` · ${td}/${tt} total` : ' done'}</div><div class="m-bar"><div class="m-fill" style="width:${pct}%"></div></div>`;
  }

  function ratingColor(r) {
    if (r == null) return 'var(--text-muted)';
    if (r < 1200) return '#8a8f98'; if (r < 1400) return '#1a9d57'; if (r < 1600) return '#03a89e';
    if (r < 1900) return '#3d6bff'; if (r < 2100) return '#a000c8'; if (r < 2400) return '#ff8c00'; return '#e5484d';
  }

  function renderSection(sid) {
    const data = S.sheets[sid], sheet = data.sheet, prog = data.progress;
    const sec = sheet.sections[S.activeSection[sid] || 0];
    if (!sec) { $('sheet-content').innerHTML = ''; return; }
    const buckets = { core: [], extended: [], stretch: [] };
    sec.items.forEach((it) => buckets[it.tier === 'core' ? 'core' : it.tier === 'stretch' ? 'stretch' : 'extended'].push(it));
    const codeable = sid === 'cp';   // scratchpad is for the CP problems, not the SD reading list
    const group = (label, items) => items.length
      ? `<div class="tier-group">${label ? `<div class="tier-label">${label}</div>` : ''}${items.map((it) => row(it, prog, codeable)).join('')}</div>` : '';
    const meta = [
      sec.placement_value ? `<span class="tm topic-pv ${esc(sec.placement_value)}">${esc(sec.placement_value)} value</span>` : '',
      sec.band ? `<span class="tm">${esc(sec.band)}</span>` : '',
      sec.sub ? `<span class="tm">${esc(sec.sub)}</span>` : ''
    ].filter(Boolean).join('');
    $('sheet-content').innerHTML =
      `<h2 class="topic-h">${esc(sec.title)}</h2>
       ${meta ? `<div class="topic-meta">${meta}</div>` : ''}
       ${sec.summary ? `<p class="topic-summary">${esc(sec.summary)}</p>` : ''}
       ${group('Must-do core', buckets.core)}${group('Extended', buckets.extended)}${group('Stretch', buckets.stretch)}`;
    const content = $('sheet-content');
    content.querySelectorAll('.prob-check').forEach((el) =>
      el.addEventListener('click', () => toggleItem(sid, el.dataset.item, el)));
    content.querySelectorAll('.prob-code-btn').forEach((el) =>
      el.addEventListener('click', () => togglePad(el)));
  }

  function row(it, prog, codeable) {
    const done = prog[it.id] === 'done';
    const rb = it.rating != null ? `<span class="rating-badge" style="background:${ratingColor(it.rating)}">${it.rating}</span>` : '';
    const tier = it.tier ? `<span class="tier-pill ${esc(it.tier)}">${esc(it.tier)}</span>` : '';
    const code = codeable ? `<button class="prob-code-btn" data-item="${esc(it.id)}" title="Draft your solution here, then copy it into the site's submit box" aria-expanded="false">Code</button>` : '';
    return `<div class="prob-item" data-item="${esc(it.id)}">
      <div class="prob-row ${done ? 'done' : ''}">
        <button class="prob-check ${done ? 'done' : ''}" data-item="${esc(it.id)}" title="Mark solved" aria-pressed="${done}">${done ? '✓' : ''}</button>
        <div class="prob-main">
          <a class="prob-title" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a>
          ${it.tag ? `<div class="prob-tag">${esc(it.tag)}</div>` : ''}
        </div>
        <div class="prob-side">${rb}<span class="plat-badge">${esc(it.platform || '')}</span>${tier}${code}</div>
      </div>
      <div class="prob-pad" hidden></div>
    </div>`;
  }

  // ---------------------------------------------------------------- scratchpad (draft-then-copy)
  const PAD_LANGS = [['cpp', 'C++'], ['python', 'Python'], ['java', 'Java'], ['kotlin', 'Kotlin'], ['c', 'C'], ['py3', 'PyPy']];

  function togglePad(btn) {
    const item = btn.closest('.prob-item');
    const pad = item.querySelector('.prob-pad');
    if (!pad.hasAttribute('hidden')) {
      pad.setAttribute('hidden', ''); btn.setAttribute('aria-expanded', 'false'); btn.classList.remove('active');
      return;
    }
    pad.removeAttribute('hidden'); btn.setAttribute('aria-expanded', 'true'); btn.classList.add('active');
    if (!pad.dataset.built) buildPad(pad, btn.dataset.item);
    else pad.querySelector('.pad-code').focus();
  }

  function autoGrow(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(Math.max(ta.scrollHeight, 128), 560) + 'px'; }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* fall through */ }
    const t = document.createElement('textarea');
    t.value = text; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.focus(); t.select();
    try { document.execCommand('copy'); } catch (_) { }
    document.body.removeChild(t); return true;
  }

  const RUNNABLE = { cpp: 1, c: 1, py: 1, python: 1, py3: 1 };   // langs the built-in compiler runs

  async function buildPad(pad, itemId) {
    pad.dataset.built = '1';
    pad.innerHTML =
      `<div class="pad-bar">
         <select class="pad-lang" title="Language">${PAD_LANGS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>
         <span class="pad-status" aria-live="polite"></span>
         <button class="pad-run" type="button" title="Compile & run with the input below (Ctrl/Cmd+Enter)">Run ▸</button>
         <button class="pad-copy" type="button" title="Copy code to clipboard">Copy</button>
       </div>
       <textarea class="pad-code" spellcheck="false" autocomplete="off" autocapitalize="off" wrap="off"
                 placeholder="Write your solution here — Run it below, or Copy it into the site's submit box."></textarea>
       <div class="pad-io" hidden>
         <div class="pad-io-col">
           <div class="pad-io-h">Custom input <span class="pad-io-sub">stdin</span></div>
           <textarea class="pad-stdin" spellcheck="false" autocomplete="off" wrap="off" placeholder="Type input for your program here…"></textarea>
         </div>
         <div class="pad-io-col">
           <div class="pad-io-h">Output <span class="pad-run-meta"></span></div>
           <pre class="pad-out" tabindex="0"></pre>
         </div>
       </div>
       <div class="pad-hint">Autosaved to your account · runs in the same sandbox as the judge (C++ &amp; Python). The problem link is unchanged.</div>`;
    const ta = pad.querySelector('.pad-code'), sel = pad.querySelector('.pad-lang');
    const status = pad.querySelector('.pad-status'), copy = pad.querySelector('.pad-copy');
    const run = pad.querySelector('.pad-run'), io = pad.querySelector('.pad-io');
    const stdin = pad.querySelector('.pad-stdin'), out = pad.querySelector('.pad-out');
    const meta = pad.querySelector('.pad-run-meta');
    try {
      const d = await jget('/api/sheet-code?item=' + encodeURIComponent(itemId));
      if (d.ok) { ta.value = d.code || ''; if (d.lang) sel.value = d.lang; }
    } catch (e) { /* start blank */ }
    autoGrow(ta); ta.focus();
    const syncRunnable = () => {
      const ok = !!RUNNABLE[sel.value];
      run.disabled = !ok;
      run.title = ok ? 'Compile & run with the input below (Ctrl/Cmd+Enter)' : 'Built-in Run supports C++ & Python';
    };
    syncRunnable();
    let timer = null;
    const save = () => {
      status.textContent = 'Saving…';
      jpost('/api/sheet-code', { item_id: itemId, lang: sel.value, code: ta.value })
        .then(() => { status.textContent = 'Saved'; })
        .catch(() => { status.textContent = 'Save failed'; });
    };
    const queue = () => { clearTimeout(timer); status.textContent = 'Editing…'; timer = setTimeout(save, 700); };
    const insertTab = (el) => {
      const s = el.selectionStart, en = el.selectionEnd;
      el.value = el.value.slice(0, s) + '    ' + el.value.slice(en);
      el.selectionStart = el.selectionEnd = s + 4;
    };
    ta.addEventListener('input', () => { autoGrow(ta); queue(); });
    sel.addEventListener('change', () => { syncRunnable(); save(); });
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doRun(); return; }
      if (e.key === 'Tab') { e.preventDefault(); insertTab(ta); queue(); }
    });
    stdin.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doRun(); return; }
      if (e.key === 'Tab') { e.preventDefault(); insertTab(stdin); }
    });
    copy.addEventListener('click', async () => {
      await copyText(ta.value);
      copy.textContent = 'Copied ✓'; copy.classList.add('ok');
      setTimeout(() => { copy.textContent = 'Copy'; copy.classList.remove('ok'); }, 1400);
    });

    async function doRun() {
      if (run.disabled || run.dataset.busy) return;
      io.hidden = false;
      run.dataset.busy = '1'; run.textContent = 'Running…';
      out.className = 'pad-out'; out.textContent = ''; meta.textContent = 'compiling…';
      try {
        const r = await jpost('/api/scratch-run', { lang: sel.value, source: ta.value, stdin: stdin.value });
        if (!r.ok) { out.classList.add('err'); out.textContent = r.error || 'Run failed.'; meta.textContent = ''; return; }
        renderRun(r, out, meta);
      } catch (e) {
        out.classList.add('err'); out.textContent = 'Could not reach the runner. Try again.'; meta.textContent = '';
      } finally {
        run.dataset.busy = ''; run.textContent = 'Run ▸';
      }
    }
    run.addEventListener('click', doRun);
  }

  const VERDICT_LABEL = { OK: 'Finished', CE: 'Compile error', TLE: 'Time limit exceeded', RE: 'Runtime error', MLE: 'Memory limit exceeded' };

  function renderRun(r, out, meta) {
    if (r.verdict === 'CE') {
      out.classList.add('err');
      out.textContent = r.compile_output || 'Compilation failed.';
      meta.innerHTML = '<span class="rv rv-bad">Compile error</span>';
      return;
    }
    const bits = [];
    const bad = r.verdict !== 'OK';
    bits.push(`<span class="rv ${bad ? 'rv-bad' : 'rv-ok'}">${esc(VERDICT_LABEL[r.verdict] || r.verdict)}</span>`);
    if (r.time_ms != null) bits.push(`${r.time_ms} ms`);
    if (r.memory_kb) bits.push(`${(r.memory_kb / 1024).toFixed(1)} MB`);
    if (r.signal) bits.push(esc(r.signal));
    else if (r.exit_code) bits.push(`exit ${r.exit_code}`);
    meta.innerHTML = bits.join('<span class="rv-dot">·</span>');
    const parts = [];
    if (r.stdout) parts.push(r.stdout);
    if (r.stderr) parts.push((r.stdout ? '\n' : '') + '── stderr ──\n' + r.stderr);
    out.classList.toggle('err', bad && !r.stdout);
    out.textContent = parts.join('') || '(no output)';
  }

  // ---------------------------------------------------------------- standalone compiler
  const CC_KEY = 'oaj_compiler_v1';
  const CC_LANGS = [['cpp', 'C++'], ['python', 'Python']];
  const CC_STARTER = {
    cpp: '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n\n    \n    return 0;\n}\n',
    py: '',
  };
  let ccBuilt = false;
  const langBase = (v) => (v === 'cpp' || v === 'c' ? 'cpp' : 'py');

  function ccLoad() { try { return JSON.parse(localStorage.getItem(CC_KEY)) || {}; } catch (e) { return {}; } }
  function ccSave(state) { try { localStorage.setItem(CC_KEY, JSON.stringify(state)); } catch (e) { } }

  function renderCompiler() {
    const host = $('compiler-inner');
    if (ccBuilt) { host.querySelector('.cc-code').focus(); return; }
    ccBuilt = true;
    const saved = ccLoad();
    host.innerHTML =
      `<div class="cc-head">
         <div class="cc-head-main">
           <h1 class="cc-title">Compiler</h1>
           <p class="cc-sub">Compile &amp; run C++ or Python against your own input. Nothing here is graded — a scratch playground in the same sandbox as the judge.</p>
           <div class="cc-env" title="The exact toolchain your code runs on"></div>
         </div>
         <div class="cc-tools">
           <select class="cc-lang" title="Language">${CC_LANGS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>
           <span class="cc-status" aria-live="polite"></span>
           <button class="cc-clear" type="button" title="Reset to a blank template">Reset</button>
           <button class="cc-copy" type="button" title="Copy code to clipboard">Copy</button>
           <button class="cc-run" type="button" title="Compile &amp; run (Ctrl/Cmd+Enter)">Run ▸</button>
         </div>
       </div>
       <div class="cc-grid">
         <div class="cc-pane cc-pane-code">
           <div class="cc-pane-h">Source</div>
           <textarea class="cc-code" spellcheck="false" autocomplete="off" autocapitalize="off" wrap="off"></textarea>
         </div>
         <div class="cc-side">
           <div class="cc-pane cc-pane-in">
             <div class="cc-pane-h">Custom input <span class="cc-pane-sub">stdin</span></div>
             <textarea class="cc-stdin" spellcheck="false" autocomplete="off" wrap="off" placeholder="Type input for your program here…"></textarea>
           </div>
           <div class="cc-pane cc-pane-out">
             <div class="cc-pane-h">Output <span class="cc-run-meta"></span></div>
             <pre class="cc-out" tabindex="0">Run your code to see output here.</pre>
           </div>
         </div>
       </div>`;
    const code = host.querySelector('.cc-code'), lang = host.querySelector('.cc-lang');
    const stdin = host.querySelector('.cc-stdin'), out = host.querySelector('.cc-out');
    const meta = host.querySelector('.cc-run-meta'), status = host.querySelector('.cc-status');
    const run = host.querySelector('.cc-run'), copy = host.querySelector('.cc-copy'), clr = host.querySelector('.cc-clear');
    const env = host.querySelector('.cc-env');
    const showEnv = async () => {
      if (!S.env) { try { S.env = await jget('/api/scratch-env'); } catch (e) { return; } }
      const e = S.env[langBase(lang.value)];
      if (!e) { env.textContent = ''; return; }
      env.textContent = e.std ? e.label + ' · ' + e.std : e.label;
      if (e.full) env.title = e.full;
    };
    lang.value = CC_LANGS.some(([v]) => v === saved.lang) ? saved.lang : 'cpp';
    code.value = saved.code != null ? saved.code : (CC_STARTER[langBase(lang.value)] || '');
    stdin.value = saved.stdin || '';
    const persist = () => ccSave({ lang: lang.value, code: code.value, stdin: stdin.value });
    let t = null;
    const queue = () => { clearTimeout(t); status.textContent = 'Editing…'; t = setTimeout(() => { persist(); status.textContent = 'Saved'; }, 400); };
    const insertTab = (el) => {
      const s = el.selectionStart, e = el.selectionEnd;
      el.value = el.value.slice(0, s) + '    ' + el.value.slice(e);
      el.selectionStart = el.selectionEnd = s + 4;
    };
    code.addEventListener('input', queue);
    stdin.addEventListener('input', queue);
    lang.addEventListener('change', () => {
      if (!code.value.trim()) code.value = CC_STARTER[langBase(lang.value)] || '';
      persist(); showEnv();
    });
    [code, stdin].forEach((el) => el.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doRun(); return; }
      if (e.key === 'Tab') { e.preventDefault(); insertTab(el); queue(); }
    }));
    copy.addEventListener('click', async () => {
      await copyText(code.value);
      copy.textContent = 'Copied ✓'; copy.classList.add('ok');
      setTimeout(() => { copy.textContent = 'Copy'; copy.classList.remove('ok'); }, 1400);
    });
    clr.addEventListener('click', () => {
      code.value = CC_STARTER[langBase(lang.value)] || ''; stdin.value = '';
      out.className = 'cc-out'; out.textContent = 'Run your code to see output here.'; meta.textContent = '';
      persist(); code.focus();
    });
    async function doRun() {
      if (run.dataset.busy) return;
      run.dataset.busy = '1'; run.textContent = 'Running…';
      out.className = 'cc-out'; out.textContent = ''; meta.textContent = 'compiling…';
      persist();
      try {
        const r = await jpost('/api/scratch-run', { lang: lang.value, source: code.value, stdin: stdin.value });
        if (!r.ok) { out.classList.add('err'); out.textContent = r.error || 'Run failed.'; meta.textContent = ''; return; }
        renderRun(r, out, meta);
      } catch (e) {
        out.classList.add('err'); out.textContent = 'Could not reach the runner. Try again.'; meta.textContent = '';
      } finally { run.dataset.busy = ''; run.textContent = 'Run ▸'; }
    }
    run.addEventListener('click', doRun);
    showEnv();
    code.focus();
  }

  async function toggleItem(sid, itemId, el) {
    const data = S.sheets[sid], now = data.progress[itemId] === 'done';
    if (now) delete data.progress[itemId]; else data.progress[itemId] = 'done';
    el.classList.toggle('done', !now); el.textContent = !now ? '✓' : ''; el.setAttribute('aria-pressed', String(!now));
    el.closest('.prob-row').classList.toggle('done', !now);
    data.counts.done = Object.values(data.progress).filter((v) => v === 'done').length;
    setMeter(data);
    refreshRail(sid);
    try { await jpost('/api/sheet-item', now ? { item_id: itemId, clear: true } : { item_id: itemId, status: 'done' }); }
    catch (e) { /* optimistic; reconciles on next load */ }
  }

  function refreshRail(sid) {
    const data = S.sheets[sid], sheet = data.sheet, prog = data.progress;
    $('sheet-rail').querySelectorAll('.rail-topic').forEach((el, i) => {
      const sp = secProgress(sheet.sections[i], prog), pc = sp.total ? Math.round(sp.done / sp.total * 100) : 0;
      el.classList.toggle('complete', sp.total && sp.done === sp.total);
      el.querySelector('.rail-tcount').textContent = `${sp.done}/${sp.total}`;
      el.querySelector('.rail-tfill').style.width = pc + '%';
    });
  }

  // ---------------------------------------------------------------- tracker
  const SITE = { codeforces: 'Codeforces', atcoder: 'AtCoder', leetcode: 'LeetCode', codechef: 'CodeChef',
    'codeforces.com': 'Codeforces', 'atcoder.jp': 'AtCoder', 'leetcode.com': 'LeetCode', 'codechef.com': 'CodeChef' };
  const siteName = (s) => SITE[s] || s;
  const tierName = (r) => r < 1200 ? 'Newbie' : r < 1400 ? 'Pupil' : r < 1600 ? 'Specialist'
    : r < 1900 ? 'Expert' : r < 2100 ? 'Candidate Master' : r < 2300 ? 'Master' : r < 2400 ? 'Int. Master' : 'Grandmaster';
  const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40);
  const fmtDate = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); } catch (e) { return iso; } };
  function fmtWhen(iso) {
    try { const d = new Date(iso), days = Math.round((d - Date.now()) / 864e5);
      const rel = days <= 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days}d`;
      return `<b>${d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</b> · ${rel}`;
    } catch (e) { return iso; }
  }

  // Deterministic contest recommendation: classify a contest, then keep it if it's rated + right-level
  // for the user's current rating band. Pure rules, no AI.
  function contestClass(c) {
    const n = (c.name || '').toLowerCase(), s = c.site || '';
    if (s.includes('atcoder')) return n.includes('beginner') ? 'ABC' : n.includes('regular') ? 'ARC' : n.includes('grand') ? 'AGC' : 'AtCoder';
    if (s.includes('codeforces')) {
      if (/div\.?\s*4/.test(n)) return 'Div4';
      if (/div\.?\s*3/.test(n)) return 'Div3';
      if (/educational/.test(n)) return 'Edu';
      if (/div\.?\s*1\s*\+\s*2|global/.test(n)) return 'Div12';
      if (/div\.?\s*2/.test(n)) return 'Div2';
      if (/div\.?\s*1/.test(n)) return 'Div1';
      return 'CF';
    }
    if (s.includes('codechef')) return 'Starters';
    if (s.includes('leetcode')) return 'LC';
    return 'other';
  }
  function recSet(r) {
    if (r == null || r < 1400) return { ABC: 1, Div4: 1, Div3: 1, Edu: 1, Div12: 1, Starters: 1, LC: 1, AtCoder: 1, CF: 1 };
    if (r < 1600) return { ABC: 1, Div3: 1, Div2: 1, Div12: 1, Edu: 1, Starters: 1 };
    if (r < 1900) return { ABC: 1, ARC: 1, Div2: 1, Div12: 1, Edu: 1, Starters: 1 };
    if (r < 2100) return { ARC: 1, AGC: 1, Div2: 1, Div12: 1, Edu: 1 };
    return { ARC: 1, AGC: 1, Div1: 1, Div12: 1 };
  }
  const CLS_NAME = { ABC: 'AtCoder Beginner', ARC: 'AtCoder Regular', AGC: 'AtCoder Grand', Div4: 'CF Div 4',
    Div3: 'CF Div 3', Div2: 'CF Div 2', Div1: 'CF Div 1', Div12: 'CF Div 1+2', Edu: 'Educational',
    Starters: 'CodeChef Starters', LC: 'LeetCode', AtCoder: 'AtCoder', CF: 'Codeforces' };

  async function loadTracker() {
    const box = $('tracker-inner');
    box.innerHTML = '<div class="tracker-inner"><p class="spinner">Loading your stats…</p></div>';
    let P, C;
    try { [P, C] = await Promise.all([jget('/api/cp/stats'), jget('/api/cp/contests')]); }
    catch (e) { box.innerHTML = '<p class="placeholder">Could not load the tracker.</p>'; return; }
    renderTracker(P, (C && C.contests) || []);
  }

  function renderTracker(P, contests) {
    const box = $('tracker-inner');
    const handles = P.handles || {}, trk = P.tracker || {}, goal = P.goal || {};
    let html = `<div class="sheet-head" style="padding:0 0 6px;border:0">
      <div class="sheet-head-main"><h1 class="sheet-title">Contest Tracker</h1>
      <p class="sheet-sub">Give contests and this tracks whether you're on pace — built automatically from your linked handles, no manual logging. Codeforces powers the on-pace trajectory.</p></div></div>`;

    if (!Object.keys(handles).length) { box.innerHTML = html + emptyState(); wireHandleForm(); return; }

    const v = trk.verdict || 'no-data';
    const vlabel = { ahead: 'Ahead of pace', 'on-track': 'On track', behind: 'Behind pace',
      reached: 'Goal reached', 'no-data': 'Link Codeforces to track' }[v] || v;
    const gapStr = trk.gap != null ? (trk.gap >= 0 ? '+' : '') + trk.gap : '—';
    const yr = String(goal.deadline || '').slice(0, 4);
    // Recommendations: every Codeforces round always qualifies (it's the goal platform), plus any
    // other contest that's rated + right-level for the current rating band.
    const rating = trk.current;
    const _rs = recSet(rating);
    const recs = contests.filter((c) => (c.site || '').includes('codeforces') || _rs[contestClass(c)]).slice(0, 6);
    const recRow = (c) => `<div class="contest-row">
        <div class="contest-when">${fmtWhen(c.start_at)}</div>
        <div class="contest-name"><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a>
          <div class="contest-site">${esc(siteName(c.site))} · ${esc(CLS_NAME[contestClass(c)] || 'contest')}${(c.site || '').includes('codeforces') ? ' · rating platform' : ' · rated for your level'}</div></div>
        <a class="contest-ics" href="${icsHref(c)}" download="${esc(slug(c.name))}.ics" title="Add to calendar">+ .ics</a>
      </div>`;

    html += `<div class="tk-grid">
      <div class="tk-card wide">
        <div class="tk-hero-top">
          <div class="tk-goal-label">Goal: <b>${esc(tierName(goal.target_rating || 1900))}</b> (${goal.target_rating || 1900}) by <b>${fmtDate(goal.deadline)} ${yr}</b></div>
          <span class="tk-verdict ${v}"><span class="vdot"></span>${vlabel}</span>
        </div>
        <div class="tk-stats">
          <div class="tk-stat"><div class="v">${trk.current != null ? trk.current : '—'}</div><div class="l">Current rating</div></div>
          <div class="tk-stat"><div class="v">${trk.expected != null ? trk.expected : '—'}</div><div class="l">Expected today</div></div>
          <div class="tk-stat"><div class="v ${trk.gap >= 0 ? 'pos' : 'neg'}">${gapStr}</div><div class="l">vs pace</div></div>
          <div class="tk-stat"><div class="v">${trk.days_left != null ? trk.days_left : '—'}</div><div class="l">Days to deadline</div></div>
        </div>
        ${trajectoryChart(trk, goal)}
      </div>

      <div class="tk-card wide">
        <h2>Recommended for you</h2>
        <div class="rec-note">Contests that move your rating${rating != null ? ` at ${rating} (${tierName(rating)})` : ''} — every Codeforces round, plus level-matched AtCoder / CodeChef / LeetCode.</div>
        ${recs.length ? recs.map(recRow).join('') : '<p class="tk-muted">No matching contests in the current window — see the full list below.</p>'}
      </div>

      <div class="tk-card"><h2>Contest cadence</h2>
        <div class="cadence"><span class="big">${trk.cadence_per_week != null ? trk.cadence_per_week : 0}</span><span class="unit">contests / week</span></div>
        <div class="cadence-note">${trk.contests_28d || 0} in the last 4 weeks · target <b>${trk.cadence_target || 2}/week</b>. ${(trk.cadence_per_week || 0) >= (trk.cadence_target || 2) ? 'Keeping pace — contests are the rating lever.' : 'Give more rounds — rating comes from contests, not just the sheet.'}</div>
        <div class="cadence-dots">${Array.from({ length: 8 }).map((_, i) => `<i class="${i < Math.min(trk.contests_28d || 0, 8) ? 'on' : ''}"></i>`).join('')}</div>
      </div>

      <div class="tk-card"><h2>Upcoming contests</h2>${contests.length
        ? contests.slice(0, 6).map((c) => `<div class="contest-row">
            <div class="contest-when">${fmtWhen(c.start_at)}</div>
            <div class="contest-name"><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a><div class="contest-site">${esc(siteName(c.site))}</div></div>
            <a class="contest-ics" href="${icsHref(c)}" download="${esc(slug(c.name))}.ics" title="Add to calendar">+ .ics</a>
          </div>`).join('')
        : '<p class="tk-muted">No upcoming contests cached yet — check back shortly.</p>'}</div>

      <div class="tk-card wide" id="tk-handles-card"><h2>Your handles</h2>
        <div class="site-tiles">${siteTiles(P)}</div>
        <div class="tk-row">
          <button class="btn btn-neutral" id="tk-refresh">↻ Refresh</button>
          <button class="btn btn-subtle" id="tk-edit-handles">Edit handles</button>
        </div>
      </div>
    </div>`;

    box.innerHTML = html;
    $('tk-refresh').addEventListener('click', async (e) => { e.target.disabled = true; e.target.textContent = 'Refreshing…'; try { await jpost('/api/cp/sync', {}); } catch (x) {} loadTracker(); });
    $('tk-edit-handles').addEventListener('click', () => {
      if ($('tk-save-handles')) return;
      $('tk-handles-card').insertAdjacentHTML('beforeend', handleFormHtml(handles)); wireHandleForm();
    });
  }

  function siteSub(s, d) {
    if (s === 'codeforces') return [d.max_rating != null ? `max ${d.max_rating}` : '', d.rank || ''].filter(Boolean).join(' · ');
    if (s === 'atcoder') return d.max_rating != null ? `max ${d.max_rating}` : '';
    if (s === 'leetcode') return [d.solved != null ? `${d.solved} solved` : '', d.rating != null ? `rating ${d.rating}` : ''].filter(Boolean).join(' · ');
    if (s === 'codechef') return d.stars != null ? `${d.stars}★` : '';
    return '';
  }
  function siteTiles(P) {
    const order = ['codeforces', 'atcoder', 'leetcode', 'codechef'];
    const tiles = order.filter((s) => P.handles[s]).map((s) => {
      const c = P.stats[s], d = (c && c.data) || {}, ok = !!(c && c.ok && d.ok !== false);
      const main = d.rating != null ? d.rating : (d.solved != null ? d.solved : '—');
      return `<div class="site-tile ${ok ? '' : 'err'}">
        ${c && !ok ? '<span class="site-stale">stale</span>' : ''}
        <div class="site-name">${siteName(s)}</div>
        <div class="site-rating">${main}</div>
        <div class="site-sub">${esc(siteSub(s, d) || (ok ? '' : (d.error || 'unavailable')))}</div>
      </div>`;
    }).join('');
    return tiles || '<p class="tk-muted">No handles linked.</p>';
  }

  function trajectoryChart(trk, goal) {
    if (!trk.start_at || trk.start_rating == null) return '';
    const hist = (trk.history || []).slice();
    const W = 920, H = 190, padL = 40, padR = 16, padT = 16, padB = 26;
    const t0 = new Date(trk.start_at).getTime(), t1 = new Date(goal.deadline).getTime(), span = Math.max(t1 - t0, 1);
    const target = goal.target_rating || 1900, start = trk.start_rating;
    const rr = [start, target].concat(hist.map((h) => h.r)); if (trk.current != null) rr.push(trk.current);
    let rmin = Math.min.apply(null, rr) - 60, rmax = Math.max.apply(null, rr) + 60; if (rmax - rmin < 100) rmax = rmin + 100;
    const x = (t) => padL + ((t - t0) / span) * (W - padL - padR);
    const y = (r) => padT + (1 - (r - rmin) / (rmax - rmin)) * (H - padT - padB);
    const pts = hist.map((h) => [x(new Date(h.t).getTime()), y(h.r)]);
    if (trk.current != null) pts.push([x(Date.now()), y(trk.current)]);
    const actual = pts.length ? 'M ' + pts.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L ') : '';
    const area = pts.length ? actual + ` L ${pts[pts.length - 1][0].toFixed(1)} ${y(rmin).toFixed(1)} L ${pts[0][0].toFixed(1)} ${y(rmin).toFixed(1)} Z` : '';
    return `<svg class="tk-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rating vs target trajectory">
      <line class="axis" x1="${padL}" y1="${y(target).toFixed(1)}" x2="${W - padR}" y2="${y(target).toFixed(1)}"/>
      <text class="lbl" x="4" y="${(y(target) + 3).toFixed(1)}">${target}</text>
      <text class="lbl" x="4" y="${(y(start) + 3).toFixed(1)}">${start}</text>
      ${area ? `<path class="actual-area" d="${area}"/>` : ''}
      <path class="target" d="M ${x(t0).toFixed(1)} ${y(start).toFixed(1)} L ${x(t1).toFixed(1)} ${y(target).toFixed(1)}"/>
      ${actual ? `<path class="actual" d="${actual}"/>` : ''}
      ${pts.map((p) => `<circle class="dot" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3"/>`).join('')}
      <text class="lbl" x="${padL}" y="${H - 7}">${fmtDate(trk.start_at)}</text>
      <text class="lbl" x="${W - padR - 44}" y="${H - 7}">${String(goal.deadline || '').slice(0, 7)}</text>
    </svg>`;
  }

  function icsHref(c) {
    const dt = new Date(c.start_at), end = new Date(dt.getTime() + (c.duration_min || 120) * 60000);
    const f = (d) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//OA Judge//CP//EN', 'BEGIN:VEVENT',
      `DTSTART:${f(dt)}`, `DTEND:${f(end)}`, `SUMMARY:${c.name}`, `URL:${c.url}`, 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
    return 'data:text/calendar;charset=utf-8,' + encodeURIComponent(ics);
  }

  function emptyState() {
    return `<div class="tk-card wide"><div class="tk-empty">
      <h3>Link your competitive-programming handles</h3>
      <p>The tracker builds itself from the contests you give — link a handle and it pulls your rating history automatically.</p>
      ${handleFormHtml({})}
    </div></div>`;
  }
  function handleFormHtml(h) {
    const f = (k, label, ph) => `<label>${label}<input type="text" data-site="${k}" value="${esc(h[k] || '')}" placeholder="${ph}" autocomplete="off" spellcheck="false"></label>`;
    return `<div class="handle-form">
        ${f('codeforces', 'Codeforces', 'handle')}${f('atcoder', 'AtCoder', 'username')}
        ${f('leetcode', 'LeetCode', 'username')}${f('codechef', 'CodeChef', 'username')}
      </div>
      <div class="tk-row"><button class="btn btn-primary" id="tk-save-handles">Save &amp; sync</button><span class="tk-muted" id="tk-save-note"></span></div>`;
  }
  function wireHandleForm() {
    const btn = $('tk-save-handles'); if (!btn) return;
    btn.addEventListener('click', async () => {
      const body = {};
      document.querySelectorAll('.handle-form input[data-site]').forEach((i) => { body[i.dataset.site] = i.value.trim(); });
      btn.disabled = true; btn.textContent = 'Saving…';
      try { await jpost('/api/cp/handles', body); await jpost('/api/cp/sync', {}); } catch (e) {}
      loadTracker();
    });
  }

  // ---------------------------------------------------------------- boot
  function boot() {
    document.querySelectorAll('.topnav-item').forEach((b) => b.addEventListener('click', () => switchView(b.dataset.view)));
    const h = (location.hash || '').replace('#', '');
    if (h === 'cp' || h === 'sd' || h === 'tracker' || h === 'compiler') switchView(h);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
