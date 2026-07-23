# OA Judge — HTTP/JSON API contract

The Flask server (`app/server.py`) serves the static frontend and this JSON API. All request and
response bodies are JSON. All endpoints are same-origin (`http://127.0.0.1:5000`). The frontend is
built **against this contract** and must not assume any field not listed here.

Verdict strings (exactly these): `"AC"`, `"WA"`, `"TLE"`, `"MLE"`, `"RE"`, `"CE"`, `"OK"`.
`"OK"` is used only for a bare Run with custom input (no expected output to compare).

---

### `GET /api/problems`
List all problems for the sidebar.

**200 →**
```json
{
  "problems": [
    {
      "id": "flipkart-q1-golden-price",
      "title": "Golden Price",
      "company": "Flipkart",
      "difficulty": "Easy",
      "tags": ["math", "digits"],
      "languages": ["cpp"],
      "runnable": true,
      "links": [{"site": "LeetCode", "url": "https://...", "note": "similar, not identical"}],
      "solved": false
    }
  ]
}
```
`solved` reflects whether attempt history contains an AC for that problem.

---

### `GET /api/problem/<id>`
Full detail for one problem.

**200 →**
```json
{
  "id": "flipkart-q1-golden-price",
  "title": "Golden Price",
  "company": "Flipkart",
  "difficulty": "Easy",
  "tags": ["math"],
  "statement_html": "<h2>...</h2>",          // statement.md rendered to HTML by the server
  "editorial_html": "<p>...</p>",            // editorial.md rendered; may be "" if none
  "languages": ["cpp"],
  "runnable": true,
  "links": [ ... ],
  "limits": {"time_ms": 2000, "memory_mb": 256},
  "stubs": {"cpp": "#include ...", "py": "..."},
  "samples": [                                // ALWAYS visible (both modes)
    {"index": 1, "input": "10 100\n", "output": "495\n"}
  ],
  "hidden_count": 12                          // number of hidden tests, contents NOT included
}
```
The frontend must never receive hidden test contents from this endpoint.

---

### `POST /api/run`
Compile (if needed) and run once against **custom input** the user typed. No judging.

**Request →**
```json
{"problem_id": "flipkart-q1-golden-price", "language": "cpp", "source": "....", "stdin": "10 100\n"}
```
**200 →**
```json
{
  "verdict": "OK",              // or "CE" / "RE" / "TLE" / "MLE"
  "compile_output": "",         // g++ stderr on CE, else ""
  "stdout": "495\n",
  "stderr": "",                 // program stderr (debug channel — always shown)
  "exit_code": 0,
  "signal": null,               // e.g. "SIGSEGV" when killed
  "time_ms": 12,
  "memory_kb": 3200
}
```

---

### `POST /api/submit`
Run against the full test set and judge. `mode` decides visibility.

**Request →**
```json
{"problem_id": "...", "language": "cpp", "source": "...", "mode": "lc"}   // mode: "lc" | "oa"
```
**200 →**
```json
{
  "verdict": "WA",                 // overall: AC only if every test AC
  "compile_output": "",
  "passed": 8,
  "total": 14,
  "time_ms_max": 120,
  "tests": [
    {
      "index": 1,
      "group": "sample",           // "sample" | "hidden"
      "verdict": "AC",
      "time_ms": 5,
      "visible": true,             // sample always true; hidden true only in lc mode
      "input": "10 100\n",         // present only when visible
      "expected": "495\n",         // present only when visible
      "got": "495\n",              // present only when visible
      "stderr": ""                 // present only when visible
    },
    {
      "index": 9,
      "group": "hidden",
      "verdict": "WA",
      "time_ms": 40,
      "visible": false             // OA mode: no input/expected/got — just the verdict + index
    }
  ]
}
```
In **oa** mode, `visible` is `false` for every hidden test and their `input`/`expected`/`got` are
omitted. In **lc** mode, hidden tests are fully visible. Samples are always visible in both.
Submitting records an attempt (see history).

---

### `POST /api/stress`
Stress the user's code against the reference on random inputs; return the smallest failing input.

**Request →**
```json
{"problem_id": "...", "language": "cpp", "source": "...", "iterations": 300}
```
**200 →**
```json
{
  "status": "counterexample",     // "counterexample" | "clean" | "no_generator" | "error"
  "checked": 143,                 // how many random cases ran before the first failure (or total)
  "counterexample": {
    "input": "3\n2 2 2\n",
    "expected": "0\n",            // reference output
    "got": "1\n"                  // user output (or a verdict like "RE"/"TLE")
  },
  "message": ""                   // populated for "clean"/"no_generator"/"error"
}
```

---

### `GET /api/history`  &  `GET /api/history/<problem_id>`
Attempt log, newest first.

**200 →**
```json
{
  "attempts": [
    {"problem_id": "...", "language": "cpp", "mode": "oa", "verdict": "AC",
     "passed": 14, "total": 14, "timestamp": "2026-07-22T18:30:00", "duration_s": 640}
  ],
  "revisit": ["deshaw-q1-music-player"]   // problems failed or never AC'd — the practice queue
}
```

---

### Frontend expectations (for the UI agent)

- Three-pane layout: problem list (left) · statement+editorial tabs (centre) · editor + result
  console (right), OR statement on top and editor/console below — your call, must be responsive and
  usable at 1280px.
- Language selector (only languages in `languages`). Load `stubs[lang]` into the editor on switch,
  but do **not** clobber unsaved edits without a confirm.
- Buttons: **Run** (custom stdin box), **Submit** (uses the mode toggle), **Stress**.
- **Mode toggle** LC ↔ OA. In OA mode: hide hidden-test I/O, show a running timer, and after a
  Submit disable further Submits until the user explicitly resets (a "give up / reveal" button).
- Result console: colour-coded verdict, per-test rows, a dedicated **stderr** panel (the one channel
  that survives — never hide it), and compile output on CE.
- Editor: plain but competent — monospace, line numbers, tab inserts spaces, Ctrl/Cmd+Enter submits.
  A vendored CodeMirror 5 is fine if available locally; otherwise an enhanced `<textarea>`. **No CDN
  / external network calls** — everything served locally.
- Persist the user's per-problem source in `localStorage` keyed by `problem_id:language`.
- Theme: light and dark, respecting `prefers-color-scheme`.
