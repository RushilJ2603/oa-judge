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
    editor: document.getElementById('editor'),
    highlightLayer: document.getElementById('highlight-layer'),
    highlightCode: document.getElementById('highlight-code'),
    lineNumbers: document.getElementById('line-numbers'),
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
};

const LANG_MAP = { cpp: 'C++17', py: 'Python 3' };

/* ============================ syntax highlighting ============================ */
const KEYWORDS = {
    cpp: new Set(['int','long','short','char','bool','float','double','void','unsigned','signed','auto',
        'const','constexpr','static','struct','class','public','private','protected','template','typename',
        'namespace','using','return','if','else','for','while','do','switch','case','default','break',
        'continue','new','delete','try','catch','throw','sizeof','true','false','nullptr','this','operator',
        'friend','virtual','override','inline','enum','union','typedef','goto','extern','volatile','mutable',
        'explicit','and','or','not','define','include','ifdef','endif']),
    py: new Set(['def','return','if','elif','else','for','while','break','continue','import','from','as',
        'class','try','except','finally','raise','with','lambda','yield','global','nonlocal','pass','in',
        'is','not','and','or','None','True','False','del','assert','async','await']),
};
const TYPES = {
    cpp: new Set(['string','vector','map','set','unordered_map','unordered_set','pair','queue','stack','deque',
        'priority_queue','size_t','int64_t','uint64_t','int32_t','ll','ull','multiset','multimap','array','list',
        'tuple','bitset','cin','cout','cerr','endl','std','make_pair']),
    py: new Set(['print','len','range','int','str','float','list','dict','set','tuple','map','filter','sorted',
        'sum','min','max','abs','input','enumerate','zip','open','isinstance','type','bool','any','all','ord',
        'chr','sys','collections','heapq','defaultdict','Counter','deque']),
};

function tokenize(src, lang) {
    const isPy = lang === 'py';
    // Groups (cpp): 1 comment, 2 string, 3 preproc, 4 number, 5 identifier, 6 ws, 7 any
    // Groups (py) : 1 comment, 2 string, 3 number, 4 identifier, 5 ws, 6 any
    const re = isPy
        ? /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(\b\d[\w.]*)|([A-Za-z_]\w*)|(\s+)|([\s\S])/g
        : /(\/\*[\s\S]*?\*\/|\/\/[^\n]*)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(#\w+)|(\b\d[\w.]*)|([A-Za-z_]\w*)|(\s+)|([\s\S])/g;
    const kw = KEYWORDS[isPy ? 'py' : 'cpp'];
    const ty = TYPES[isPy ? 'py' : 'cpp'];
    let out = '';
    let m;
    while ((m = re.exec(src)) !== null) {
        const t = m[0];
        let cls = null;
        if (isPy) {
            if (m[1]) cls = 'tok-comment';
            else if (m[2]) cls = 'tok-string';
            else if (m[3]) cls = 'tok-number';
            else if (m[4]) cls = kw.has(t) ? 'tok-keyword' : (ty.has(t) ? 'tok-type' : (src[re.lastIndex] === '(' ? 'tok-func' : null));
        } else {
            if (m[1]) cls = 'tok-comment';
            else if (m[2]) cls = 'tok-string';
            else if (m[3]) cls = 'tok-preproc';
            else if (m[4]) cls = 'tok-number';
            else if (m[5]) cls = kw.has(t) ? 'tok-keyword' : (ty.has(t) ? 'tok-type' : (src[re.lastIndex] === '(' ? 'tok-func' : null));
        }
        const esc = escapeHTML(t);
        out += cls ? `<span class="${cls}">${esc}</span>` : esc;
    }
    return out;
}

function refreshEditor() {
    // Strip any stray CR so the highlight layer's line count matches the textarea exactly.
    const src = els.editor.value.replace(/\r/g, '');
    els.highlightCode.innerHTML = tokenize(src, els.langSelect.value || 'cpp');
    updateLineNumbers();
    syncScroll();
}

// Insert text at the caret (replacing any selection). Uses execCommand('insertText') so the
// browser's native undo stack is preserved and the 'input' event fires (which refreshes the
// highlight + saves). Falls back to a manual splice if execCommand is unavailable.
function insertAtCursor(text) {
    els.editor.focus();
    let ok = false;
    try { ok = document.execCommand && document.execCommand('insertText', false, text); } catch (e) { ok = false; }
    if (!ok) {
        const s = els.editor.selectionStart, en = els.editor.selectionEnd;
        els.editor.value = els.editor.value.slice(0, s) + text + els.editor.value.slice(en);
        els.editor.selectionStart = els.editor.selectionEnd = s + text.length;
        refreshEditor();
        saveSource();
    }
}

function syncScroll() {
    els.highlightLayer.scrollTop = els.editor.scrollTop;
    els.highlightLayer.scrollLeft = els.editor.scrollLeft;
    els.lineNumbers.scrollTop = els.editor.scrollTop;
}

function updateLineNumbers() {
    const lines = els.editor.value.split('\n').length;
    let s = '';
    for (let i = 1; i <= lines; i++) s += i + '\n';
    els.lineNumbers.textContent = s;
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
    });
}

