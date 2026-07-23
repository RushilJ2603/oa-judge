'use strict';

const state = {
    problems: [],
    history: { attempts: [], revisit: [] },
    currentProblemId: null,
    currentProblemData: null,
    oaStartTime: null,
    oaTimerInterval: null,
    submittedInOa: false,
    prevLang: null,
    oaSessionId: null,
};

const els = {
    problemList: document.getElementById('problem-list'),
    breadcrumb: document.getElementById('breadcrumb'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    langSelect: document.getElementById('lang-select'),
    modeRadios: document.getElementsByName('mode'),
    oaTimer: document.getElementById('oa-timer'),
    themeToggle: document.getElementById('theme-toggle'),
    monacoHost: document.getElementById('monaco-host'),
    saveStatus: document.getElementById('save-status'),
    btnRun: document.getElementById('btn-run'),
    btnSubmit: document.getElementById('btn-submit'),
    btnStress: document.getElementById('btn-stress'),
    btnResetOa: document.getElementById('btn-reset-oa'),
    btnResetStub: document.getElementById('btn-reset-stub'),
    btnCustomInputToggle: document.getElementById('btn-custom-input-toggle'),
    customInputDrawer: document.getElementById('custom-input-drawer'),
    resultDrawer: document.getElementById('result-drawer'),
    customStdin: document.getElementById('custom-stdin'),
    console: document.getElementById('console'),
    sidebar: document.getElementById('sidebar'),
    sidebarToggle: document.getElementById('sidebar-toggle'),
    divider: document.getElementById('divider'),
    leftPane: document.getElementById('left-pane'),
    drawerTitle: document.getElementById('drawer-title'),
    btnStats: document.getElementById('btn-stats'),
    btnSync: document.getElementById('btn-sync'),
    btnAddProblem: document.getElementById('btn-add-problem'),
    btnHistory: document.getElementById('btn-history'),
    attemptsCount: document.getElementById('attempts-count'),
    tabAttempts: document.getElementById('tab-attempts'),
    tabNotes: document.getElementById('tab-notes'),
    modalOverlay: document.getElementById('modal-overlay'),
    modalTitle: document.getElementById('modal-title'),
    modalActions: document.getElementById('modal-actions'),
    modalBody: document.getElementById('modal-body'),
    modalClose: document.getElementById('modal-close'),
};

const LANG_MAP = { cpp: 'C++17', py: 'Python 3' };

/* ============================ editor bridge ============================ */
/* Syntax highlighting, line numbers, auto-indent and caret handling all moved into Monaco
 * (see editor.js). The hand-written tokenizer + transparent-textarea overlay that used to
 * live here is deleted: it required two DOM layers to lay out identically to the pixel, and
 * any disagreement drifted the caret off the text. What remains is draft persistence. */

const AUTOSAVE_MS = 1200;        // debounce after the last keystroke
const SNAPSHOT_MS = 120000;      // periodic version for the draft scrubber
let saveTimer = null;
let snapshotTimer = null;

function setSaveStatus(text, cls) {
    if (!els.saveStatus) return;
    els.saveStatus.textContent = text;
    els.saveStatus.className = 'save-status' + (cls ? ' ' + cls : '');
}

/* Drafts live in the SQLite DB on the server. localStorage is kept only as an offline
 * fallback: it is partitioned per origin, so the 5000 -> 5137 port move stranded everything
 * written before it, and it holds no history. */
function saveDraftNow() {
    if (!state.currentProblemId || !window.OAEditor || !OAEditor.isReady()) return;
    const lang = els.langSelect.value;
    const source = OAEditor.getValue();
    localStorage.setItem(`${state.currentProblemId}:${lang}`, source);   // fallback copy
    setSaveStatus('saving…');
    api(`/api/draft/${state.currentProblemId}/${lang}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, cursor_pos: OAEditor.getCursorOffset() }),
    }).then(() => setSaveStatus('saved', 'ok'))
      .catch(() => setSaveStatus('offline — saved locally', 'warn'));
}

function scheduleSave() {
    setSaveStatus('editing…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraftNow, AUTOSAVE_MS);
}

/* A point-in-time copy so half-written code can be replayed later. The server drops a
 * snapshot identical to the previous one, so idle time costs nothing. */
function snapshotNow(reason) {
    if (!state.currentProblemId || !window.OAEditor || !OAEditor.isReady()) return Promise.resolve();
    const source = OAEditor.getValue();
    if (!source.trim()) return Promise.resolve();
    return api('/api/snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            problem_id: state.currentProblemId,
            language: els.langSelect.value,
            source, reason,
        }),
    }).catch(() => { /* snapshots are best-effort; never block the user */ });
}

/* Flush before the tab closes so the last few seconds of typing are not lost. */
function flushOnExit() {
    if (!state.currentProblemId || !window.OAEditor || !OAEditor.isReady()) return;
    const lang = els.langSelect.value;
    const body = JSON.stringify({ source: OAEditor.getValue(),
                                  cursor_pos: OAEditor.getCursorOffset() });
    // fetch() is cancelled on unload; sendBeacon is not.
    if (navigator.sendBeacon) {
        navigator.sendBeacon(`/api/draft/${state.currentProblemId}/${lang}`,
                             new Blob([body], { type: 'application/json' }));
    }
}

/* ============================ setup ============================ */
async function api(path, options = {}) {
    const res = await fetch(path, options);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

function init() {
    setupTheme();
    setupEventListeners();
    fetchProblemsAndHistory();
}

function setupTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
    els.themeToggle.addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme');
        const isDark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
        const next = isDark ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        if (window.OAEditor && OAEditor.isReady()) OAEditor.setTheme(next === 'dark');
    });
}

function setupEventListeners() {
    els.tabBtns.forEach(btn => btn.addEventListener('click', () => {
        els.tabBtns.forEach(b => b.classList.remove('active'));
        els.tabContents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        if (btn.dataset.tab === 'attempts') renderAttemptsTab();
        if (btn.dataset.tab === 'notes') renderNotesTab();
    }));

    els.btnStats.addEventListener('click', openStats);
    els.btnSync.addEventListener('click', syncBank);
    els.btnAddProblem.addEventListener('click', openAuthoring);
    els.btnHistory.addEventListener('click', openDraftScrubber);
    els.modalClose.addEventListener('click', closeModal);
    els.modalOverlay.addEventListener('click', (e) => { if (e.target === els.modalOverlay) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

    // Monaco handles typing, indentation, paste and Tab natively — no keydown gymnastics.
    OAEditor.init(els.monacoHost, {
        language: 'cpp',
        dark: !isLightTheme(),
    }).then(() => {
        OAEditor.onChange(scheduleSave);
        OAEditor.addSubmitShortcut(() => { if (!els.btnSubmit.disabled) els.btnSubmit.click(); });
        snapshotTimer = setInterval(() => snapshotNow('periodic'), SNAPSHOT_MS);
        // The editor became usable after the problem may already have loaded.
        if (state.currentProblemData) loadSourceForLanguage('initial');
    });

    window.addEventListener('beforeunload', flushOnExit);

    els.langSelect.addEventListener('change', () => loadSourceForLanguage('switch'));
    els.modeRadios.forEach(r => r.addEventListener('change', handleModeChange));

    els.btnRun.addEventListener('click', handleRun);
    els.btnSubmit.addEventListener('click', handleSubmit);
    els.btnStress.addEventListener('click', handleFindFailing);
    els.btnResetOa.addEventListener('click', handleResetOa);
    els.btnResetStub.addEventListener('click', () => {
        if (!confirm('Reset the editor to the starter code? Your changes will be lost.')) return;
        // Snapshot first, so "lost" is recoverable from the draft scrubber.
        snapshotNow('pre-reset').then(() => loadSourceForLanguage('reset'));
    });

    els.btnCustomInputToggle.addEventListener('click', () => {
        els.customInputDrawer.classList.toggle('open');
        if (els.customInputDrawer.classList.contains('open')) els.resultDrawer.classList.remove('open');
    });
    document.getElementById('drawer-close-custom').addEventListener('click', () => els.customInputDrawer.classList.remove('open'));
    document.getElementById('drawer-close-result').addEventListener('click', () => els.resultDrawer.classList.remove('open'));

    els.sidebarToggle.addEventListener('click', () => els.sidebar.classList.toggle('collapsed'));

    // divider drag
    let dragging = false;
    els.divider.addEventListener('mousedown', () => { dragging = true; document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'; });
    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const workspace = document.querySelector('.workspace').offsetWidth;
        const sidebarW = els.sidebar.classList.contains('collapsed') ? 0 : els.sidebar.offsetWidth;
        let w = e.clientX - sidebarW;
        w = Math.max(320, Math.min(w, workspace - sidebarW - 360));
        els.leftPane.style.flex = `0 0 ${w}px`;
    });
    document.addEventListener('mouseup', () => { if (dragging) { dragging = false; document.body.style.cursor = ''; document.body.style.userSelect = ''; } });
}

function isLightTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    return cur ? cur === 'light' : !window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/* ============================ problem list ============================ */
async function fetchProblemsAndHistory() {
    try {
        state.problems = (await api('/api/problems')).problems;
        try { state.history = await api('/api/history'); } catch (e) { state.history = { attempts: [], revisit: [] }; }
        renderSidebar();
        // Honour a #problem-id deep link on first load.
        const want = decodeURIComponent(location.hash.slice(1));
        if (want && state.problems.some(p => p.id === want)) loadProblem(want);
    } catch (e) { console.error('Failed to fetch problems', e); }
}

function renderSidebar() {
    const grouped = {};
    for (const p of state.problems) (grouped[p.company] = grouped[p.company] || []).push(p);
    const revisit = new Set(state.history.revisit || []);
    els.problemList.innerHTML = '';

    for (const [company, probs] of Object.entries(grouped).sort()) {
        const g = document.createElement('div');
        g.className = 'company-group';
        g.textContent = company || 'Other';
        els.problemList.appendChild(g);

        for (const p of probs) {
            const item = document.createElement('div');
            item.className = 'problem-item' + (p.id === state.currentProblemId ? ' active' : '');
            item.onclick = () => loadProblem(p.id);

            const row = document.createElement('div');
            row.className = 'problem-title-row';
            const title = document.createElement('span');
            title.className = 'problem-title';
            title.textContent = p.title;
            const badges = document.createElement('div');
            badges.className = 'problem-badges';
            if (p.difficulty) badges.innerHTML += `<span class="pill pill-${p.difficulty}">${p.difficulty}</span>`;
            if (p.solved) badges.innerHTML += `<span class="pill pill-solved" title="Solved">✓</span>`;
            else if (revisit.has(p.id)) badges.innerHTML += `<span class="pill pill-revisit" title="Not solved yet">•</span>`;
            row.appendChild(title); row.appendChild(badges);
            item.appendChild(row);
            els.problemList.appendChild(item);
        }
    }
}

async function loadProblem(id) {
    if (state.currentProblemId === id) return;
    // Flush the outgoing problem's draft before switching away from it.
    if (state.currentProblemId) saveDraftNow();
    state.currentProblemId = id;
    state.submittedInOa = false;
    state.oaSessionId = null;
    // Deep link, so a problem can be opened (or shared) by URL.
    if (location.hash.slice(1) !== id) history.replaceState(null, '', '#' + id);
    renderSidebar();

    try {
        const data = await api(`/api/problem/${id}`);
        state.currentProblemData = data;
        els.breadcrumb.textContent = `${data.company} › ${data.title}`;

        let links = '';
        if (data.links && data.links.length) {
            links = '<div class="prob-links">' + data.links.map(l =>
                `<a href="${l.url}" target="_blank" rel="noopener">🔗 ${l.site}${l.note ? ' — ' + escapeHTML(l.note) : ''}</a>`).join('') + '</div>';
        }
        document.getElementById('tab-statement').innerHTML = links + (data.statement_html || '<p class="placeholder">No statement.</p>');
        document.getElementById('tab-editorial').innerHTML = data.editorial_html || '<p class="placeholder">No editorial for this problem.</p>';

        els.langSelect.innerHTML = '';
        (data.languages || []).forEach(l => {
            const o = document.createElement('option');
            o.value = l; o.textContent = LANG_MAP[l] || l;
            els.langSelect.appendChild(o);
        });

        if (!data.runnable || !data.languages.length) {
            if (OAEditor.isReady()) {
                OAEditor.setValue('// This problem has a statement only — no reference solution yet.\n');
                OAEditor.setReadOnly(true);
            }
            [els.btnRun, els.btnSubmit, els.btnStress].forEach(b => b.disabled = true);
            setSaveStatus('');
            els.breadcrumb.textContent += '  (statement only)';
        } else {
            if (OAEditor.isReady()) OAEditor.setReadOnly(false);
            [els.btnRun, els.btnSubmit, els.btnStress].forEach(b => b.disabled = false);
            if (data.samples && data.samples.length) els.customStdin.value = data.samples[0].input;
            loadSourceForLanguage('initial');
        }

        handleModeChange();
        els.resultDrawer.classList.remove('open');
        els.customInputDrawer.classList.remove('open');
        updateAttemptsCount();
        // Refresh whichever secondary tab is open for the new problem.
        if (els.tabAttempts.classList.contains('active')) renderAttemptsTab();
        if (els.tabNotes.classList.contains('active')) renderNotesTab();
    } catch (e) {
        console.error('Failed to load problem', e);
    }
}

async function loadSourceForLanguage(reason) {
    if (!state.currentProblemData || !OAEditor.isReady()) return;
    const lang = els.langSelect.value;
    const stub = (state.currentProblemData.stubs || {})[lang] || '';
    const current = OAEditor.getValue();

    if (reason === 'switch' && current.trim() !== '' &&
        current !== (state.currentProblemData.stubs || {})[state.prevLang]) {
        // The old code is snapshotted either way, so a mis-click is recoverable.
        await snapshotNow('pre-switch');
        if (!confirm('Switch language and discard the current code?')) {
            els.langSelect.value = state.prevLang;
            return;
        }
    }
    state.prevLang = lang;
    OAEditor.setLanguage(lang);

    if (reason === 'reset') {
        OAEditor.setValue(stub);
        saveDraftNow();
        return;
    }

    // Server draft is authoritative; localStorage is only a fallback for when the API is
    // unreachable. Whichever has more content wins, so a stale short copy never clobbers work.
    let draft = null;
    try {
        draft = await api(`/api/draft/${state.currentProblemId}/${lang}`);
    } catch (e) {
        draft = null;
    }
    const local = localStorage.getItem(`${state.currentProblemId}:${lang}`);
    const server = draft && draft.source_code;
    let chosen = stub;
    if (server && local) chosen = server.length >= local.length ? server : local;
    else if (server) chosen = server;
    else if (local != null) chosen = local;

    OAEditor.setValue(chosen);
    if (draft && draft.cursor_pos != null && chosen === server) {
        OAEditor.setCursorOffset(draft.cursor_pos);
    }
    setSaveStatus(server ? 'saved' : '', server ? 'ok' : '');
}

/* ============================ modes / timer ============================ */
function getMode() {
    let mode = 'lc';
    els.modeRadios.forEach(r => { if (r.checked) mode = r.value; });
    return mode;
}

function handleModeChange() {
    const mode = getMode();
    if (mode === 'oa') {
        els.oaTimer.style.display = 'inline-block';
        if (!state.submittedInOa) {
            startOaTimer();
            els.btnSubmit.disabled = false;
            els.btnResetOa.style.display = 'none';
        } else {
            els.btnSubmit.disabled = true;
            els.btnResetOa.style.display = 'inline-block';
        }
    } else {
        els.oaTimer.style.display = 'none';
        clearInterval(state.oaTimerInterval);
        els.btnResetOa.style.display = 'none';
        els.btnSubmit.disabled = !state.currentProblemData || !state.currentProblemData.runnable;
        state.submittedInOa = false;
    }
}

function startOaTimer() {
    clearInterval(state.oaTimerInterval);
    state.oaStartTime = Date.now();
    // Open a server-side session so time-per-problem survives a reload or a crash.
    if (state.currentProblemId) {
        api('/api/oa-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ problem_id: state.currentProblemId }),
        }).then(r => { state.oaSessionId = r.session_id; }).catch(() => {});
    }
    const upd = () => {
        const e = Math.floor((Date.now() - state.oaStartTime) / 1000);
        els.oaTimer.textContent = `${String(Math.floor(e / 60)).padStart(2, '0')}:${String(e % 60).padStart(2, '0')}`;
    };
    upd();
    state.oaTimerInterval = setInterval(upd, 1000);
}

function handleResetOa() {
    state.submittedInOa = false;
    els.btnResetOa.style.display = 'none';
    els.btnSubmit.disabled = false;
    startOaTimer();
}

function openResultDrawer(title) {
    els.customInputDrawer.classList.remove('open');
    els.resultDrawer.classList.add('open');
    els.drawerTitle.textContent = title;
}

/* ============================ run / submit / find-failing ============================ */
function reqBody(extra) {
    return JSON.stringify(Object.assign({
        problem_id: state.currentProblemId,
        language: els.langSelect.value,
        source: OAEditor.getValue(),
    }, extra));
}
function post(path, extra) {
    return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: reqBody(extra) });
}

async function handleRun() {
    if (!state.currentProblemId) return;
    openResultDrawer('Run — custom input');
    els.console.innerHTML = '<div class="spinner">Compiling and running…</div>';
    try {
        const r = await post('/api/run', { stdin: els.customStdin.value });
        let html = `<div class="result-summary">`;
        html += `<span class="verdict-badge v-${r.verdict}">${r.verdict}</span>`;
        if (r.time_ms !== undefined && r.time_ms !== null) html += `<span class="kv"><b>${r.time_ms}</b> ms</span>`;
        if (r.memory_kb) html += `<span class="kv"><b>${fmtMem(r.memory_kb)}</b></span>`;
        if (r.signal) html += `<span class="kv">signal <b>${r.signal}</b></span>`;
        if (r.exit_code !== undefined && r.exit_code !== null && r.exit_code !== 0) html += `<span class="kv">exit <b>${r.exit_code}</b></span>`;
        html += `</div>`;
        if (r.compile_output) html += compilePanel(r.compile_output);
        // stdout is always shown on Run — the primary debugging output.
        if (r.verdict !== 'CE') html += ioBlock('stdout', r.stdout, true);
        if (r.stderr) html += stderrPanel(r.stderr);
        els.console.innerHTML = html;
    } catch (e) {
        els.console.innerHTML = `<div class="note" style="color:var(--error)">Error: ${escapeHTML(e.message)}</div>`;
    }
}

async function handleSubmit() {
    if (!state.currentProblemId) return;
    const mode = getMode();
    openResultDrawer(mode === 'oa' ? 'Submission — OA mode (hidden tests)' : 'Submission — all tests');
    els.console.innerHTML = '<div class="spinner">Judging…</div>';
    els.btnSubmit.disabled = true;

    // Time-on-problem is recorded in both modes now; v1 sent it in neither, which is why
    // duration_s was NULL on every historical row.
    const duration = state.oaStartTime
        ? Math.round((Date.now() - state.oaStartTime) / 1000 * 10) / 10 : null;
    if (mode === 'oa') {
        clearInterval(state.oaTimerInterval);
        state.submittedInOa = true;
        els.btnResetOa.style.display = 'inline-block';
    }

    saveDraftNow();   // the judged code is the draft; flush before the round-trip

    try {
        const r = await post('/api/submit', {
            mode, duration_s: duration, oa_session_id: state.oaSessionId || null,
        });
        if (mode === 'oa') state.oaSessionId = null;
        let html = `<div class="result-summary">`;
        html += `<span class="verdict-badge v-${r.verdict}">${r.verdict}</span>`;
        html += `<span class="kv">passed <b>${r.passed}/${r.total}</b></span>`;
        if (r.time_ms_max !== undefined) html += `<span class="kv">max <b>${r.time_ms_max}</b> ms</span>`;
        html += `</div>`;
        if (r.compile_output) html += compilePanel(r.compile_output);
        if (r.tests && r.tests.length) {
            html += '<div class="test-list">' + r.tests.map(t => renderTestRow(t, mode)).join('') + '</div>';
        }
        els.console.innerHTML = html;
        if (mode === 'lc') els.btnSubmit.disabled = false;
        fetchProblemsAndHistory();
        updateAttemptsCount();
        // If the Attempts tab is open, refresh it so the new submission appears immediately.
        if (els.tabAttempts.classList.contains('active')) renderAttemptsTab();
    } catch (e) {
        els.console.innerHTML = `<div class="note" style="color:var(--error)">Error: ${escapeHTML(e.message)}</div>`;
        if (mode === 'lc') els.btnSubmit.disabled = false;
    }
}

async function handleFindFailing() {
    if (!state.currentProblemId) return;
    openResultDrawer('Find Failing Test');
    els.console.innerHTML = '<div class="spinner">Racing your code against the reference on random inputs… this can take a moment.</div>';
    try {
        const r = await post('/api/stress', { iterations: 300 });
        let html = '';
        if (r.status === 'counterexample' && r.counterexample) {
            const c = r.counterexample;
            html += `<div class="result-summary"><span class="verdict-badge v-WA">FAILING CASE FOUND</span>`;
            html += `<span class="kv">after <b>${r.checked}</b> random cases</span></div>`;
            html += `<p class="note">The smallest input where your output differs from the reference:</p>`;
            html += ioBlock('input', c.input, true);
            html += ioBlock('expected (reference)', c.expected, true);
            html += ioBlock('your output', c.got, true);
        } else if (r.status === 'clean') {
            html += `<div class="result-summary"><span class="verdict-badge v-AC">NO FAILURE</span>`;
            html += `<span class="kv"><b>${r.checked}</b> random cases</span></div>`;
            html += `<p class="note">${escapeHTML(r.message || '')}</p>`;
        } else {
            html += `<div class="result-summary"><span class="verdict-badge v-CE">${(r.status || 'error').toUpperCase()}</span></div>`;
            html += `<p class="note">${escapeHTML(r.message || 'Stress testing unavailable for this problem.')}</p>`;
            if (r.message && r.message.indexOf('did not compile') !== -1) html += compilePanel(r.message);
        }
        els.console.innerHTML = html;
    } catch (e) {
        els.console.innerHTML = `<div class="note" style="color:var(--error)">Error: ${escapeHTML(e.message)}</div>`;
    }
}

/* ============================ result rendering ============================ */
function renderTestRow(t, mode) {
    // OA mode never leaks hidden-test I/O — only the verdict and index.
    if (!t.visible) {
        return `<div class="test-row locked">
            <div class="test-head">
                <div class="left"><span class="lock">🔒</span> Hidden test ${t.index}</div>
                <div class="right"><span class="verdict-text v-${t.verdict}">${t.verdict}</span>
                    <span class="test-time">${t.time_ms != null ? t.time_ms + 'ms' : ''}</span></div>
            </div></div>`;
    }
    const hasIO = t.input != null || t.expected != null || t.got != null || t.stderr;
    const passCls = t.verdict === 'AC' ? 'pass' : 'fail';
    const label = t.verdict === 'AC'
        ? `Passed ${t.group} test ${t.index}`
        : (t.verdict === 'WA' ? `Wrong answer on ${t.group} test ${t.index}` : `${t.verdict} on ${t.group} test ${t.index}`);

    let body = '';
    if (hasIO) {
        body = `<div class="test-body">`;
        if (t.input != null) body += ioBlock('input', t.input);
        if (t.expected != null) body += ioBlock('expected output', t.expected);
        if (t.got != null) body += ioBlock('your output', t.got);
        if (t.stderr) body += stderrPanel(t.stderr);
        body += `</div>`;
    }
    const clickable = hasIO ? ' clickable' : '';
    const onclick = hasIO ? ` onclick="this.parentElement.querySelector('.test-body').classList.toggle('open'); this.querySelector('.caret').textContent = this.parentElement.querySelector('.test-body').classList.contains('open')?'▼':'▶';"` : '';
    return `<div class="test-row ${passCls}">
        <div class="test-head${clickable}"${onclick}>
            <div class="left">${hasIO ? '<span class="caret">▶</span>' : ''}<strong>${label}</strong></div>
            <div class="right"><span class="verdict-text v-${t.verdict}">${t.verdict}</span>
                <span class="test-time">${t.time_ms != null ? t.time_ms + 'ms' : ''}</span></div>
        </div>${body}</div>`;
}

function ioBlock(label, value, alwaysShow) {
    const v = value == null ? '' : String(value);
    if (!v && !alwaysShow) return '';
    const empty = v.trim() === '';
    return `<div class="io-block"><div class="io-label">${escapeHTML(label)}</div>
        <div class="io-content${empty ? ' empty' : ''}">${empty ? '(no output)' : escapeHTML(v)}</div></div>`;
}
function stderrPanel(s) {
    return `<div class="stderr-panel"><div class="stderr-head">stderr · debug channel</div>
        <div class="stderr-content">${escapeHTML(s)}</div></div>`;
}
function compilePanel(s) {
    return `<div class="compile-panel"><div class="compile-head">compiler output</div>
        <div class="compile-content">${escapeHTML(s)}</div></div>`;
}
function fmtMem(kb) {
    return kb >= 1024 ? (kb / 1024).toFixed(1) + ' MB' : kb + ' KB';
}
function escapeHTML(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/[&<>'"]/g, t => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t]));
}

/* ============================ Phase 3: the data becomes useful ============================ */

function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit' });
}
function fmtDuration(s) {
    if (s == null) return '';
    s = Math.round(s);
    if (s < 60) return s + 's';
    const m = Math.floor(s / 60);
    return m + 'm ' + (s % 60) + 's';
}

/* ---- modal shell ---- */
function openModal(title, bodyHTML, actionsHTML) {
    els.modalTitle.textContent = title;
    els.modalActions.innerHTML = actionsHTML || '';
    els.modalBody.innerHTML = bodyHTML;
    els.modalOverlay.style.display = 'flex';
}
function closeModal() {
    els.modalOverlay.style.display = 'none';
    els.modalBody.innerHTML = '';
    els.modalActions.innerHTML = '';
    diffState.a = diffState.b = null;   // reset any in-progress attempt comparison
}

/* ---- Attempts tab: every submit for this problem, newest first ---- */
async function renderAttemptsTab() {
    if (!state.currentProblemId) {
        els.tabAttempts.innerHTML = '<p class="placeholder">Select a problem to see your attempts.</p>';
        return;
    }
    els.tabAttempts.innerHTML = '<p class="placeholder">Loading…</p>';
    let attempts = [];
    try { attempts = (await api(`/api/history/${state.currentProblemId}`)).attempts || []; }
    catch (e) { els.tabAttempts.innerHTML = '<p class="placeholder">Could not load attempts.</p>'; return; }

    if (!attempts.length) {
        els.tabAttempts.innerHTML = '<p class="placeholder">No submissions yet. Solve it and they show up here.</p>';
        return;
    }

    // Attempts carrying stored code are selectable for the diff. Pre-v2 rows (imported from
    // history.json) have no code, so they render but cannot be opened or compared.
    const rows = attempts.map(a => {
        const codeable = a.has_code ? '' : ' no-code';
        const detail = a.first_fail_idx ? `test #${a.first_fail_idx}` : '';
        return `<div class="attempt-row${codeable}" data-id="${a.id}" data-code="${a.has_code ? 1 : 0}">
            <span class="verdict-badge v-${a.verdict}">${a.verdict}</span>
            <span class="attempt-score">${a.passed}/${a.total}</span>
            <span class="attempt-meta">${escapeHTML((a.language || '').toUpperCase())}
                · ${a.mode === 'oa' ? 'OA' : 'LC'}${detail ? ' · ' + detail : ''}</span>
            <span class="attempt-when">${fmtTime(a.created_at)}${a.duration_s != null
                ? ' · ' + fmtDuration(a.duration_s) : ''}</span>
            ${a.has_code ? '<button class="mini-btn view-code">view</button>' : '<span class="mini-note">no code</span>'}
        </div>`;
    }).join('');

    const withCode = attempts.filter(a => a.has_code).length;
    els.tabAttempts.innerHTML = `
        <div class="attempts-toolbar">
            <span class="muted">${attempts.length} submission${attempts.length === 1 ? '' : 's'}</span>
            ${withCode >= 2 ? '<span class="hint">Tick two to diff them.</span>' : ''}
        </div>
        <div class="attempt-list">${rows}</div>`;

    els.tabAttempts.querySelectorAll('.view-code').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            viewAttemptCode(+btn.closest('.attempt-row').dataset.id);
        });
    });
    // Click anywhere else on a code-bearing row toggles it into the diff selection.
    els.tabAttempts.querySelectorAll('.attempt-row').forEach(row => {
        if (row.dataset.code !== '1') return;
        row.addEventListener('click', () => toggleDiffPick(+row.dataset.id, row));
    });
}

