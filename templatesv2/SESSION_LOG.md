# SESSION_LOG.md
# ── Personal Developer Journal — For the User, Not the AI ─────────
#
# Purpose: A detailed, narrative record of every session for the human.
# The AI-facing handoff files (PROJECT_STATE, session.json, CHANGELOG,
# dead_ends) are terse and optimized for fast onboarding. This file is
# the opposite: verbose, story-shaped, honest about mistakes, written
# so you can re-read it months later and remember what actually happened.
#
# RULES FOR THE AI WRITING ENTRIES:
#   1. Append a new entry at the TOP of the log every session.
#   2. ALWAYS include the date AND time (start + end, with timezone).
#   3. ALWAYS list the EXACT file paths touched, not vague summaries.
#      Example: `src/api/users.ts` (lines 42–87, added pagination)
#   4. Be honest about what went wrong, what got redone, and what you
#      were uncertain about. The user wants the truth, not a clean diff.
#   5. Use the section template below. Skip sections that don't apply,
#      but don't invent content to fill them.
#
# ─────────────────────────────────────────────────────────────────

## Session 1 — 2026-07-23 (built the OA Judge from nothing to a working, polished app)

**AI:** Claude (Opus 4.8) via Claude Code, using 6 Gemini/agy (Gemini 3.1 Pro) subagents for parallel grunt work
**Start → End:** 2026-07-23 ~11:00 IST → 2026-07-23 18:45 IST (~7.75h; start time approximate, from the earliest `oa-judge/` file mtime 11:03)
**Goal at start:** "Make a LeetCode/HackerRank-style compiler here that you can add all of these OA questions onto, with test cases, so I compile fully — with hide/show test cases like HackerRank OAs, and a normal LC mode with visible tests." Standalone folder on the Desktop, no relation to the DSA-notes project.

### What we set out to do
Turn the transcribed OA problems (Flipkart, DE Shaw, Millennium, Uber, Cisco) into a real, runnable local judge: an in-browser editor that actually compiles and runs C++/Python against real tests, with an OA mode (hidden tests, timer) and an LC mode (visible tests), plus a "race against a reference to find your smallest failing input" feature. Then, across follow-up requests: make the code colourful, back-fill proper edge cases, rename a confusing button, show all OA-realistic debug output, polish the whole UI, add a clickable Desktop launcher, and finally initialize a context-bridge template set.

### Files touched (all under `C:\Users\jishu\Desktop\oa-judge\` = `/mnt/c/Users/jishu/Desktop/oa-judge/`)
**Engine (written this session, correctness-critical):**
- `app/server.py` — Flask app + all `/api/*` endpoints (problems, problem, run, submit, stress, history)
- `app/runner/sandbox.py` — subprocess runner with RLIMIT_CPU/AS/FSIZE + wall-clock timeout; maps to TLE/MLE/RE
- `app/runner/run_cpp.py`, `app/runner/run_py.py` — compile + execute per language
- `app/runner/judge.py` — token/exact output comparison + verdict mapping
- `app/runner/execute.py` — unified compile+run+judge used by every endpoint
- `app/runner/stress.py` — generator→reference-vs-user→shrink; **rewritten mid-session** to compile the reference once (was recompiling per iteration) and to skip shrink when the counterexample is already small
- `app/runner/problems.py`, `app/runner/history.py`, `app/runner/md.py` (hand-written Markdown→HTML)
**Frontend (fully rewritten late in the session for highlighting + polish):**
- `app/static/index.html` — HackerRank-style layout; editor wrapped in a `.code-scroll` with a `<pre class="highlight-layer">` overlay + transparent `<textarea>`
- `app/static/app.js` — the syntax highlighter (`tokenize()` for C++/Python), `refreshEditor()`/`syncScroll()`, run/submit/find-failing handlers, OA leak-guard in `renderTestRow()`, comprehensive output panels
- `app/static/style.css` — design system, Dracula editor theme + token colors, light/dark, output/test/stderr/compile panels
**Tooling:**
- `add_problem.py`, `make_hidden.py` (**rewritten** to add the `tests/edge/` curated layer), `verify_all.py`, `smoke_test.py`, `merge_links.py`
- `start.sh`, `start.command`, `start.bat`, and the Desktop launcher `launch.bat` + `_serve.sh`; `C:\Users\jishu\Desktop\OA Judge.lnk` created via PowerShell (icon = `wsl.exe,0`)
**Content:**
- `problems/<id>/` for 14 problems — `problem.json`, `statement.md`, `editorial.md`, `stub.*`, `reference.*`, `generator.py`, `tests/{sample,edge,hidden}`; the uber `generator.py` files were **rewritten** from string-size to integer-size; `tests/edge/*.in` curated for all 11 runnable problems
- clean single-answer references authored fresh for `problems/millennium-q1-append-reverse/reference.cpp` and `problems/uber-q1-min-penalty-partition/reference.cpp`
- `_migrated_raw/` (copied the original transcriptions in), `_research/links.json` (curated)
- docs: `PLAN.md`, `API.md`, `FORMAT.md` (**edited** to add the edge-case standard), `PACKAGING_BRIEF.md`, `AGENTS.md`, `README.md`
**Context templates (this close-out):**
- `templatesv2/CLAUDE.md`, `templatesv2/PROJECT_STATE.md`, `templatesv2/CHANGELOG.md`, `templatesv2/.context/dead_ends.md`, `templatesv2/.context/session.json` (+ archived the blank template to `templatesv2/.context/sessions/template-bootstrap.json`), and this file

