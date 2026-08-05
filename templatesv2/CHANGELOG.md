# CHANGELOG.md
# ── Full project history — newest entry on top ─────────────────

## [2026-08-03] — session 9: the Mock OA, and another Grok authoring batch | By: Claude (Opus 5, Claude Code)

### Done This Session

- **MOCK OA — a timed paper, not a timed problem.** The judge could already put a clock on one
  problem (`oa_session`, client-side). An OA is a *paper*, and what it actually measures is
  **triage**: which question you open first, when you give up on Q2 for Q3, whether you left enough
  of the clock for the hard one. New tab `Mock OA`; new module `app/mockoa.py`, migration 013,
  `app/static/mockoa.js`, `MOCKOA.md`, and `test_mockoa.py` (91 invariants).
  - **15 hand-picked papers** — 5 × 1 hour, 5 × 2 hours, 5 × 3 hours, **45 distinct questions with
    no repeats**. Not sampled: each paper ramps, no two questions in one paper want the same
    technique, and the company papers (Microsoft, Amazon, Goldman, DE Shaw, Uber, Flipkart, Google,
    Citadel) are built from that company's own bank problems. Two are declared **themed drills**.
  - **Random papers from a time model**, which is what "adjust the count to the difficulty" means:
    Easy 18 / Medium 32 / Hard 50 expected minutes, and a paper is any non-decreasing ladder of 2–4
    questions filling 78–114% of the requested length. Three hours is four questions when two are
    Hard. Prefers questions never solved; gives each slot a different technique family.
  - **The clock belongs to the server.** `ends_at` is written once at start; the browser's countdown
    is a rendering of it that re-syncs. Reloading, closing the tab or opening a second device cannot
    buy a minute, expiry is settled server-side (a closed laptop still ends the paper on time), and
    **a submission after the deadline does not score**.
  - **Results are derived, never stored twice** — from the same `attempt` rows the rest of the app
    uses, so a paper cannot disagree with your history. Partial credit is passed/total on the best
    submission, because a near-miss is the most useful line in a report.
  - **No technique is ever named.** Cards carry title / difficulty / company and nothing else — the
    same rule the problem list follows by hiding `topic`. The hand-written blurbs are grepped for
    algorithm names by an invariant, since a blurb is exactly where that rule would rot.
  - OA mode is forced inside a paper (hidden tests), but its **one-submission lock is skipped** —
    that lock is a practice rule; real OA platforms let you resubmit until the clock stops.
  - Bug caught before shipping: the expiry payload had no `cards`, so the report the browser draws
    when the clock runs out would have had **no rows on it**.

- **Grok authoring batch 10 — bank 142 → 163.** 36 slugs from the OA-Helper scrape (2,951 scraped,
  917 still eligible after de-duping against the bank and everything previously attempted).
  Deliberately **hard-first**: every eligible Hard was taken before topping up with Mediums, because
  the bank skewed 98 Medium / 33 Hard and a mock paper needs a hard anchor. Same untrusted-author
  pipeline as batches 5–9: Grok writes, `gate_candidate.py` decides, nothing merges without
  `GATE: PASS`. **22 authored, 22 passed the sandbox gate, 21 merged** — `oahelper-new-game` was
  rejected on the way in when the repo's own `mutation_test.py` scored it 98.9% (one mutant
  survived). That is the merge gate catching what the candidate gate did not, which is exactly why
  there are two of them. Grok also skipped 14 slugs on its own for being too easy or ambiguous,
  which is the behaviour that makes the batch usable at all.

### Bank +3: Schrodinger (Iris — Personal), recalled from the user's own OA

Every ambiguity was settled with the user before a line was written, and each reading was checked
against their worked example first — the Q3 cost model only reconciles at 1 unit per machine (their
own narration gives cost 5 for `20 -> 25`), which rules out the "1 unit per operation" reading that
the problem text also admits and that would have made the sample answer 3 instead of 8.

- `schrodinger-min-removal-unique` (Medium) — shortest contiguous block to delete so every letter is
  distinct. What makes it not-quadratic: an all-distinct prefix or suffix is at most 26 characters,
  so the search is a 27x27 table however long the string is.
- `schrodinger-palindromic-ancestors` (Hard) — XOR prefix masks + 27 lookups per node in ONE dfs
  answers every node at once. The per-query walk the user hit TLE with measures >30s here against a
  3s limit. **The reported "were treeFrom/treeTo given reversed?" confusion is the problem itself:
  the pairs are unordered.** Sample 2 is sample 1 with every edge flipped and the answers are
  identical, which states the rule instead of leaving the solver to discover it.