async function viewAttemptCode(id) {
    let a;
    try { a = await api(`/api/attempt/${id}`); } catch (e) { return; }
    const body = `
        <div class="code-view-meta">
            <span class="verdict-badge v-${a.verdict}">${a.verdict}</span>
            <span>${a.passed}/${a.total}</span>
            <span class="muted">${escapeHTML((a.language || '').toUpperCase())}
                · ${a.mode === 'oa' ? 'OA' : 'LC'} · ${fmtTime(a.created_at)}</span>
        </div>
        ${a.compile_output ? compilePanel(a.compile_output) : ''}
        <pre class="code-view">${escapeHTML(a.source_code || '(no code stored)')}</pre>`;
    const actions = a.source_code
        ? '<button class="mini-btn" id="load-into-editor">Load into editor</button>' : '';
    openModal(`Attempt #${a.id}`, body, actions);
    const load = document.getElementById('load-into-editor');
    if (load) load.addEventListener('click', () => {
        snapshotNow('pre-load').then(() => {
            OAEditor.setValue(a.source_code);
            if ((a.language === 'py') !== (els.langSelect.value === 'py')) {
                els.langSelect.value = a.language; OAEditor.setLanguage(a.language);
            }
            saveDraftNow();
            closeModal();
        });
    });
}