### Chronological narrative
1. Recon: confirmed g++ 13.3, Python 3.12, Flask 3.1.3, and that agy/Gemini pro-tier auth worked. No Node in WSL.
2. Wrote the contracts first (`PLAN.md`, `API.md`, `FORMAT.md`), then built the engine myself and packaged `flipkart-q1` end-to-end as the template. Booted the server and confirmed AC/WA/CE/TLE/RE all map correctly and OA mode hides hidden-test I/O.
3. Fired 6 Gemini subagents in parallel: the frontend, four per-company packaging batches, and LC/GfG research. Verified every returned package by running it (never trusted "done").
4. Integrated batches as they landed; found + fixed the stress recompile bug and the uber generator size-category bug. Generated hidden tests from references; full smoke test green.
5. Built the Desktop launcher; proved WSL2 forwarding lets the Windows browser reach the WSL server.
6. On follow-ups: rewrote the whole frontend for syntax highlighting + polish + OA-realistic output + the "Find Failing Test" rename; verified via Chrome headless screenshots (light/dark/live).
7. Added the curated `tests/edge/` layer and back-filled 53 edge cases across 11 problems; re-verified.
8. Cisco questions flagged by the user as "no language option, editor empty" — explained they're statement-only; read the specs to make them runnable, then deferred to next session at the user's request. Closed out by filling these context templates.

### What went right
- The "verify by running" discipline held throughout — every reference, every agent output, every verdict was executed, not eyeballed. The full gate is genuinely green.
- Parallel Gemini delegation saved real time on the bulky, repetitive packaging while I kept correctness.
- The transparent-overlay highlighter came out clean and is provably lossless, so it aligns with the caret with zero dependencies.
- WSL2 localhost forwarding "just worked" for the Desktop→browser→WSL-server path.

### What went wrong / what got redone
- `stress.py` was too slow (recompiled the reference every iteration) — rewrote to compile once; big latency win.
- Three uber `generator.py` files emitted megabyte inputs because they read the size hint as a category, not an integer — rewrote all three and regenerated tests.
- The frontend was written once by an agent, then I rewrote all three files from scratch for the highlighting/polish pass — a deliberate redo, not a mistake, but it was a big chunk of work.
- Couldn't test the literal Desktop double-click from inside WSL (nested `wsl.exe` is an artifact); had to settle for component-level verification.

### Decisions made (with rationale)
| Decision | Why | Reversible? |
|---|---|---|
| References are the source of truth; hidden `.out` generated, never hand-written | Hand-derived values kept being wrong | No (core principle) |
| Ambiguous OA statements commit to one reading; alternatives in the editorial | A judge needs one correct answer | Yes (per problem) |
| Hand-written highlighter, not CodeMirror/CDN | Offline + no build step | Yes (if constraint lifts) |
| Integer size hint in generators | Categorical sizes made huge inputs | No |
| Curated `tests/edge/` required per problem | Random-only misses bounds/adversarial | No |