- `schrodinger-three-regions` (Medium) — 4^n labelling over n <= 10; a region that transfers its
  machines away is spent, so the plan shape is forced. Edge 11 answers 2999999997, which overflows
  a 32-bit result.

References are mine and were stress-verified against independent brute forces before packaging
(4000 random strings / 1500 random trees under random edge orientation / 600 random cost cases).
`verify_all` + `audit` clean, mutation 100% on all three (31/31, 50/50, 25/25). Q3's limit is 4000ms
because a plain Python 4^n enumeration measures 1.1s and the judge runs on a shared-cpu machine.

### Fixed / new tooling
- `store.py` gained the mock-OA lifecycle; starting a paper while one runs **abandons** the first,
  because two live clocks would both claim the same submissions.
- `_loop/gate_agents.sh` (new): gate a batch in waves, so finished agents can be verified while the
  slower ones are still authoring. Detached runs need `setsid` — a plain `nohup … &` from the
  harness dies with its process group, which is why the first gate run produced an empty file.

## [2026-08-02] — session 8: interview fixes from real use | By: Claude (Opus 5, Claude Code)

### Done This Session
Five asks, all from actually sitting interviews. Two further bugs fell out of verifying them.

- **Completion state, and the score where you can see it.** The report was already strong — overall %,
  a meter per phase, every missed point with your own words quoted back — but it lived behind a button
  or in the history list, and **the catalog showed no completion state whatsoever**: all 322 topic
  cards looked the same whether you had never opened one or aced it three times. Cards now carry a
  mastery badge (✓ solid / ↻ shaky), a strip counts "N of 322 attempted · M solid", and four chips
  filter to Not started / Needs work / Solid. Finishing an interview now shows the score on the
  completion panel instead of only "Interview complete".
  Progress is derived from **checkoffs**, not `interview_session.rubric_id` — that column holds only
  the segment a session stopped in, so counting from it would credit one topic for a 4-topic loop.

- **Raw LaTeX reaching the reader** (`($\text{RT} = \text{WT}$)` shown literally). Two causes.
  `md.py` only understood `\(…\)` — authored statements can be rewritten offline, live model output
  cannot — so `$…$`/`$$…$$` are handled now, with boundaries strict enough that "it costs $5 and $10"
  stays prose. And **reopened interviews rendered nothing at all**: only raw markdown is stored and
  the live turn was rendered at apply-time, so resume showed literal `**bold**` and fences.
  `_math_inner` became ONE `\name` lookup pass (a LaTeX command name is letters only, so it ends at
  the first non-letter — per-command `\b` anchors failed on `\sum_{i=1}` because `_` is a word
  character, and the sigma silently never appeared). Code spans are lifted out before every other
  rule, which also fixed `*` inside backticks being italicised.
  **Measured: 166 user-facing files, 56 leftover LaTeX artefacts → 0, 0 injected tags.**
- **Deletable past interviews, ordered by last interaction.** Delete hard-removes the session,
  transcript, evidence and queued jobs, then **rebuilds the skill model from surviving evidence** —
  read-time filtering would have been cheaper and wrong, since mastery is an accumulated EMA.
  Ordering moved to `MAX(turn.created_at)` with a relative "3 hours ago" label.
- **Weak spots made visible.** The evidence already steered loop composition invisibly; now it is a
  tab — per-topic mastery, "3 of 7 points still shaky", click to drill, or one loop from the top 4.
- **Context management.** `record_behavior` had **zero callers**, so the behavioural profile was dead
  code and INTERVIEW HABITS never rendered; it is now written at session close from stored turns and
  the app's own stuck counter, as instructions rather than raw numbers. `topic_recall` gives the
  interviewer prior-attempt context for a topic it has asked before — counts only, never point ids or
  text, since the dossier deliberately drops the live rubric to avoid leaking answers.
- **Cross-segment answer leak (found while verifying the above).** The dossier dropped only the live
  rubric, so in a mixed loop a weak-area line could name a point from segment 3 — previewing it. Not
  incidental: weak-spot drills compose loops from exactly the topics that rank weakest. Reproduced
  with 3 leaked points, 0 after. Pinned by an invariant that also asserts the dossier is still
  populated, so the guard cannot pass by quietly emptying it.