/* ---- diff two attempts ---- */
const diffState = { a: null, b: null };
function toggleDiffPick(id, row) {
    if (diffState.a === id) { diffState.a = null; row.classList.remove('picked'); }
    else if (diffState.b === id) { diffState.b = null; row.classList.remove('picked'); }
    else if (diffState.a == null) { diffState.a = id; row.classList.add('picked'); }
    else if (diffState.b == null) { diffState.b = id; row.classList.add('picked'); }
    else { return; }   // already two picked; ignore until one is cleared
    if (diffState.a != null && diffState.b != null) showAttemptDiff(diffState.a, diffState.b);
}

async function showAttemptDiff(idA, idB) {
    let a, b;
    try { [a, b] = await Promise.all([api(`/api/attempt/${idA}`), api(`/api/attempt/${idB}`)]); }
    catch (e) { return; }
    // Order oldest -> newest so the diff reads as "what I changed".
    if (new Date(a.created_at) > new Date(b.created_at)) { const t = a; a = b; b = t; }
    const rows = lineDiff(a.source_code || '', b.source_code || '');
    const body = `
        <div class="diff-legend">
            <span class="muted">left: #${a.id} (${a.verdict}, ${fmtTime(a.created_at)})</span>
            <span class="arrow">→</span>
            <span class="muted">right: #${b.id} (${b.verdict}, ${fmtTime(b.created_at)})</span>
        </div>
        <div class="diff-view">${rows}</div>`;
    openModal('What changed between two attempts', body);
    // Clear the picks so the next selection starts fresh once the modal closes.
    diffState.a = diffState.b = null;
    els.tabAttempts.querySelectorAll('.attempt-row.picked').forEach(r => r.classList.remove('picked'));
}