### Surprises / things learned
- LeetCode returns HTTP 403 to both `curl` and `WebFetch` — you cannot machine-verify problem links from here; the links stay unverified.
- The `/mnt/c` Windows mount is ~10× slower for subprocess/file I/O under WSL — the single biggest performance drag (agents timed out on it; stress takes a few seconds).
- A subtle but important property: the syntax highlighter must be *lossless* (strip tags → exact source) or the colored layer drifts from the textarea caret.

### Loose ends / deferred
- **cisco-q1 and cisco-q2 are statement-only** — make them runnable next session (specs already read; this is the #1 next action).
- LC/GfG links unverified; flipkart-q4 generator doesn't scale (both low priority).
- No `git init` yet, so the protocol's end-of-session commit can't run. Templates sit in `templatesv2/`; move to the `oa-judge/` root if you want the Session Protocol to auto-trigger on future onboarding.

### Time-rough breakdown
- engine + backend: ~20%
- problem packaging + verification (incl. agent orchestration): ~30%
- frontend build + full polish/highlighting rewrite: ~30%
- edge-case layer + re-verification: ~10%
- launcher + context templates: ~10%

### Addendum — 18:30→18:45 IST — editor paste-alignment fix + auto-indent
After I'd filled the context templates, the user reported two editor problems: (1) pasting a block of code broke the display — the highlighting showed on one line but edits landed on the line below; (2) having to add indentation whitespace manually was annoying.
- **Root cause of (1):** the editor overlay used `font-size: 13.5px; line-height: 1.55` — a fractional font-size with a ratio line-height. The `<textarea>` and the highlight `<pre>` round each line box slightly differently and the error accumulates down the file, so after a big paste the visible layer drifted a whole line off the (transparent) caret. Classic textarea-overlay trap.
- **Fix:** `app/static/style.css` — `.line-numbers` and `.highlight-layer, .code-input` changed to fixed integer **`font-size: 13px; line-height: 20px`** (both rules). `app/static/app.js` — added `insertAtCursor()` (uses `execCommand('insertText')` to preserve undo + auto-fire the highlight refresh), rewrote the `keydown` handler for **Enter auto-indent** (carry leading whitespace, +4 after `{ ( :`), a **paste** handler normalizing CRLF/CR→LF and tabs→4 spaces, and a defensive `\r` strip in `refreshEditor()`.
- **Verified:** overlaid the textarea text (magenta) on the highlight layer (grey) for a 25-line deeply-indented block via a Chrome headless screenshot — perfect character-for-character overlap, zero drift at the bottom. `node --check app.js` passed. Confirmed port 5000 free / no listeners → safe to run.
- **Uncertain / not done live:** couldn't test the actual paste+type interaction headlessly (no way to drive keystrokes), so auto-indent and undo behaviour are verified by logic + syntax-check, not by a live keystroke test — worth a real try in the browser.
- **Follow-up (19:00): "still not working."** The user reported the misalignment persisted. I re-tested the exact `millennium-q1` stub in the overlay (20 lines incl. trailing newline + blank lines) — it aligned perfectly, and the *served* `app.js`/`style.css` contained the fix. So the code was right; the browser was serving the **cached old assets**. Added `@app.after_request` no-cache headers in `app/server.py` (`Cache-Control: no-store, no-cache, must-revalidate`; verified via `curl -D-`). Lesson recorded: for this overlay editor, "looks unfixed after a CSS change" = suspect the browser cache first. The user needs to relaunch + hard-refresh (Ctrl+Shift+R) once to drop the stale copy; no-cache prevents recurrence.

---

## Session N — YYYY-MM-DD (one-line headline)   [FORMAT REFERENCE — keep below newest entries]

**AI:** <which AI / IDE / model>
**Start → End:** YYYY-MM-DD HH:MM TZ → YYYY-MM-DD HH:MM TZ (~Xh)
**Goal at start:** <what the user asked for at the top of the session>

### What we set out to do
<2–4 sentence narrative of the intent>

### Files touched
- `path/to/file.ext` — what changed, with line numbers if useful

### Chronological narrative
1. ...

### What went right
- ...

### What went wrong / what got redone
- ...

### Decisions made (with rationale)
| Decision | Why | Reversible? |
|---|---|---|
| ... | ... | Yes / No |

### Surprises / things learned
- ...

### Loose ends / deferred
- ...

### Time-rough breakdown
- area A: ~X%

---
<!-- Append new sessions ABOVE this line, newest first. -->