- **Progress rail highlighted the wrong step** in mixed loops (`indexOf` over repeated phase names).
  Walked a 3-segment loop end to end: the old logic gave `[0,1,0,1,0,1]`. Server now sends the step.
- **Timestamps to microseconds** — the ordering key must be finer than the events it orders, and
  `rebuild_skills` replays an order-dependent EMA over checkoffs written in one tight loop.

### Later the same session — hosting, speed, and a 66-agent hunt
- **The interviewer became hosted.** `app/interview/cloud.py` answers turns from the Fly server, so
  no laptop is needed: **5.0s** for a real turn with no worker running. The local agy worker remains
  the fallback for when the free tier rate-limits (it does, quickly).
- **~10s off every turn** by long-polling the lease. The old geometric backoff existed to let Fly
  sleep, but an interview is mostly idle, so the worker was on a 20s interval by the time the
  candidate hit send. **Discovery 10.0s → 0.10s**, with fewer requests than the poll.
- **A rate limit no longer ends an interview** — it stopped spending retry attempts and stopped being
  reported to the browser as a terminal error while the job sat queued about to succeed.
- **A 66-agent hunt** (24 of them holding REAL interviews through `interview_cli.py`) produced 389
  findings; **10 were real** after verification. Three were misgrading the student: correct answers
  discarded when a phase advanced mid-exchange, `TAUGHT` clawing back earned credit, and `[PARTIAL]`
  frozen at half credit. Also: ending mid-question, curiosity counted as being stuck, help arriving a
  turn late, truncated SAFETY/RECITATION replies accepted as complete, and the report spinner.
- **Mobile**: the shell claimed more height than the screen had (one wrong height, every tab), and
  the six-item nav made the header wider than a phone so the page panned into empty space.

### Verification
- `test_interview.py`: **17 → 105 invariants**, plus **12** in `test_worker_routing.py`.
- `smoke_test.py`: **ALL GOOD** — every reference ACs, every stub correctly fails.
- Endpoints exercised through a real `test_client()`: rendered turns on session/resume, delete →
  history and weak spots both empty, double-delete → 404, weak-spot drill starts a MIXED plan.
- Deployed to Fly **v47 → v59** across the session; `/api/interview/weak` answers **401, not 404**, on the live host, and the
  live `interview.js?v=9` carries the new code.

### Not Done / Deferred
- **The mixed-loop rail still shows repeated phase names** ("recognition, approach" ×3) with no
  indication of which topic each belongs to. The *highlight* is now correct; the labels are ambiguous.
- **`interview.js` still cannot be run or even syntax-checked locally** — no `node`/`deno`/`bun` in
  WSL. Server-side behaviour was driven through Python; client-only bugs remain browser-only finds.

---

## [2026-08-02 14:00 IST] — session 7: +3 gated problems, statement-render fix, and a full MOCK INTERVIEW system | By: Claude (Opus 4.8, Claude Code)