/* A compact LCS line diff — enough to see what changed between two attempts, without a library. */
function lineDiff(oldStr, newStr) {
    const o = oldStr.split('\n'), n = newStr.split('\n');
    const m = o.length, k = n.length;
    const dp = Array.from({ length: m + 1 }, () => new Int32Array(k + 1));
    for (let i = m - 1; i >= 0; i--)
        for (let j = k - 1; j >= 0; j--)
            dp[i][j] = o[i] === n[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = [];
    let i = 0, j = 0;
    const push = (cls, sign, text) =>
        out.push(`<div class="diff-line ${cls}"><span class="diff-sign">${sign}</span>${escapeHTML(text) || '&nbsp;'}</div>`);
    while (i < m && j < k) {
        if (o[i] === n[j]) { push('same', ' ', o[i]); i++; j++; }
        else if (dp[i + 1][j] >= dp[i][j + 1]) { push('del', '−', o[i]); i++; }
        else { push('add', '+', n[j]); j++; }
    }
    while (i < m) push('del', '−', o[i++]);
    while (j < k) push('add', '+', n[j++]);
    return out.join('');
}

/* ---- Notes tab: markdown-ish free text, autosaved ---- */
let noteTimer = null;
async function renderNotesTab() {
    if (!state.currentProblemId) {
        els.tabNotes.innerHTML = '<p class="placeholder">Select a problem to take notes.</p>';
        return;
    }
    let note = { body: '' }, flags = {};
    try { note = await api(`/api/note/${state.currentProblemId}`); } catch (e) {}
    try { flags = await api(`/api/flags/${state.currentProblemId}`); } catch (e) {}
    els.tabNotes.innerHTML = `
        <div class="notes-flags">
            <label class="chk"><input type="checkbox" id="flag-star" ${flags.starred ? 'checked' : ''}> ⭐ Starred</label>
            <label class="chk"><input type="checkbox" id="flag-revisit" ${flags.revisit ? 'checked' : ''}> 🔁 Revisit</label>
            <label class="conf">Confidence
                <select id="flag-conf">
                    <option value="">–</option>
                    ${[1,2,3,4,5].map(v => `<option value="${v}" ${flags.confidence == v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
            </label>
            <span class="save-status" id="note-status"></span>
        </div>
        <textarea id="note-body" class="note-body" spellcheck="true"
            placeholder="Approach, edge cases, why the WA happened, the trick you missed…">${escapeHTML(note.body || '')}</textarea>`;

    const status = document.getElementById('note-status');
    document.getElementById('note-body').addEventListener('input', (e) => {
        status.textContent = 'saving…'; status.className = 'save-status';
        clearTimeout(noteTimer);
        const body = e.target.value;
        noteTimer = setTimeout(() => {
            api(`/api/note/${state.currentProblemId}`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ body }),
            }).then(() => { status.textContent = 'saved'; status.className = 'save-status ok'; })
              .catch(() => { status.textContent = 'save failed'; status.className = 'save-status warn'; });
        }, 800);
    });
    const saveFlags = () => api(`/api/flags/${state.currentProblemId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            starred: document.getElementById('flag-star').checked,
            revisit: document.getElementById('flag-revisit').checked,
            confidence: document.getElementById('flag-conf').value || null,
        }),
    }).then(() => fetchProblemsAndHistory());
    ['flag-star', 'flag-revisit', 'flag-conf'].forEach(id =>
        document.getElementById(id).addEventListener('change', saveFlags));
}