function setupEventListeners() {
    els.tabBtns.forEach(btn => btn.addEventListener('click', () => {
        els.tabBtns.forEach(b => b.classList.remove('active'));
        els.tabContents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    }));

    els.editor.addEventListener('input', () => { refreshEditor(); saveSource(); });
    els.editor.addEventListener('scroll', syncScroll);
    els.editor.addEventListener('keydown', (e) => {
        // Ctrl/Cmd+Enter submits — check before the plain-Enter auto-indent.
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!els.btnSubmit.disabled) els.btnSubmit.click();
            return;
        }
        if (e.key === 'Tab') {
            e.preventDefault();
            insertAtCursor('    ');
            return;
        }
        if (e.key === 'Enter') {
            // Auto-indent: carry the current line's leading whitespace to the new line,
            // and add one level after an opening brace/paren or a trailing colon.
            e.preventDefault();
            const v = els.editor.value, s = els.editor.selectionStart;
            const lineStart = v.lastIndexOf('\n', s - 1) + 1;
            const prefix = v.slice(lineStart, s);
            const indent = (prefix.match(/^[ \t]*/) || [''])[0];
            const extra = /[{(:]\s*$/.test(prefix) ? '    ' : '';
            insertAtCursor('\n' + indent + extra);
            return;
        }
    });
    // Normalise pasted text: CRLF/CR -> LF and tabs -> 4 spaces, so the highlight overlay
    // stays line-aligned with the textarea and indentation is consistent.
    els.editor.addEventListener('paste', (e) => {
        e.preventDefault();
        const cd = e.clipboardData || window.clipboardData;
        if (!cd) return;
        const text = cd.getData('text').replace(/\r\n?/g, '\n').replace(/\t/g, '    ');
        insertAtCursor(text);
    });

    els.langSelect.addEventListener('change', () => loadSourceForLanguage('switch'));
    els.modeRadios.forEach(r => r.addEventListener('change', handleModeChange));

    els.btnRun.addEventListener('click', handleRun);
    els.btnSubmit.addEventListener('click', handleSubmit);
    els.btnStress.addEventListener('click', handleFindFailing);
    els.btnResetOa.addEventListener('click', handleResetOa);
    els.btnResetStub.addEventListener('click', () => {
        if (confirm('Reset the editor to the starter code? Your changes will be lost.')) loadSourceForLanguage('reset');
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

function saveSource() {
    if (!state.currentProblemId) return;
    localStorage.setItem(`${state.currentProblemId}:${els.langSelect.value}`, els.editor.value);
}

/* ============================ problem list ============================ */
async function fetchProblemsAndHistory() {
    try {
        state.problems = (await api('/api/problems')).problems;
        try { state.history = await api('/api/history'); } catch (e) { state.history = { attempts: [], revisit: [] }; }
        renderSidebar();
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
    state.currentProblemId = id;
    state.submittedInOa = false;
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
            els.editor.value = '';
            els.editor.disabled = true;
            [els.btnRun, els.btnSubmit, els.btnStress].forEach(b => b.disabled = true);
            els.highlightCode.textContent = '';
            updateLineNumbers();
            els.breadcrumb.textContent += '  (statement only)';
        } else {
            els.editor.disabled = false;
            [els.btnRun, els.btnSubmit, els.btnStress].forEach(b => b.disabled = false);
            if (data.samples && data.samples.length) els.customStdin.value = data.samples[0].input;
            loadSourceForLanguage('initial');
        }

        handleModeChange();
        els.resultDrawer.classList.remove('open');
        els.customInputDrawer.classList.remove('open');
    } catch (e) {
        console.error('Failed to load problem', e);
    }
}

function loadSourceForLanguage(reason) {
    if (!state.currentProblemData) return;
    const lang = els.langSelect.value;
    const stub = (state.currentProblemData.stubs || {})[lang] || '';

    if (reason === 'switch' && els.editor.value.trim() !== '' &&
        els.editor.value !== (state.currentProblemData.stubs || {})[state.prevLang]) {
        if (!confirm('Switch language and discard the current code?')) {
            els.langSelect.value = state.prevLang;
            return;
        }
    }
    state.prevLang = lang;

    const saved = localStorage.getItem(`${state.currentProblemId}:${lang}`);
    els.editor.value = (reason === 'reset') ? stub : (saved != null ? saved : stub);
    if (reason === 'reset') saveSource();
    refreshEditor();
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
        source: els.editor.value,
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

    let duration = null;
    if (mode === 'oa') {
        duration = state.oaStartTime ? Math.floor((Date.now() - state.oaStartTime) / 1000) : null;
        clearInterval(state.oaTimerInterval);
        state.submittedInOa = true;
        els.btnResetOa.style.display = 'inline-block';
    }

    try {
        const r = await post('/api/submit', { mode, duration_s: duration });
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

document.addEventListener('DOMContentLoaded', init);