### Done This Session
- **+2 gated Arcesium problems** (Iris — Personal), both **GATE: PASS, 100% mutation**:
  `arcesium-max-campaign-score` (Hard — the answer is the sum of the k largest `max−min` window
  spreads; the user's priority-queue sweep was the trap, and their worked example `[1,2,5,3,4], k=4
  → 15` was verified with a brute force before anything was written) and `arcesium-banquet-seating`
  (Medium — feasible iff `m ≥ n + (S − minD) + maxD`; cross-checked on 400 cases against exhaustive
  circular permutations, 0 mismatches). With `goldman-min-refueling-stops` earlier: bank **139 → 142**.
- **Statement rendering fix.** 8 statements (incl. that day's POTD) wrapped constraints in `$…$`
  LaTeX, which the renderer does not process, so they displayed raw. Converted corpus-wide to
  backticks + Unicode (`\le`→≤, `\cdot`→·, `\binom{4}{2}`→`C(4, 2)`).
- **CP-sheet scratchpad parity** — per-question pads now seed the standalone compiler's starter
  scaffold via a shared `ccStarter()`; Python was blank and C/Java/Kotlin were getting the wrong
  template.

### MOCK INTERVIEW SYSTEM (the bulk of the session)
- **Corpus: 322 gated rubrics** in `problems/_interview/` — CS Fundamentals 194 (the user's own
  OS/DBMS/C++/C/Python/DSA/Aptitude notes), CP 65, SD foundations 27, HLD 18, LLD 18. Sources:
  `oa-staging/{sd,cp}_research` (180k words, already interview-shaped) + 194 notes sections.
- **`gate_rubric.py`** — 8 rules incl. **rule 8: every multi-digit number in a rubric point must
  appear in its source**. Caught a genuine hallucination (`dsa_s26_mental_math` invented `3971`,
  0 occurrences in source). 8/343 quarantined initially; all recovered, four by switching generator
  model (`gpt-5.3-codex-high`) rather than relaxing the gate. **Re-gated from scratch: 322 pass, 0 fail.**
- **`audit_rubrics.py`** — corpus-wide semantic drift check (median 78% term overlap with source).
- **`app/interview/`** — `rubrics` (corpus + source loader), `context` (turn assembly), `dossier`
  (persistent memory), `session` (orchestration), `jobs` (queue + liveness), `mixed` (loop
  composition), `subjects` (taxonomy + interview weights). Migrations **010** and **011**.
- **The app owns judgement.** Scores are computed from rubric point ids, so no candidate text can move
  a number; a model claiming `ADVANCE: YES` with core points unmet is overridden. Later phases are
  *physically absent* from the prompt (the leak guard), and hint tiers 1→3 release on an app-side
  stuck counter.
- **Context is flat:** ~4,140 tokens at turn 14, still 4,141 at turn 120 (role + dossier + current
  phase + full source section + compacted transcript).
- **`interview_worker.py`** — outbound-only, thread-pooled, agy with no workspace / empty cwd /
  `--sandbox` / never `--yolo`. Starting it IS the host toggle. `GEMINI_API_KEY` path implemented.
- **UI** (`interview.js`, style.css v28→v35): loops / by-topic / past-interviews tabs, exclusion-based
  custom loops, resumable sessions, dictation + neural TTS, markdown+code+LaTeX rendering.
- **`Start Interviewer.bat`** on the Desktop — Windows→WSL bridge, token from gitignored `.env`.

### Bugs Found & Fixed
- **Duplicated interviewer turns (user saw the opening message 11×).** `/api/interview/poll` was not
  idempotent while the client polled every 2s regardless of in-flight requests, so ~7 polls all saw
  `done` and each ran `apply_turn`. Fixed server-first (conditional `done → applying` UPDATE) *and*
  client-side. Verified: 10 concurrent polls → exactly 1 turn.
- **36s → 16.1s per turn.** Measured the CLI: 0.3s spawn + ~5s auth + ~8s generation, no warm-up, no
  usable streaming. The thief was the worker's fixed 20s idle poll. Adaptive backoff + direct agy call
  + 1s browser poll.
- **`agy --print --model X <prompt>` silently loses the prompt**; correct order is
  `--model X --print <prompt>`, and the prompt is **argv, not stdin**.
- **Lease race** — two worker threads could claim the same turn; now a conditional UPDATE.
- **21 duplicated C topics** (`cpp_` and `c_`, byte-identical — the copy walked `C++_OOPs`, which
  contains `C programming`), and the **aptitude set interleaved with DSA** by section number
  (`dsa_s26` is both *Advanced String Algorithms* and *Mental Math*) → subject decided by title.
- **Weight bug** — a bare `"reference"` in the low-value list demoted *Rvalue References* to 1/5.
- **Past interviews wouldn't open** — a TDZ `ReferenceError` (`live` read above its `const`) threw
  mid-render, emptying the list while the tab still said "(1)".
- **`/api/interview/shapes` took 18s** — uncached `summaries()` rebuilt from 322 files on `/mnt/c`,
  ~8× per request. Now 2.7s cold / 0.03s warm.
- **Hint escalation felt broken** — needed 2 stuck signals for tier 1 (so the first "I'm stuck" did
  nothing) and a phase advance reset the tier to 0, wiping earned help. Now first signal → tier 1,
  and a phase change steps back one tier.

### Verified
- **16 users × 2 turns:** 0 errors, 0 double-leased jobs, 0 cross-user leakage (`loadtest_interview.py`).
- **17 invariants** pass (`test_interview.py`): phase scoping, hint gating, flat cost, injection
  resistance, mastery evolution.
- **Real end-to-end quality:** a deliberately weak URL-shortener answer scored 0.17 → 0.33 → 0.50,
  was never told "correct", never advanced — and a NEW session on *caching* opened carrying
  `KNOWN WEAK AREAS: NFRs… (mastery 50%)` earned in the earlier session.
- **agy's file tools are auto-denied headless** (tested directly) — the sandbox is real.

### Deployed
Fly **v35+** (`style.css v35, interview.js v8, sheets.js v25`); corpus synced to `/data/problems`.
Secrets set: `OAJ_WORKER_TOKEN`, `OAJ_INTERVIEW_CONCURRENCY=12`, `OAJ_HTTP_THREADS=24`.

### Deferred
FTS5 retrieval over the 1.4M-word notes · exercising the `GEMINI_API_KEY` path (16s → ~1–3s) ·
CP-sheet dedup (312 copies, analysed not executed) · mixed-loop unit tests · judged DSA round.

## [2026-07-27 20:00 IST] — session 6: reconciled a context loss, closed 2 gaps, +6 gated Microsoft problems (bank 133 → 139 live) | By: Claude (Opus 4.8, Claude Code)

### Done This Session
- **Reconciled a mid-project context loss.** A standing-check found work had landed past the
  session-5 templatesv2 cutoff (`bd67f36`): a **built-in C++/Python compiler + per-problem scratchpad
  + standalone Compiler tab** (reusable `OAEditor.create()` Monaco factory; commits `f0efead`,
  `f48daf5`; assets **v16 → v19**, editor.js **→ v14**), a **Dockerfile `safe.directory` fix**
  (`35c33d9`) so git dubious-ownership can't break Sync, and **batch9** (10 gated OA-Helper problems)
  merged into the bank (`6fceac2`). Both repos were fully pushed.
- **Gap 1 — live bank was 10 behind (123 vs pushed 133).** batch9 had never been synced to
  production. Pulled it into the live volume (`fly ssh` git pull) and rebuilt the index → **133**.
- **+6 gated Microsoft OA problems** under **Iris — Personal** (company `Microsoft`, source `gyan`),
  authored by Claude, each **GATE: PASS at 100% mutation** (reference.cpp + independent Python brute +
  deterministic generator + ≥5 edges incl. max-scale):
  - `microsoft-q1-valid-parentheses-replacements` — greedy count + forced-upgrade check.
  - `microsoft-q2-dynamic-network-strength` — **incremental DSU**. This is the user's own problem that
    TLE'd 8/15; their DSU recomputed the whole sum each second — the fix is O((n+m)·α) with an
    incremental running sum (max-scale 2·10⁵ runs ~1.1 s).
  - `microsoft-q3-password-strength` — weak/strong classifier (needed a range-endpoint edge to kill a
    `c<='9'` boundary mutant).
  - `microsoft-q4-compare-flat-json` — hand-rolled quote-scanning parser (no JSON lib), tolerant of
    `:`/`,`/`{`/`}` inside values.
  - `microsoft-q5-min-abs-diff-pairs` — sort + dedup, adjacent gaps.
  - `microsoft-q6-maximize-binary-reverse-append` — constructive: the reverse-append procedure is a
    **fixed position-permutation**, so the max final string is the multiset sorted descending and the
    input permutation is its **unique preimage** (built with the O(n) deque trick). **Theory verified
    exhaustively** against brute-force over all binary strings of length 1..9 (0 theory failures,
    optimum always unique). **The user's transcribed sample 1 was wrong** (claimed `00001` optimal; the
    true optimum is `00010` → `10000`) — shipped the corrected sample.
- **Pushed** oa-problems (`732e6de`), **pulled + reindexed** the live volume → **bank 139 live**.
- **Gap 2 — updated templatesv2 to session 6** (this file, PROJECT_STATE, SESSION_LOG, dead_ends,
  session.json archived + regenerated).

## [2026-07-26 23:30 IST] — session 5: CP + System Design sheets, per-user contest tracker, Ctrl+' submit, company dedup, +1 gated problem, sync-infra fix | By: Claude (Opus 4.8, Claude Code)

### Done This Session
- **Two new sheets, native to the judge (judge UI untouched).** A **CP sheet** (43 topics, 1513
  problems) and a **System Design sheet** (63 HLD/LLD modules), authored from a **106-agent Grok
  research fan-out** (`_research_pool/run_pool.py`, memory-guarded pool; Grok beat agy 10/10 vs 7/10 on
  deep-research-with-link-verification) and synthesized into `app/sheets/cp.json` + `sd.json` by
  `synth.py` (parse ladders → dedup by URL → drop LeetCode from CP → importance-weighted retier).
  CP is **post-Striver, Codeforces-style**, ceiling Candidate Master; core is **weighted by OA/interview
  frequency to 335 must-do problems** (backbone topics 16 each, advanced 2, FFT 0) → **~4–5 months at
  2–3/day**. SD is **explicitly sequential** (grouped rail Frameworks→Foundations→HLD→LLD, numbered steps).
- **Contest Tracker (deterministic, per-user, $0).** Link CF/AtCoder/LeetCode/CodeChef handles once →
  auto **rating trajectory vs a target line** (CM/1900 by 2027-05-31) with an on-track verdict (SVG
  chart), **cadence**, a **multi-site upcoming-contest feed with NO clist key** (CF `contest.list`,
  AtCoder page scrape, CodeChef list API, LeetCode **GraphQL** `upcomingContests`), `.ics`, and a
  **deterministic "Recommended for you"** (every Codeforces round always qualifies + level-matched
  others). No AI. Backend: `migration 006`, `cp.py`, `store.py` data layer, 8 routes.
- **Ctrl/Cmd+' submits** (LeetCode-style), alongside Ctrl/Cmd+Enter.
- **Sidebar company dedup**: `canon_company()` merges variants (de shaw + DE Shaw → DE Shaw) and routes
  blank/unknown companies to a single **Practice** company (at index time).
- **+1 gated problem**: `practice-min-edge-reversals` (0-1 BFS) under **Iris — Personal / Practice** —
  GATE: PASS (100% mutation; reference cross-checked vs a Dijkstra brute over 500 random graphs).
- **Fixed a real infra bug**: the live **volume bank was not a git checkout**, so `Sync` had been
  silently failing — prior bank pushes (batch8, DE Shaw) never reached live (stuck at 122). Re-cloned
  the public `oa-problems` onto `/data/problems` as a proper checkout + restarted; **live bank now 123
  and Sync works again.**
- Deployed several times; assets **v12 → v16**; visual QA via headless-chromium screenshots (desktop +
  mobile) with a fix pass (tofu glyphs, SD slug-titles, goal label, mobile header overlap).

## [2026-07-25 22:35 IST] — session 4: mutation-testing gate, gated Grok pilot (+14 problems), app features, $0 storage | By: Claude (Opus 4.8, Claude Code)

### Done This Session
- **Mutation-testing quality system.** `mutation_test.py` (NEW) mutates the verified reference and
  requires the suite to KILL every non-equivalent mutant; survivors are auto-triaged (generator + ±1
  fuzz) into equivalent vs a real GAP, and `--fix` writes each gap's distinguishing input as an edge
  test. `gate_candidate.py` (NEW) is a one-command PASS/FAIL: **anchor** (reference reproduces every
  scraped `provided_test`) + **independent brute** cross-check + `audit` + **100% mutation**. Codified
  in `SOLUTION.md` §4.1 (binding standard) + §4.2 (difficulty rubric).
- **Fixed 4 gate-soundness bugs**: (a) score flap + a >30min hang — now a reliable oracle
  (retry@4×, drop uncomputable) + mutant timeout/crash = KILL (confirm-retry) + adaptive per-mutant
  timeout + `OAJ_MUT_WORKERS` cap; (b) fuzzer mangling a COUNT field → phantom gaps — now perturbs
  payload rows only; (c) `run()` reading a reference CRASH as `""` → phantom gaps — now non-zero exit
  = `<ERR>` (oracle drops it, triage skips it); (d) a Python-only reference silently skipped mutation
  yet passed — now a hard FAIL.
- **Healed the whole bank to 100% mutation** (goldman-2048, rippling-q2, tuf-aggressive-cows,
  tuf-nice-subarrays), **relabelled 2 Easy** (oahelper calculate-amount + final-price), **clarified
  book-allocation** (contiguity + a 2nd discriminating sample).
- **Gated Grok pilot** — `cursor-grok-4.5-high`, 4 agents in isolated `../oa-staging`. **14 problems
  merged** (meeting-room-allocation, train-reservation-reroute-auditor, walking-in-light,
  maximize-score-after-n-operations, colorful-construction, the-magic-graph,
  vertex-disappearance-in-a-graph, warehouse-robotics-system, maximum-array-sum-with-subarray-flips,
  valid-edge-addition, valid-memory-block-sizes, weighted-meeting-scheduler,
  kth-number-containing-101-in-binary, uber-zone-clusters), **1 deferred** (valid-number-partitions —
  Python bignum ref, un-gateable), **3 correct SKIPs** (too easy). Cleaned Grok's scraping artifacts
  (LaTeX `\n` note + literal-`\n` edge input) on the two affected problems. Bank **42 → 62**.
- **App features (all deployed).** (1) **LaTeX rendering** in `app/runner/md.py` — `\(…\)` → Unicode +
  `<sup>/<sub>`, dependency-free (fixes constraints showing raw). (2) **One-click bug reporting** —
  migration `005_bug_reports.sql`, `POST /api/report` + `GET /api/reports`, a box under the statement
  **and** an always-visible Report button in the tab bar. (3) **Topic search** — free-text now matches
  `topic`, but topic is HIDDEN on the problem view (approach-giveaway).
- **$0 storage.** Hidden tests gzipped (`*.in.gz`, deterministic mtime=0); judge + `mutation_test` read
  plain-or-`.gz` transparently; `compress_bank.py` (NEW) compresses in place. **Bank 112M → 58M (2.9×)**
  ≈ doubles the free-3GB-volume ceiling.
- **Deployed 3× (Fly v8/v9/v10).** Also earlier this session: OA-Helper batches A/B (DE Shaw ×2,
  Arcesium, Google, Uber ×2) and **Python enabled as a 2nd language** on all runnable problems.

### Errors Hit
- **mutation_test flapped 100↔96.8% then HUNG >30min** — reliable oracle + timeout/crash-as-KILL +
  adaptive timeout; and **running two heavy mutation procs at once OOM-crashed the 10GB WSL VM** (the
  reported "crash", NOT Grok) → cap workers, never stack heavy runs.
- **Phantom gaps** from the fuzzer corrupting count fields / crashing the reference → grammar-safe
  fuzzer + `run()` treats non-zero exit as unreliable.
- **User report: vertex constraints rendered as raw `\(2 \le N \le 10^5\)`** → renderer fix. The
  problem itself was verified correct (3000-case independent simulation) — the bug was presentation.
- **User couldn't find the bug-report control** (buried at statement bottom) → added the tab-bar button.
- **valid-number-partitions un-gateable** (Python bignum ref) → DEFERRED, not merged.
- **First `fly deploy` failed 'missing an app name'** — `cd X && git push &` backgrounded the `cd`, so
  deploy ran from the wrong dir; re-ran with explicit `-a oa123` from the app dir.

### Next Session Must
- Take the user's direction: (1) scale Grok authoring beyond the pilot (up to 25 agents, each gated);
  (2) ship valid-number-partitions via a mod-1e9+7 C++ ref (or add Python mutation support);
  (3) if growing past ~3,500 problems, cap max-scale hidden-test size in `make_hidden` (lossy).
- Every batch stays on the gate: `gate_candidate.py` = PASS (anchor + brute + audit + 100% mutation),
  push the bank; deploy the app **only** when app code changes (bank changes just need Sync).

## [2026-07-24 20:45 IST] — session 3: deployed live (Fly + OAuth), scraping pipeline, verified batches | By: Claude (Opus 4.8, Claude Code)

### Done This Session
- **Deployed to Fly.io** (`oa123.fly.dev`) with **GitHub OAuth multi-user**, scale-to-zero (~$0/mo),
  DB + bank on a persistent volume. Hosted is in sync at 42 problems.
- **Scalable, source-grouped UI.** `problem_index` search table → paginated sidebar; **two-level
  `source ▸ company` dropdown** (TUF+ / OA-Helper / Iris — Personal), company filter + search.
  Relabelled `gyan` → "Iris — Personal" (disk key unchanged). Added **presence** ("who's online",
  best-effort, $0, no heartbeat; migration `004_presence.sql`, `/api/presence`).
- **Fixed the Sync-doesn't-stick bug.** Moved the live bank onto the Fly **persistent volume**
  (`OAJ_PROBLEMS_DIR=/data/problems`, seeded once from the image via `sharing.ensure_seeded()`);
  scale-to-zero was discarding every `git pull`. One Sync now persists.
- **Stub-rule regression fixed + gated.** All stubs now expose a **separate solution function**
  (never solve in `main()`). New `audit.py` structural gate (stub rule + metadata + reference +
  **≥5-edge test-quality** warning). `SOLUTION.md` authored as the authoritative build+authoring
  reference; `FORMAT.md` points to both gates.
- **Built the scraper** (`../oa-scraper`) by orchestrating **Grok 4.5 via `cursor-agent`**, scoped to
  that repo only. TUF+: **397** scraped with premium fields (authenticated `backend-go` API).
  OA-Helper: **~1500/3586** with premium content (`oahelper.in /api/proxy/question` + `oa_session`
  cookie). Raw JSON local + gitignored; ingested only in reviewed batches.
- **Ingested + verified 18 new problems** (each: stub-with-separate-function, verified reference,
  ≥5 edges incl. max-scale/overflow, `verify_all`+`audit` green, **independent brute-force check**):
  Microsoft TUF+ textbook ×13, Microsoft OA-Helper story ×2 (Calculate Amount, Final Price),
  Goldman Iris-Personal ×3 (Missed Courses, Unstable Tasks, Largest Container).

### Errors Hit
- **Sync required multiple clicks** on the hosted site — root cause: bank in ephemeral fs under
  scale-to-zero; fixed by relocating to the persistent volume.
- **Bearer-on-HTML didn't unlock TUF premium** — the data comes from the authenticated `backend-go`
  API, not the SSR page; rewired the scraper to call it.
- **OA-Helper premium is cookie-authed, not JWT** — the site uses an `oa_session` cookie + a
  `get_question` proxy, not a Supabase user token; mapped the real endpoint (`base64("{id}|0")` refs).
- **OA #8 Square Tile Arrangement**: its own official solution contradicts its samples → skipped, not
  shipped.

### Next Session Must
- Take the user's direction on **content batches**: more Microsoft (243 TUF left + OA-Helper story),
  finish the OA-Helper scrape (~2000 left; re-capture the `oa_session` cookie if it 401s), or backfill
  the **14 older problems** flagged by `audit.py` for <5 edge cases.
- Keep every batch on the gate: verified reference + brute-force cross-check + ≥5 edges + `verify_all`
  + `audit`, then push to `oa-problems` and Sync.

## [2026-07-23 session 2] — Phases 5–6: sharing + deployment; published public repos | By: Claude (Opus 4.8)

### Done This Session
- **Phase 5 — sharing.** Split the question bank into a standalone `oa-problems` git repo; the app
  reads it via `app/config.py` (`PROBLEMS_DIR`), so app and bank version independently. Added
  `app/sharing.py` (ff-only git sync; scaffold → generate hidden tests → verify → publish-on-branch)
  and the endpoints `/api/bank/{status,sync,author,publish}`. Frontend: header **Sync** + **Add**,
  an authoring modal with live Verify-&-preview that only enables Publish on a green package, and a
  toast. A GitHub Action (`verify.yml`) re-runs `verify_all.py` on every PR. `setup.sh` onboards a
  friend in one command. Verified end-to-end: authored a throwaway problem via the API → it
  scaffolded, generated hidden tests, verified, and was judgeable (AC 16/16).
- **Both CISCO problems runnable.** cisco-q1 (0-1 BFS over (r,c,battery,vouchers)) cross-checked vs
  an independent Dijkstra on 3000 random grids; cisco-q2 (sliding window + hash-map + ordered set)
  vs an O(N²) brute on 5000 cases; all provided samples reproduced. 12 of 13 problems now runnable.
- **Phase 6 — deployment.** New `docker` execution backend: every compile and run happens in an
  ephemeral container with `--network none --read-only --cap-drop ALL --user 65534 --pids-limit
  --memory --cpus --rm`. Untrusted source is compiled in the same isolation. `Dockerfile`,
  `docker-compose.yml` (trusted-friends vs untrusted models), `DEPLOY.md` (threat model, Fly/Railway/
  VPS, Postgres port, OAuth as an additive step). `server.py` binds `config.HOST/PORT`.
  **Validated against real Docker:** a Python problem judged 17/17 AC through containers, and
  adversarial submissions confirmed network egress blocked, infinite loop → TLE, read-only FS, and
  fork-bomb containment. Two live-surfaced bugs fixed (host interpreter path → basename; workspace
  perms for uid 65534).
- **Published.** Pushed `RushilJ2603/oa-judge` + `RushilJ2603/oa-problems`, both **public**, branch
  `main`; the bank's CI ran and passed on GitHub.

### Errors Hit
- Snippet autocomplete (session 1 carryover) and, this session, two docker-backend bugs — both found
  by running the code, not by inspection; fixed and re-verified.
- Docker image build blocked on this WSL host: its containers have no network egress (apt/DNS fail
  inside any container). Environment issue, not the Dockerfile — the sandbox is proven via the cached
  slim image; build the g++ image on a host with working Docker networking.

### Next Session Could
- Multi-user OAuth (only if hosting one instance for several people; additive migration — see DEPLOY.md).
- Build + push the g++ runner image from a healthy-network host; wire a friend's fork of oa-problems.


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