/* ---- draft scrubber: replay half-written code over time ---- */
async function openDraftScrubber() {
    if (!state.currentProblemId) return;
    const lang = els.langSelect.value;
    let snaps = [];
    try { snaps = (await api(`/api/snapshots/${state.currentProblemId}?lang=${lang}`)).snapshots || []; }
    catch (e) {}
    if (!snaps.length) {
        openModal('Draft history', '<p class="placeholder">No saved drafts yet for this language. ' +
            'They accumulate as you type (every couple of minutes, and before each submit or reset).</p>');
        return;
    }
    const body = `
        <div class="scrub-controls">
            <input type="range" id="scrub" min="0" max="${snaps.length - 1}" value="${snaps.length - 1}" step="1">
            <div class="scrub-label" id="scrub-label"></div>
        </div>
        <pre class="code-view" id="scrub-code">loading…</pre>`;
    openModal('Draft history — ' + LANG_MAP[lang], body,
        '<button class="mini-btn" id="restore-draft">Restore this version</button>');

    const slider = document.getElementById('scrub');
    const label = document.getElementById('scrub-label');
    const codeEl = document.getElementById('scrub-code');
    const cache = {};
    async function show(i) {
        const s = snaps[i];
        label.innerHTML = `<b>${i + 1}/${snaps.length}</b> · ${escapeHTML(s.reason)}
            · ${fmtTime(s.created_at)} · ${s.chars} chars`;
        if (!cache[s.id]) {
            try { cache[s.id] = (await api(`/api/snapshot/${s.id}`)).source_code || ''; }
            catch (e) { cache[s.id] = '(could not load)'; }
        }
        codeEl.textContent = cache[s.id];
    }
    slider.addEventListener('input', () => show(+slider.value));
    document.getElementById('restore-draft').addEventListener('click', async () => {
        const s = snaps[+slider.value];
        const code = cache[s.id] != null ? cache[s.id] : (await api(`/api/snapshot/${s.id}`)).source_code;
        await snapshotNow('pre-restore');
        OAEditor.setValue(code || '');
        saveDraftNow();
        closeModal();
    });
    show(snaps.length - 1);
}

