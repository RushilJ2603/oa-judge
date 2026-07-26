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
    const sv = $('sheet-view'), tv = $('tracker-view'), bc = $('breadcrumb');
    if (ws) ws.style.display = view === 'judge' ? '' : 'none';
    if (sv) sv.style.display = (view === 'cp' || view === 'sd') ? 'flex' : 'none';
    if (tv) tv.style.display = view === 'tracker' ? 'block' : 'none';
    if (bc) bc.style.display = view === 'judge' ? '' : 'none';
    try { history.replaceState(null, '', view === 'judge' ? location.pathname : '#' + view); } catch (e) {}
    if (view === 'cp') loadSheet('cp');
    else if (view === 'sd') loadSheet('sd');
    else if (view === 'tracker') loadTracker();
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
    $('sheet-rail').innerHTML = sheet.sections.map((sec, i) => {
      const sp = secProgress(sec, prog), pc = sp.total ? Math.round(sp.done / sp.total * 100) : 0;
      const complete = sp.total && sp.done === sp.total;
      return `<div class="rail-topic ${i === active ? 'active' : ''} ${complete ? 'complete' : ''}" data-idx="${i}">
        <div class="rail-trow"><span class="rail-tname">${esc(sec.title)}</span><span class="rail-tcount">${sp.done}/${sp.total}</span></div>
        <div class="rail-tbar"><div class="rail-tfill" style="width:${pc}%"></div></div>
      </div>`;
    }).join('');
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
    const group = (label, items) => items.length
      ? `<div class="tier-group">${label ? `<div class="tier-label">${label}</div>` : ''}${items.map((it) => row(it, prog)).join('')}</div>` : '';
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
    $('sheet-content').querySelectorAll('.prob-check').forEach((el) =>
      el.addEventListener('click', () => toggleItem(sid, el.dataset.item, el)));
  }

  function row(it, prog) {
    const done = prog[it.id] === 'done';
    const rb = it.rating != null ? `<span class="rating-badge" style="background:${ratingColor(it.rating)}">${it.rating}</span>` : '';
    const tier = it.tier ? `<span class="tier-pill ${esc(it.tier)}">${esc(it.tier)}</span>` : '';
    return `<div class="prob-row ${done ? 'done' : ''}">
      <button class="prob-check ${done ? 'done' : ''}" data-item="${esc(it.id)}" title="Mark solved" aria-pressed="${done}">${done ? '✓' : ''}</button>
      <div class="prob-main">
        <a class="prob-title" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a>
        ${it.tag ? `<div class="prob-tag">${esc(it.tag)}</div>` : ''}
      </div>
      <div class="prob-side">${rb}<span class="plat-badge">${esc(it.platform || '')}</span>${tier}</div>
    </div>`;
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
    if (h === 'cp' || h === 'sd' || h === 'tracker') switchView(h);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
