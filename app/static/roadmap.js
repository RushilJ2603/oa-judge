/* Roadmap — the study plan as something you can DO, not read.

   The research behind this lives in ~280 KB of markdown (DOMAIN_MAP, SUBDOMAINS, RESOURCES,
   ROADMAP). None of that is consumable at 9am on a Tuesday. This turns it into: today's four
   tasks, each with a working link, each with a checkbox. Everything else — the 42-week plan, the
   tier -> domain -> subdomain -> resource graph — is one click away and never in the way.

   Deliberately NOT here: hour logging. Kernel owns that, and two places to log the same hour is
   how both stop being true. This is a checkbox system.

   Rides the same data path as the CP/SD sheets: /api/sheet/roadmap for content + per-user
   progress, /api/sheet-item to tick, /api/sheet-code for the pads. No new tables. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (window.escapeHTML ? window.escapeHTML(String(s == null ? '' : s)) : String(s == null ? '' : s));
  async function jget(p) { const r = await fetch(p); if (!r.ok) throw new Error(r.status); return r.json(); }
  async function jpost(p, b) {
    const r = await fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) });
    return r.json();
  }

  const S = { data: null, prog: {}, mode: 'today', week: null, dom: null, q: '', days: {}, order: [],
              guide: 'OVERVIEW' };

  // ---------------------------------------------------------------- markdown
  // Small on purpose. The guides use a deliberately narrow subset — headings, tables, lists,
  // blockquotes, fenced code, bold/italic/code/links — so a 60-line renderer covers all of it and
  // there is no library to ship. Everything is escaped BEFORE any pattern runs, so no authored
  // content can inject markup.
  function inline(t) {
    return esc(t)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Non-greedy, and NOT [^*]+ — bold containing an italic ("asked *more* at the full-time
      // stage") is common in the guides, and a no-asterisks-inside rule leaves it raw on screen.
      // Bold runs before italic so the inner single asterisks are still there to match.
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]+)\)/g,
               '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  function md(src) {
    const lines = String(src || '').split('\n');
    const out = [];
    let i = 0, list = null, para = [], item = null;
    // The source hard-wraps at 100 columns, so **bold** and [links](…) routinely straddle two
    // lines. Inline formatting therefore runs on the JOINED text of a paragraph or list item, never
    // line by line — doing it per line leaves the asterisks visible on screen.
    const flushPara = () => {
      if (para.length) { out.push(`<p class="gd-p">${inline(para.join(' '))}</p>`); para = []; }
    };
    const flushItem = () => {
      if (item !== null) { out.push(`<li>${inline(item.join(' '))}</li>`); item = null; }
    };
    const closeList = () => {
      flushItem();
      if (list) { out.push(`</${list}>`); list = null; }
    };
    const flushAll = () => { flushPara(); closeList(); };
    while (i < lines.length) {
      const ln = lines[i];
      if (/^```/.test(ln)) {                                     // fenced code
        flushAll();
        const buf = [];
        for (i++; i < lines.length && !/^```/.test(lines[i]); i++) buf.push(lines[i]);
        i++;
        out.push(`<pre class="gd-pre"><code>${esc(buf.join('\n'))}</code></pre>`);
        continue;
      }
      if (/^\|/.test(ln) && /^\|[\s:|-]+\|$/.test(lines[i + 1] || '')) {   // table
        flushAll();
        const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()));
        const head = cells(ln);
        i += 2;
        const body = [];
        for (; i < lines.length && /^\|/.test(lines[i]); i++) body.push(cells(lines[i]));
        out.push(`<div class="gd-tablewrap"><table class="gd-table"><thead><tr>${
          head.map((c) => `<th>${c}</th>`).join('')}</tr></thead><tbody>${
          body.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')
          }</tbody></table></div>`);
        continue;
      }
      let m;
      if ((m = /^(#{1,4})\s+(.*)$/.exec(ln))) {
        flushAll(); out.push(`<h${m[1].length} class="gd-h${m[1].length}">${inline(m[2])}</h${m[1].length}>`);
      } else if (/^---+$/.test(ln.trim())) {
        flushAll(); out.push('<hr class="gd-hr">');
      } else if (/^>\s?/.test(ln)) {                             // blockquote, possibly wrapped
        flushAll();
        const buf = [];
        for (; i < lines.length && /^>\s?/.test(lines[i]); i++) buf.push(lines[i].replace(/^>\s?/, ''));
        out.push(`<blockquote class="gd-quote">${inline(buf.join(' '))}</blockquote>`);
        continue;
      } else if ((m = /^[-*]\s+(.*)$/.exec(ln))) {
        flushPara(); flushItem();
        if (list !== 'ul') { closeList(); out.push('<ul class="gd-ul">'); list = 'ul'; }
        item = [m[1]];
      } else if ((m = /^\d+\.\s+(.*)$/.exec(ln))) {
        flushPara(); flushItem();
        if (list !== 'ol') { closeList(); out.push('<ol class="gd-ol">'); list = 'ol'; }
        item = [m[1]];
      } else if (!ln.trim()) {
        flushAll();
      } else if (item !== null) {
        item.push(ln.trim());                                    // wrapped list item
      } else {
        para.push(ln.trim());                                    // wrapped paragraph
      }
      i++;
    }
    flushAll();
    return out.join('\n');
  }

  const iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const today = () => iso(new Date());
  const long = (s) => new Date(s + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const short = (s) => new Date(s + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

  // ---------------------------------------------------------------- load
  async function load() {
    if (S.data) return true;
    $('rd-body').innerHTML = '<p class="spinner">Loading the plan…</p>';
    try {
      const d = await jget('/api/sheet/roadmap');
      S.data = d.sheet; S.prog = d.progress || {};
    } catch (e) {
      $('rd-body').innerHTML = '<p class="placeholder">Could not load the roadmap.</p>';
      return false;
    }
    S.data.sections.forEach((sec) => sec.items.forEach((it) => {
      (S.days[it.date] || (S.days[it.date] = [])).push(it);
    }));
    S.order = Object.keys(S.days).sort();
    return true;
  }

  // The plan runs 8 Aug 2026 -> 31 May 2027. Outside that window "today" is meaningless, so clamp
  // to the nearest real day rather than showing an empty page.
  function anchorDate() {
    const t = today();
    if (S.days[t]) return t;
    if (t < S.order[0]) return S.order[0];
    if (t > S.order[S.order.length - 1]) return S.order[S.order.length - 1];
    return S.order.find((d) => d >= t) || S.order[0];
  }

  function weekOf(date) {
    return S.data.sections.find((sec) => sec.days.indexOf(date) >= 0) || S.data.sections[0];
  }
  function sprintOf(sid) { return S.data.sprints.find((s) => s.id === sid); }

  function count(items) {
    const done = items.filter((i) => S.prog[i.id] === 'done').length;
    return { done, total: items.length, h: items.reduce((a, b) => a + b.h, 0) };
  }

  // ---------------------------------------------------------------- render
  async function render() {
    if (!(await load())) return;
    const all = S.data.sections.reduce((a, s) => a.concat(s.items), []);
    const c = count(all);
    $('rd-title').textContent = S.data.title;
    $('rd-sub').textContent = S.data.subtitle;
    $('rd-meter').innerHTML =
      `<div class="m-num"><b>${c.done}</b> / ${c.total} tasks</div>
       <div class="m-bar"><div class="m-fill" style="width:${c.total ? (c.done / c.total * 100).toFixed(1) : 0}%"></div></div>`;
    document.querySelectorAll('.rd-mode').forEach((b) => b.classList.toggle('active', b.dataset.mode === S.mode));
    if (S.mode === 'today') renderToday();
    else if (S.mode === 'plan') renderPlan();
    else if (S.mode === 'guide') renderGuide();
    else renderMap();
  }

  // ---------------------------------------------------------------- guide
  // The written plan: one page per subject, plus the whole-plan overview. Everything else in this
  // tab tells you WHAT to do today; this is the only place that says why, in what order, and how
  // the resources fit together.
  function renderGuide() {
    const briefs = S.data.briefs || {};
    const byCode = {};
    S.data.graph.forEach((g) => { byCode[g.code] = g; });
    // Built from the GUIDES, not from the graph: the subjects delivered inside a project carry no
    // scheduled hours and so never appear in the graph, but they still have something to read.
    const codes = Object.keys(briefs).filter((c) => c !== 'OVERVIEW').sort((a, b) => {
      const ga = byCode[a], gb = byCode[b];
      return (ga ? ga.tier : 9) - (gb ? gb.tier : 9)
          || (gb ? gb.planned : 0) - (ga ? ga.planned : 0) || a.localeCompare(b);
    });
    const seen = new Set();
    let rail = `<div class="rail-topic ${S.guide === 'OVERVIEW' ? 'active' : ''}" data-g="OVERVIEW">
        <div class="rail-trow"><span class="rail-tname"><b>The whole plan</b></span></div></div>
      <div class="rail-section-h">By subject</div>`;
    codes.forEach((c) => {
      if (seen.has(briefs[c])) return;        // the four coursework subjects share one guide
      seen.add(briefs[c]);
      const g = byCode[c];
      const name = (g && g.short) || (md(briefs[c]).match(/<h1[^>]*>(.*?)<\/h1>/) || [, c])[1];
      rail += `<div class="rail-topic ${S.guide === c ? 'active' : ''}" data-g="${esc(c)}">
        <div class="rail-trow"><span class="rail-tname">${name}</span>
          <span class="rail-tcount">${g && g.planned ? g.planned + ' h' : 'in a project'}</span>
        </div></div>`;
    });

    const cur = briefs[S.guide] ? S.guide : 'OVERVIEW';
    const d = byCode[cur];
    $('rd-body').innerHTML = `<div class="sheet-body rd-split">
        <aside class="sheet-rail" id="rd-rail">${rail}</aside>
        <div class="sheet-content gd-doc" id="rd-content">
          ${d ? `<div class="gd-jump">
            <button class="rd-open" data-jump="map" data-dom="${esc(d.code)}">See it in the map ↗</button>
            <button class="rd-open" data-jump="plan">Find it in the plan ↗</button></div>` : ''}
          ${md(briefs[cur])}</div></div>`;
    $('rd-rail').querySelectorAll('[data-g]').forEach((el) => el.addEventListener('click', () => {
      S.guide = el.dataset.g; render();
      const c = $('rd-content'); if (c) c.scrollTop = 0;
    }));
    $('rd-body').querySelectorAll('[data-jump]').forEach((el) => el.addEventListener('click', () => {
      if (el.dataset.jump === 'map') { S.dom = el.dataset.dom; S.mode = 'map'; }
      else { S.q = (d && d.short) || ''; S.mode = 'plan'; const s = $('rd-search'); if (s) s.value = S.q; }
      render();
    }));
  }

  // ---------------------------------------------------------------- today
  function renderToday() {
    const date = anchorDate(), sec = weekOf(date), sp = sprintOf(sec.sprint);
    const items = S.days[date] || [], c = count(items);
    const cp = S.data.checkpoints[date];
    const late = date !== today();

    $('rd-body').innerHTML = `
      <div class="rd-today">
        <div class="rd-hero">
          <div>
            <div class="rd-hero-date">${esc(long(date))}</div>
            <div class="rd-hero-ctx">${esc(sec.sprint)} · week ${sec.week} of ${S.data.sections.length}
              · <span class="rd-depth">${esc(sp ? sp.depth : '')}</span></div>
          </div>
          <div class="rd-hero-load">
            <div class="rd-hero-h">${c.h.toFixed(1)}<span>h</span></div>
            <div class="rd-hero-n">${c.done}/${c.total} done</div>
          </div>
        </div>
        ${late ? `<div class="rd-banner soft">Today is outside the plan window — showing ${esc(short(date))}, the nearest planned day.</div>` : ''}
        ${cp ? `<div class="rd-banner"><b>${esc(cp[0])}</b> ${esc(cp[1])}</div>` : ''}
        ${sp && sec.summary ? `<div class="rd-note">${esc(sec.summary)}</div>` : ''}
        <div class="rd-tasks">${items.map(taskRow).join('') || '<p class="placeholder">Nothing planned.</p>'}</div>
        <div class="rd-weekstrip">${sec.days.map((d) => {
          const dc = count(S.days[d] || []);
          const cls = d === date ? 'now' : (d < today() ? 'past' : '');
          const full = dc.total && dc.done === dc.total;
          return `<button class="rd-chip ${cls} ${full ? 'full' : ''}" data-goto="${d}">
            <span class="rd-chip-d">${esc(new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' }))}</span>
            <span class="rd-chip-n">${new Date(d + 'T00:00:00').getDate()}</span>
            <span class="rd-chip-h">${dc.h.toFixed(1)}h</span>
            <span class="rd-chip-p">${dc.done}/${dc.total}</span></button>`;
        }).join('')}</div>
        <div class="rd-rules">
          <div class="rd-rules-h">Standing rules — every week, all 42</div>
          <ol>${S.data.rules.map((r) => `<li>${esc(r)}</li>`).join('')}</ol>
        </div>
      </div>`;
    wire();
    $('rd-body').querySelectorAll('[data-goto]').forEach((b) => b.addEventListener('click', () => {
      S.mode = 'plan'; S.week = weekOf(b.dataset.goto).week; render();
      requestAnimationFrame(() => { const el = $('day-' + b.dataset.goto); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); });
    }));
  }

  // ---------------------------------------------------------------- one task
  function taskRow(it) {
    const done = S.prog[it.id] === 'done';
    const sub = [it.res, it.span, it.pos].filter(Boolean).join(' · ');
    const link = it.url
      ? `<a class="rd-open" href="${esc(it.url)}" target="_blank" rel="noopener"
            title="${esc(it.at || it.url)}">${it.url.indexOf('/notes/') === 0 ? 'Notes' : 'Open'} ↗</a>` : '';
    const pad = it.code
      ? `<button class="prob-code-btn" data-item="${esc(it.id)}" aria-expanded="false" title="Scratch pad — same sandbox as the judge">Code</button>` : '';
    return `<div class="prob-item rd-task" data-item="${esc(it.id)}">
      <div class="rd-task-row ${done ? 'done' : ''}">
        <button class="prob-check ${done ? 'done' : ''}" data-item="${esc(it.id)}" aria-pressed="${done}" title="Mark done">${done ? '✓' : ''}</button>
        <span class="rd-dom" style="--dc:${esc(it.color)}" title="${esc(it.dname)}">${esc(it.label)}</span>
        <span class="rd-role ${esc(it.role || '')}" title="${it.role === 'practice'
            ? 'Practice — something other than you says whether you were right'
            : it.role === 'ref' ? 'Reference — look-up only, never read front to back'
            : 'Learn — where the knowledge comes from'}">${esc((it.role || 'learn').toUpperCase())}</span>
        <span class="rd-h">${it.h}h</span>
        <div class="rd-task-main">
          <div class="rd-task-title"><span class="rd-verb">${esc(it.verb)}</span> ${esc(it.title)}</div>
          ${sub ? `<div class="rd-task-sub">${esc(sub)}</div>` : ''}
          ${it.leaf ? `<div class="rd-task-leaf">${esc(it.dname)} → ${esc(it.leaf)}${it.at ? ` · <span class="rd-at">${esc(it.at)}</span>` : ''}</div>` : ''}
          ${it.note ? `<div class="rd-task-note">${esc(it.note)}</div>` : ''}
          ${!it.note && it.how ? `<div class="rd-task-note how"><b>How to use it</b> ${esc(it.how)}</div>` : ''}
        </div>
        <div class="rd-task-side">${link}${pad}</div>
      </div>
      <div class="prob-pad" hidden></div>
    </div>`;
  }

  function wire() {
    const b = $('rd-body');
    b.querySelectorAll('.prob-check').forEach((el) => el.addEventListener('click', () => toggle(el.dataset.item, el)));
    b.querySelectorAll('.prob-code-btn').forEach((el) => el.addEventListener('click', () => {
      if (window.OAPad) window.OAPad.toggle(el);
    }));
  }

  async function toggle(id, el) {
    const now = S.prog[id] === 'done';
    if (now) { delete S.prog[id]; } else { S.prog[id] = 'done'; }
    el.classList.toggle('done', !now);
    el.textContent = now ? '' : '✓';
    el.setAttribute('aria-pressed', String(!now));
    const row = el.closest('.rd-task-row') || el.closest('.rd-task');
    if (row) row.classList.toggle('done', !now);
    try { await jpost('/api/sheet-item', { item_id: id, clear: now ? 1 : 0, status: 'done' }); }
    catch (e) { /* optimistic; the next load re-syncs */ }
    // Counters elsewhere on the page are now stale — refresh them without re-rendering the row.
    const all = S.data.sections.reduce((a, s) => a.concat(s.items), []);
    const c = count(all);
    const m = $('rd-meter');
    if (m) m.innerHTML = `<div class="m-num"><b>${c.done}</b> / ${c.total} tasks</div>
      <div class="m-bar"><div class="m-fill" style="width:${(c.done / c.total * 100).toFixed(1)}%"></div></div>`;
  }

  // ---------------------------------------------------------------- plan (week rail + day cards)
  function renderPlan() {
    if (S.week == null) S.week = weekOf(anchorDate()).week;
    const q = S.q.trim().toLowerCase();
    let rail = '', lastGroup = null;
    S.data.sections.forEach((sec) => {
      const c = count(sec.items), pc = c.total ? Math.round(c.done / c.total * 100) : 0;
      if (sec.group !== lastGroup) { rail += `<div class="rail-section-h">${esc(sec.group)}</div>`; lastGroup = sec.group; }
      rail += `<div class="rail-topic ${sec.week === S.week ? 'active' : ''} ${c.done === c.total ? 'complete' : ''}" data-week="${sec.week}">
        <div class="rail-trow"><span class="rail-step ${c.done === c.total ? 'done' : ''}">${c.done === c.total ? '✓' : sec.week}</span>
          <span class="rail-tname">${esc(sec.title.replace(/^Week \d+ · /, ''))}</span>
          <span class="rail-tcount">${c.done}/${c.total}</span></div>
        <div class="rail-tbar"><div class="rail-tfill" style="width:${pc}%"></div></div></div>`;
    });

    let content;
    if (q) {
      const hits = S.data.sections.reduce((a, s) => a.concat(s.items), [])
        .filter((it) => (it.title + ' ' + it.res + ' ' + it.leaf + ' ' + it.dname + ' ' + it.label).toLowerCase().indexOf(q) >= 0);
      content = `<h2 class="topic-h">${hits.length} task${hits.length === 1 ? '' : 's'} match “${esc(S.q)}”</h2>
        <p class="topic-summary">Every day this appears in, across all 42 weeks.</p>
        ${hits.slice(0, 300).map((it) => `<div class="rd-dayline">${esc(short(it.date))}</div>${taskRow(it)}`).join('')}`;
    } else {
      const sec = S.data.sections.find((s) => s.week === S.week) || S.data.sections[0];
      const sp = sprintOf(sec.sprint), c = count(sec.items);
      content = `<h2 class="topic-h">${esc(sec.title)}</h2>
        <div class="topic-meta"><span class="tm">${esc(sec.group)}</span>
          <span class="tm">${c.h.toFixed(1)} h planned</span><span class="tm">${c.done}/${c.total} done</span></div>
        ${sec.summary ? `<p class="topic-summary">${esc(sec.summary)}</p>` : ''}
        ${sp ? `<div class="rd-alloc">${Object.keys(sp.alloc).map((k) =>
            `<span class="rd-alloc-i"><b>${esc(k)}</b> ${sp.alloc[k]}</span>`).join('')}
            <span class="rd-alloc-note">h/week this sprint</span></div>` : ''}
        ${sec.days.map((d) => {
          const its = S.days[d] || [], dc = count(its);
          const cp = S.data.checkpoints[d];
          return `<div class="rd-day ${d === today() ? 'is-today' : ''}" id="day-${d}">
            <div class="rd-day-h"><span class="rd-day-name">${esc(short(d))}</span>
              <span class="rd-day-meta">${dc.h.toFixed(1)} h · ${dc.done}/${dc.total}</span></div>
            ${cp ? `<div class="rd-banner"><b>${esc(cp[0])}</b> ${esc(cp[1])}</div>` : ''}
            ${its.map(taskRow).join('')}</div>`;
        }).join('')}`;
    }

    $('rd-body').innerHTML = `<div class="sheet-body rd-split">
        <aside class="sheet-rail" id="rd-rail">${rail}</aside>
        <div class="sheet-content" id="rd-content">${content}</div></div>`;
    wire();
    $('rd-rail').querySelectorAll('.rail-topic').forEach((el) => el.addEventListener('click', () => {
      S.week = +el.dataset.week; S.q = ''; const s = $('rd-search'); if (s) s.value = '';
      render();
    }));
    const act = $('rd-rail').querySelector('.rail-topic.active');
    if (act) act.scrollIntoView({ block: 'center' });
  }

  // ---------------------------------------------------------------- map (tier → domain → resource)
  const TIER_NAME = ['Tier 0 · the gate', 'Tier 1 · every OA', 'Tier 2 · every interview',
    'Tier 3 · situational', 'Tier 4 · your degree', 'Tier 5 · build phase', 'Tier 6 · your resume'];

  function renderMap() {
    const doms = S.data.graph.slice().sort((a, b) => a.tier - b.tier || b.planned - a.planned);
    // Progress per domain comes from the tasks, not a second checkbox: a domain is as done as the
    // hours you have actually ticked off in it.
    const hrs = {};
    S.data.sections.forEach((sec) => sec.items.forEach((it) => {
      const r = hrs[it.dcode] || (hrs[it.dcode] = { done: 0, total: 0 });
      r.total += it.h; if (S.prog[it.id] === 'done') r.done += it.h;
    }));

    const ROW = 30, GAP = 8, PADT = 22;
    const blocks = []; let y = PADT;
    doms.forEach((d) => {
      const rn = Math.max(1, d.resources.length);
      const h = rn * ROW + (rn - 1) * GAP;
      blocks.push({ d, top: y, h, mid: y + h / 2 });
      y += h + 26;
    });
    const H = y + 20, W = 980;
    const COL = { tier: 78, dom: 250, res: 560 };
    const tiers = [];
    blocks.forEach((b) => {
      const t = tiers.find((x) => x.tier === b.d.tier);
      if (t) { t.lo = Math.min(t.lo, b.mid); t.hi = Math.max(t.hi, b.mid); t.n++; }
      else tiers.push({ tier: b.d.tier, lo: b.mid, hi: b.mid, n: 1 });
    });

    const curve = (x1, y1, x2, y2) => {
      const dx = Math.max(30, (x2 - x1) * 0.45);
      return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
    };
    let svg = '';
    tiers.forEach((t) => {
      const my = (t.lo + t.hi) / 2;
      svg += `<text class="rd-tier" x="6" y="${(my - 8).toFixed(1)}">${esc(TIER_NAME[t.tier] || 'Tier ' + t.tier)}</text>`;
      svg += `<line class="rd-tierline" x1="6" y1="${(my - 2).toFixed(1)}" x2="${COL.tier}" y2="${(my - 2).toFixed(1)}"/>`;
      blocks.filter((b) => b.d.tier === t.tier).forEach((b) => {
        svg += `<path class="rd-edge" d="${curve(COL.tier, my - 2, COL.dom - 4, b.mid)}"/>`;
      });
    });
    blocks.forEach((b) => {
      const p = hrs[b.d.code] || { done: 0, total: 1 };
      const pct = p.total ? p.done / p.total : 0;
      const sel = S.dom === b.d.code;
      b.d.resources.forEach((r, i) => {
        const ry = b.top + ROW / 2 + i * (ROW + GAP);
        svg += `<path class="rd-edge ${sel ? 'on' : ''}" d="${curve(COL.dom + 196, b.mid, COL.res - 4, ry)}"/>`;
        svg += `<g class="rd-res" data-url="${esc(r.url)}" transform="translate(${COL.res},${(ry - ROW / 2).toFixed(1)})">
          <rect width="380" height="${ROW}" rx="7" class="${r.url ? 'has-link' : ''}"/>
          <text x="10" y="${ROW / 2 + 4}">${esc(r.name.length > 46 ? r.name.slice(0, 45) + '…' : r.name)}</text>
          <text class="rd-res-h" x="370" y="${ROW / 2 + 4}" text-anchor="end">${r.hrs}h</text></g>`;
      });
      svg += `<g class="rd-node ${sel ? 'sel' : ''}" data-dom="${esc(b.d.code)}" transform="translate(${COL.dom},${(b.mid - 19).toFixed(1)})">
        <rect width="196" height="38" rx="9" style="--dc:${esc(b.d.color)}"/>
        <text class="rd-node-t" x="11" y="16">${esc(b.d.code)} · ${esc(b.d.name.length > 22 ? b.d.name.slice(0, 21) + '…' : b.d.name)}</text>
        <text class="rd-node-s" x="11" y="30">${b.d.planned} h · ${b.d.leaves.length} subdomains</text>
        <rect class="rd-node-bar" x="0" y="36" width="196" height="2.5" rx="1.5"/>
        <rect class="rd-node-fill" x="0" y="36" width="${(196 * pct).toFixed(1)}" height="2.5" rx="1.5" style="--dc:${esc(b.d.color)}"/>
      </g>`;
    });

    const d = S.dom ? doms.find((x) => x.code === S.dom) : null;
    $('rd-body').innerHTML = `<div class="rd-maparea">
      <div class="rd-mapscroll"><svg class="rd-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${svg}</svg></div>
      <aside class="rd-detail">${d ? domDetail(d, hrs[d.code]) : `
        <div class="rd-detail-empty"><h3>Pick a domain</h3>
        <p>Every node carries its subdomains and its approved resources — the whole
        <code>SUBDOMAINS</code> tree and <code>RESOURCES</code> shortlist, clickable.</p>
        <p class="rd-detail-stat"><b>${doms.length}</b> domains · <b>${doms.reduce((a, x) => a + x.leaves.length, 0)}</b>
        subdomains · <b>${doms.reduce((a, x) => a + x.resources.length, 0)}</b> resources</p></div>`}</aside>
    </div>`;
    $('rd-body').querySelectorAll('.rd-node').forEach((el) => el.addEventListener('click', () => {
      S.dom = S.dom === el.dataset.dom ? null : el.dataset.dom; renderMap();
    }));
    $('rd-body').querySelectorAll('.rd-res').forEach((el) => el.addEventListener('click', () => {
      if (el.dataset.url) window.open(el.dataset.url, '_blank', 'noopener');
    }));
    $('rd-body').querySelectorAll('[data-read]').forEach((el) => el.addEventListener('click', () => {
      S.guide = el.dataset.read; S.mode = 'guide'; render();
    }));
  }

  function domDetail(d, p) {
    const pct = p && p.total ? Math.round(p.done / p.total * 100) : 0;
    return `<div class="rd-detail-h" style="--dc:${esc(d.color)}">
        <div class="rd-detail-code">${esc(d.code)}</div>
        <div><h3>${esc(d.name)}</h3>
          <div class="rd-detail-meta">${esc(TIER_NAME[d.tier] || '')} · ${d.planned} h planned · ${pct}% ticked</div></div>
      </div>
      ${S.data.briefs && S.data.briefs[d.code]
        ? `<button class="rd-open gd-readbtn" data-read="${esc(d.code)}">Read the guide for this subject ↗</button>` : ''}
      ${['learn', 'practice', 'ref'].map((role) => {
        const rs = d.resources.filter((r) => (r.role || 'learn') === role);
        if (!rs.length) return '';
        const label = { learn: 'Learn', practice: 'Practice', ref: 'Reference' }[role];
        const why = { learn: 'where the knowledge comes from',
                      practice: 'something else says whether you were right',
                      ref: 'look-up only — never read front to back' }[role];
        return `<div class="rd-detail-sec">${label} <span>${rs.length}</span>
            <div class="rd-detail-why">${why}</div></div>
          ${rs.map((r) => `<div class="rd-rrow ${esc(role)}">
            ${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)} ↗</a>`
                    : `<span>${esc(r.name)}</span>`}
            <div class="rd-rmeta">${r.hrs ? `${r.hrs} h` : 'no scheduled hours'}${r.total ? ` · ${r.total} ${esc(r.unit)}` : ''}</div>
            ${r.how ? `<div class="rd-rhow">${esc(r.how)}</div>` : ''}
          </div>`).join('')}`;
      }).join('')}
      <div class="rd-detail-sec">Subdomains <span>${d.leaves.length}</span></div>
      <div class="rd-leaves">${d.leaves.map((l) => l.url
        ? `<a class="rd-leaf has" href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.at)}">${esc(l.name)}</a>`
        : `<span class="rd-leaf">${esc(l.name)}</span>`).join('')}</div>
      ${d.notes ? `<div class="rd-detail-foot">Linked subdomains open your own notes at the section.
        <a href="/notes/${esc(d.notes)}.pdf" target="_blank" rel="noopener">Open the whole PDF ↗</a></div>` : ''}`;
  }

  // ---------------------------------------------------------------- boot
  function boot() {
    document.querySelectorAll('.rd-mode').forEach((b) => b.addEventListener('click', () => {
      S.mode = b.dataset.mode; render();
    }));
    const s = $('rd-search');
    if (s) {
      let t = null;
      s.addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => { S.q = s.value; S.mode = 'plan'; render(); s.focus(); }, 200);
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();

  window.OARoadmap = { render, setMode: (m) => { S.mode = m; return render(); } };
})();