/* ---- stats dashboard ---- */
async function openStats() {
    openModal('Your statistics', '<p class="placeholder">Loading…</p>',
        '<button class="mini-btn" id="export-all" title="Download everything as a zip">⬇ Export all</button>');
    const exp = document.getElementById('export-all');
    if (exp) exp.addEventListener('click', exportAll);
    let s;
    try { s = await api('/api/stats'); } catch (e) {
        els.modalBody.innerHTML = '<p class="placeholder">Could not load stats.</p>'; return;
    }
    const totalProblems = state.problems.length || 0;
    const acRate = s.total_attempts ? Math.round(100 * s.ac_attempts / s.total_attempts) : 0;
    const avgToAc = s.attempts_to_ac && s.attempts_to_ac.length
        ? (s.attempts_to_ac.reduce((a, r) => a + r.attempts_to_ac, 0) / s.attempts_to_ac.length).toFixed(1)
        : '–';
    const firstTry = s.attempts_to_ac ? s.attempts_to_ac.filter(r => r.attempts_to_ac === 1).length : 0;

    const vColors = { AC: 'ok', WA: 'err', TLE: 'warn', MLE: 'warn', RE: 'err', CE: 'muted' };
    const vTotal = Object.values(s.verdicts || {}).reduce((a, b) => a + b, 0) || 1;
    const verdictBars = Object.entries(s.verdicts || {}).map(([v, n]) =>
        `<div class="vbar-row"><span class="vbar-label verdict-badge v-${v}">${v}</span>
            <div class="vbar-track"><div class="vbar-fill ${vColors[v] || 'muted'}"
                style="width:${Math.round(100 * n / vTotal)}%"></div></div>
            <span class="vbar-n">${n}</span></div>`).join('');

    els.modalBody.innerHTML = `
        <div class="stat-grid">
            <div class="stat-tile"><div class="stat-num">${s.problems_solved}<span class="stat-den">/${totalProblems}</span></div><div class="stat-cap">problems solved</div></div>
            <div class="stat-tile"><div class="stat-num">${acRate}%</div><div class="stat-cap">AC rate</div></div>
            <div class="stat-tile"><div class="stat-num">${firstTry}</div><div class="stat-cap">first-try solves</div></div>
            <div class="stat-tile"><div class="stat-num">${avgToAc}</div><div class="stat-cap">avg attempts to AC</div></div>
            <div class="stat-tile"><div class="stat-num">${s.total_attempts}</div><div class="stat-cap">total submissions</div></div>
            <div class="stat-tile"><div class="stat-num">${s.runs}</div><div class="stat-cap">custom runs</div></div>
        </div>
        <h3 class="stat-h">Verdict distribution</h3>
        <div class="vbars">${verdictBars || '<span class="muted">No attempts yet.</span>'}</div>
        <div class="stat-foot muted">${s.drafts} saved drafts · ${s.snapshots} snapshots kept</div>`;
}

