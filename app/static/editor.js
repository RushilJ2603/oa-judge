/* OA Judge — Monaco editor wrapper (Phase 2).
 *
 * Replaces the hand-written transparent-textarea + highlight-overlay editor. That design
 * required the textarea and the <pre> behind it to lay out identically to the pixel; any
 * disagreement (fractional line-height rounding, a stray \r, a tab) drifted the caret away
 * from the text and produced the "backspace deletes the line below" class of bug. Monaco
 * owns caret and highlighting in one layer, so that failure mode cannot occur here.
 *
 * Loaded from app/static/vendor/monaco (AMD build, ~4.3 MB, fully offline — no CDN).
 * Exposes window.OAEditor; app.js talks only to this interface.
 */
(function () {
    'use strict';

    const BASE = '/static/vendor/monaco/';
    let editor = null;
    let monacoRef = null;
    let changeHandler = null;
    // Set while the app writes the buffer itself (loading a draft, switching language,
    // resetting to the stub). Without this, merely opening a problem would look like an
    // edit and save the untouched stub as a draft.
    let programmatic = false;
    let readyResolve;
    const ready = new Promise((res) => { readyResolve = res; });

    // ---------------------------------------------------------------- completion data
    // Hand-curated rather than parsed from headers: these are the things actually reached
    // for in contest/OA code. A short, relevant list beats an exhaustive one you scroll past.
    const CPP_KEYWORDS = [
        'alignas', 'alignof', 'auto', 'bool', 'break', 'case', 'catch', 'char', 'class',
        'const', 'constexpr', 'const_cast', 'continue', 'decltype', 'default', 'delete',
        'do', 'double', 'dynamic_cast', 'else', 'enum', 'explicit', 'export', 'extern',
        'false', 'float', 'for', 'friend', 'goto', 'if', 'inline', 'int', 'long', 'mutable',
        'namespace', 'new', 'noexcept', 'nullptr', 'operator', 'override', 'private',
        'protected', 'public', 'register', 'reinterpret_cast', 'return', 'short', 'signed',
        'sizeof', 'static', 'static_assert', 'static_cast', 'struct', 'switch', 'template',
        'this', 'throw', 'true', 'try', 'typedef', 'typeid', 'typename', 'union', 'unsigned',
        'using', 'virtual', 'void', 'volatile', 'while'
    ];

    const CPP_TYPES = [
        'std::vector', 'std::string', 'std::map', 'std::unordered_map', 'std::set',
        'std::unordered_set', 'std::pair', 'std::tuple', 'std::queue', 'std::deque',
        'std::stack', 'std::priority_queue', 'std::array', 'std::bitset', 'std::list',
        'std::multiset', 'std::multimap', 'std::optional', 'std::function', 'std::complex',
        'int64_t', 'uint64_t', 'int32_t', 'size_t', 'ptrdiff_t', 'long long', 'unsigned long long'
    ];

    const CPP_FUNCS = [
        'std::sort', 'std::stable_sort', 'std::reverse', 'std::max', 'std::min',
        'std::max_element', 'std::max_element', 'std::min_element', 'std::accumulate',
        'std::lower_bound', 'std::upper_bound', 'std::binary_search', 'std::next_permutation',
        'std::prev_permutation', 'std::unique', 'std::count', 'std::count_if', 'std::find',
        'std::find_if', 'std::fill', 'std::iota', 'std::swap', 'std::abs', 'std::gcd',
        'std::lcm', 'std::to_string', 'std::stoi', 'std::stoll', 'std::getline',
        'std::push_heap', 'std::pop_heap', 'std::partial_sort', 'std::nth_element',
        'push_back', 'emplace_back', 'pop_back', 'begin', 'end', 'rbegin', 'rend',
        'size', 'empty', 'clear', 'insert', 'erase', 'find', 'count', 'resize', 'assign',
        'front', 'back', 'top', 'push', 'pop', 'first', 'second', 'substr', 'length'
    ];

    const CPP_HEADERS = [
        'bits/stdc++.h', 'iostream', 'vector', 'string', 'algorithm', 'map', 'unordered_map',
        'set', 'unordered_set', 'queue', 'stack', 'deque', 'cmath', 'cstdio', 'cstring',
        'numeric', 'utility', 'tuple', 'climits', 'cstdint', 'iomanip', 'bitset', 'functional'
    ];

    // ${1:x} placeholders are Monaco snippet syntax: Tab jumps between them.
    const CPP_SNIPPETS = [
        { label: 'fori', doc: 'indexed for loop',
          body: 'for (int ${1:i} = 0; ${1:i} < ${2:n}; ++${1:i}) {\n\t$0\n}' },
        { label: 'forr', doc: 'reverse for loop',
          body: 'for (int ${1:i} = ${2:n} - 1; ${1:i} >= 0; --${1:i}) {\n\t$0\n}' },
        { label: 'fore', doc: 'range-for over a container',
          body: 'for (auto& ${1:x} : ${2:v}) {\n\t$0\n}' },
        { label: 'vec', doc: 'vector declaration',
          body: 'std::vector<${1:int}> ${2:v}(${3:n});' },
        { label: 'vec2', doc: '2-D vector',
          body: 'std::vector<std::vector<${1:int}>> ${2:g}(${3:n}, std::vector<${1:int}>(${4:m}));' },
        { label: 'readvec', doc: 'read n then n values',
          body: 'int ${1:n};\nstd::cin >> ${1:n};\nstd::vector<${2:int}> ${3:a}(${1:n});\n' +
                'for (auto& x : ${3:a}) std::cin >> x;\n$0' },
        { label: 'fastio', doc: 'untie cin/cout for speed',
          body: 'std::ios::sync_with_stdio(false);\nstd::cin.tie(nullptr);' },
        { label: 'main', doc: 'main() with fast IO',
          body: 'int main() {\n\tstd::ios::sync_with_stdio(false);\n\tstd::cin.tie(nullptr);\n\n' +
                '\t$0\n\n\treturn 0;\n}' },
        { label: 'sortv', doc: 'sort a container',
          body: 'std::sort(${1:v}.begin(), ${1:v}.end());' },
        { label: 'sortcmp', doc: 'sort with a comparator',
          body: 'std::sort(${1:v}.begin(), ${1:v}.end(),\n' +
                '\t[](const ${2:auto}& a, const ${2:auto}& b) { return ${3:a < b}; });' },
        { label: 'pq', doc: 'min-heap priority_queue',
          body: 'std::priority_queue<${1:int}, std::vector<${1:int}>, std::greater<${1:int}>> ${2:pq};' },
        { label: 'binsearch', doc: 'lower_bound index',
          body: 'int ${1:idx} = int(std::lower_bound(${2:v}.begin(), ${2:v}.end(), ${3:key})' +
                ' - ${2:v}.begin());' },
        { label: 'dsu', doc: 'disjoint set union',
          body: 'struct DSU {\n\tstd::vector<int> p, r;\n\tDSU(int n) : p(n), r(n, 0) {' +
                ' std::iota(p.begin(), p.end(), 0); }\n' +
                '\tint find(int x) { return p[x] == x ? x : p[x] = find(p[x]); }\n' +
                '\tbool join(int a, int b) {\n\t\ta = find(a); b = find(b);\n' +
                '\t\tif (a == b) return false;\n\t\tif (r[a] < r[b]) std::swap(a, b);\n' +
                '\t\tp[b] = a; if (r[a] == r[b]) ++r[a];\n\t\treturn true;\n\t}\n};$0' },
        { label: 'debug', doc: 'stderr debug print (never counted as output)',
          body: 'std::cerr << "${1:label} = " << ${2:value} << "\\n";' }
    ];

    const PY_KEYWORDS = [
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del',
        'elif', 'else', 'except', 'False', 'finally', 'for', 'from', 'global', 'if', 'import',
        'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
        'True', 'try', 'while', 'with', 'yield'
    ];

    const PY_BUILTINS = [
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod', 'enumerate', 'filter',
        'float', 'format', 'frozenset', 'hex', 'input', 'int', 'isinstance', 'iter', 'len',
        'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow', 'print', 'range', 'repr',
        'reversed', 'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip',
        'collections.defaultdict', 'collections.Counter', 'collections.deque',
        'heapq.heappush', 'heapq.heappop', 'heapq.heapify', 'bisect.bisect_left',
        'bisect.bisect_right', 'bisect.insort', 'itertools.permutations',
        'itertools.combinations', 'itertools.accumulate', 'math.gcd', 'math.inf',
        'math.isqrt', 'functools.lru_cache', 'sys.stdin', 'sys.setrecursionlimit'
    ];

    const PY_SNIPPETS = [
        { label: 'fori', doc: 'for over range',
          body: 'for ${1:i} in range(${2:n}):\n\t$0' },
        { label: 'fore', doc: 'for over an iterable',
          body: 'for ${1:x} in ${2:items}:\n\t$0' },
        { label: 'readints', doc: 'read a line of ints',
          body: '${1:a} = list(map(int, input().split()))' },
        { label: 'readint', doc: 'read a single int',
          body: '${1:n} = int(input())' },
        { label: 'fastio', doc: 'fast stdin reader',
          body: 'import sys\ninput = sys.stdin.readline' },
        { label: 'main', doc: 'main guard',
          body: 'def main():\n\t$0\n\n\nif __name__ == "__main__":\n\tmain()' },
        { label: 'defaultdict', doc: 'defaultdict',
          body: 'from collections import defaultdict\n${1:d} = defaultdict(${2:int})' },
        { label: 'counter', doc: 'Counter',
          body: 'from collections import Counter\n${1:c} = Counter(${2:items})' },
        { label: 'heap', doc: 'heapq usage',
          body: 'import heapq\n${1:h} = []\nheapq.heappush(${1:h}, ${2:item})' },
        { label: 'memo', doc: 'memoized recursion',
          body: 'from functools import lru_cache\n\n@lru_cache(maxsize=None)\n' +
                'def ${1:solve}(${2:i}):\n\t$0' },
        { label: 'recurlimit', doc: 'raise the recursion limit',
          body: 'import sys\nsys.setrecursionlimit(300000)' },
        { label: 'debug', doc: 'stderr debug print (never counted as output)',
          body: 'print(f"${1:label} = {${2:value}}", file=sys.stderr)' }
    ];

    // ---------------------------------------------------------------- theme
    // Matches the Dracula palette the app already used, so the switch is invisible.
    function defineTheme(monaco) {
        monaco.editor.defineTheme('oaj-dark', {
            base: 'vs-dark', inherit: true,
            rules: [
                { token: 'comment', foreground: '6272a4', fontStyle: 'italic' },
                { token: 'keyword', foreground: 'ff79c6' },
                { token: 'string', foreground: 'f1fa8c' },
                { token: 'number', foreground: 'bd93f9' },
                { token: 'type', foreground: '8be9fd', fontStyle: 'italic' },
                { token: 'identifier', foreground: 'f8f8f2' },
                { token: 'delimiter', foreground: 'f8f8f2' },
                { token: 'keyword.directive', foreground: 'ff79c6' }
            ],
            colors: {
                'editor.background': '#1e2029',
                'editor.foreground': '#f8f8f2',
                'editorLineNumber.foreground': '#5b5f7a',
                'editorLineNumber.activeForeground': '#b8bcd8',
                'editor.selectionBackground': '#3a3f5a',
                'editor.lineHighlightBackground': '#242733',
                'editorCursor.foreground': '#f8f8f2',
                'editorIndentGuide.background1': '#2c2f3d',
                'editorGutter.background': '#1e2029'
            }
        });
        monaco.editor.defineTheme('oaj-light', {
            base: 'vs', inherit: true,
            rules: [
                { token: 'comment', foreground: '8a90a6', fontStyle: 'italic' },
                { token: 'keyword', foreground: 'c2185b' },
                { token: 'string', foreground: '9a6700' },
                { token: 'number', foreground: '6f42c1' },
                { token: 'type', foreground: '0b6b78', fontStyle: 'italic' }
            ],
            colors: {
                'editor.background': '#ffffff',
                'editor.foreground': '#1f2328',
                'editorLineNumber.foreground': '#b0b4c4',
                'editor.lineHighlightBackground': '#f4f5fa'
            }
        });
    }

    // ---------------------------------------------------------------- completions
    function registerCompletions(monaco) {
        const mk = (monaco, range) => ({
            simple: (label, kind, detail) => ({
                label, kind, detail, insertText: label, range
            }),
            snippet: (s) => ({
                label: s.label,
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: s.doc,
                documentation: { value: '```\n' + s.body.replace(/\$\{\d+:?|\}|\$0/g, '') + '\n```' },
                insertText: s.body,
                // Singular "Rule" — the plural spelling does not exist, and referencing it
                // throws inside the provider, surfacing only as a bare "No suggestions".
                insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
                range,
                sortText: '0' + s.label      // snippets sort above plain words
            })
        });

        monaco.languages.registerCompletionItemProvider('cpp', {
            provideCompletionItems(model, position) {
                const w = model.getWordUntilPosition(position);
                const range = {
                    startLineNumber: position.lineNumber, endLineNumber: position.lineNumber,
                    startColumn: w.startColumn, endColumn: w.endColumn
                };
                const b = mk(monaco, range);
                const K = monaco.languages.CompletionItemKind;
                const line = model.getLineContent(position.lineNumber);

                // Inside an #include, offer headers and nothing else — anything else is noise.
                if (/^\s*#\s*include\s*[<"]/.test(line)) {
                    return { suggestions: CPP_HEADERS.map((h) => b.simple(h, K.File, 'header')) };
                }
                return {
                    suggestions: [].concat(
                        CPP_SNIPPETS.map(b.snippet),
                        CPP_KEYWORDS.map((k) => b.simple(k, K.Keyword, 'keyword')),
                        CPP_TYPES.map((t) => b.simple(t, K.Class, 'type')),
                        CPP_FUNCS.map((f) => b.simple(f, K.Function, 'function'))
                    )
                };
            }
        });

        monaco.languages.registerCompletionItemProvider('python', {
            provideCompletionItems(model, position) {
                const w = model.getWordUntilPosition(position);
                const range = {
                    startLineNumber: position.lineNumber, endLineNumber: position.lineNumber,
                    startColumn: w.startColumn, endColumn: w.endColumn
                };
                const b = mk(monaco, range);
                const K = monaco.languages.CompletionItemKind;
                return {
                    suggestions: [].concat(
                        PY_SNIPPETS.map(b.snippet),
                        PY_KEYWORDS.map((k) => b.simple(k, K.Keyword, 'keyword')),
                        PY_BUILTINS.map((f) => b.simple(f, K.Function, 'builtin'))
                    )
                };
            }
        });
    }

    // ---------------------------------------------------------------- public API
    const OAEditor = {
        /** Boot Monaco into `container`. Resolves once the editor is usable. */
        init(container, opts) {
            opts = opts || {};
            // The AMD loader and the web worker both need to resolve paths offline.
            window.require = { paths: { vs: BASE + 'vs' } };
            window.MonacoEnvironment = {
                getWorkerUrl() {
                    const src = 'self.MonacoEnvironment={baseUrl:"' + location.origin + BASE + '"};' +
                                'importScripts("' + location.origin + BASE + 'vs/base/worker/workerMain.js");';
                    return 'data:text/javascript;charset=utf-8,' + encodeURIComponent(src);
                }
            };

            const loader = document.createElement('script');
            loader.src = BASE + 'vs/loader.js';
            loader.onload = () => {
                window.require.config({ paths: { vs: BASE + 'vs' } });
                window.require(['vs/editor/editor.main'], () => {
                    // The global is the conventional AMD entry point and is complete once
                    // this module resolves.
                    const monaco = window.monaco;
                    monacoRef = monaco;
                    defineTheme(monaco);
                    registerCompletions(monaco);

                    editor = monaco.editor.create(container, {
                        value: opts.value || '',
                        language: opts.language === 'py' ? 'python' : 'cpp',
                        theme: opts.dark === false ? 'oaj-light' : 'oaj-dark',
                        fontFamily: "'JetBrains Mono','Cascadia Code',Consolas,'Courier New',monospace",
                        fontSize: 13.5,
                        lineHeight: 20,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        tabSize: 4,
                        insertSpaces: true,
                        renderWhitespace: 'selection',
                        bracketPairColorization: { enabled: true },
                        autoClosingBrackets: 'languageDefined',
                        autoIndent: 'full',
                        formatOnPaste: false,
                        smoothScrolling: true,
                        cursorBlinking: 'smooth',
                        padding: { top: 10, bottom: 10 },
                        suggestOnTriggerCharacters: true,
                        quickSuggestions: { other: true, comments: false, strings: false },
                        acceptSuggestionOnEnter: 'off',   // Enter = newline; Tab accepts.
                        tabCompletion: 'on',
                        wordBasedSuggestions: 'currentDocument',
                        suggestSelection: 'first',
                        scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
                        stickyScroll: { enabled: false },
                        occurrencesHighlight: 'singleFile',
                        renderLineHighlight: 'line'
                    });

                    editor.onDidChangeModelContent(() => {
                        if (programmatic) return;
                        if (changeHandler) changeHandler(editor.getValue());
                    });

                    readyResolve(OAEditor);
                });
            };
            document.head.appendChild(loader);
            return ready;
        },

        whenReady() { return ready; },
        isReady() { return editor !== null; },

        getValue() { return editor ? editor.getValue() : ''; },

        /** Replace the buffer. `keepUndo` false pushes a clean undo stop (problem/language switch). */
        setValue(text, keepUndo) {
            if (!editor) return;
            programmatic = true;
            try {
                if (keepUndo) {
                    editor.executeEdits('oaj', [{
                        range: editor.getModel().getFullModelRange(), text, forceMoveMarkers: true
                    }]);
                } else {
                    editor.setValue(text);
                }
            } finally {
                programmatic = false;
            }
        },

        setLanguage(lang) {
            if (!editor || !monacoRef) return;
            monacoRef.editor.setModelLanguage(editor.getModel(), lang === 'py' ? 'python' : 'cpp');
        },

        setTheme(dark) {
            if (monacoRef) monacoRef.editor.setTheme(dark ? 'oaj-dark' : 'oaj-light');
        },

        setReadOnly(ro) { if (editor) editor.updateOptions({ readOnly: !!ro }); },

        focus() { if (editor) editor.focus(); },
        layout() { if (editor) editor.layout(); },

        getCursorOffset() {
            if (!editor) return null;
            const p = editor.getPosition();
            return p ? editor.getModel().getOffsetAt(p) : null;
        },

        setCursorOffset(off) {
            if (!editor || off == null) return;
            try {
                editor.setPosition(editor.getModel().getPositionAt(off));
                editor.revealPositionInCenterIfOutsideViewport(editor.getPosition());
            } catch (e) { /* offset from a stale buffer; ignore */ }
        },

        onChange(cb) { changeHandler = cb; },

        /** Raw Monaco instance — self-test only; app code should use the methods above. */
        _editorForTest() { return editor; },

        /** Bind Ctrl/Cmd+Enter to submit, matching the old editor's shortcut. */
        addSubmitShortcut(fn) {
            if (!editor || !monacoRef) return;
            editor.addCommand(monacoRef.KeyMod.CtrlCmd | monacoRef.KeyCode.Enter, fn);
        }
    };

    window.OAEditor = OAEditor;
})();
