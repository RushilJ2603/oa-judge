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

## Session 5 — 2026-07-26 (CP + System Design sheets, per-user contest tracker, Ctrl+' submit, company dedup, +1 problem, sync-infra fix)

**AI:** Claude (Opus 4.8) via Claude Code. Orchestrated a large **Grok 4.5** research fan-out for the sheet content; all synthesis, the app code, the design/QA, and every deploy were mine.
**Start → End:** 2026-07-26 (long continued session) → 2026-07-26 ~23:30 IST.

### What we set out to do
Turn the user's competitive-programming + system-design prep into structure inside OA Judge: a curated **CP sheet** (post-Striver, Codeforces-style, aiming Candidate Master) and a **System Design sheet** (HLD + LLD for placements), plus a **per-user contest tracker** that says whether they're on pace — all without touching the existing judge UI.

### What actually happened
- **Research (Grok vs agy).** Fanned out **106 Grok agents** (10 agy + 10 grok first, then a 106-job pool) via a memory-guarded pool (`_research_pool/run_pool.py`, cap 6, MemAvailable floor) so the 10GB WSL box never OOM'd. Grok clearly won on deep-research-with-link-verification (**10/10 vs agy 7/10** completion; richer, more accurate links), so Grok became the default. All 106 finished clean.
- **Synthesis.** `synth.py` parsed the Grok ladders into `app/sheets/cp.json` + `sd.json`: dedup by URL, **drop LeetCode from CP** (post-Striver = CF-style), then an **importance-weighted retier** — a flat 8/topic was wrong, so backbone OA topics (two-pointer, DP-1D, graphs, binary search…) get 16 core each and pure rating topics (FFT, HLD, centroid) get 0–2. Result: **335 must-do core** → ~4–5 months at 2–3/day. SD sections carry a `group` so the rail renders **sequentially** (Frameworks→Foundations→HLD→LLD, numbered steps).
- **Build (native, judge untouched).** `app/migrations/006_cp_sheets.sql`, `app/cp.py` (fetchers + deterministic tracker + multi-site contest feed), `app/store.py` (data layer + `canon_company`), `app/server.py` (8 routes), `app/static/sheets.js` + big `style.css` additions (v12→v16), `app/static/index.html` (header nav), `app/static/editor.js` (Ctrl+' = KeyCode.Quote).
- **Visual QA.** Used the Playwright chromium cache (`--headless --screenshot`) to shoot CP/SD/Tracker on desktop **and** mobile, then a single fix pass: tofu `+` glyph → ASCII, SD titles leaking `h02_load_balancing` (fixed `h1_title` to strip id/slug prefixes), goal label "Rating 1900 (1900)" → CF tier name, and a **mobile header overlap** (hide wordmark + scroll the left cluster).
- **New problem.** Authored + gated `practice-min-edge-reversals` (0-1 BFS, `problems/practice-min-edge-reversals/`) under Iris — Personal / **Practice**; reference cross-checked vs a Dijkstra brute over 500 random graphs, `gate_candidate.py --allow-no-anchor` = PASS, 100% mutation, 23 hidden gz tests.
- **Company dedup.** `store.canon_company()` merges `de shaw` + `DE Shaw` → `DE Shaw` and routes blank/`Unknown OA` → a single **Practice** company (verified: Iris — Personal 27→28, DE Shaw 5+3→8).

### The gnarly bug (worth remembering)
The user reported the tracker still showed **only Codeforces contests** after I'd shipped the multi-site fetch. Two things: (1) the `contest_cache` has a 1h TTL so the old CF-only rows were still served — force-refreshed via `fly ssh`; (2) more importantly, `sharing.sync()` on live returned **"problems/ is not a git checkout"** — the volume bank at `/data/problems` had been seeded WITHOUT a usable `.git`, so **every bank push since seeding (batch8, DE Shaw) had silently never reached the live app** (it sat at 122). Since `oa-problems` is public, I git-cloned it fresh onto the volume (temp dir → swap → `fly apps restart`), which also made future Syncs work. Also learned LeetCode's `/contest/api/list/` REST endpoint 403s bots — switched to its **GraphQL `upcomingContests`**, which works.

### State at end
Live at oa123.fly.dev: **123 problems** (bank now a real git checkout), CP + SD sheets, deterministic per-user tracker with a keyless four-site contest feed + rating-band recommendations (CF always included), Ctrl+' submit. app HEAD `ab50adb`, bank HEAD `6e6c47c`, assets v16. Parked: batch9's 14 grok judge-problems still need gate/merge.

## Session 4 — 2026-07-25 (mutation-testing gate, gated Grok pilot +14 problems, 3 app features, $0 storage, 3 deploys)

**AI:** Claude (Opus 4.8) via Claude Code. Orchestrated **Grok 4.5** (`cursor-agent --model cursor-grok-4.5-high`) to bulk-author candidate problems — but ONLY inside an isolated staging clone, and nothing merged without my gate passing. The gate tooling, all fixes, all app code, and every merge decision were mine.
**Start → End:** 2026-07-25 (long continued session, spanning the quality pivot through content + features) → 2026-07-25 ~22:35 IST.
**Goal at start (evolved):** finish pushing the last authored problems → then a hard pivot the user asked for: *"ensure the quality never drops even a single bit, not for questions or test cases."* That became: build real test-suite-strength checking, use Grok to scale authoring safely behind it, then fix whatever the user found while using the live app.

### What we set out to do (and did)
1. **Made quality a tool, not a checklist.** Built `mutation_test.py` — it mutates the verified reference (flip `<`/`<=`/`==`/`+`/`min`, delete statements) and demands the suite KILL every non-equivalent mutant; survivors are auto-triaged (generator + ±1 fuzz) into "equivalent" vs a real GAP, and `--fix` saves each gap's distinguishing input as an edge test. Wrapped everything into `gate_candidate.py` (one command: anchor + independent brute + audit + 100% mutation).
2. **Fought the gate until it was trustworthy.** Four real soundness bugs, each of which would have silently corrupted the bank at scale (see "what went wrong").
3. **Healed the existing bank to 100% mutation**, relabelled 2 mislabeled Easy problems, clarified book-allocation.
4. **Ran a gated Grok pilot** (4 agents, 18 slugs) → **14 merged, 1 deferred, 3 correct SKIPs**. Bank 42 → 62.
5. **Fixed/added 3 app features the user asked for or hit:** LaTeX statement rendering, one-click bug reporting (+ a discoverable tab-bar button), topic search that's hidden on the problem view.
6. **$0 storage:** gzipped hidden tests (bank 112M → 58M) with transparent decompression.
7. **Deployed 3× (Fly v8/v9/v10)** and answered the user's Fly cost question.

### Files touched (exact paths)
**Gate tooling (`/mnt/c/Users/jishu/Desktop/oa-judge/`):**
- `mutation_test.py` (NEW then hardened) — `cpp_mutants`/`cpp_deletion_mutants`, PCH-based compile, `oracle_outputs` (reliable: retry@4× then drop uncomputable, returns `max_ref_seconds`), `killed_by` (timeout/crash = kill w/ confirm-retry), adaptive `mutant_to`, `find_distinguisher` (generator + `_fuzz_inputs`), grammar-safe `_fuzz_inputs` (payload rows only), `run()` (non-zero exit → `<ERR>`), `_slurp` + gzip-aware `collect_inputs`, `OAJ_MUT_WORKERS` cap.
- `gate_candidate.py` (NEW) — full per-candidate gate; hard-fails on a mutation SKIP (Python-only ref).
- `compress_bank.py` (NEW) — gzip existing hidden tests in place (idempotent, mtime=0).
- `make_hidden.py` — `_write_gz` (writes `*.in.gz/*.out.gz`), `OAJ_PROBLEMS_DIR` isolation.
- `audit.py` — `OAJ_PROBLEMS_DIR` isolation; `SOLUTION.md` — §4.1 mutation standard + §4.2 difficulty rubric.
**App (`app/`), deployed:**
- `app/runner/md.py` — `_mathify`/`_math_inner` (inline `\(…\)` → Unicode + `<sup>/<sub>`).
- `app/runner/problems.py` — `_read` + `_load_tests` read plain-or-`.gz` (the judge's compressed-test support).
- `app/store.py` — free-text search matches `topic`; `add_bug_report`/`bug_reports`.
- `app/server.py` — `POST /api/report`, `GET /api/reports` (owner-gated by `OAJ_OWNER_GITHUB_ID`).
- `app/migrations/005_bug_reports.sql` (NEW) — `bug_report` table.
- `app/static/app.js` — hide topic on the sidebar sub-line; report box + `wireReportIssue`/`openReportBox`; tab-bar Report button.
- `app/static/index.html` — `#tab-report-btn`; `app/static/style.css` — `.math`, `.report-*`, `.tab-report`.
**Bank (`problems/`, repo `oa-problems`):** 14 merged Grok packages (`oahelper-meeting-room-allocation`, `-train-reservation-reroute-auditor`, `-walking-in-light`, `-maximize-score-after-n-operations`, `-colorful-construction`, `-the-magic-graph`, `-vertex-disappearance-in-a-graph`, `-warehouse-robotics-system`, `-maximum-array-sum-with-subarray-flips`, `-valid-edge-addition`, `-valid-memory-block-sizes`, `-weighted-meeting-scheduler`, `-kth-number-containing-101-in-binary`, `-uber-zone-clusters`); healed `goldman-2048`, `rippling-q2-array-merge`, `tuf-aggressive-cows`, `tuf-count-number-of-nice-subarrays`; relabelled `oahelper-calculate-amount` + `oahelper-final-price`; clarified `tuf-book-allocation-problem`; ALL `tests/hidden/*` gzipped by `compress_bank.py`.
**Staging (`/mnt/c/Users/jishu/Desktop/oa-staging/`):** `agentA..D/` (gate tools + `scraped/` + `PROMPT.txt` + `out/`); `agentD/out/oahelper-valid-number-partitions` kept as the deferred package.
**Context manager (this close-out):** `templatesv2/PROJECT_STATE.md`, `templatesv2/CHANGELOG.md`, `templatesv2/.context/dead_ends.md` (3 new entries), `templatesv2/.context/session.json` (+ archived prior to `templatesv2/.context/sessions/2026-07-24T20-45-00+05-30.json`), and this file.

### What went right
- The gate did its job on Grok's output: every package with a *correct* reference but a *weak suite* was caught and auto-healed to 100%; the too-easy ones Grok correctly SKIPped. Nothing weak slipped through.
- The user's "the constraints don't render" report turned out to be presentation, not correctness — I verified the vertex problem against a 3000-case independent simulator before touching anything, so I fixed the renderer (the real bug) instead of the problem.
- Caught my own bugs before they hit the bank: the phantom-gap classes were found because I actually re-ran and read the outputs, not because a test told me.

### What went wrong / got redone (honest)
- **My own timeout "fix" hung the gate for >30 min.** I first made a mutant timeout "skip, don't kill" — which let an infinite-loop mutant survive and get re-run 80×. Root cause was the oracle, not the kill rule; redone properly (reliable oracle, timeout/crash = kill, adaptive timeout).
- **Two phantom-gap classes.** The ±1 fuzzer mangled count fields, and `run()` read a reference SIGSEGV as empty output — both made harmless mutants look killable and would have persisted invalid edge tests. Found the crash one only because `make_hidden` printed `rc=-11`; fixed both, then RE-HEALED train-reservation (its 5 "gaps" collapsed to 1 real one; 4 mutants correctly reclassified as equivalent-on-valid-domain).
- **I OOM-crashed the WSL VM** by running a full-bank mutation sweep concurrently with single runs. That was the "it crashed again" the user saw — not Grok. Capped workers; never stack heavy runs.
- **A `fly deploy` failed** because `cd X && git push &` backgrounded the `cd`, so deploy ran from the wrong directory. Re-ran with explicit `-a oa123`.
- **The compressed-bank commit looked "lost"** — the background `git add -A` of 4304 files over `/mnt/c` was slow and I checked mid-push, saw the old HEAD, and pkill'd a push that had actually already committed. Recovered cleanly (commit `05266ce` was there; re-pushed).

### What I was uncertain about / deferred
- **valid-number-partitions** — Python bignum reference, so `mutation_test` (C++ only) can't certify its suite. I refused to merge it under-gated. It needs a mod-1e9+7 C++ rewrite or Python-mutation support.
- **gzip only gave ~2.3–2.9×** on max-scale numeric data (high entropy), not the 5–8× I hoped. It roughly doubles the volume ceiling; past ~3,500 problems the next lever is capping max-scale hidden-test size (lossy) — I left that as a deliberate future choice rather than silently reducing coverage.
- Exact per-problem provenance of the +20 oa-helper count is approximate; the 14 pilot merges are exact (commits `12f6a9b`…`8399dbb`), the rest were OA-Helper batches A/B earlier this session.

## Session 3 — 2026-07-24 (went live on Fly + OAuth, built a scraper via Grok, ingested verified problem batches)

**AI:** Claude (Opus 4.8) via Claude Code. Orchestrated **Grok 4.5** through the Cursor CLI (`cursor-agent`) for the scraper only; the app + all problem authoring were done by Claude directly.
**Start → End:** 2026-07-24 (start time approximate — this was a long continued session spanning the deploy work) → 2026-07-24 ~20:45 IST.
**Goal at start (evolved across the session):** deploy the judge so friends can use it with logins; make the UI scale to thousands of questions grouped by *source ▸ company*; build a scraper for TUF+ and OA-Helper (the user has paid logins); then ingest specific problem batches (Microsoft, Goldman) with OA-quality, verified test cases; and finally fill this context-manager (templatesv2) with the latest state.

### What we set out to do (and did)
1. **Deploy + multi-user.** Live on Fly.io (`oa123.fly.dev`), GitHub OAuth, scale-to-zero (~$0/mo), DB + bank on a persistent volume.
2. **Scale the UI.** A `problem_index` search table + a two-level **source ▸ company** dropdown; relabel `gyan` → "Iris — Personal"; add a **$0 presence** chip ("who's online", no heartbeat).
3. **Fix the Sync bug.** New problems didn't stick on the hosted site → the bank was in the ephemeral image fs under scale-to-zero → moved it to the persistent volume, seeded from the image.
4. **Harden authoring.** Fixed a stub regression (solve-in-main → separate function); wrote `SOLUTION.md` + a new `audit.py` gate; made **test quality mandatory** (≥5 edges incl. max-scale + brute-force cross-check every reference).
5. **Build the scraper** (`../oa-scraper`) by driving Grok, scoped strictly to that repo; TUF 397 + OA-Helper ~1500 with premium content.
6. **Ingest verified batches:** Microsoft ×15 (13 TUF textbook + 2 OA-Helper story) and Goldman ×3 (Iris-Personal).

### Files touched (exact paths)
**App (`/mnt/c/Users/jishu/Desktop/oa-judge/`):**
- `app/store.py` — `SOURCE_LABELS`/`SOURCE_ORDER` (gyan → "Iris — Personal"), `companies_by_source` in `problem_facets()`, `touch_user()`/`online_users()` presence helpers
- `app/server.py` — `_touch_presence()` in `before_request`, `/api/presence`, `sharing.ensure_seeded()` on boot
- `app/config.py` — `PROBLEMS_SEED`; `app/sharing.py` — `ensure_seeded()` (copytree seed→volume)
- `app/migrations/004_presence.sql` — `user.last_seen` + index
- `app/static/app.js` — source▸company dropdown tree (`renderSourceTabs`/`sourceRow`/`companyRow`), presence widget (`setupPresence`/`refreshPresence`/`showPresenceList`)
- `app/static/index.html` (presence chip, `?v=9`), `app/static/style.css` (dropdown tree + presence styles)
- `fly.toml` — `OAJ_PROBLEMS_DIR=/data/problems`, `OAJ_PROBLEMS_SEED=/problems`
- `audit.py` (NEW), `SOLUTION.md` (NEW)
- `problems/*/stub.cpp` — 9 stubs refactored to a separate solution function (goldman-2048, goldman-book-cricket, goldman-dora-preferred-route, goldman-non-repeating-digit-product, oa-q1/q2/q3, rippling-q1/q2)
- `problems/FORMAT.md` — gate pointers + mandatory test standard
- **18 new problem packages** under `problems/`: `tuf-assign-cookies`, `tuf-best-time-to-buy-and-sell-stock`, `tuf-climbing-stairs`, `tuf-best-time-to-buy-and-sell-stock-ii`, `tuf-count-inversions`, `tuf-aggressive-cows`, `tuf-book-allocation-problem`, `tuf-binary-subarrays-with-sum`, `tuf-count-subarrays-with-given-xor-k`, `tuf-count-number-of-nice-subarrays`, `tuf-candy`, `tuf-0-and-1-knapsack`, `tuf-burst-balloons`, `oahelper-calculate-amount`, `oahelper-final-price`, `goldman-missed-courses`, `goldman-unstable-tasks`, `goldman-largest-container` (each: problem.json, statement.md, stub.cpp, reference.cpp, generator.py, tests/{sample,edge,hidden})
**Scraper (`/mnt/c/Users/jishu/Desktop/oa-scraper/`):** `git init`; Grok edited `oa_scraper/oa_helper.py`, `oa_scraper/tuf.py`, `oa_scraper/html_md.py`; `config.local.json` holds (gitignored) the TUF Bearer token + OA-Helper `oa_session` cookie + device id/signature.
**Context manager (this close-out):** `templatesv2/PROJECT_STATE.md`, `templatesv2/CHANGELOG.md`, `templatesv2/.context/dead_ends.md` (4 new entries), `templatesv2/.context/session.json` (+ archived prior to `templatesv2/.context/sessions/2026-07-23T19-00-00+05-30.json`), and this file.

### What went right
- Every one of the 18 new references passed an **independent brute-force cross-check** (1500–4000 trials), not just `verify_all`. The Largest Container reading was validated against full **BFS reachability** — that turned an ambiguous OA into a defensible judge.
- Catching **OA #8**'s self-contradicting official solution before shipping — exactly what the verification discipline is for.
- The Grok delegation stayed perfectly in its lane: after every run I confirmed `oa-judge`'s git HEAD was unchanged and both gates still green. The app was never touched by the scraper.

### What went wrong / redone
- The **Sync-persistence** bug was subtle: it only manifested after a scale-to-zero cold start, and the first debugging assumption (multi-machine index split) was wrong — there's only one machine; the real cause was the ephemeral-fs bank. Redirected once I checked the volume mounts.
- Spent effort chasing TUF+ premium via the SSR page + Bearer header before realising the data lives on the `backend-go` API. Two Grok rounds (wire → then fetch-from-API) instead of one.
- Mis-identified the OA-Helper credential twice (thought device_id was the cookie; then thought a Supabase JWT was needed) before the user's `Copy as cURL` revealed the real `oa_session` cookie + `/api/proxy/question` flow.

### Uncertain / judgement calls
- Problems (b) Unstable Tasks and (c) Largest Container were **ambiguous in the user's description**; I committed each statement to one reading (stated as THE rule) and brute-verified that reading. If the real OA meant something else, they'll need a tweak.
- OA-Helper has 55 Microsoft questions but many premium ones **lack stored samples** and some have broken official solutions — only the verifiable ones were ingested; the rest are deliberately skipped for now.

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
