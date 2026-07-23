# CHANGELOG.md
# ── Full project history — newest entry on top ─────────────────

## [2026-07-23] — v2 rework: durable database, Monaco editor, data UI, stability (Phases 0–4) | By: Claude (Opus 4.8)

Approved plan in PLAN_V2.md (scope 0–6, Monaco, two repos, public). This session delivered a
fully-usable local product through Phase 4; Phases 5 (sharing) and 6 (hosting) were deferred to
the next session at the user's request ("stop at a point where it's still usable for me fully").

### Done This Session
- **Phase 0 — safety net.** Full folder backup (`../oa-judge-backup-2026-07-23`). `git init`
  with a `.gitignore` that keeps personal data (`app/data/`, `*.db`) out of the repo — the
  project had *no* version control before this. Built `rescue_drafts.py`: a one-shot tool that
  serves a recovery page on both 5000 and 5137 to pull back editor drafts stranded in
  per-origin localStorage by the earlier port move. (User still needs to run it in-browser.)
- **Phase 1 — persistence.** New SQLite DB (`app/data/judge.db`, WAL) with a migration runner
  (`app/db.py`) and a data-access layer (`app/store.py`) replacing the flat-file
  `runner/history.py`. **Submits now store the full source code** (v1 discarded it), plus
  compile output, first-failing-test index and runtime; custom Runs are logged; drafts autosave
  server-side; snapshots enable draft time-travel; OA sessions capture real time-on-problem
  (v1's `duration_s` was NULL on every row). Imported the 20 existing `history.json` attempts
  (`import_v1_data.py`, idempotent). Schema kept Postgres-portable for Phase 6.
- **Phase 2 — Monaco editor.** Replaced the hand-written transparent-textarea + highlight-overlay
  editor with vendored Monaco (`app/static/vendor/monaco/`, trimmed to 4.3 MB, fully offline).
  This eliminates by construction the caret-drift / paste-misalignment / line-height-rounding bug
  class that cost the most time on this project. Added a wrapper (`app/static/editor.js`,
  window.OAEditor) with Dracula-matched themes and C++/Python autocomplete: STL + builtin
  dictionaries and competitive-programming snippets (fori, fastio, vec, dsu, pq, binsearch, memo…).
  Drafts autosave (debounced) with periodic + pre-submit/reset/switch snapshots; localStorage is
  demoted to an offline fallback. Deep links via `#problem-id`.
- **Phase 3 — the data becomes useful.** Attempts tab (every submission, with the stored code);
  two-attempt **LCS line diff** auto-ordered old→new (see exactly what turned WA into AC); **draft
  scrubber** slider with Restore; **Stats** dashboard (solved / AC-rate / first-try / avg-attempts-
  to-AC / verdict bars); per-problem **Notes** with star/revisit/confidence; **Export all** endpoint
  (zip of the DB + a readable tree of code and notes — data is never locked in the app).
- **Phase 4 essentials.** Confirmed a forking TLE is killed as a process group and leaves zero
  orphans (this was already correct in v1's sandbox — verified, not assumed). Server now prefers
  `waitress` when installed and falls back to the Flask dev server (not force-installed into an
  externally-managed Python). Added a `/api/health` **single-instance guard**: double-launching
  detects the running copy and exits cleanly instead of crashing on the port.

### Verified
- v2 API end-to-end (26 checks): a submit's exact source is retrievable afterwards; drafts,
  snapshots, runs, OA sessions, notes, flags, stats all round-trip.
- Monaco headless self-test: boot, exact value/line/cursor round-trip, highlighting, language
  switch, and the completion widget opening with relevant C++ suggestions (fixed a real bug found
  there — the snippet enum is `CompletionItemInsertTextRule`, singular).
- All five Phase 3 views screenshotted with real seeded data; the diff correctly showed
  `int _m()`→`int main()` and the removed junk line. Export zip passes an integrity check.
- `verify_all.py` still green — every runnable reference ACs its own suite after all changes.

### Errors Hit
- Snippet completions silently returned "No suggestions": the insert-rule enum is
  `CompletionItemInsertTextRule` (singular), not the plural I first wrote. Found by capturing the
  in-page console error, not by guessing. Fixed.
- Monaco 0.56 ships hashed ESM chunks needing a bundler; used the 0.52.2 classic AMD build, which
  self-hosts with no build step.

### Next Session Must
- Phase 5 (sharing: `oa-problems` repo split, Sync/Add-Problem/Publish UI, CI, `setup.sh`) then
  Phase 6 (Docker per-run sandbox, Postgres, GitHub OAuth, deploy). Fold in making the two CISCO
  problems runnable. Import rescued drafts once the user runs `rescue_drafts.py`.

---

## [2026-07-23 19:00 IST] — Fixed editor paste-misalignment (metrics + browser caching) + auto-indent (same-session follow-up) | By: Claude (Opus 4.8)

### Done This Session
- Fixed the syntax-highlight overlay drifting out of line-alignment after pasting a block — root cause was a fractional font-size (13.5px) with a ratio line-height (1.55), which rounds per-line differently between the `<textarea>` and the highlight `<pre>` and accumulates. Switched both (and the line-number gutter) to a fixed **13px / 20px** integer metric in `app/static/style.css`. Verified with an overlay screenshot: identical text in both layers superimposes with zero drift (tested a 25-line block and the exact 20-line millennium-q1 stub incl. trailing newline + blank lines).
- Added **paste normalization** (CRLF/CR → LF, tabs → 4 spaces) and **Enter auto-indent** (carries the current line's leading whitespace, +4 after `{ ( :`) in `app/static/app.js`, via a new `insertAtCursor()` helper that uses `execCommand('insertText')` so native undo is preserved and the highlight auto-refreshes. Also strip stray `\r` in `refreshEditor()`.
- **Root-caused a "still broken after the fix" report to browser caching:** the metric fix was correct but the user's browser was serving the old cached `app.js`/`style.css`. **Proved the code is correct** by driving the *real* app (real `app.js`/`index.html`/`style.css`) headless with the user's exact `count1++` / `x++;` example and overlaying the textarea text on the highlight — perfect line alignment, no drift. Then belt-and-suspenders on caching: added `@app.after_request` no-cache headers in `app/server.py`, version-stamped the asset URLs in `index.html` (`style.css?v=2`, `app.js?v=2`), and — because the user's browser cache stayed stuck through hard-refreshes — **moved the app off port 5000 to 5137** (updated `_serve.sh`, `launch.bat`, `start.sh`, `start.bat`). A never-visited port URL cannot serve a cached copy, so relaunching loads fresh with no cache-clearing needed. Verified 5137 serves the fixed no-cache assets and is Windows-reachable.

### Errors Hit
- Editor still looked misaligned after the CSS fix → **cause was browser caching**, not the code (proven: served assets contain the fix and the overlay screenshot aligns). Resolved with no-cache headers; user must hard-refresh (Ctrl+Shift+R) or relaunch once to drop the already-cached old assets.

### Next Session Must
- Unchanged: make cisco-q1 and cisco-q2 runnable (see the entry below).

---

## [2026-07-23 18:30 IST] — Built OA Judge end-to-end; polished UI + syntax highlighting; edge-case test layer; Desktop launcher; context logs initialized | By: Claude (Opus 4.8)

### Done This Session
- **Built the whole judge from scratch:** Flask backend (`app/server.py`) + execution engine (`app/runner/`: sandbox with CPU/mem/output rlimits, C++/Python runners, verdict logic, unified execute, stress/shrink, problem loader, history, Markdown renderer). Verdicts AC/WA/TLE/MLE/RE/CE all confirmed with deliberate triggers.
- **Packaged 11 runnable problems** (Flipkart ×3, DE Shaw ×3, Millennium ×2, Uber ×3) + 3 statement-only (2 CISCO + 1 SQL). Verified references (copied from the DSA-notes `src/`, or freshly written+verified for millennium-q1 and uber-q1 where the originals printed two-part output). Used 6 Gemini/agy subagents in parallel for the frontend, per-company packaging batches, and LC/GfG research; **orchestrator verified everything by running it**, not by trusting agent "done".
- **Frontend overhaul:** rebuilt `index.html`, `app.js`, `style.css` — HackerRank-style layout, **syntax highlighting** via a lossless transparent-textarea overlay (Dracula palette, C++/Python tokenizers), renamed "Stress" → **"Find Failing Test"**, comprehensive OA-realistic output panels (stdout / stderr-debug-channel / compiler output / exit+signal on Run; input/expected/got/stderr on visible test rows; verdict-only on OA hidden rows). Verified in light + dark + live via Chrome headless screenshots.
- **Test-design upgrade:** added a curated `tests/edge/` layer (`make_hidden.py` now = edge cases solved by the reference + random). Backfilled **53 curated edge + 132 random** hidden tests across all 11 runnable problems. Full `verify_all.py` + `smoke_test.py` green.
- **Desktop launcher:** `OA Judge.lnk` on the Desktop → `launch.bat` → `wsl.exe bash _serve.sh`; confirmed the Windows browser reaches the WSL server (WSL2 localhost forwarding, HTTP 200).
- **Initialized context logs** (this file, `CLAUDE.md`, `PROJECT_STATE.md`, `.context/*`, `SESSION_LOG.md`) in `templatesv2/`.

### Errors Hit
- **`stress.py` recompiled the reference every iteration** (~1000 compiles/run → timeout). Fixed: compile reference once, reuse; skip the shrink phase when the first counterexample is already small.
- **Uber generators used string size-categories** ("small"/"large"); the tooling passes integer sizes, so they hit the "large" branch and emitted megabyte inputs. Fixed all three to an integer size hint; regenerated tests.
- **Two hand-written worked examples were wrong** (caught by brute force earlier in the DSA-notes phase); reinforced the "verify by running" rule.
- **Nested `wsl.exe` from inside WSL** didn't start the launcher server in testing — determined to be a test-environment artifact (real Explorer double-click is a clean entry); validated every component instead.
- **"Failed to fetch" on Find Failing Test** — user reported, then confirmed it was because the server window had been closed. Not a code bug.

### Next Session Must
- Make **cisco-q1-drone-delivery** (min-moves 0-1 BFS/Dijkstra over `(row,col,battery,vouchersLeft)`; samples 7/11/-1) and **cisco-q2-sniper-detector** (sliding-window; output `flag sniper` per line) runnable: write+brute-force-verify `reference.cpp`, add stub/generator/samples/edge cases, flip `problem.json` to `runnable:true, languages:["cpp"]`, then `make_hidden.py` + `verify_all.py` + `smoke_test.py`. Specs already in `_migrated_raw/cisco/coding.md`.
- (Optional) `git init` the repo so the session-end commit step can run; consider moving `templatesv2/` files to the `oa-judge/` root so the Session Protocol auto-triggers.