async function updateAttemptsCount() {
    if (!state.currentProblemId) { els.attemptsCount.textContent = ''; return; }
    try {
        const n = ((await api(`/api/history/${state.currentProblemId}`)).attempts || []).length;
        els.attemptsCount.textContent = n ? `(${n})` : '';
    } catch (e) { els.attemptsCount.textContent = ''; }
}

/* ============================ Phase 5: sharing ============================ */

/* ---- Sync: pull the shared bank ---- */
async function syncBank() {
    const btn = els.btnSync;
    const prev = btn.textContent;
    btn.disabled = true; btn.textContent = '⟳ Syncing…';
    try {
        const r = await api('/api/bank/sync', { method: 'POST' });
        if (!r.ok) {
            toast(r.error || 'Sync failed', 'warn');
        } else if (!r.changed) {
            toast('Already up to date', 'ok');
        } else {
            const n = (r.new_or_changed || []).length;
            toast(`Synced — ${n} problem${n === 1 ? '' : 's'} new or updated`, 'ok');
            fetchProblemsAndHistory();   // the sidebar picks up new problems
        }
    } catch (e) {
        toast('Sync failed: ' + e.message, 'warn');
    } finally {
        btn.disabled = false; btn.textContent = prev;
    }
}

/* ---- Add Problem: author → verify → publish ---- */
function openAuthoring() {
    const body = `
        <div class="author-form">
            <div class="af-row">
                <label>Problem ID<span class="req">*</span>
                    <input id="af-id" placeholder="company-q1-short-name" autocomplete="off">
                    <span class="af-hint">lowercase words, hyphen-separated</span>
                </label>
                <label>Title<span class="req">*</span>
                    <input id="af-title" placeholder="Human-readable title" autocomplete="off">
                </label>
            </div>
            <div class="af-row">
                <label>Company <input id="af-company" placeholder="optional" autocomplete="off"></label>
                <label>Difficulty
                    <select id="af-diff"><option>Easy</option><option selected>Medium</option><option>Hard</option></select>
                </label>
                <label>Language
                    <select id="af-lang"><option value="cpp">C++17</option><option value="py">Python 3</option></select>
                </label>
            </div>
            <label>Tags <input id="af-tags" placeholder="comma,separated,tags" autocomplete="off"></label>
            <label>Statement (Markdown)<span class="req">*</span>
                <textarea id="af-statement" class="af-ta" rows="6"
                    placeholder="# Title&#10;&#10;Describe the problem, input, output, constraints…"></textarea>
            </label>
            <label>Reference solution<span class="req">*</span>
                <span class="af-hint">the correct solution — its output defines the expected answers</span>
                <textarea id="af-reference" class="af-ta mono" rows="8"
                    placeholder="A verified-correct solution."></textarea>
            </label>
            <label>Starter stub (shown in the editor)
                <textarea id="af-stub" class="af-ta mono" rows="4" placeholder="Optional — a sensible default is used if blank."></textarea>
            </label>
            <label>Generator (optional, Python)
                <span class="af-hint">argv[1]=seed, argv[2]=integer size hint; prints one random input</span>
                <textarea id="af-generator" class="af-ta mono" rows="4"
                    placeholder="import sys, random&#10;random.seed(int(sys.argv[1]))&#10;..."></textarea>
            </label>
            <div id="af-samples"></div>
            <button class="mini-btn" id="af-add-sample">＋ Add sample</button>
            <div class="af-status" id="af-status"></div>
        </div>`;
    openModal('Add a problem to the shared bank', body,
        '<button class="mini-btn" id="af-verify">Verify &amp; preview</button>' +
        '<button class="mini-btn primary" id="af-publish" disabled>Publish</button>');

    let sampleN = 0;
    const addSample = (inp = '', out = '') => {
        sampleN++;
        const div = document.createElement('div');
        div.className = 'af-sample';
        div.innerHTML = `<span class="af-sample-n">#${sampleN}</span>
            <textarea class="af-si mono" rows="2" placeholder="input">${escapeHTML(inp)}</textarea>
            <textarea class="af-so mono" rows="2" placeholder="expected output">${escapeHTML(out)}</textarea>
            <button class="af-rm" title="Remove">×</button>`;
        div.querySelector('.af-rm').addEventListener('click', () => div.remove());
        document.getElementById('af-samples').appendChild(div);
    };
    addSample();
    document.getElementById('af-add-sample').addEventListener('click', () => addSample());

    const gather = () => ({
        id: val('af-id').trim(),
        title: val('af-title').trim(),
        company: val('af-company').trim(),
        difficulty: val('af-diff'),
        language: val('af-lang'),
        tags: val('af-tags').split(',').map(t => t.trim()).filter(Boolean),
        statement: val('af-statement'),
        reference: val('af-reference'),
        stub: val('af-stub'),
        generator: val('af-generator'),
        samples: [...document.querySelectorAll('.af-sample')].map(s => ({
            input: s.querySelector('.af-si').value,
            output: s.querySelector('.af-so').value,
        })).filter(s => s.input.trim() || s.output.trim()),
    });

    const status = document.getElementById('af-status');
    let authoredId = null;
    document.getElementById('af-verify').addEventListener('click', async () => {
        const spec = gather();
        if (!spec.id || !spec.title || !spec.reference || !spec.samples.length) {
            status.innerHTML = '<span class="warn">Fill ID, title, reference, and at least one sample.</span>';
            return;
        }
        status.innerHTML = '<span class="muted">Scaffolding, generating hidden tests, and verifying…</span>';
        try {
            const r = await api('/api/bank/author', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(spec),
            });
            if (r.ok) {
                authoredId = r.id;
                status.innerHTML = `<span class="ok">✓ Verified — the reference reproduces every sample. `
                    + `Ready to publish.</span><pre class="af-verify-out">${escapeHTML((r.verify.output||'').slice(-600))}</pre>`;
                document.getElementById('af-publish').disabled = false;
                fetchProblemsAndHistory();   // it's already runnable locally
            } else {
                const msg = (r.error) || (r.verify && r.verify.output) || 'Verification failed.';
                status.innerHTML = `<span class="warn">✗ ${escapeHTML(r.error || 'Verification failed — fix the reference or samples.')}</span>`
                    + `<pre class="af-verify-out">${escapeHTML(((r.verify&&r.verify.output)||msg).slice(-800))}</pre>`;
                document.getElementById('af-publish').disabled = true;
            }
        } catch (e) {
            status.innerHTML = `<span class="warn">${escapeHTML(e.message)}</span>`;
        }
    });

    document.getElementById('af-publish').addEventListener('click', async () => {
        if (!authoredId) return;
        status.innerHTML = '<span class="muted">Committing and pushing…</span>';
        try {
            const r = await api('/api/bank/publish', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: authoredId }),
            });
            if (!r.ok) {
                status.innerHTML = `<span class="warn">${escapeHTML(r.error || 'Publish failed')}</span>`;
            } else if (r.pushed) {
                status.innerHTML = `<span class="ok">✓ Pushed branch <b>${escapeHTML(r.branch)}</b>.</span>`
                    + (r.pr_url ? ` <a href="${r.pr_url}" target="_blank" rel="noopener">Open a pull request →</a>` : '');
            } else {
                status.innerHTML = `<span class="ok">✓ Committed locally.</span> <span class="muted">${escapeHTML(r.note || '')}</span>`;
            }
        } catch (e) {
            status.innerHTML = `<span class="warn">${escapeHTML(e.message)}</span>`;
        }
    });
}
function val(id) { const el = document.getElementById(id); return el ? el.value : ''; }

/* ---- lightweight toast ---- */
let toastTimer = null;
function toast(msg, kind) {
    let t = document.getElementById('oaj-toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'oaj-toast';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.className = 'toast show ' + (kind || '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.className = 'toast ' + (kind || ''); }, 3200);
}

/* ---- export everything ---- */
function exportAll() { window.location.href = '/api/export'; }

document.addEventListener('DOMContentLoaded', init);
